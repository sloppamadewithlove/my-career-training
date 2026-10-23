"""Launch boundaries that protect the user's normal Rocket League session."""
from __future__ import annotations

import json

import pytest

from my_career_training import bootstrap, platforms
from my_career_training.map_guard import MapGuard, digest


@pytest.mark.parametrize("launcher", ["epic", "unknown", "", None])
def test_offline_entry_refuses_unverified_or_default_launcher(launcher, tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    monkeypatch.setattr(bootstrap, "game_processes", lambda: [])

    with pytest.raises(RuntimeError, match="currently requires Steam"):
        bootstrap.preflight_offline({"launcher": launcher, "install_path": str(tmp_path)})


def test_offline_entry_refuses_to_overlap_an_existing_game(monkeypatch):
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    monkeypatch.setattr(bootstrap, "game_processes", lambda: [object()])

    with pytest.raises(RuntimeError, match="Close the existing Rocket League"):
        bootstrap.preflight_offline({"launcher": "steam", "install_path": "unverified"})


@pytest.mark.parametrize(
    ("launcher", "running_game"),
    [("epic", False), ("steam", True)],
)
def test_rejected_offline_entry_has_no_setup_or_game_launch_side_effects(
    launcher, running_game, monkeypatch
):
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    monkeypatch.setattr(bootstrap, "game_processes", lambda: [object()] if running_game else [])
    monkeypatch.setattr(
        bootstrap, "install_plugin", lambda: pytest.fail("BakkesMod changed before launch preflight passed")
    )
    monkeypatch.setattr(
        bootstrap, "ensure_injector_running", lambda: pytest.fail("BakkesMod started before launch preflight passed")
    )
    monkeypatch.setattr(
        bootstrap.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("Rocket League started after refusal")
    )

    with pytest.raises(RuntimeError):
        bootstrap.launch_offline({"launcher": launcher, "install_path": "unverified"})


def test_normal_steam_entry_uses_the_regular_game_launch_uri(monkeypatch):
    calls = []
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    monkeypatch.setattr(platforms, "game_processes", lambda: [])
    monkeypatch.setattr(platforms.os, "startfile", calls.append, raising=False)

    message = platforms.launch_online("steam")

    assert calls == ["steam://run/252950"]
    assert "normal EAC-enabled mode" in message


@pytest.mark.parametrize(
    ("arguments", "allowed"),
    [
        (["RocketLeague.exe", "-noeac", "-rlbot"], True),
        (["RocketLeague.exe", "-NOEAC", "-RLBOT"], True),
        (["RocketLeague.exe"], False),
        (["RocketLeague.exe", "-noeac"], False),
        (["RocketLeague.exe", "-rlbot"], False),
        (["RocketLeague.exe", "-noeac", "-rlbot", "-eac"], False),
        (["RocketLeague.exe", "-noeac-extra", "-rlbot-helper"], False),
    ],
)
def test_offline_mode_uses_exact_expected_launch_flags(arguments, allowed):
    assert platforms.offline_launch_arguments(arguments) is allowed


@pytest.mark.parametrize(
    ("created", "executable", "arguments"),
    [
        (123.0, r"C:\Games\RocketLeague.exe", ["RocketLeague.exe"]),
        (123.0, r"C:\Games\RocketLeague.exe", ["RocketLeague.exe", "-rlbot"]),
        (123.0, r"C:\Games\RocketLeague.exe", ["RocketLeague.exe", "-noeac"]),
        (123.0, r"C:\Other\RocketLeague.exe", ["RocketLeague.exe", "-rlbot", "-noeac"]),
        (124.0, r"C:\Games\RocketLeague.exe", ["RocketLeague.exe", "-rlbot", "-noeac"]),
        (123.0, r"C:\Games\RocketLeague.exe", ["RocketLeague.exe", "-rlbot", "-noeac", "-eac"]),
    ],
)
def test_offline_identity_rejects_default_online_wrong_or_reused_process(
    created, executable, arguments, monkeypatch
):
    expected = r"C:\Games\RocketLeague.exe"

    class FakeProcess:
        def create_time(self):
            return created

        def exe(self):
            return executable

        def cmdline(self):
            return arguments

    import psutil

    monkeypatch.setattr(psutil, "Process", lambda _pid: FakeProcess())
    identity = platforms.ProcessIdentity(pid=73, created=123.0, executable=expected)

    assert bootstrap.verify_owned_offline(identity) is False


def test_offline_identity_accepts_only_the_exact_offline_child(monkeypatch):
    expected = r"C:\Games\RocketLeague.exe"

    class FakeProcess:
        def create_time(self):
            return 123.0

        def exe(self):
            return expected

        def cmdline(self):
            return ["RocketLeague.exe", "-noeac", "-rlbot"]

    import psutil

    monkeypatch.setattr(psutil, "Process", lambda _pid: FakeProcess())
    identity = platforms.ProcessIdentity(pid=73, created=123.0, executable=expected)

    assert bootstrap.verify_owned_offline(identity) is True


def _legacy_map_recovery(tmp_path):
    install = tmp_path / "Steam" / "steamapps/common/Rocket League"
    original = install / "TAGame/CookedPCConsole/Haunted_TrainStation_P.upk"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"legacy custom map occupying the old slot")
    data_dir = tmp_path / "career-data"
    guard = MapGuard(data_dir)
    guard.directory.mkdir(parents=True)
    backup = guard.directory / "Haunted_TrainStation_P.original.upk"
    backup.write_bytes(b"original Steam map")
    receipt = {
        "original": str(original),
        "backup": str(backup),
        "original_sha256": digest(backup),
        "custom_sha256": digest(original),
    }
    guard.receipt.write_text(json.dumps(receipt), encoding="utf-8")
    return guard, original, backup


def test_legacy_map_recovery_refuses_to_write_while_rocket_league_is_running(
    tmp_path, monkeypatch
):
    guard, game_map, backup = _legacy_map_recovery(tmp_path)
    replaced_bytes = game_map.read_bytes()
    backup_bytes = backup.read_bytes()
    monkeypatch.setattr(platforms, "game_processes", lambda: [object()])

    with pytest.raises(RuntimeError):
        guard.recover()

    assert game_map.read_bytes() == replaced_bytes
    assert backup.read_bytes() == backup_bytes
    assert guard.receipt.exists()


