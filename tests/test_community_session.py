import hashlib
import io
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import struct
import subprocess
import zipfile

import pytest

from my_career_training import community_session
from my_career_training.community_plugins import download_plugin
from my_career_training.community_session import (
    CommunitySession,
    CommunitySessionError,
    DerivedPluginCommand,
    OwnedTrialScope,
    RecoveryReport,
    ReviewedPluginProfile,
    RuntimeIdentity,
    StagedCommunityTrial,
    derived_plugin_commands,
    derived_plugin_filename,
    production_eligible,
    production_profiles,
)


PLUGIN_ID = "910001"
VERSION = 4
NONCE = "12345678-1234-4234-8234-123456789abc"
MEMBER = "UpstreamHelper.dll"
DOWNLOAD = "https://cdn.bakkesplugins.com/uploads/" + ("a" * 32) + "-Fixture_v1.zip"


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self._body = body
        self._offset = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self):
        return None


class Running:
    def __init__(self, value=False):
        self.value = value

    def __call__(self):
        return self.value


def minimal_amd64_dll():
    dos = bytearray(64)
    dos[0:2] = b"MZ"
    dos[0x3C:0x40] = struct.pack("<I", 64)
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 112, 0x2002)
    optional = bytearray(112)
    optional[0:2] = struct.pack("<H", 0x20B)
    section = bytearray(40)
    section[0:8] = b".text\0\0\0"
    return bytes(dos) + b"PE\0\0" + coff + bytes(optional) + bytes(section)


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, payload in files:
            bundle.writestr(name, payload)
    return buffer.getvalue()


def publish(cache, archive, *, plugin_id=PLUGIN_ID, version=VERSION, download=DOWNLOAD):
    raw = json.dumps({
        "success": True,
        "response": {"plugins": {plugin_id: {
            "version": version,
            "download_url": download,
            "verified": False,
        }}},
    }).encode()

    def opener(request, timeout=None):
        if request.full_url == f"https://bakkesplugins.com/api/v1/plugins/get/short?pluginids={plugin_id}":
            return Response(200, {
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
            }, raw)
        if request.full_url == download:
            return Response(200, {
                "Content-Type": "application/zip",
                "Content-Length": str(len(archive)),
            }, archive)
        raise AssertionError(request.full_url)

    record = {"id": plugin_id, "version": version, "download_url": download, "can_activate": False}
    return download_plugin(record, cache, opener=opener)


def make_profile(receipt, dll, **overrides):
    values = {
        "site_id": receipt["id"],
        "api_version": receipt["version"],
        "archive_sha256": receipt["artifact_sha256"],
        "member": MEMBER,
        "member_sha256": hashlib.sha256(dll).hexdigest(),
        "plugin_name": "UpstreamHelper",
        "source_url": "https://example.invalid/fixtures/upstream-helper",
        "source_commit": "0123456789abcdef0123456789abcdef01234567",
        "license": "GPL-3.0",
        "download_url": receipt["download_url"],
        "game_exe_sha256": "11" * 32,
        "core_identity": "fixture-core",
        "build_identity": "fixture-build",
    }
    values.update(overrides)
    return ReviewedPluginProfile(**values)


def make_scope(**overrides):
    values = {
        "nonce": NONCE,
        "pid": 4242,
        "start_identity": "1740000000.125",
        "fresh": True,
        "offline": True,
        "steam": True,
        "frontend": True,
        "development_trial": True,
    }
    values.update(overrides)
    return OwnedTrialScope(**values)


