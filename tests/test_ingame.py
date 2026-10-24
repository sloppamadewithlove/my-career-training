"""Integration risks: stale local commands, repeat delivery, recovery and same-game transitions."""
import io
import json
import sys
import uuid

import pytest

from my_career_training.ingame import FileBridge
from my_career_training.map_guard import MapGuard, custom_map_requested, digest
from my_career_training.adapter import match_config
from my_career_training.game_worker import GameSession, Worker
from my_career_training import bridge


def command(pipe, action="navigate", session=None, identity=None, payload=None):
    identity = identity or str(uuid.uuid4())
    value = {"protocol":1,"id":identity,"session":session or pipe.session,
             "action":action,"payload":payload or {"page":"hub"}}
    (pipe.commands / f"{identity}.json").write_text(json.dumps(value))
    return identity


def test_bridge_rejects_stale_session_and_online_action_without_dispatch(tmp_path):
    actions = []
    pipe = FileBridge(tmp_path, lambda a,p: actions.append(a), lambda: {"error":""})
    command(pipe, session=str(uuid.uuid4()))
    pipe.poll()
    assert not pipe.ack["ok"] and not actions
    command(pipe, action="online_request")
    pipe.poll()
    assert not pipe.ack["ok"] and not actions


def test_bridge_consumes_command_once_and_publishes_current_nonce(tmp_path):
    actions = []
    pipe = FileBridge(tmp_path, lambda a,p: actions.append((a,p)), lambda: {"error":""})
    identity = command(pipe)
    pipe.poll()
    command(pipe, identity=identity)
    pipe.poll()
    assert len(actions) == 1
    state = json.loads((pipe.directory / "state.json").read_text())
    assert state["bridge_session"] == pipe.session and state["offline"] is True
    pipe.close()
    assert json.loads((pipe.directory / "state.json").read_text())["bridge_session"] == ""


def test_bridge_reports_backend_rejection_and_rejects_large_command(tmp_path):
    pipe = FileBridge(tmp_path, lambda a,p: None, lambda: {"error":"Match is unfinished"})
    command(pipe)
    pipe.poll()
    assert pipe.ack == {"id":pipe.ack["id"],"ok":False,"error":"Match is unfinished"}
    identity = str(uuid.uuid4())
    (pipe.commands / f"{identity}.json").write_text("x" * 65537)
    pipe.poll()
    assert not pipe.ack["ok"]


def test_plugin_status_requires_current_nonce_and_fresh_timestamp(tmp_path):
    pipe = FileBridge(tmp_path, lambda a,p: None, lambda: {}, clock=lambda: 100)
    path = pipe.directory / "plugin-status.json"
    path.write_text(json.dumps({"published_at":100,"bridge_session":"previous"}))
    assert pipe.plugin_status() == {}
    path.write_text(json.dumps({"published_at":100,"bridge_session":pipe.session}))
    assert pipe.plugin_status()["bridge_session"] == pipe.session
    path.write_text(json.dumps({"published_at":90,"bridge_session":pipe.session}))
    assert pipe.plugin_status() == {}


def test_plugin_status_freshness_does_not_depend_on_filesystem_timestamp(tmp_path, monkeypatch):
    from my_career_training import ingame
    pipe = FileBridge(tmp_path, lambda *_: None, lambda: {}, clock=lambda: 100.123456)
    record = {"published_at": 100.123456, "bridge_session": pipe.session}
    # A filesystem timestamp rounded below the service creation time is not
    # evidence that a current-nonce publisher handshake belongs to an old run.
    monkeypatch.setattr(ingame, "_read_shared", lambda *_: (json.dumps(record).encode(), 100.12))
    assert pipe.plugin_status() == record
    record["bridge_session"] = "previous"
    assert pipe.plugin_status() == {}
    record.update(bridge_session=pipe.session, published_at=94)
    assert pipe.plugin_status() == {}


def game_map(tmp_path):
    root = tmp_path / "Rocket League"
    exe = root / "Binaries/Win64/RocketLeague.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    slot = root / "TAGame/CookedPCConsole/Haunted_TrainStation_P.upk"
    slot.parent.mkdir(parents=True)
    slot.write_bytes(b"original game map")
    custom = tmp_path / "practice.udk"
    custom.write_bytes(b"custom practice map")
    return exe, slot, custom


def legacy_journal(tmp_path, slot, custom_sha):
    """On-disk journal an older build wrote before it replaced the game map."""
    guard = MapGuard(tmp_path / "data")
    guard.directory.mkdir(parents=True)
    backup = guard.directory / "Haunted_TrainStation_P.original.upk"
    backup.write_bytes(b"original game map")
    guard.receipt.write_text(json.dumps({
        "original": str(slot), "backup": str(backup),
        "original_sha256": digest(backup), "custom_sha256": custom_sha,
    }))
    return guard


