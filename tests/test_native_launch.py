import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from my_career_training import native_launch
from my_career_training.native_launch import (
    NativeLaunchError,
    NativeLaunchUncertain,
    launch_native_offline,
)

SESSION = "12345678-1234-4234-8234-123456789abc"
CHILD_PID = 424242
HELPER_PID = 900001
CREATED = 1735000000.125
PRIVATE_BYTES = b"PRIVATE-PACKAGE"
ORIGINAL_POPEN = native_launch._popen


def _pe(kind="exe", machine=0x8664):
    header = bytearray(64)
    header[0:2] = b"MZ"
    header[60:64] = (64).to_bytes(4, "little")
    image = bytearray(b"PE\0\0")
    image += int(machine).to_bytes(2, "little")
    image += (0).to_bytes(2, "little")
    image += (0).to_bytes(4, "little")
    image += (0).to_bytes(4, "little")
    image += (0).to_bytes(4, "little")
    image += (240).to_bytes(2, "little")
    characteristics = 0x0002 | 0x0020
    if kind == "dll":
        characteristics |= 0x2000
    image += characteristics.to_bytes(2, "little")
    image += (0x20B).to_bytes(2, "little")
    return bytes(header) + bytes(image) + b"\0" * 32


class LineStream:
    def __init__(self, lines, block=False):
        self.lines = list(lines)
        self.block = block
        self.closed = False
        self._event = threading.Event()

    def readline(self, limit=-1):
        if self.lines:
            data = self.lines.pop(0)
            if limit and limit > 0:
                return data[:limit]
            return data
        if self.closed or not self.block:
            return b""
        while not self.closed:
            self._event.wait(0.01)
        return b""

    def read(self, _size=-1):
        return b""

    def close(self):
        self.closed = True
        self._event.set()


class MemoryIn:
    def __init__(self):
        self.buf = bytearray()
        self.closed = False

    def write(self, data):
        if self.closed:
            raise ValueError("closed")
        self.buf += data
        return len(data)

    def flush(self):
        return None

    def close(self):
        self.closed = True


class FakeHelper:
    def __init__(self, args, stdout, stderr, pid, returncode):
        self.args = args
        self.kwargs = {}
        self.pid = pid
        self.returncode = returncode
        self.stdin = MemoryIn()
        self.stdout = stdout
        self.stderr = io.BytesIO(stderr)
        self.stopped = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.stopped = True
        raise AssertionError("kill")

    def terminate(self):
        self.stopped = True
        raise AssertionError("terminate")

    def wait(self, timeout=None):
        self.stopped = True
        raise AssertionError("wait")


class Child:
    def __init__(self, exe, created=CREATED, command=None):
        self.pid = CHILD_PID
        self.created = created
        self.gone = False
        self._exe = str(Path(exe).resolve())
        self.command = command or [self._exe, *native_launch.OFFLINE_ARGUMENTS]

    def create_time(self):
        if self.gone:
            raise psutil.NoSuchProcess(self.pid)
        return self.created

    def exe(self):
        if self.gone:
            raise psutil.NoSuchProcess(self.pid)
        return self._exe

    def cmdline(self):
        if self.gone:
            raise psutil.NoSuchProcess(self.pid)
        return list(self.command)


def _write_runtime(directory, *, helper=None, dll=None, notice=None, receipt=None, extra=None):
    directory.mkdir(parents=True, exist_ok=True)
    helper_blob = _pe("exe") if helper is None else helper
    dll_blob = _pe("dll") if dll is None else dll
    notice_blob = native_launch.DETOURS_NOTICE_BYTES if notice is None else notice
    (directory / "MctNativeLauncher.exe").write_bytes(helper_blob)
    (directory / "MctNativeFileView64.dll").write_bytes(dll_blob)
    (directory / "DETOURS-MIT-LICENSE.txt").write_bytes(notice_blob)
    if receipt is None:
        receipt = native_launch.build_runtime_receipt(
            hashlib.sha256(helper_blob).hexdigest(),
            len(helper_blob),
            hashlib.sha256(dll_blob).hexdigest(),
            len(dll_blob),
        )
    (directory / "native-launch-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    if extra is not None:
        (directory / extra).write_bytes(b"x")
    return directory


def _write_game(tmp, exe_size, package_size):
    root = tmp / "game"
    exe = root / "Binaries" / "Win64" / "RocketLeague.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"R" * exe_size)
    package = root / "TAGame" / "CookedPCConsole" / "GFX_MainMenu_SF.upk"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"U" * package_size)
    private = tmp / "private" / "menu.upk"
    private.parent.mkdir()
    private.write_bytes(PRIVATE_BYTES)
    return root, private, hashlib.sha256(PRIVATE_BYTES).hexdigest(), exe