class World:
    def __init__(self, tmp_path, *, dll=None, files=None):
        self.dll = minimal_amd64_dll() if dll is None else dll
        self.root = tmp_path / "bakkes"
        self.plugins = self.root / "plugins"
        self.plugins.mkdir(parents=True)
        (self.plugins / "AlreadyThere.dll").write_bytes(b"not-our-plugin")
        extra = self.plugins / "extra"
        extra.mkdir()
        (extra / "keep.txt").write_bytes(b"keep")
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "plugins.cfg").write_bytes(b"plugin load AlreadyThere\n")
        (cfg / "config.cfg").write_bytes(b"sf_keep 1\n")
        self.app = tmp_path / "app"
        self.app.mkdir()
        (self.app / "keep.txt").write_bytes(b"app-keep")
        self.cache = tmp_path / "cache"
        payload = files or [
            (MEMBER, self.dll),
            ("LICENSE", b"fixture license\n"),
            ("README.md", b"fixture readme\n"),
        ]
        self.receipt = publish(self.cache, zip_bytes(payload))
        self.receipt_bytes = (self.cache / self.receipt["archive"]).with_name("receipt.json").read_bytes()
        self.profile = make_profile(self.receipt, self.dll)
        self.scope = make_scope()
        self.runtime = RuntimeIdentity("11" * 32, "fixture-core", "fixture-build")
        self.running = Running(False)
        self.session = CommunitySession(self.app, self.root, game_running=self.running)
        self.before = self.snapshot()

    @property
    def destination(self):
        return self.plugins / derived_plugin_filename(self.profile.site_id, self.scope.nonce)

    @property
    def journal(self):
        return self.app / "community-session" / "active.json"

    def snapshot(self):
        paths = [
            self.root / "cfg" / "plugins.cfg",
            self.root / "cfg" / "config.cfg",
            self.plugins / "AlreadyThere.dll",
            self.plugins / "extra" / "keep.txt",
            self.app / "keep.txt",
        ]
        return {path: path.read_bytes() for path in paths}

    def stage(self, **kwargs):
        return self.session.stage(
            kwargs.get("profile", self.profile),
            kwargs.get("scope", self.scope),
            kwargs.get("runtime", self.runtime),
            kwargs.get("cache", self.cache),
            verify_scope=kwargs.get("verify_scope", lambda scope: True),
        )


def _symlink_or_skip(link, target, *, target_is_directory=False):
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows denied symlink creation because this account lacks the required privilege")
        raise


def _junction_or_skip(link, target):
    if os.name != "nt":
        pytest.skip("Junctions are only available on Windows")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        detail = f"{completed.stdout}\n{completed.stderr}"
        folded = detail.casefold()
        if "privilege" in folded or "1314" in folded:
            pytest.skip("Windows denied junction creation because this account lacks the required privilege")
        raise AssertionError(detail)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_stage_writes_the_reviewed_dll_and_fixed_commands(world):
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        assert isinstance(scope, OwnedTrialScope)
        assert scope.nonce == NONCE and scope.development_trial is True
        assert scope.fresh is True and scope.offline is True and scope.steam is True and scope.frontend is True
        return True

    world.running.value = True
    result = world.stage(verify_scope=verify)
    assert calls["n"] == 3
    assert isinstance(result, StagedCommunityTrial)
    assert result.filename == derived_plugin_filename(PLUGIN_ID, NONCE)
    assert os.path.normcase(str(result.dll_path)) == os.path.normcase(str(world.destination.resolve()))
    assert result.dll_path.read_bytes() == world.dll
    assert result.command == derived_plugin_commands(PLUGIN_ID, NONCE)
    assert result.command.load_command == f"plugin load {result.command.stem}"
    assert result.command.unload_command == f"plugin unload {result.command.stem}"
    assert "UpstreamHelper" not in result.command.load_command
    assert ":" not in result.command.load_command
    assert result.command.app_bridge_action is None
    assert "action" not in DerivedPluginCommand.__dataclass_fields__
    assert "action" not in StagedCommunityTrial.__dataclass_fields__
    assert result.production_eligible is False
    assert result.autoload_modified is False
    assert result.pe_shape_is_abi_proof is False
    assert "not ABI" in result.pe_note
    assert production_profiles() == ()
    assert production_eligible(world.profile) is False
    assert sorted(path.name for path in world.plugins.iterdir() if path.is_file()) == [
        "AlreadyThere.dll", result.filename,
    ]
    assert sorted(path.name for path in (world.root / "cfg").iterdir()) == ["config.cfg", "plugins.cfg"]
    assert world.snapshot() == world.before
    receipt_path = (world.cache / world.receipt["archive"]).with_name("receipt.json")
    assert receipt_path.read_bytes() == world.receipt_bytes
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["can_activate"] is False
    record = json.loads(world.journal.read_text(encoding="ascii"))
    assert record["state"] == "staged"
    assert record["can_activate"] is False and record["production_eligible"] is False
    assert record["autoload_modified"] is False and record["cfg_modified"] is False
    assert record["load_command"] == result.command.load_command
    assert "action" not in record
    volume, index = record["owned_file_id"].split(":")
    assert len(volume) == 8 and len(index) == 16


