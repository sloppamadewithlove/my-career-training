import hashlib
import io
import json
import struct
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from my_career_training import native_community
from my_career_training.community_plugins import download_plugin
from my_career_training.community_session import (
    OwnedTrialScope,
    RuntimeIdentity,
    derived_plugin_filename,
    production_eligible,
    production_profiles,
)
from my_career_training.native_community import (
    NativeCommunityController,
    NativeCommunityError,
    _use_synthetic_profile,
    owned_start_identity,
    pinned_profile,
)


NONCE = "12345678-1234-4234-8234-123456789abc"
DOWNLOAD = "https://cdn.bakkesplugins.com/uploads/fixture286-speedflip.zip"
CREATED = 1740000000.125


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


def publish(cache, archive):
    raw = json.dumps({
        "success": True,
        "response": {"plugins": {"286": {
            "version": 3,
            "download_url": DOWNLOAD,
            "verified": True,
        }}},
    }).encode()

    def opener(request, timeout=None):
        if request.full_url == "https://bakkesplugins.com/api/v1/plugins/get/short?pluginids=286":
            return Response(200, {"Content-Type": "application/json", "Content-Length": str(len(raw))}, raw)
        if request.full_url == DOWNLOAD:
            return Response(200, {"Content-Type": "application/zip", "Content-Length": str(len(archive))}, archive)
        raise AssertionError(request.full_url)

    record = {"id": "286", "version": 3, "download_url": DOWNLOAD, "can_activate": False}
    return download_plugin(record, cache, opener=opener)


class Probes:
    def __init__(self):
        self.scope = OwnedTrialScope(
            NONCE, 4242, owned_start_identity(CREATED), True, True, True, True, True,
        )
        self.runtime = RuntimeIdentity(
            native_community.GAME_EXE_SHA256,
            native_community.CORE_IDENTITY,
            native_community.BUILD_IDENTITY,
        )
        self.game = False
        self.helper = False
        self.game_error = False
        self.online = False
        self.movie_fail_at = None
        self.movie_value = True
        self.lease_mode = "scope"
        self.counts = {"lease": 0, "runtime": 0, "heartbeat": 0, "movie": 0}

    def lease(self):
        self.counts["lease"] += 1
        if self.lease_mode == "dict":
            return {"fresh": True, "offline": True, "steam": True, "frontend": True}
        return self.scope

    def runtime_cb(self):
        self.counts["runtime"] += 1
        return self.runtime

    def heartbeat(self):
        self.counts["heartbeat"] += 1
        scope = self.scope
        return {
            "protocol": 1,
            "bridge_session": scope.nonce,
            "published_at": 1_700_000_000,
            "pid": scope.pid,
            "online": self.online,
            "in_game": False,
            "version": "0.3.0",
        }

    def movie(self):
        self.counts["movie"] += 1
        if self.movie_fail_at is not None and self.counts["movie"] >= self.movie_fail_at:
            return False
        return self.movie_value

    def game_running(self):
        if self.game_error:
            raise OSError("enumeration failed")
        return self.game

    def helper_pending(self):
        return self.helper


