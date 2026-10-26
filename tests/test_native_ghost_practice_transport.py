"""Service-side native bridge contracts for ghost toggle and recording choice."""
from __future__ import annotations

import json
import uuid

from my_career_training.ingame import ALLOWED_ACTIONS, FileBridge


def _publish(pipe, action, payload):
    command_id = str(uuid.uuid4())
    command = {"protocol": 1, "id": command_id, "session": pipe.session,
               "action": action, "payload": payload}
    (pipe.commands / f"{command_id}.json").write_text(json.dumps(command), encoding="utf-8")
    pipe.poll()
    state = json.loads((pipe.directory / "state.json").read_text(encoding="utf-8"))
    return command_id, state


def test_native_training_actions_are_allowlisted_and_acknowledged(tmp_path):
    sent = []
    pipe = FileBridge(tmp_path, lambda action, payload: sent.append((action, payload)),
                      lambda: {"error": ""})
    commands = [
        ("play_recording", {"id": "speed-flip", "recording_id": "recording-a"}),
        ("ghost_control", {"operation": "toggle", "enabled": True}),
        ("ghost_control", {"operation": "toggle", "enabled": False}),
    ]

    for action, payload in commands:
        assert action in ALLOWED_ACTIONS
        command_id, state = _publish(pipe, action, payload)
        assert sent[-1] == (action, payload)
        assert state["command_ack"] == {"id": command_id, "ok": True, "error": ""}


def test_native_training_transport_preserves_backend_rejection(tmp_path):
    pipe = FileBridge(tmp_path, lambda *_args: None,
                      lambda: {"error": "Choose an available recording before turning on ghost practice."})

    command_id, state = _publish(pipe, "ghost_control", {"operation": "toggle", "enabled": True})

    assert state["command_ack"] == {
        "id": command_id,
        "ok": False,
        "error": "Choose an available recording before turning on ghost practice.",
    }