def test_cleanup_waits_for_every_game_process_then_removes_only_the_owned_dll(world):
    world.running.value = True
    world.stage()
    deferred = world.session.recover()
    assert deferred == RecoveryReport(
        "deferred", False, True, "Rocket League is running. The staged plugin was left in place.")
    assert world.destination.read_bytes() == world.dll
    world.running.value = False
    recovered = world.session.recover()
    assert recovered.status == "recovered" and recovered.dll_removed is True and recovered.journal_kept is False
    assert not world.destination.exists()
    assert world.plugins.is_dir() and (world.plugins / "extra").is_dir()
    assert world.snapshot() == world.before
    assert world.session.recover().status == "idle"


def test_recovery_without_the_live_lease_removes_the_unchanged_dll(world):
    world.stage()
    restarted = CommunitySession(world.app, world.root, game_running=lambda: False)
    report = restarted.recover()
    assert report.status == "recovered" and report.dll_removed is True
    assert not world.destination.exists()
    assert world.snapshot() == world.before


def test_missing_profile_and_path_write_nothing(world):
    with pytest.raises(CommunitySessionError, match="complete reviewed profile"):
        world.stage(profile=None)
    with pytest.raises(CommunitySessionError, match="developer code"):
        world.stage(profile=world.cache / "archive.zip")
    assert not world.journal.exists()
    assert world.snapshot() == world.before


def test_production_staging_stays_unavailable(world):
    assert production_profiles() == ()
    assert production_eligible(world.profile) is False
    assert production_eligible(None) is False
    scope = replace(world.scope, development_trial=False)
    with pytest.raises(CommunitySessionError, match="Production"):
        world.stage(scope=scope)
    assert not world.journal.exists()
    assert world.snapshot() == world.before


@pytest.mark.parametrize("field", ["fresh", "offline", "steam", "frontend"])
def test_wrong_scope_is_refused_before_writing(world, field):
    scope = replace(world.scope, **{field: False})
    with pytest.raises(CommunitySessionError, match="scope is not valid"):
        world.stage(scope=scope)
    assert not world.journal.exists()


def test_unverified_scope_writes_nothing(world):
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        return False

    with pytest.raises(CommunitySessionError, match="not verified"):
        world.stage(verify_scope=verify)
    assert calls["n"] == 1
    assert not world.journal.exists()
    assert world.snapshot() == world.before


def test_missing_or_mismatched_runtime_writes_nothing(world):
    with pytest.raises(CommunitySessionError, match="Runtime identity is required"):
        world.stage(runtime=None)
    runtime = replace(world.runtime, core_identity="other-core")
    with pytest.raises(CommunitySessionError, match="does not match"):
        world.stage(runtime=runtime)
    assert not world.journal.exists()


def test_missing_hash_and_bad_member_are_refused(world):
    with pytest.raises(CommunitySessionError, match="Archive hash"):
        replace(world.profile, archive_sha256="")
    with pytest.raises(CommunitySessionError, match="member"):
        replace(world.profile, member="CON.dll")
    with pytest.raises(CommunitySessionError, match="member"):
        replace(world.profile, member="../UpstreamHelper.dll")
    assert not world.journal.exists()


def test_cache_identity_mismatches_write_nothing(world):
    other_url = "https://cdn.bakkesplugins.com/uploads/" + ("b" * 32) + "-Other_v1.zip"
    profiles = [
        replace(world.profile, archive_sha256="ab" * 32),
        replace(world.profile, site_id="910002"),
        replace(world.profile, api_version=VERSION + 1),
        replace(world.profile, download_url=other_url),
        replace(world.profile, member_sha256="cd" * 32),
    ]
    messages = ["cache", "identity", "identity", "identity", "member hash"]
    for profile, message in zip(profiles, messages, strict=True):
        with pytest.raises(CommunitySessionError, match=message):
            world.stage(profile=profile)
        assert not world.journal.exists()
        assert world.snapshot() == world.before


def _mz_only(_data):
    blob = bytearray(128)
    blob[:2] = b"MZ"
    return bytes(blob)


def _pe32(data):
    return data[:88] + struct.pack("<H", 0x10B) + data[90:]


def _i386(data):
    return data[:68] + struct.pack("<H", 0x14C) + data[70:]


def _not_a_dll(data):
    return data[:86] + struct.pack("<H", 0x0002) + data[88:]


def _short_optional(data):
    return data[:84] + struct.pack("<H", 2) + data[86:]


