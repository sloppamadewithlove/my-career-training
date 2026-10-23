"""Injected callback tests for online handoff ordering and launcher boundaries."""
from __future__ import annotations

import json
import sys
import types

import pytest

from my_career_training import career, lifecycle, platforms


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _make_lifecycle(log, *, clock=None, save=None, stop_worker=None, close_game=None,
                    game_alive=None, launch=None):
    return lifecycle.Lifecycle(
        save=save or (lambda: log.append("save")),
        stop_worker=stop_worker or (lambda: log.append("stop_worker")),
        close_game=close_game or (lambda: log.append("close_game")),
        game_alive=game_alive or (lambda: False),
        launch=launch or (lambda: log.append("launch") or "Opening Rocket League."),
        clock=clock or (lambda: 100.0),
    )


def test_confirmation_copy_and_no_or_dialog_close_are_side_effect_free():
    assert lifecycle.CONFIRMATION == "Are you sure you want to close this and play online?"
    log = []
    session = _make_lifecycle(log)

    session.request_online()
    session.confirm_online(False)  # The dialog's No button or window close.

    assert log == []
    assert session.state == "Idle"
    assert session.frozen is False
    assert session.confirming is False
    assert session.message == ""


def test_yes_saves_before_shutdown_and_drains_late_result_before_closing_game():
    log = []
    clock = FakeClock()
    model = {"result": None}
    save_snapshots = []
    game_is_alive = [True]
    base = career.new_career("Late Result", seed=71)
    fixture = career.next_fixture(base)
    session_id = "late-final-session"
    model["career"] = career.start_fixture(base, session_id)

    def save():
        log.append("save")
        save_snapshots.append(model.copy())

    def final_event():
        log.append("final_event")
        model["career"] = career.complete_fixture(
            model["career"], fixture["id"], session_id, 3, 2
        )
        model["result"] = "committed"

    def stop_worker():
        log.append("stop_worker")
        # Simulates a final authoritative packet delivered while stop is draining.
        final_event()
        final_event()  # Repeated end packet for the same fixture/session.

    def close_game():
        log.append("close_game")
        assert model["result"] == "committed"
        assert save_snapshots[-1]["result"] == "committed"

    def game_alive():
        log.append("game_alive")
        return game_is_alive[0]

    def launch():
        log.append("launch")
        assert not game_is_alive[0]
        return "Opening Rocket League."

    session = _make_lifecycle(
        log, clock=clock, save=save, stop_worker=stop_worker,
        close_game=close_game, game_alive=game_alive, launch=launch,
    )
    session.request_online()
    session.confirm_online(True)

    assert log[:2] == ["save", "stop_worker"]
    assert session.state == "Stopping Career"
    assert session.frozen is True
    assert save_snapshots[0]["result"] is None

    session.worker_stopped()
    assert log == ["save", "stop_worker", "final_event", "final_event",
                   "save", "close_game", "game_alive"]
    assert session.state == "Waiting for Game Exit"
    assert session.frozen is True
    completed = model["career"]
    current = completed["seasons"][completed["current_season"]]
    assert sum(f["status"] == "completed" and "human" in (f["home"], f["away"])
               for f in current["fixtures"]) == 1
    assert len([r for r in completed["rewards"] if r["type"] == "match_experience"]) == 1

    game_is_alive[0] = False
    session.tick()
    assert log[-1] == "launch"
    assert session.state == "Online Launch Requested"
    assert session.message == "Opening Rocket League."
    assert session.frozen is False


def test_first_save_failure_keeps_career_recoverable_and_has_no_shutdown_effects():
    log = []

    def fail_save():
        log.append("save")
        raise OSError("disk full")

    session = _make_lifecycle(log, save=fail_save)
    session.request_online()
    session.confirm_online(True)

    assert log == ["save"]
    assert session.state == "Error/Recovery"
    assert session.message == "disk full"
    assert session.frozen is False


def test_drain_save_failure_prevents_game_close_and_online_launch():
    log = []
    saves = 0

    def save():
        nonlocal saves
        saves += 1
        log.append(f"save-{saves}")
        if saves == 2:
            raise OSError("late result could not be saved")

    session = _make_lifecycle(log, save=save)
    session.request_online()
    session.confirm_online(True)
    session.worker_stopped()

    assert log == ["save-1", "stop_worker", "save-2"]
    assert session.state == "Error/Recovery"
    assert session.message == "late result could not be saved"
    assert session.frozen is False


def test_game_exit_timeout_does_not_start_conflicting_online_session():
    log = []
    clock = FakeClock()
    session = _make_lifecycle(log, clock=clock, game_alive=lambda: True)
    session.request_online()
    session.confirm_online(True)
    session.worker_stopped()

    assert session.state == "Waiting for Game Exit"
    assert "launch" not in log
    clock.now = session.deadline
    session.tick()

    assert session.state == "Error/Recovery"
    assert "still open" in session.message
    assert "launch" not in log
    assert log.count("close_game") == 1