class World:
    def __init__(self, tmp_path):
        self.dll = minimal_amd64_dll()
        self.root = tmp_path / "bakkes"
        self.plugins = self.root / "plugins"
        self.plugins.mkdir(parents=True)
        (self.plugins / "AlreadyThere.dll").write_bytes(b"not-our-plugin")
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "plugins.cfg").write_bytes(b"plugin load AlreadyThere\n")
        (cfg / "config.cfg").write_bytes(b"sf_keep 1\n")
        self.app = tmp_path / "app"
        self.app.mkdir()
        self.cache = tmp_path / "cache"
        self.cache.mkdir()
        self.receipt = publish(self.cache, zip_bytes([
            (native_community.MEMBER, self.dll),
            ("LICENSE", b"fixture license\n"),
        ]))
        self.receipt_path = (self.cache / self.receipt["archive"]).with_name("receipt.json")
        self.receipt_bytes = self.receipt_path.read_bytes()
        self.profile = replace(
            pinned_profile(),
            archive_sha256=self.receipt["artifact_sha256"],
            member_sha256=hashlib.sha256(self.dll).hexdigest(),
            download_url=self.receipt["download_url"],
        )
        self.probes = Probes()
        self.controller = self.fresh_controller()
        self.destination = self.plugins / derived_plugin_filename("286", NONCE)
        self.journal = self.app / "community-session" / "active.json"
        self.before = self.snapshot()

    def fresh_controller(self):
        probes = self.probes
        return NativeCommunityController(
            self.app, self.root, self.cache,
            lease=probes.lease,
            runtime=probes.runtime_cb,
            heartbeat=probes.heartbeat,
            movie_ready=probes.movie,
            game_running=probes.game_running,
            helper_pending=probes.helper_pending,
        )

    def snapshot(self):
        paths = [
            self.root / "cfg" / "plugins.cfg",
            self.root / "cfg" / "config.cfg",
            self.plugins / "AlreadyThere.dll",
            self.receipt_path,
        ]
        return {path: path.read_bytes() for path in paths}

    def stage(self):
        _use_synthetic_profile(self.controller, self.profile)
        return self.controller.prepare()


def confirmation(request, **overrides):
    body = {
        "status": "loaded",
        "site_id": request["site_id"],
        "nonce": request["nonce"],
        "stem": request["stem"],
        "filename": f"{request['stem']}.dll",
        "pid": request["pid"],
        "start_identity": request["start_identity"],
        "member_sha256": request["member_sha256"],
        "archive_sha256": request["archive_sha256"],
    }
    body.update(overrides)
    return body


def published_text(controller):
    return json.dumps({"state": controller.state(), "request": controller.request()}, default=str)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_pins_match_the_reviewed_artifact_and_production_stays_empty():
    receipt = json.loads(
        (Path(__file__).resolve().parents[1] / "docs" / "validation"
         / "community-plugin-286-2026-10-24.json").read_text(encoding="utf-8")
    )
    profile = pinned_profile()
    assert profile.site_id == "286" == receipt["plugin_id"]
    assert profile.api_version == 3 == receipt["api_version"]
    assert profile.archive_sha256 == receipt["archive_sha256"]
    assert profile.member == "plugins/SpeedFlipTrainer.dll"
    assert profile.member_sha256 == receipt["archive_members"][1]["sha256"]
    assert profile.source_commit == receipt["source_commit"]
    assert profile.license == "GPL-3.0"
    assert profile.download_url == receipt["download_url"]
    assert profile.game_exe_sha256 == native_community.GAME_EXE_SHA256
    assert profile.core_identity == "Bakkes229"
    assert profile.build_identity == "261013.63066.530866"
    assert production_profiles() == ()
    assert production_eligible(profile) is False
    assert owned_start_identity(CREATED) == "1740000000.125"
    with pytest.raises(NativeCommunityError):
        owned_start_identity(True)
    with pytest.raises(NativeCommunityError):
        owned_start_identity(float("nan"))


def test_prepare_stages_a_synthetic_archive_without_enabling(world):
    idle = world.controller.state()
    assert idle["enabled"] is False and idle["status"] == "idle" and idle["can_activate"] is False
    assert idle["production_eligible"] is False and idle["game_verified"] is False
    assert world.controller.request() is None

    staged = world.stage()
    request = world.controller.request()
    record = json.loads(world.journal.read_text(encoding="ascii"))
    text = published_text(world.controller)

    assert staged["enabled"] is False and staged["status"] == "staged"
    assert staged["game_verified"] is False and staged["can_activate"] is False
    assert request["site_id"] == "286"
    assert request["nonce"] == NONCE
    assert request["stem"] == world.destination.stem
    assert request["archive_sha256"] == world.profile.archive_sha256
    assert request["member_sha256"] == hashlib.sha256(world.dll).hexdigest()
    assert request["pid"] == 4242 and request["start_identity"] == "1740000000.125"
    assert request["game_exe_sha256"] == native_community.GAME_EXE_SHA256
    assert request["core_identity"] == "Bakkes229"
    assert request["build_identity"] == "261013.63066.530866"
    assert "plugin load" not in text and "plugin unload" not in text and ".dll" not in text
    assert world.destination.read_bytes() == world.dll
    assert record["owned_file_id"] and record["can_activate"] is False
    assert record["production_eligible"] is False and record["autoload_modified"] is False
    assert record["cfg_modified"] is False
    assert world.snapshot() == world.before
    assert json.loads(world.receipt_bytes)["can_activate"] is False
    assert min(world.probes.counts.values()) >= 4