class World:
    def __init__(self, monkeypatch, tmp):
        monkeypatch.setattr(native_launch, "SOURCE_EXE_SIZE", 32)
        monkeypatch.setattr(native_launch, "SOURCE_PACKAGE_SIZE", 16)
        self.root, self.private, self.digest, self.exe = _write_game(tmp, 32, 16)
        self.runtime = _write_runtime(tmp / "runtime" / "native")
        monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (self.runtime,))
        self.child = Child(self.exe)
        self.owned = []
        self.existing = []
        self.helper = None
        self.stdout = LineStream([])
        self.create_child = True
        self.stderr = b"x" * 20000
        self.returncode_on_start = None

        def popen(args, **kwargs):
            if self.create_child:
                self.owned = [SimpleNamespace(pid=CHILD_PID)]
            self.helper = FakeHelper(args, self.stdout, self.stderr, HELPER_PID, self.returncode_on_start)
            self.helper.kwargs = kwargs
            return self.helper

        monkeypatch.setattr(native_launch, "_popen", popen)
        monkeypatch.setattr(native_launch, "_game_processes", lambda: [*self.existing, *self.owned])
        monkeypatch.setattr(native_launch, "_process", self._process)

    def _process(self, pid):
        if pid != CHILD_PID:
            raise psutil.NoSuchProcess(pid)
        return self.child

    def ready(self, **overrides):
        receipt = {
            "protocol": 1,
            "kind": "launch",
            "pid": CHILD_PID,
            "create_time": CREATED,
            "executable": str(self.exe.resolve()),
            "session": SESSION,
            "private_package": str(self.private.resolve()),
            "private_package_sha256": self.digest,
            "source_executable_sha256": native_launch.SOURCE_EXE_SHA256,
            "source_package_sha256": native_launch.SOURCE_PACKAGE_SHA256,
            "game_verified": False,
            "production_ready": False,
            "file_view_observed": False,
        }
        receipt.update(overrides)
        return json.dumps(receipt, separators=(",", ":")).encode("ascii") + b"\n"

    def error_line(self):
        body = {
            "protocol": 1,
            "kind": "error",
            "error": "Private package hash does not match.",
            "game_verified": False,
            "production_ready": False,
            "file_view_observed": False,
        }
        return json.dumps(body).encode("ascii") + b"\n"

    def exit_line(self, code=0):
        body = {
            "protocol": 1,
            "kind": "exit",
            "pid": CHILD_PID,
            "create_time": CREATED,
            "exit_code": code,
            "session": SESSION,
            "executable": str(self.exe.resolve()),
            "game_verified": False,
            "production_ready": False,
            "file_view_observed": False,
        }
        return json.dumps(body).encode("ascii") + b"\n"

    def launch(self, lines):
        self.stdout = LineStream(lines)
        return launch_native_offline(self.root, self.private, self.digest, SESSION)

    def launch_stream(self, stream):
        self.stdout = stream
        return launch_native_offline(self.root, self.private, self.digest, SESSION)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("real helper was started")

    def explode_process(pid):
        raise AssertionError(f"real process lookup {pid}")

    monkeypatch.setattr(native_launch, "_popen", explode)
    monkeypatch.setattr(native_launch, "_game_processes", lambda: ())
    monkeypatch.setattr(native_launch, "_process", explode_process)
    native_launch._RETAINED.clear()
    yield
    native_launch._RETAINED.clear()


def _error(call):
    with pytest.raises(NativeLaunchError) as caught:
        call()
    assert type(caught.value) is NativeLaunchError
    assert caught.value.defer_restore is False
    assert caught.value.game_verified is False
    assert caught.value.production_ready is False
    return caught.value


def test_pinned_contract_and_detours_notice():
    assert native_launch.SOURCE_EXE_SHA256 == "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
    assert native_launch.SOURCE_EXE_SIZE == 39727616
    assert native_launch.SOURCE_PACKAGE_SHA256 == "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65"
    assert native_launch.SOURCE_PACKAGE_SIZE == 3418271
    assert native_launch.SOURCE_MIDGAME_SHA256 == "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50"
    assert native_launch.SOURCE_MIDGAME_SIZE == 814718
    assert native_launch.SOURCE_ENDGAME_SHA256 == "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc"
    assert native_launch.SOURCE_ENDGAME_SIZE == 4348661
    assert native_launch.RECEIPT_MAX_BYTES == 8192
    assert native_launch.OFFLINE_ARGUMENTS == (
        "-rlbot", "RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=240", "-nomovie",
    )
    notice = native_launch.DETOURS_NOTICE_BYTES
    assert len(notice) == native_launch.DETOURS_NOTICE_SIZE == 1099
    assert hashlib.sha256(notice).hexdigest() == native_launch.DETOURS_NOTICE_SHA256
    assert notice.startswith(b"# Copyright (c) Microsoft Corporation\n")
    assert b"MIT License" in notice
    assert b"Permission is hereby granted" in notice
    receipt = native_launch.build_runtime_receipt("a" * 64, 10, "b" * 64, 20)
    assert set(receipt) == native_launch.BUILD_RECEIPT_FIELDS
    assert receipt["source_exe_size"] == 39727616
    assert receipt["game_verified"] is False
    assert receipt["production_ready"] is False
    assert "subprocess.Popen" in inspect.getsource(ORIGINAL_POPEN)