def test_launcher_failure_happens_only_after_owned_game_exit_and_is_reported():
    log = []
    alive = [True]

    def close_game():
        log.append("close_game")

    def launch():
        log.append("launch")
        raise OSError("Steam could not open Rocket League")

    session = _make_lifecycle(
        log, close_game=close_game, game_alive=lambda: alive[0], launch=launch
    )
    session.request_online()
    session.confirm_online(True)
    session.worker_stopped()
    assert "launch" not in log
    assert session.state == "Waiting for Game Exit"

    alive[0] = False
    session.tick()
    assert log[-1] == "launch"
    assert session.state == "Error/Recovery"
    assert session.message == "Steam could not open Rocket League"
    assert log.count("launch") == 1


@pytest.mark.parametrize(
    ("launcher", "expected"),
    [
        ("steam", "steam://run/252950"),
        ("epic", "com.epicgames.launcher://apps/Sugar?action=launch&silent=true"),
    ],
)
def test_platform_launch_uses_normal_entry_only_after_no_game_remains(
    monkeypatch, launcher, expected
):
    launched = []
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    monkeypatch.setattr(platforms, "game_processes", lambda: [])
    monkeypatch.setattr(platforms.os, "startfile", launched.append, raising=False)

    message = platforms.launch_online(launcher)

    assert launched == [expected]
    assert "Opening Rocket League" in message
    assert "EAC-enabled" in message
    assert "rlbot" not in launched[0].lower()


def test_platform_refuses_normal_launch_while_any_game_process_is_running(monkeypatch):
    launched = []
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    monkeypatch.setattr(platforms, "game_processes", lambda: [object()])
    monkeypatch.setattr(platforms.os, "startfile", launched.append, raising=False)

    with pytest.raises(RuntimeError, match="still running"):
        platforms.launch_online("steam")

    assert launched == []


def test_installation_detection_finds_steam_secondary_library_and_epic_manifest(
    tmp_path, monkeypatch
):
    program_files = tmp_path / "Program Files x86"
    steam_root = program_files / "Steam"
    secondary = tmp_path / "My Steam Library ñ"
    steam_apps = steam_root / "steamapps"
    steam_apps.mkdir(parents=True)
    (steam_apps / "libraryfolders.vdf").write_text(
        f'"libraryfolders" {{ "0" {{ "path" "{steam_root}" }} '
        f'"1" {{ "path" "{secondary}" }} }}',
        encoding="utf-8",
    )
    steam_manifest = secondary / "steamapps" / "appmanifest_252950.acf"
    steam_exe = secondary / "steamapps" / "common" / "rocketleague" / "Binaries" / "Win64" / "RocketLeague.exe"
    steam_manifest.parent.mkdir(parents=True)
    steam_manifest.write_text('"AppState" { "installdir" "rocketleague" }', encoding="utf-8")
    steam_exe.parent.mkdir(parents=True)
    steam_exe.touch()

    epic_root = tmp_path / "Epic Install"
    epic_exe = epic_root / "Binaries" / "Win64" / "RocketLeague.exe"
    epic_exe.parent.mkdir(parents=True)
    epic_exe.touch()
    manifests = tmp_path / "ProgramData" / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    manifests.mkdir(parents=True)
    (manifests / "rocket-league.item").write_text(json.dumps({
        "AppName": "Sugar",
        "DisplayName": "Rocket League",
        "InstallLocation": str(epic_root),
        "LaunchExecutable": "Binaries/Win64/RocketLeague.exe",
    }), encoding="utf-8")

    class RegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    fake_winreg = types.ModuleType("winreg")
    fake_winreg.HKEY_CURRENT_USER = object()
    fake_winreg.OpenKey = lambda *_: RegistryKey()

    def query_missing(*_):
        raise OSError("no registry Steam path")

    fake_winreg.QueryValueEx = query_missing
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES(X86)", str(program_files))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "ProgramData"))

    found = platforms.detect_installations()

    assert found == [
        {"launcher": "steam", "path": str(steam_exe), "available": True},
        {"launcher": "epic", "path": str(epic_exe), "available": True, "app_name": "Sugar"},
    ]


def test_owned_game_identity_ignores_preexisting_or_unmarked_processes(monkeypatch):
    class FakeProcess:
        def __init__(self, pid, created, command):
            self.pid = pid
            self.created = created
            self.command = command

        def cmdline(self):
            return self.command

        def create_time(self):
            return self.created

        def exe(self):
            return "/games/RocketLeague.exe"

    old = FakeProcess(41, 98.9, ["RocketLeague.exe", "-rlbot"])
    unrelated = FakeProcess(42, 101.0, ["RocketLeague.exe"])
    owned = FakeProcess(43, 102.0, ["RocketLeague.exe", "-rlbot"])
    monkeypatch.setattr(platforms, "game_processes", lambda: [old, unrelated, owned])

    identity = platforms.owned_game_since(100.0, "/games/RocketLeague.exe")

    assert identity == platforms.ProcessIdentity(43, 102.0, "/games/RocketLeague.exe")


def test_process_identity_does_not_follow_pid_reuse(monkeypatch):
    identity = platforms.ProcessIdentity(43, 102.0, "/games/RocketLeague.exe")

    class ReusedPid:
        def is_running(self):
            return True

        def create_time(self):
            return 150.0

    monkeypatch.setattr(platforms.psutil, "Process", lambda _pid: ReusedPid())

    assert platforms.is_alive(identity) is False