@pytest.mark.parametrize("builder", [_mz_only, _pe32, _i386, _not_a_dll, _short_optional])
def test_pe_shape_is_rejected_before_staging(tmp_path, builder):
    world = World(tmp_path, dll=builder(minimal_amd64_dll()))
    with pytest.raises(CommunitySessionError, match="not ABI"):
        world.stage()
    assert not world.journal.exists()
    assert not any(path.name.startswith("MCTCommunity_") for path in world.plugins.iterdir())
    assert world.snapshot() == world.before


def test_second_dll_and_extra_resource_are_rejected(tmp_path):
    dll = minimal_amd64_dll()
    second = World(tmp_path / "second", dll=dll, files=[
        (MEMBER, dll),
        ("Other.dll", b"MZ-second"),
        ("LICENSE", b"fixture license\n"),
    ])
    with pytest.raises(CommunitySessionError, match="exactly one reviewed DLL"):
        second.stage()
    assert not second.journal.exists()
    extra = World(tmp_path / "extra", dll=dll, files=[
        (MEMBER, dll),
        ("README.md", b"fixture readme\n"),
        ("data/speedflip/state.cfg", b"sf_keep 1\n"),
    ])
    with pytest.raises(CommunitySessionError, match="resource this pilot cannot stage"):
        extra.stage()
    assert not extra.journal.exists()
    assert extra.snapshot() == extra.before


def test_traversal_archive_is_rejected_before_staging(tmp_path):
    dll = minimal_amd64_dll()
    blob = zip_bytes([("../evil.dll", b"nope"), (MEMBER, dll)])
    with zipfile.ZipFile(io.BytesIO(blob)) as bundle:
        assert any(".." in name for name in bundle.namelist())
    digest = hashlib.sha256(blob).hexdigest()
    cache = tmp_path / "cache"
    folder = cache / "objects" / digest
    folder.mkdir(parents=True)
    (folder / "archive.zip").write_bytes(blob)
    root = tmp_path / "bakkes"
    (root / "plugins").mkdir(parents=True)
    app = tmp_path / "app"
    app.mkdir()
    profile = ReviewedPluginProfile(
        PLUGIN_ID, VERSION, digest, MEMBER, hashlib.sha256(dll).hexdigest(), "UpstreamHelper",
        "https://example.invalid/fixtures/upstream-helper",
        "0123456789abcdef0123456789abcdef01234567", "GPL-3.0", DOWNLOAD,
        "11" * 32, "fixture-core", "fixture-build",
    )
    session = CommunitySession(app, root, game_running=lambda: False)
    with pytest.raises(CommunitySessionError, match="unsafe path"):
        session.stage(profile, make_scope(), RuntimeIdentity("11" * 32, "fixture-core", "fixture-build"),
                      cache, verify_scope=lambda scope: True)
    assert list((root / "plugins").iterdir()) == []
    assert not (app / "community-session" / "active.json").exists()


def test_existing_dll_and_second_stage_do_not_overwrite(world):
    world.destination.write_bytes(b"existing-bytes")
    with pytest.raises(CommunitySessionError, match="already exists"):
        world.stage()
    assert world.destination.read_bytes() == b"existing-bytes"
    assert not world.journal.exists()
    world.destination.unlink()
    world.stage()
    original = world.destination.read_bytes()
    with pytest.raises(CommunitySessionError, match="journal already exists"):
        world.stage()
    assert world.destination.read_bytes() == original
    assert world.snapshot() == world.before


def test_scope_loss_before_create_keeps_the_journal_and_writes_no_dll(world):
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        return calls["n"] < 2

    with pytest.raises(CommunitySessionError, match="not verified"):
        world.stage(verify_scope=verify)
    assert calls["n"] == 2
    assert not world.destination.exists()
    assert world.journal.is_file()
    report = world.session.recover()
    assert report.status == "recovered" and report.dll_removed is False and report.journal_kept is False
    assert not world.journal.exists()
    assert world.snapshot() == world.before


def test_scope_loss_after_create_keeps_the_file_until_ownership_is_recorded(world):
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        return calls["n"] < 3

    world.running.value = True
    with pytest.raises(CommunitySessionError, match="not verified"):
        world.stage(verify_scope=verify)
    assert calls["n"] == 3
    assert world.destination.read_bytes() == world.dll
    assert world.session.recover().status == "deferred"
    world.running.value = False
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False and report.journal_kept is True
    assert "review" in report.reason
    assert world.destination.read_bytes() == world.dll
    record = json.loads(world.journal.read_text(encoding="ascii"))
    assert record["state"] == "prepared" and record["owned_file_id"] is None
    assert world.snapshot() == world.before