def test_launch_signature_has_no_executable_pid_or_arguments():
    params = inspect.signature(launch_native_offline).parameters
    assert list(params) == [
        "game_root", "private_package", "private_package_sha256", "session", "runtime_directory",
        "additional_packages",
    ]
    assert params["runtime_directory"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["additional_packages"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["additional_packages"].default is None


def test_build_receipt_rejects_bool_size_and_uppercase_hash():
    with pytest.raises(NativeLaunchError):
        native_launch.build_runtime_receipt("a" * 64, True, "b" * 64, 4)
    with pytest.raises(NativeLaunchError):
        native_launch.build_runtime_receipt("A" * 64, 4, "b" * 64, 4)


def test_spawn_kwargs_omit_creationflags_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    kwargs = native_launch._spawn_kwargs()
    assert "creationflags" not in kwargs
    assert kwargs["shell"] is False
    assert kwargs["env"] is None
    error = _error(lambda: launch_native_offline(r"C:\game", r"C:\private\menu.upk", "ab" * 32, SESSION))
    assert error.code == "not_windows"


def test_spawn_kwargs_hide_the_helper_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    kwargs = native_launch._spawn_kwargs()
    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["shell"] is False
    assert kwargs["env"] is None
    assert kwargs["cwd"] is None


def test_unc_device_and_parent_paths_are_rejected():
    digest = "ab" * 32
    error = _error(lambda: launch_native_offline(r"\\server\share\game", r"C:\private\menu.upk", digest, SESSION))
    assert error.code == "bad_path"
    error = _error(lambda: launch_native_offline(r"\\.\C:\game", r"C:\private\menu.upk", digest, SESSION))
    assert error.code == "bad_path"
    error = _error(lambda: launch_native_offline(r"C:\game\..\other", r"C:\private\menu.upk", digest, SESSION))
    assert error.code == "bad_path"
    error = _error(lambda: launch_native_offline(r"C:\game", r"C:\private\menu.upk", digest, SESSION.upper()))
    assert error.code == "bad_session"


def test_source_size_pin_rejects_a_small_executable(tmp_path):
    root, private, digest, _exe = _write_game(tmp_path, 32, 16)
    error = _error(lambda: launch_native_offline(root, private, digest, SESSION))
    assert error.code == "source_exe_size"
    assert private.read_bytes() == PRIVATE_BYTES


def test_runtime_receipt_accepts_the_pinned_directory(monkeypatch, tmp_path):
    runtime = _write_runtime(tmp_path / "native")
    monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (runtime,))
    receipt = native_launch.validate_native_runtime(runtime)
    assert receipt["game_verified"] is False
    assert receipt["production_ready"] is False
    assert receipt["source_exe_sha256"] == native_launch.SOURCE_EXE_SHA256
    assert receipt["machine"] == "AMD64"


def test_runtime_rejects_unknown_fields_bad_images_and_notice_edits(monkeypatch, tmp_path):
    runtime = tmp_path / "native"
    receipt = native_launch.build_runtime_receipt("a" * 64, len(_pe()), "b" * 64, len(_pe("dll")))
    receipt["publisher"] = "local"
    _write_runtime(runtime, receipt=receipt)
    monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (runtime,))
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_receipt"

    _write_runtime(runtime, helper=b"MZ" + b"\0" * 80)
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_pe"

    _write_runtime(runtime, helper=_pe("exe", machine=0x14C))
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_pe"

    _write_runtime(runtime, dll=_pe("exe"))
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_pe"

    notice = bytearray(native_launch.DETOURS_NOTICE_BYTES)
    notice[40] ^= 1
    _write_runtime(runtime, notice=bytes(notice))
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_notice"

    _write_runtime(runtime, extra="notes.txt")
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "runtime_allowlist"


def test_untrusted_and_missing_runtime_are_rejected(monkeypatch, tmp_path):
    runtime = _write_runtime(tmp_path / "native")
    monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (tmp_path / "missing",))
    assert _error(lambda: native_launch.validate_native_runtime(runtime)).code == "untrusted_runtime"
    assert _error(lambda: native_launch.validate_native_runtime(None)).code == "runtime_missing"


def test_first_existing_runtime_is_used_and_a_broken_one_is_not_skipped(monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    second = _write_runtime(tmp_path / "second")
    monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (missing, second))
    assert native_launch.validate_native_runtime(None)["kind"] == native_launch.BUILD_RECEIPT_KIND

    first = tmp_path / "first"
    first.mkdir()
    (first / "stray.txt").write_bytes(b"x")
    monkeypatch.setattr(native_launch, "trusted_runtime_directories", lambda: (first, second))
    assert _error(lambda: native_launch.validate_native_runtime(None)).code == "runtime_allowlist"


