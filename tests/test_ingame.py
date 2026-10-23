"""Integration risks: stale local commands, repeat delivery, recovery and same-game transitions."""
import json
import uuid

import pytest

from my_career_training.ingame import FileBridge
from my_career_training.map_guard import MapGuard, digest
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


def test_interrupted_workshop_restores_only_exact_owned_substitution(tmp_path):
    exe, slot, custom = game_map(tmp_path)
    guard = MapGuard(tmp_path / "data")
    guard.prepare(exe, {"path":str(custom),"sha256":digest(custom)})
    slot.write_bytes(custom.read_bytes())
    MapGuard(tmp_path / "data").recover()
    assert slot.read_bytes() == b"original game map"
    assert not guard.receipt.exists()


def test_recovery_preserves_unrelated_map_modifications(tmp_path):
    exe, slot, custom = game_map(tmp_path)
    guard = MapGuard(tmp_path / "data")
    guard.prepare(exe, {"path":str(custom),"sha256":digest(custom)})
    slot.write_bytes(b"another tool changed this")
    with pytest.raises(ValueError, match="Another tool"):
        guard.recover()
    assert slot.read_bytes() == b"another tool changed this"
    assert guard.receipt.exists()


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