def test_modified_dll_is_retained(world):
    world.stage()
    world.destination.write_bytes(world.dll + b"x")
    changed = world.destination.read_bytes()
    report = world.session.recover()
    assert report.status == "retained" and report.dll_removed is False and report.journal_kept is True
    assert world.destination.read_bytes() == changed
    assert world.journal.is_file()
    assert world.snapshot() == world.before


def test_tampered_journal_refuses_an_arbitrary_path(world, tmp_path):
    world.stage()
    victim = tmp_path / "victim.dll"
    victim.write_bytes(b"victim")
    record = json.loads(world.journal.read_text(encoding="ascii"))
    record["destination"] = str(victim)
    world.journal.write_text(json.dumps(record), encoding="ascii")
    staged = world.destination.read_bytes()
    with pytest.raises(CommunitySessionError, match="owned plugin path"):
        world.session.recover()
    assert victim.read_bytes() == b"victim"
    assert world.destination.read_bytes() == staged
    assert world.journal.is_file()
    assert (world.plugins / "AlreadyThere.dll").read_bytes() == b"not-our-plugin"


def test_interrupted_partial_write_is_retained(world, monkeypatch):
    def partial(path, data):
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        try:
            os.write(descriptor, data[:24])
        finally:
            os.close(descriptor)
        raise CommunitySessionError("interrupted write")

    monkeypatch.setattr(community_session, "_exclusive_write", partial)
    with pytest.raises(CommunitySessionError, match="interrupted write"):
        world.stage()
    assert world.destination.read_bytes() == world.dll[:24]
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False and report.journal_kept is True
    assert "ownership" in report.reason and "review" in report.reason
    assert world.destination.read_bytes() == world.dll[:24]
    assert world.journal.is_file()
    assert world.snapshot() == world.before


def test_crash_after_create_before_ownership_record_retains_the_file(world, monkeypatch):
    original = community_session._exclusive_write

    def full_then_fail(path, data):
        original(path, data)
        raise CommunitySessionError("interrupted write")

    monkeypatch.setattr(community_session, "_exclusive_write", full_then_fail)
    world.running.value = True
    with pytest.raises(CommunitySessionError, match="interrupted write"):
        world.stage()
    assert world.destination.read_bytes() == world.dll
    assert world.session.recover().status == "deferred"
    world.running.value = False
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False and report.journal_kept is True
    assert world.destination.read_bytes() == world.dll
    assert json.loads(world.journal.read_text(encoding="ascii"))["state"] == "prepared"
    assert world.snapshot() == world.before


def test_second_recheck_keeps_a_racing_file_with_the_same_bytes(world, monkeypatch):
    calls = {"n": 0}
    original = CommunitySession._recheck_before_create

    def wrapped(self, plan):
        calls["n"] += 1
        if calls["n"] == 3:
            plan.destination.write_bytes(plan.dll_bytes)
        original(self, plan)

    monkeypatch.setattr(CommunitySession, "_recheck_before_create", wrapped)
    with pytest.raises(CommunitySessionError, match="already exists"):
        world.stage()
    assert calls["n"] == 3
    assert world.destination.read_bytes() == world.dll
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False and report.journal_kept is True
    assert world.destination.read_bytes() == world.dll
    assert world.snapshot() == world.before


def test_exclusive_create_conflict_keeps_the_foreign_file(world, monkeypatch):
    original = community_session._exclusive_write

    def race(path, data):
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
        try:
            os.write(descriptor, data)
        finally:
            os.close(descriptor)
        original(path, data)

    monkeypatch.setattr(community_session, "_exclusive_write", race)
    with pytest.raises(CommunitySessionError, match="already exists"):
        world.stage()
    assert world.destination.read_bytes() == world.dll
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False
    assert world.destination.read_bytes() == world.dll
    assert world.snapshot() == world.before


def test_prepared_journal_keeps_a_foreign_file_with_the_same_bytes(world):
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        return calls["n"] < 2

    with pytest.raises(CommunitySessionError, match="not verified"):
        world.stage(verify_scope=verify)
    world.destination.write_bytes(world.dll)
    report = world.session.recover()
    assert report.status == "ambiguous" and report.dll_removed is False and report.journal_kept is True
    assert world.destination.read_bytes() == world.dll
    assert world.snapshot() == world.before