def test_exact_ack_enables_and_a_duplicate_does_not(world):
    world.stage()
    request = world.controller.request()
    first = world.controller.accept_status(confirmation(request))
    second = world.controller.accept_status(confirmation(request))
    foreign = world.controller.accept_status({"status": "loaded"})

    assert first["accepted"] is True and first["reason"] == "loaded" and first["enabled"] is True
    assert first["game_verified"] is False and first["can_activate"] is False
    assert first["production_eligible"] is False
    assert world.controller.request() is None
    assert second["accepted"] is False and second["reason"] == "duplicate" and second["enabled"] is True
    assert foreign["reason"] == "duplicate" and foreign["enabled"] is True
    assert world.destination.read_bytes() == world.dll
    assert world.snapshot() == world.before


@pytest.mark.parametrize(("field", "value"), [
    ("pid", 4243),
    ("nonce", "12345678-1234-4234-8234-123456789abd"),
    ("start_identity", "1740000000.999"),
])
def test_stale_pid_nonce_and_start_identity_cannot_enable(world, field, value):
    world.stage()
    request = world.controller.request()
    result = world.controller.accept_status(confirmation(request, **{field: value}))
    assert result["accepted"] is False and result["reason"] == "stale" and result["enabled"] is False
    assert world.controller.state()["status"] == "staged"
    assert world.destination.read_bytes() == world.dll


def test_live_pid_drift_cannot_enable(world):
    world.stage()
    request = world.controller.request()
    world.probes.scope = replace(world.probes.scope, pid=4243)
    result = world.controller.accept_status(confirmation(request))
    assert result["accepted"] is False and result["reason"] == "stale" and result["enabled"] is False


def test_foreign_and_unknown_acks_cannot_enable(world):
    early = world.controller.accept_status({
        "status": "loaded", "site_id": "286", "nonce": NONCE, "stem": "MCTCommunity_286_x",
        "filename": "MCTCommunity_286_x.dll", "pid": 4242, "start_identity": "1740000000.125",
        "member_sha256": "ab" * 32, "archive_sha256": "cd" * 32,
    })
    assert early["reason"] == "unknown" and early["enabled"] is False
    assert not world.journal.exists()

    world.stage()
    request = world.controller.request()
    foreign = world.controller.accept_status(confirmation(request, site_id="223"))
    hashed = world.controller.accept_status(confirmation(request, member_sha256="ab" * 32))
    command = dict(confirmation(request), load_command="plugin load SpeedFlipTrainer")
    unknown = world.controller.accept_status(command)
    path = world.controller.accept_status(
        confirmation(request, filename=str(world.destination)))
    unloaded = world.controller.accept_status(confirmation(request, status="unloaded"))
    flagged = world.controller.accept_status(confirmation(request, pid=True))

    assert foreign["reason"] == "foreign" and hashed["reason"] == "foreign"
    assert unknown["reason"] == "unknown" and path["reason"] == "unknown"
    assert unloaded["reason"] == "unknown" and flagged["reason"] == "unknown"
    assert world.controller.state()["enabled"] is False
    assert world.controller.request()["stem"] == request["stem"]
    assert "plugin load" not in json.dumps(unknown)
    assert world.snapshot() == world.before