def test_interrupted_workshop_restores_only_exact_owned_substitution(tmp_path, monkeypatch):
    monkeypatch.setattr("my_career_training.platforms.game_processes", lambda: [])
    _exe, slot, custom = game_map(tmp_path)
    guard = legacy_journal(tmp_path, slot, digest(custom))
    slot.write_bytes(custom.read_bytes())
    MapGuard(tmp_path / "data").recover()
    assert slot.read_bytes() == b"original game map"
    assert not guard.receipt.exists()


def test_recovery_preserves_unrelated_map_modifications(tmp_path, monkeypatch):
    monkeypatch.setattr("my_career_training.platforms.game_processes", lambda: [])
    _exe, slot, custom = game_map(tmp_path)
    guard = legacy_journal(tmp_path, slot, digest(custom))
    slot.write_bytes(b"another tool changed this")
    with pytest.raises(ValueError, match="Another tool"):
        guard.recover()
    assert slot.read_bytes() == b"another tool changed this"
    assert guard.receipt.exists()


def test_legacy_recovery_does_not_write_while_rocket_league_is_running(tmp_path, monkeypatch):
    from my_career_training import platforms
    _exe, slot, custom = game_map(tmp_path)
    guard = legacy_journal(tmp_path, slot, digest(custom))
    slot.write_bytes(custom.read_bytes())
    monkeypatch.setattr(platforms, "game_processes", lambda: [object()])
    with pytest.raises(RuntimeError, match="Close Rocket League"):
        guard.recover()
    assert slot.read_bytes() == custom.read_bytes()
    assert guard.receipt.exists()


def test_prepare_does_not_start_or_consume_a_map_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr("my_career_training.platforms.game_processes", lambda: [])
    exe, slot, custom = game_map(tmp_path)
    guard = legacy_journal(tmp_path, slot, digest(custom))
    slot.write_bytes(custom.read_bytes())
    with pytest.raises(ValueError, match="Custom map launch is unavailable"):
        guard.prepare(exe, {"path": str(custom), "sha256": digest(custom)})
    assert slot.read_bytes() == custom.read_bytes()
    assert guard.receipt.exists()
    assert not (slot.parent / "Haunted_TrainStation_P_copy.upk").exists()
    guard.recover()
    assert slot.read_bytes() == b"original game map"
    assert not guard.receipt.exists()


def test_builtin_sessions_are_not_custom_map_requests():
    assert custom_map_requested({"fixture": {"map": "Stadium_P"}, "settings": {"launcher": "steam"}}) is False
    assert custom_map_requested({"lesson_id": "speed-flip", "settings": {"launcher": "epic"}}) is False
    assert custom_map_requested({"workshop": False, "fixture": {"map": "EuroStadium_P"}}) is False
    assert custom_map_requested({"workshop": {}}) is True
    assert custom_map_requested({"fixture": {"map": r"C:\maps\Practice.UDK"}}) is True


def test_adapter_rejects_custom_map_before_building_a_match(tmp_path):
    custom = tmp_path / "practice.udk"
    custom.write_bytes(b"custom practice map")
    base = {"settings": {"launcher": "steam"}, "fixture": {"format": 1, "home": "human", "map": "Stadium_P"}}
    with pytest.raises(ValueError, match="Custom map launch is unavailable"):
        match_config({**base, "workshop": {"path": str(custom), "sha256": "ab", "route": "rlbot_steam_local_map"}})
    with pytest.raises(ValueError, match="Custom map launch is unavailable"):
        match_config({**base, "fixture": {**base["fixture"], "map": str(tmp_path / "Practice.UDK")}})
    assert custom.read_bytes() == b"custom practice map"


def _workshop_start(tmp_path, exe, custom):
    return {
        "type": "start", "session_id": str(uuid.uuid4()), "data_dir": str(tmp_path / "data"),
        "settings": {"launcher": "steam", "install_path": str(exe)},
        "workshop": {"path": str(custom), "sha256": digest(custom), "route": "rlbot_steam_local_map"},
    }