def test_same_bytes_with_a_new_file_identity_are_retained(world):
    world.stage()
    data = world.destination.read_bytes()
    world.destination.unlink()
    world.destination.write_bytes(data)
    report = world.session.recover()
    assert report.status == "retained" and report.dll_removed is False and report.journal_kept is True
    assert "identity" in report.reason
    assert world.destination.read_bytes() == data
    assert world.snapshot() == world.before


def test_concurrent_journal_replacement_is_left_in_place(world, monkeypatch):
    original = CommunitySession._replace_receipt

    def swap(self, directory, data, expected, identity):
        self.receipt_path.unlink()
        self.receipt_path.write_bytes(b"foreign-journal")
        with pytest.raises(CommunitySessionError, match="journal changed"):
            original(self, directory, data, expected, identity)
        assert self.receipt_path.read_bytes() == b"foreign-journal"
        raise CommunitySessionError("The trial journal changed and was left in place.")

    monkeypatch.setattr(CommunitySession, "_replace_receipt", swap)
    with pytest.raises(CommunitySessionError, match="journal changed"):
        world.stage()
    assert world.destination.read_bytes() == world.dll
    assert world.journal.read_bytes() == b"foreign-journal"
    assert world.snapshot() == world.before


def test_unknown_receipt_temp_is_not_deleted(world):
    journal = world.app / "community-session"
    journal.mkdir()
    stray = journal / (".receipt-" + ("ab" * 16) + ".json")
    stray.write_bytes(b"stray")
    world.stage()
    assert stray.read_bytes() == b"stray"
    assert world.destination.read_bytes() == world.dll
    report = world.session.recover()
    assert report.status == "recovered" and report.dll_removed is True
    assert stray.read_bytes() == b"stray"


def test_interrupted_publication_has_one_link_and_recovers(world, monkeypatch):
    def refuse_link(*_args, **_kwargs):
        raise AssertionError("journal publication must not create a second link")

    monkeypatch.setattr(os, "link", refuse_link)
    calls = {"n": 0}

    def verify(scope):
        calls["n"] += 1
        return calls["n"] < 2

    with pytest.raises(CommunitySessionError, match="not verified"):
        world.stage(verify_scope=verify)
    assert calls["n"] == 2
    assert not world.destination.exists()
    assert world.journal.is_file() and world.journal.stat().st_nlink == 1
    assert list(world.journal.parent.glob(".receipt-*.json")) == []
    report = world.session.recover()
    assert report.status == "recovered" and report.dll_removed is False and report.journal_kept is False
    assert not world.journal.exists()
    assert world.snapshot() == world.before


def test_rename_publication_does_not_overwrite_a_foreign_journal(world, monkeypatch):
    directory = world.app / "community-session"
    directory.mkdir()
    final = directory / "active.json"
    final.write_bytes(b"foreign-active")
    seen = {"n": 0}
    real_exists = community_session._exists_nofollow

    def hide_the_existing_journal_once(path):
        if path == final and seen["n"] == 0:
            seen["n"] += 1
            return False
        return real_exists(path)

    monkeypatch.setattr(community_session, "_exists_nofollow", hide_the_existing_journal_once)
    with pytest.raises(CommunitySessionError, match="already exists"):
        world.session._create_receipt(directory, b"scratch-journal")
    assert seen["n"] == 1
    assert final.read_bytes() == b"foreign-active"
    assert list(directory.glob(".receipt-*.json")) == []
    assert world.snapshot() == world.before


def test_temp_cleanup_keeps_a_replacement_and_a_foreign_identity(tmp_path):
    replaced = tmp_path / ".receipt-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json"
    identity = community_session._write_exclusive(replaced, b"ours")
    replaced.unlink()
    replaced.write_bytes(b"foreign")
    neighbor = tmp_path / "neighbor.txt"
    neighbor.write_bytes(b"keep")
    community_session._unlink_name_if_identity(replaced, identity)
    assert replaced.read_bytes() == b"foreign"
    owned = tmp_path / ".receipt-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.json"
    community_session._write_exclusive(owned, b"owned-scratch")
    community_session._unlink_name_if_identity(owned, "01234567:0123456789abcdef")
    assert owned.read_bytes() == b"owned-scratch"
    assert neighbor.read_bytes() == b"keep"