def test_ui_booleans_and_unpinned_inputs_are_refused(world, tmp_path):
    world.probes.lease_mode = "dict"
    with pytest.raises(NativeCommunityError, match="not active"):
        world.stage()
    world.probes.lease_mode = "scope"
    world.probes.movie_value = 1
    with pytest.raises(NativeCommunityError, match="not ready"):
        world.controller.prepare()
    world.probes.movie_value = True
    world.probes.online = True
    with pytest.raises(NativeCommunityError, match="heartbeat"):
        world.controller.prepare()
    world.probes.online = False
    assert not world.journal.exists() and not world.destination.exists()

    with pytest.raises(TypeError):
        world.controller.prepare(tmp_path / "SpeedFlipTrainer.dll")
    with pytest.raises(NativeCommunityError, match="path or URL"):
        _use_synthetic_profile(world.controller, tmp_path / "SpeedFlipTrainer.dll")
    with pytest.raises(NativeCommunityError, match="path or URL"):
        _use_synthetic_profile(world.controller, "plugin load SpeedFlipTrainer")
    with pytest.raises(NativeCommunityError, match="pinned"):
        _use_synthetic_profile(world.controller, replace(world.profile, site_id="287"))
    with pytest.raises(NativeCommunityError, match="pinned"):
        _use_synthetic_profile(world.controller, replace(world.profile, member="plugins/Other.dll"))

    pinned_dir = world.cache / "objects" / native_community.ARCHIVE_SHA256
    pinned_dir.mkdir()
    (pinned_dir / "archive.zip").write_bytes(b"not-the-reviewed-zip")
    receipt = pinned_dir / "receipt.json"
    receipt.write_bytes(b'{"can_activate": true}')
    with pytest.raises(NativeCommunityError, match="hash"):
        world.fresh_controller().prepare()
    assert receipt.read_bytes() == b'{"can_activate": true}'
    assert not world.journal.exists() and not world.destination.exists()
    assert world.snapshot() == world.before


@pytest.mark.parametrize(("fail_at", "journal", "dll"), [(2, False, False), (3, True, False), (4, True, True)])
def test_scope_loss_between_staging_boundaries(world, fail_at, journal, dll):
    world.probes.movie_fail_at = fail_at
    with pytest.raises(NativeCommunityError, match="not verified"):
        world.stage()
    assert world.journal.exists() is journal
    assert world.destination.exists() is dll
    assert world.controller.state()["enabled"] is False
    assert world.controller.request() is None
    assert world.probes.counts["movie"] == fail_at
    assert world.snapshot() == world.before
    if fail_at == 3:
        report = world.controller.recover()
        assert report["status"] == "recovered" and report["dll_removed"] is False
        assert not world.journal.exists()
    if fail_at == 4:
        record = json.loads(world.journal.read_text(encoding="ascii"))
        report = world.controller.recover()
        assert record["state"] == "prepared" and record["owned_file_id"] is None
        assert report["status"] == "ambiguous" and report["dll_removed"] is False
        assert report["journal_kept"] is True
        assert world.destination.read_bytes() == world.dll


def test_second_prepare_does_not_overwrite(world):
    world.stage()
    first = world.destination.read_bytes()
    journal = world.journal.read_bytes()
    with pytest.raises(NativeCommunityError, match="already staged"):
        world.controller.prepare()
    second = world.fresh_controller()
    with pytest.raises(NativeCommunityError, match="already staged"):
        second.prepare()
    assert world.destination.read_bytes() == first
    assert world.journal.read_bytes() == journal
    assert world.snapshot() == world.before


def test_recovery_waits_for_the_game_and_the_helper(world):
    world.probes.game = True
    world.probes.helper = True
    world.stage()
    while_both = world.controller.recover()
    world.probes.game = False
    while_helper = world.controller.recover()
    assert while_both["status"] == "deferred" and while_both["dll_removed"] is False
    assert while_helper["journal_kept"] is True and while_helper["enabled"] is False
    assert world.destination.read_bytes() == world.dll
    assert world.controller.request() is not None
    world.probes.helper = False
    done = world.controller.recover()
    assert done["status"] == "recovered" and done["dll_removed"] is True
    assert done["journal_kept"] is False and not world.destination.exists()
    assert world.snapshot() == world.before