def test_worker_rejects_forged_workshop_before_a_session(tmp_path, monkeypatch):
    exe, slot, custom = game_map(tmp_path)
    monkeypatch.setattr("my_career_training.game_worker.subprocess.Popen", lambda *a, **k: pytest.fail("launched"))
    monkeypatch.setattr(MapGuard, "prepare", lambda *a, **k: pytest.fail("prepare"))
    monkeypatch.setattr(MapGuard, "recover", lambda self: pytest.fail("recover"))
    output = io.StringIO()
    worker = Worker(output)
    assert worker.run(io.StringIO(json.dumps(_workshop_start(tmp_path, exe, custom)) + "\n")) == 0
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert events[0]["type"] == "ready"
    assert events[1]["type"] == "error" and "Custom map launch is unavailable" in events[1]["message"]
    assert worker.session is None
    assert slot.read_bytes() == b"original game map"
    assert sorted(path.name for path in slot.parent.iterdir()) == ["Haunted_TrainStation_P.upk"]
    assert not (tmp_path / "data").exists()


def test_worker_rejects_forged_arena_path_without_a_workshop_key(tmp_path, monkeypatch):
    exe, slot, custom = game_map(tmp_path)
    monkeypatch.setattr("my_career_training.game_worker.subprocess.Popen", lambda *a, **k: pytest.fail("launched"))
    output = io.StringIO()
    worker = Worker(output)
    command = {
        "type": "start", "session_id": str(uuid.uuid4()), "data_dir": str(tmp_path / "data"),
        "settings": {"launcher": "steam", "install_path": str(exe)},
        "fixture": {"id": "forged", "format": 1, "home": "human", "map": str(custom)},
    }
    assert worker.run(io.StringIO(json.dumps(command) + "\n")) == 0
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert any(event["type"] == "error" and "Custom map launch is unavailable" in event["message"] for event in events)
    assert worker.session is None
    assert slot.read_bytes() == b"original game map"


def test_setup_rejects_workshop_before_recovery_or_launch(tmp_path, monkeypatch):
    exe, slot, custom = game_map(tmp_path)
    monkeypatch.setattr(MapGuard, "prepare", lambda *a, **k: pytest.fail("prepare"))
    monkeypatch.setattr(MapGuard, "recover", lambda self: pytest.fail("recover"))
    monkeypatch.setattr("my_career_training.game_worker.subprocess.Popen", lambda *a, **k: pytest.fail("launched"))
    session = GameSession(_workshop_start(tmp_path, exe, custom), lambda _event: None)
    with pytest.raises(ValueError, match="Custom map launch is unavailable"):
        session.setup()
    assert session.core is None and session.map_guard is None
    assert slot.read_bytes() == b"original game map"


def test_allowed_session_restores_legacy_map_before_the_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("my_career_training.platforms.game_processes", lambda: [])
    exe, slot, custom = game_map(tmp_path)
    guard = legacy_journal(tmp_path, slot, digest(custom))
    slot.write_bytes(custom.read_bytes())
    from types import SimpleNamespace as NS
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "rlbot", NS())
    monkeypatch.setitem(sys.modules, "rlbot.interface", NS(SocketRelay=object))
    monkeypatch.setitem(sys.modules, "rlbot.managers.match", NS(MatchManager=object))
    monkeypatch.setitem(sys.modules, "rlbot.managers.rendering", NS(Renderer=object))
    monkeypatch.setattr("my_career_training.game_worker.preflight", lambda owned=None: None)
    monkeypatch.setattr(MapGuard, "prepare", lambda *a, **k: pytest.fail("prepare"))

    def core_path():
        assert slot.read_bytes() == b"original game map"
        raise RuntimeError("stop before the runtime process")

    monkeypatch.setattr("my_career_training.game_worker.core_path", core_path)
    monkeypatch.setattr("my_career_training.game_worker.subprocess.Popen", lambda *a, **k: pytest.fail("launched"))
    session = GameSession({
        "type": "start", "session_id": str(uuid.uuid4()), "data_dir": str(tmp_path / "data"),
        "fixture": {"id": "fixture-1", "format": 1, "map": "Stadium_P", "home": "human"},
        "settings": {"launcher": "steam", "install_path": str(exe)},
    }, lambda _event: None)
    with pytest.raises(RuntimeError, match="stop before the runtime"):
        session.setup()
    assert not guard.receipt.exists()
    assert slot.read_bytes() == b"original game map"


def test_return_to_hub_preserves_owned_game_and_waits_for_worker(monkeypatch):
    # Exercise actual transition method without creating a GUI or process.
    instance = object.__new__(Harness)
    instance.in_game = True
    instance.stop_reason = "return_hub"
    instance.owned_game = object()
    instance._save_current = lambda: None
    monkeypatch.setattr(bridge, "graceful_close", lambda game: pytest.fail("Game closed during hub transition"))
    bridge.Backend._close_after_stop(instance)
    assert instance.session_state == "Waiting for Worker"
    assert instance.owned_game is not None


class Harness:
    pass