def test_valid_launch_keeps_the_helper_and_the_child_distinct(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    before = dict(os.environ)
    owned = world.launch([world.ready(), world.exit_line(code=3)])
    helper = world.helper
    assert dict(os.environ) == before
    assert helper.args == [str((world.runtime / "MctNativeLauncher.exe").resolve()), "--launch-offline"]
    assert helper.kwargs["shell"] is False
    assert helper.kwargs["env"] is None
    assert helper.kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert "text" not in helper.kwargs
    plan = json.loads(bytes(helper.stdin.buf))
    assert set(plan) == native_launch.PLAN_FIELDS
    assert plan["session"] == SESSION
    assert plan["protocol"] == 1
    assert plan["private_package_sha256"] == world.digest
    assert "RocketLeague.exe" not in json.dumps(plan)
    assert "-noeac" not in json.dumps(plan)
    assert helper.stdin.closed is True
    assert owned.identity.pid == CHILD_PID
    assert owned.helper.pid == HELPER_PID
    assert owned.identity.pid != owned.helper.pid
    assert owned.identity.created == CREATED
    assert owned.game_verified is False
    assert owned.production_ready is False
    assert owned.view_active is False
    assert owned.lock_active is False
    assert owned.file_view_observed is False
    assert owned.poll() == "ready"
    assert helper in native_launch.retained_helpers()
    assert helper.stopped is False
    assert owned.release() is False
    assert world.private.read_bytes() == PRIVATE_BYTES


def test_helper_exit_is_degraded_while_the_game_remains_then_exited(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    owned = world.launch([world.ready(), world.exit_line(code=3)])
    world.helper.returncode = 0
    assert owned.poll() == "degraded"
    assert owned.view_active is False
    assert owned.lock_active is False
    assert owned.file_view_observed is False
    assert owned.game_verified is False
    world.child.gone = True
    assert owned.poll() == "exited"
    assert owned.exit_receipt["exit_code"] == 3
    assert owned.exit_receipt["game_verified"] is False
    assert owned.production_ready is False
    assert owned.release() is True
    assert world.helper not in native_launch.retained_helpers()
    assert world.helper.stopped is False
    assert world.private.read_bytes() == PRIVATE_BYTES


def test_receipt_mismatches_stay_uncertain_and_preserve_files(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    other = tmp_path / "other" / "RocketLeague.exe"
    other.parent.mkdir()
    other.write_bytes(b"other-exe")
    cases = [
        {"session": "abcdefab-1234-4234-8234-123456789abc"},
        {"private_package_sha256": "ab" * 32},
        {"executable": str(other.resolve())},
        {"create_time": CREATED + 5},
        {"pid": True},
        {"game_verified": True},
        {"file_view_observed": True},
        {"extra": 1},
    ]
    reasons = [
        "session_mismatch", "hash_mismatch", "exe_mismatch", "starttime_mismatch",
        "malformed", "claimed_verified", "claimed_verified", "extra_field",
    ]
    for overrides, reason in zip(cases, reasons, strict=True):
        world.helper = None
        world.owned = []
        with pytest.raises(NativeLaunchUncertain) as caught:
            world.launch([world.ready(**overrides)])
        assert caught.value.reason == reason
        assert caught.value.defer_restore is True
        assert caught.value.game_verified is False
        assert world.helper.stopped is False
        assert world.private.read_bytes() == PRIVATE_BYTES
        assert caught.value.release() is False


def test_cmdline_must_be_the_whole_offline_vector(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    world.child.command = [str(world.exe.resolve()), "-rlbot", "RLBot_ControllerURL=127.0.0.1:23233",
                            "RLBot_PacketSendRate=240"]
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([world.ready()])
    assert caught.value.reason == "cmdline_mismatch"
    for conflict in ("-eac", "-noeac", "-NOEAC"):
        world.owned = []
        world.child.command = [str(world.exe.resolve()), *native_launch.OFFLINE_ARGUMENTS, conflict]
        with pytest.raises(NativeLaunchUncertain) as caught:
            world.launch([world.ready()])
        assert caught.value.reason == "cmdline_mismatch"
    assert world.private.read_bytes() == PRIVATE_BYTES


@pytest.mark.parametrize("arguments", [
    ("RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=240", "-nomovie"),
    ("-rlbot", "RLBot_PacketSendRate=240", "-nomovie"),
    ("-rlbot", "RLBot_ControllerURL=127.0.0.1:23234", "RLBot_PacketSendRate=240", "-nomovie"),
    ("-rlbot", "RLBot_ControllerURL=127.0.0.1:23233", "-nomovie"),
    ("-rlbot", "RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=120", "-nomovie"),
])
def test_cmdline_rejects_missing_or_changed_rlbot_settings(monkeypatch, tmp_path, arguments):
    world = World(monkeypatch, tmp_path)
    world.child.command = [str(world.exe.resolve()), *arguments]
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([world.ready()])
    assert caught.value.reason == "cmdline_mismatch"
    assert world.private.read_bytes() == PRIVATE_BYTES


def test_helper_pid_and_a_second_game_are_rejected(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([world.ready(pid=HELPER_PID)])
    assert caught.value.reason == "helper_pid"
    world.owned = []
    world.create_child = False

    def popen(args, **kwargs):
        world.owned = [SimpleNamespace(pid=CHILD_PID), SimpleNamespace(pid=7)]
        world.helper = FakeHelper(args, world.stdout, world.stderr, HELPER_PID, None)
        world.helper.kwargs = kwargs
        return world.helper

    monkeypatch.setattr(native_launch, "_popen", popen)
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([world.ready()])
    assert caught.value.reason == "other_game"
    assert world.helper.stopped is False


def test_timeout_oversized_utf8_and_eof(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    monkeypatch.setattr(native_launch, "RECEIPT_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch_stream(LineStream([], block=True))
    assert caught.value.reason == "timeout"
    assert caught.value.helper_running is True
    assert caught.value.defer_restore is True
    assert world.helper.stopped is False
    assert world.private.read_bytes() == PRIVATE_BYTES

    world.owned = []
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([b"A" * (native_launch.LINE_LIMIT + 1)])
    assert caught.value.reason == "oversized"

    world.owned = []
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([b"\xff\n"])
    assert caught.value.reason == "invalid_utf8"

    world.owned = []
    world.create_child = False
    world.returncode_on_start = 1
    error = _error(lambda: world.launch([]))
    assert error.code == "eof"
    assert world.private.read_bytes() == PRIVATE_BYTES

    world.returncode_on_start = None
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([b'{"protocol":1,"event":"ready","create_time":Infinity}\n'])
    assert caught.value.reason == "malformed"
    assert world.helper.stopped is False


def test_explicit_error_before_child_is_a_refusal(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    world.create_child = False
    world.returncode_on_start = 1
    error = _error(lambda: world.launch([world.error_line()]))
    assert error.code == "helper_refused"
    assert "does not match" in str(error)
    assert error.child_created is False
    assert world.helper.stopped is False
    assert world.private.read_bytes() == PRIVATE_BYTES

    world.returncode_on_start = None
    world.create_child = True
    with pytest.raises(NativeLaunchUncertain) as caught:
        world.launch([world.error_line()])
    assert caught.value.reason == "helper_error"
    assert caught.value.defer_restore is True
    assert world.helper.stopped is False


def test_existing_game_and_helper_start_failure_do_not_spawn_a_child(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    world.existing = [SimpleNamespace(pid=3)]
    error = _error(lambda: world.launch([world.ready()]))
    assert error.code == "game_already_running"
    assert world.helper is None

    def boom(*_args, **_kwargs):
        raise OSError("helper missing")

    monkeypatch.setattr(native_launch, "_popen", boom)
    world.existing = []
    error = _error(lambda: launch_native_offline(world.root, world.private, world.digest, SESSION))
    assert error.code == "helper_start_failed"
    assert native_launch.retained_helpers() == ()
    assert world.private.read_bytes() == PRIVATE_BYTES


def test_private_hash_mismatch_and_package_inside_the_game(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    error = _error(lambda: launch_native_offline(world.root, world.private, "ab" * 32, SESSION))
    assert error.code == "private_hash_mismatch"
    assert world.helper is None
    inside = world.root / "TAGame" / "CookedPCConsole" / "custom.upk"
    inside.write_bytes(b"INSIDE")
    digest = hashlib.sha256(b"INSIDE").hexdigest()
    error = _error(lambda: launch_native_offline(world.root, inside, digest, SESSION))
    assert error.code == "private_inside_game"
    assert inside.read_bytes() == b"INSIDE"


def test_reparse_runtime_is_rejected(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    monkeypatch.setattr(native_launch, "_is_reparse", lambda _path: True)
    error = _error(lambda: world.launch([world.ready()]))
    assert error.code == "reparse"
    assert world.helper is None
    assert world.private.read_bytes() == PRIVATE_BYTES


def _assert_helper_locked(path: Path, snapshot: bytes) -> None:
    assert path.read_bytes() == snapshot
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    os.close(descriptor)
    write_flags = os.O_WRONLY | getattr(os, "O_BINARY", 0)
    with pytest.raises(OSError):
        descriptor = os.open(path, write_flags)
        os.close(descriptor)
    replacement = path.with_name(path.name + ".replacement")
    replacement.write_bytes(b"other")
    try:
        with pytest.raises(OSError):
            os.replace(replacement, path)
        with pytest.raises(OSError):
            path.unlink()
    finally:
        replacement.unlink(missing_ok=True)
    assert path.read_bytes() == snapshot


def _assert_helper_unlocked(path: Path) -> None:
    snapshot = path.read_bytes()
    flags = os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    os.close(descriptor)
    path.unlink()
    assert not path.exists()
    path.write_bytes(snapshot)


def test_held_helper_refuses_replacement_until_popen_returns(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    helper = world.runtime / "MctNativeLauncher.exe"
    snapshot = helper.read_bytes()
    world.stdout = LineStream([world.ready()])

    def popen(args, **kwargs):
        assert args == [str(helper.resolve()), "--launch-offline"]
        _assert_helper_locked(helper, snapshot)
        world.owned = [SimpleNamespace(pid=CHILD_PID)]
        world.helper = FakeHelper(args, world.stdout, world.stderr, HELPER_PID, None)
        world.helper.kwargs = kwargs
        return world.helper

    monkeypatch.setattr(native_launch, "_popen", popen)
    owned = launch_native_offline(world.root, world.private, world.digest, SESSION)
    assert owned.identity.pid == CHILD_PID
    assert world.helper.stopped is False
    _assert_helper_unlocked(helper)


def test_held_helper_closes_when_popen_fails(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    helper = world.runtime / "MctNativeLauncher.exe"
    snapshot = helper.read_bytes()

    def popen(args, **_kwargs):
        _assert_helper_locked(helper, snapshot)
        raise OSError("helper missing")

    monkeypatch.setattr(native_launch, "_popen", popen)
    error = _error(lambda: launch_native_offline(world.root, world.private, world.digest, SESSION))
    assert error.code == "helper_start_failed"
    assert native_launch.retained_helpers() == ()
    _assert_helper_unlocked(helper)


def test_held_helper_closes_when_the_open_image_no_longer_matches(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    helper = world.runtime / "MctNativeLauncher.exe"
    original = helper.read_bytes()
    real_load = native_launch._load_runtime
    calls = {"popen": 0}

    def load(directory):
        runtime = real_load(directory)
        helper.write_bytes(original + b"X")
        return runtime

    def popen(*_args, **_kwargs):
        calls["popen"] += 1
        raise AssertionError("popen")

    monkeypatch.setattr(native_launch, "_load_runtime", load)
    monkeypatch.setattr(native_launch, "_popen", popen)
    error = _error(lambda: launch_native_offline(world.root, world.private, world.digest, SESSION))
    assert error.code == "runtime_hash"
    assert calls["popen"] == 0
    _assert_helper_unlocked(helper)


def test_injected_hold_wraps_popen_and_closes_after_start_failure(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    events = []

    class Hold:
        def __init__(self, path):
            self.path = path

        def close(self):
            events.append("close")

    def open_held(path, size, digest):
        blob = path.read_bytes()
        assert size == len(blob)
        assert digest == hashlib.sha256(blob).hexdigest()
        events.append("open")
        return Hold(path)

    def popen(args, **_kwargs):
        events.append(tuple(args))
        raise OSError("injected")

    monkeypatch.setattr(native_launch, "_open_held_helper", open_held)
    monkeypatch.setattr(native_launch, "_popen", popen)
    error = _error(lambda: launch_native_offline(world.root, world.private, world.digest, SESSION))
    assert error.code == "helper_start_failed"
    assert events == [
        "open",
        (str((world.runtime / "MctNativeLauncher.exe").resolve()), "--launch-offline"),
        "close",
    ]


FIXTURE_SESSION = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
FIXTURE_EXE = r"C:\Games\rocketleague\Binaries\Win64\RocketLeague.exe"
FIXTURE_PRIVATE = r"C:\Users\me\AppData\Local\MyCareerTraining\private\GFX_MainMenu_SF.upk"
FIXTURE_PRIVATE_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
FIXTURE_PID = 4242
FIXTURE_CREATED = 1710000000.25
FIXTURE_ERROR = "Rocket League is already running"
FIXTURE_BINARY = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "native-launcher"
    / "bin"
    / "mct_native_launcher_tests.exe"
)


def _fixture_flags():
    return {"production_ready": False, "game_verified": False, "file_view_observed": False}


def _fixture_launch():
    return {
        "protocol": 1,
        "kind": "launch",
        "pid": FIXTURE_PID,
        "create_time": FIXTURE_CREATED,
        "executable": FIXTURE_EXE,
        "session": FIXTURE_SESSION,
        "source_package_sha256": native_launch.SOURCE_PACKAGE_SHA256,
        "source_executable_sha256": native_launch.SOURCE_EXE_SHA256,
        "private_package_sha256": FIXTURE_PRIVATE_SHA,
        "private_package": FIXTURE_PRIVATE,
        **_fixture_flags(),
    }


def _fixture_error():
    return {
        "protocol": 1,
        "kind": "error",
        "error": FIXTURE_ERROR,
        **_fixture_flags(),
    }


def _fixture_exit():
    return {
        "protocol": 1,
        "kind": "exit",
        "pid": FIXTURE_PID,
        "create_time": FIXTURE_CREATED,
        "exit_code": 0,
        "session": FIXTURE_SESSION,
        "executable": FIXTURE_EXE,
        **_fixture_flags(),
    }


def _wire(receipt: dict) -> bytes:
    return json.dumps(receipt, separators=(",", ":")).encode("ascii") + b"\n"


def _accept_fixture_receipts(monkeypatch, launch, error, exit_receipt):
    exe = Path(FIXTURE_EXE)
    private = Path(FIXTURE_PRIVATE)

    def hash_file(path, limit):
        if os.path.normcase(str(path)) != os.path.normcase(FIXTURE_PRIVATE) or limit < 1:
            raise NativeLaunchError("unexpected private package", code="bad_path")
        return FIXTURE_PRIVATE_SHA

    def real_file(path, label, _limit):
        native_launch._syntax(path, label)
        native_launch._reject_reparse_chain(path)
        if path.suffix.casefold() != ".upk":
            raise NativeLaunchError(f"{label} must be a private .upk package.", code="bad_path")
        return path

    def same_file(left, right):
        return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))

    monkeypatch.setattr(native_launch, "_hash_file", hash_file)
    monkeypatch.setattr(native_launch, "_real_file", real_file)
    monkeypatch.setattr(native_launch, "_same_file", same_file)
    child = Child(exe, created=FIXTURE_CREATED, command=[FIXTURE_EXE, *native_launch.OFFLINE_ARGUMENTS])

    def process(pid):
        if pid != FIXTURE_PID:
            raise psutil.NoSuchProcess(pid)
        return child

    monkeypatch.setattr(native_launch, "_process", process)
    monkeypatch.setattr(native_launch, "_game_processes", lambda: [SimpleNamespace(pid=FIXTURE_PID)])
    helper = FakeHelper(["helper", "--launch-offline"], LineStream([]), b"", 111, None)
    owned = native_launch._confirm_child(
        native_launch._parse_wire_object(_wire(launch)),
        session=FIXTURE_SESSION,
        private=private,
        process=helper,
        exe=exe,
        digest=FIXTURE_PRIVATE_SHA,
    )
    assert owned.identity.pid == FIXTURE_PID
    assert owned.identity.created == FIXTURE_CREATED
    assert owned.receipt["kind"] == "launch"
    assert owned.game_verified is False
    assert owned.view_active is False
    monkeypatch.setattr(native_launch, "_game_processes", lambda: [])
    finished = FakeHelper(["helper", "--launch-offline"], LineStream([]), b"", 112, 1)
    with pytest.raises(NativeLaunchError) as caught:
        native_launch._accept_error(
            native_launch._parse_wire_object(_wire(error)),
            process=finished,
            session=FIXTURE_SESSION,
            private_package=FIXTURE_PRIVATE,
        )
    assert caught.value.code == "helper_refused"
    assert FIXTURE_ERROR in str(caught.value)
    parsed_exit = native_launch._parse_exit_receipt(_wire(exit_receipt), owned.identity, FIXTURE_SESSION)
    assert parsed_exit["exit_code"] == exit_receipt["exit_code"]
    assert parsed_exit["kind"] == "exit"
    assert parsed_exit["pid"] == FIXTURE_PID


@pytest.mark.parametrize("exit_code", [0, 259, 0xFFFFFFFF])
def test_synthetic_receipt_fixtures_are_accepted(monkeypatch, exit_code):
    launch = _fixture_launch()
    error = _fixture_error()
    exit_receipt = _fixture_exit()
    exit_receipt["exit_code"] = exit_code
    assert set(launch) == native_launch.LAUNCH_RECEIPT_FIELDS
    assert set(error) == native_launch.ERROR_RECEIPT_FIELDS
    assert set(exit_receipt) == native_launch.EXIT_RECEIPT_FIELDS
    _accept_fixture_receipts(monkeypatch, launch, error, exit_receipt)


def test_cpp_emit_receipt_fixtures_match_the_parser(monkeypatch):
    binary = FIXTURE_BINARY
    if not binary.is_file():
        pytest.skip(
            "build/native-launcher/bin/mct_native_launcher_tests.exe is not built; "
            "--emit-receipt-fixtures was not run"
        )
    if binary.name != "mct_native_launcher_tests.exe" or native_launch._is_reparse(binary):
        raise AssertionError("refusing to run anything except the receipt fixture test binary")
    completed = subprocess.run(
        [str(binary), "--emit-receipt-fixtures"],
        check=False,
        capture_output=True,
        timeout=10,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line]
    assert len(lines) == 3
    parsed = [native_launch._parse_wire_object(line + b"\n") for line in lines]
    assert parsed == [_fixture_launch(), _fixture_error(), _fixture_exit()]
    _accept_fixture_receipts(monkeypatch, *parsed)


def test_stdout_deadline_does_not_wait_for_buffered_pipe_close():
    # BufferedReader holds its I/O lock during a pending read. close() from the
    # waiter would block on that lock, so use a real anonymous pipe here.
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(read_fd, "rb")
    finished = threading.Event()
    reasons = []
    def wait_for_line():
        try:
            native_launch._read_bounded_line(stream, 0.02)
        except native_launch._Signal as exc:
            reasons.append(exc.reason)
        finally:
            finished.set()
    caller = threading.Thread(target=wait_for_line, daemon=True)
    caller.start()
    try:
        assert finished.wait(1.0), "stdout timeout blocked on a concurrent close"
        assert reasons == ["timeout"]
    finally:
        os.close(write_fd)
        caller.join(1.0)
        stream.close()


def test_stdin_deadline_returns_while_a_helper_does_not_read():
    entered, unblock, closed, finished = (threading.Event() for _ in range(4))
    reasons = []
    class BlockedInput:
        def write(self, payload):
            entered.set()
            unblock.wait(2.0)
            return len(payload)
        def flush(self):
            pass
        def close(self):
            closed.set()
    process = SimpleNamespace(stdin=BlockedInput())
    def write():
        try:
            native_launch._write_plan(process, b"{\"protocol\":1}\n", 0.02)
        except native_launch._Signal as exc:
            reasons.append(exc.reason)
        finally:
            finished.set()
    caller = threading.Thread(target=write, daemon=True)
    caller.start()
    try:
        assert entered.wait(1.0)
        assert finished.wait(1.0), "stdin write bypassed the startup deadline"
        assert reasons == ["timeout"] and not closed.is_set()
    finally:
        unblock.set()
        caller.join(1.0)
        assert closed.wait(1.0)


def _extra_files(root, tmp, *, mid_size, end_size):
    cooked = root / "TAGame" / "CookedPCConsole"
    (cooked / "GFX_MidGameMenu_SF.upk").write_bytes(b"M" * mid_size)
    (cooked / "GFX_EndGameMenu_SF.upk").write_bytes(b"E" * end_size)
    mid = tmp / "private" / "mid.upk"
    end = tmp / "menus" / "end.upk"
    mid.write_bytes(b"MID-PRIVATE")
    end.parent.mkdir()
    end.write_bytes(b"END-PRIVATE-BYTES")
    return mid, end


def test_absent_additional_packages_keep_the_legacy_plan(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path)
    world.launch([world.ready(), world.exit_line()])
    legacy = json.loads(bytes(world.helper.stdin.buf))
    world.helper = None
    world.owned = []
    world.stdout = LineStream([world.ready(), world.exit_line()])
    launch_native_offline(world.root, world.private, world.digest, SESSION, additional_packages={})
    assert json.loads(bytes(world.helper.stdin.buf)) == legacy
    assert set(legacy) == native_launch.PLAN_FIELDS


def test_additional_packages_echo_pins_and_reject_mutations(monkeypatch, tmp_path):
    monkeypatch.setattr(native_launch, "SOURCE_MIDGAME_SIZE", 8)
    monkeypatch.setattr(native_launch, "SOURCE_ENDGAME_SIZE", 9)
    world = World(monkeypatch, tmp_path)
    mid, end = _extra_files(world.root, tmp_path, mid_size=8, end_size=9)
    packages = {
        "midgame": {"private_package": mid, "private_package_sha256": hashlib.sha256(mid.read_bytes()).hexdigest()},
        "endgame": {"private_package": end, "private_package_sha256": hashlib.sha256(end.read_bytes()).hexdigest()},
    }
    receipt = json.loads(world.ready())
    receipt["private_midgame_package"] = str(mid.resolve())
    receipt["private_midgame_package_sha256"] = packages["midgame"]["private_package_sha256"]
    receipt["source_midgame_package_sha256"] = native_launch.SOURCE_MIDGAME_SHA256
    receipt["private_endgame_package"] = str(end.resolve())
    receipt["private_endgame_package_sha256"] = packages["endgame"]["private_package_sha256"]
    receipt["source_endgame_package_sha256"] = native_launch.SOURCE_ENDGAME_SHA256
    world.stdout = LineStream([json.dumps(receipt).encode("ascii") + b"\n", world.exit_line()])
    owned = launch_native_offline(
        world.root, world.private, world.digest, SESSION, additional_packages=packages,
    )
    plan = json.loads(bytes(world.helper.stdin.buf))
    assert set(plan) == native_launch.PLAN_FIELDS | {
        "private_midgame_package", "private_midgame_package_sha256",
        "private_endgame_package", "private_endgame_package_sha256",
    }
    assert "source_midgame_package" not in plan
    assert "source_midgame_package_sha256" not in plan
    assert plan["private_endgame_package_sha256"] == packages["endgame"]["private_package_sha256"]
    assert owned.receipt["source_endgame_package_sha256"] == native_launch.SOURCE_ENDGAME_SHA256
    assert owned.game_verified is False

    world.helper = None
    world.owned = []
    mutated = dict(receipt)
    mutated["source_midgame_package_sha256"] = "ab" * 32
    world.stdout = LineStream([json.dumps(mutated).encode("ascii") + b"\n"])
    with pytest.raises(NativeLaunchUncertain) as uncertain:
        launch_native_offline(world.root, world.private, world.digest, SESSION, additional_packages=packages)
    assert uncertain.value.reason == "hash_mismatch"

    world.helper = None
    world.owned = []
    dropped = dict(receipt)
    del dropped["private_endgame_package_sha256"]
    world.stdout = LineStream([json.dumps(dropped).encode("ascii") + b"\n"])
    with pytest.raises(NativeLaunchUncertain) as missing:
        launch_native_offline(world.root, world.private, world.digest, SESSION, additional_packages=packages)
    assert missing.value.reason == "malformed"

    world.helper = None
    world.owned = []
    sourced = dict(receipt)
    sourced["source_endgame_package"] = str(end.resolve())
    world.stdout = LineStream([json.dumps(sourced).encode("ascii") + b"\n"])
    with pytest.raises(NativeLaunchUncertain) as extra_field:
        launch_native_offline(world.root, world.private, world.digest, SESSION, additional_packages=packages)
    assert extra_field.value.reason == "extra_field"


def test_additional_package_requests_reject_bad_shape_and_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr(native_launch, "SOURCE_MIDGAME_SIZE", 8)
    monkeypatch.setattr(native_launch, "SOURCE_ENDGAME_SIZE", 9)
    world = World(monkeypatch, tmp_path)
    mid, end = _extra_files(world.root, tmp_path, mid_size=8, end_size=9)
    mid_sha = hashlib.sha256(mid.read_bytes()).hexdigest()
    end_sha = hashlib.sha256(end.read_bytes()).hexdigest()

    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"movie": {"private_package": mid, "private_package_sha256": mid_sha}},
    ))
    assert error.code == "plan"
    assert world.helper is None

    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"midgame": {"private_package": str(mid)}},
    ))
    assert error.code == "plan"

    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"midgame": {
            "private_package": str(mid),
            "private_package_sha256": mid_sha,
            "source_package_sha256": native_launch.SOURCE_MIDGAME_SHA256,
        }},
    ))
    assert error.code == "plan"

    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"midgame": {"private_package": str(mid), "private_package_sha256": "ab" * 32}},
    ))
    assert error.code == "private_hash_mismatch"

    alias = tmp_path / "private" / "alias.upk"
    os.link(world.private, alias)
    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"endgame": {
            "private_package": alias,
            "private_package_sha256": hashlib.sha256(alias.read_bytes()).hexdigest(),
        }},
    ))
    assert error.code == "private_overlaps_source"

    inside = world.root / "TAGame" / "CookedPCConsole" / "private-end.upk"
    inside.write_bytes(b"INSIDE")
    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"endgame": {
            "private_package": inside,
            "private_package_sha256": hashlib.sha256(inside.read_bytes()).hexdigest(),
        }},
    ))
    assert error.code == "private_inside_game"

    folder = tmp_path / "private" / "菜单"
    folder.mkdir()
    unicode_private = folder / "end.upk"
    unicode_private.write_bytes(end.read_bytes())
    packages = {"endgame": {
        "private_package": unicode_private,
        "private_package_sha256": end_sha,
    }}
    receipt = json.loads(world.ready())
    receipt["private_endgame_package"] = str(unicode_private.resolve())
    receipt["private_endgame_package_sha256"] = end_sha
    receipt["source_endgame_package_sha256"] = native_launch.SOURCE_ENDGAME_SHA256
    world.stdout = LineStream([json.dumps(receipt).encode("utf-8") + b"\n", world.exit_line()])
    launch_native_offline(world.root, world.private, world.digest, SESSION, additional_packages=packages)
    plan = json.loads(bytes(world.helper.stdin.buf))
    assert plan["private_endgame_package"].endswith("菜单\\end.upk") or plan["private_endgame_package"].endswith("菜单/end.upk")
    assert "source_endgame_package_sha256" not in plan


def test_optional_private_hardlink_to_its_source_fails_before_helper_start(monkeypatch, tmp_path):
    monkeypatch.setattr(native_launch, "SOURCE_MIDGAME_SIZE", 8)
    world = World(monkeypatch, tmp_path)
    _extra_files(world.root, tmp_path, mid_size=8, end_size=9)
    source = world.root / "TAGame" / "CookedPCConsole" / "GFX_MidGameMenu_SF.upk"
    alias = tmp_path / "private" / "mid-source-link.upk"
    os.link(source, alias)
    error = _error(lambda: launch_native_offline(
        world.root, world.private, world.digest, SESSION,
        additional_packages={"midgame": {
            "private_package": alias,
            "private_package_sha256": hashlib.sha256(alias.read_bytes()).hexdigest(),
        }},
    ))
    assert error.code == "private_overlaps_source"
    assert str(error) == "Private package must be a different file from the installed game files."
    assert world.helper is None