def test_uncertain_probe_and_startup_recover(world):
    world.stage()
    world.probes.game_error = True
    blocked = world.controller.recover()
    assert blocked["status"] == "deferred" and blocked["journal_kept"] is True
    assert "could not be checked" in blocked["message"]
    assert world.destination.read_bytes() == world.dll
    world.probes.game_error = False
    world.probes.game = None
    unclear = world.controller.recover()
    assert unclear["dll_removed"] is False and world.journal.is_file()

    def boom():
        raise AssertionError("live lease")

    startup = NativeCommunityController(
        world.app, world.root, world.cache,
        lease=boom, runtime=boom, heartbeat=boom, movie_ready=boom,
        game_running=lambda: False, helper_pending=lambda: False,
    )
    assert startup.state()["enabled"] is False and startup.state()["outstanding"] is True
    recovered = startup.recover()
    assert recovered["status"] == "recovered" and recovered["dll_removed"] is True
    assert not world.journal.exists() and not world.destination.exists()
    assert world.snapshot() == world.before


def test_changed_bytes_and_file_identity_stay_recorded(world, tmp_path):
    world.stage()
    journal = world.journal.read_bytes()
    record = json.loads(journal)
    world.destination.write_bytes(world.dll + b"x")
    retained = world.controller.recover()
    assert retained["status"] == "retained" and retained["dll_removed"] is False
    assert retained["journal_kept"] is True and world.controller.request() is None
    assert world.journal.read_bytes() == journal
    assert world.destination.read_bytes() == world.dll + b"x"
    assert record["owned_file_id"] and record["member_sha256"] == hashlib.sha256(world.dll).hexdigest()

    replaced = World(tmp_path / "replaced")
    replaced.stage()
    data = replaced.destination.read_bytes()
    identity = json.loads(replaced.journal.read_text(encoding="ascii"))["owned_file_id"]
    journal_bytes = replaced.journal.read_bytes()
    replaced.destination.unlink()
    replaced.destination.write_bytes(data)
    report = replaced.controller.recover()
    assert report["status"] == "retained" and "identity" in report["message"]
    assert report["dll_removed"] is False and report["journal_kept"] is True
    assert replaced.journal.read_bytes() == journal_bytes
    assert json.loads(journal_bytes)["owned_file_id"] == identity
    assert replaced.destination.read_bytes() == data
    assert replaced.snapshot() == replaced.before


def test_a_conflicted_journal_and_a_loaded_game_are_left_in_place(world, tmp_path):
    world.stage()
    victim = tmp_path / "victim.dll"
    victim.write_bytes(b"victim")
    record = json.loads(world.journal.read_text(encoding="ascii"))
    record["destination"] = str(victim)
    world.journal.write_text(json.dumps(record), encoding="ascii")
    conflict = world.controller.recover()
    assert conflict["status"] == "retained" and conflict["journal_kept"] is True
    assert conflict["dll_removed"] is False and conflict["enabled"] is False
    assert victim.read_bytes() == b"victim"
    assert world.destination.is_file() and world.journal.is_file()

    held = World(tmp_path / "held")
    held.stage()
    assert held.controller.accept_status(confirmation(held.controller.request()))["enabled"] is True
    held.probes.game = True
    deferred = held.controller.recover()
    assert deferred["status"] == "deferred" and deferred["enabled"] is True
    assert deferred["dll_removed"] is False and deferred["journal_kept"] is True
    assert "plugin unload" not in json.dumps(deferred)
    assert held.destination.read_bytes() == held.dll
    held.probes.game = False
    finished = held.controller.recover()
    assert finished["dll_removed"] is True and finished["enabled"] is False
    assert held.snapshot() == held.before


def test_helper_starting_during_recovery_keeps_the_owned_file(world):
    world.stage()
    journal = world.journal.read_bytes()
    calls = []
    def pending():
        calls.append(True)
        # Outer recovery sees no helper; the first deletion-boundary probe
        # catches one that appeared while the journal was being inspected.
        return len(calls) > 1
    world.controller._helper_pending = pending
    result = world.controller.recover()
    assert len(calls) >= 2
    assert result["journal_kept"] and not result["dll_removed"]
    assert world.journal.read_bytes() == journal
    assert world.destination.read_bytes() == world.dll