def test_temp_cleanup_disposition_does_not_delete_a_replacement(tmp_path, monkeypatch):
    path = tmp_path / ".receipt-cccccccccccccccccccccccccccccccc.json"
    identity = community_session._write_exclusive(path, b"ours")
    original = community_session._handle_info
    state = {"replaced": False}

    def replace_while_checked(handle):
        info = original(handle)
        try:
            path.unlink()
            path.write_bytes(b"foreign")
            state["replaced"] = True
        except OSError:
            state["replaced"] = False
        return info

    monkeypatch.setattr(community_session, "_handle_info", replace_while_checked)
    community_session._unlink_name_if_identity(path, identity)
    assert state["replaced"] is False
    assert not path.exists()


def test_path_escape_device_and_unc_are_refused(world, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "marker.txt").write_bytes(b"marker")
    with pytest.raises(CommunitySessionError, match="not allowed"):
        CommunitySession(world.app, world.root / "plugins" / ".." / ".." / "outside", game_running=lambda: False)
    assert (outside / "marker.txt").read_bytes() == b"marker"
    with pytest.raises(CommunitySessionError, match="device"):
        CommunitySession(world.app, world.root / "NUL", game_running=lambda: False)
    with pytest.raises(CommunitySessionError, match="not allowed"):
        CommunitySession(world.app, Path(r"\\localhost\share\bakkes"), game_running=lambda: False)
    assert world.snapshot() == world.before


def test_journal_and_bakkes_trees_must_stay_separate(tmp_path):
    root = tmp_path / "bakkes"
    plugins = root / "plugins"
    app = plugins / "state"
    app.mkdir(parents=True)
    (app / "keep.txt").write_bytes(b"keep")
    with pytest.raises(CommunitySessionError, match="separate"):
        CommunitySession(app, root, game_running=lambda: False)
    assert (app / "keep.txt").read_bytes() == b"keep"
    assert list(plugins.iterdir()) == [app]


def test_symlinked_ancestor_and_journal_are_refused(world, tmp_path):
    link_parent = tmp_path / "link-parent"
    _symlink_or_skip(link_parent, tmp_path, target_is_directory=True)
    with pytest.raises(CommunitySessionError, match="symlink or reparse"):
        CommunitySession(world.app, link_parent / "bakkes", game_running=lambda: False)
    outside = tmp_path / "outside-journal"
    outside.mkdir()
    _symlink_or_skip(world.app / "community-session", outside, target_is_directory=True)
    with pytest.raises(CommunitySessionError, match="symlink or reparse"):
        world.stage()
    assert list(outside.iterdir()) == []
    assert world.snapshot() == world.before


def test_plugins_symlink_is_not_followed(world, tmp_path):
    moved = tmp_path / "moved-plugins"
    world.plugins.rename(moved)
    linked = tmp_path / "linked-plugins"
    linked.mkdir()
    (linked / "sentinel.dll").write_bytes(b"sentinel")
    _symlink_or_skip(world.root / "plugins", linked, target_is_directory=True)
    with pytest.raises(CommunitySessionError, match="symlink or reparse"):
        world.stage()
    assert (linked / "sentinel.dll").read_bytes() == b"sentinel"
    assert not any(path.name.startswith("MCTCommunity_") for path in linked.iterdir())
    assert not (world.app / "community-session" / "active.json").exists()


def test_plugins_junction_is_not_followed(world, tmp_path):
    moved = tmp_path / "moved-plugins"
    elsewhere = tmp_path / "junction-target"
    elsewhere.mkdir()
    (elsewhere / "sentinel.dll").write_bytes(b"junction")
    world.plugins.rename(moved)
    _junction_or_skip(world.root / "plugins", elsewhere)
    with pytest.raises(CommunitySessionError, match="symlink or reparse"):
        world.stage()
    assert (elsewhere / "sentinel.dll").read_bytes() == b"junction"
    assert [path.name for path in elsewhere.iterdir()] == ["sentinel.dll"]
    assert not (world.app / "community-session" / "active.json").exists()


def test_profile_and_commands_are_immutable(world):
    with pytest.raises(FrozenInstanceError):
        world.profile.member_sha256 = "00" * 32
    command = derived_plugin_commands(PLUGIN_ID, NONCE)
    with pytest.raises(CommunitySessionError):
        DerivedPluginCommand(command.stem, "plugin load SomethingElse", command.unload_command)
    assert command.app_bridge_action is None
