"""Private cross-language fixture runner for an actual Backend/FileBridge state."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path,
                        help="Exact checkout's src directory")
    parser.add_argument("--gate", required=True, type=Path,
                        help="Built mct_native_return_gate_tests executable")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    gate = args.gate.resolve(strict=True)
    if not source.is_dir() or not gate.is_file():
        raise SystemExit("source directory or native gate executable is missing")
    sys.path.insert(0, str(source))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import QApplication
    from my_career_training import bridge, career
    from my_career_training.ingame import FileBridge

    app = QApplication.instance() or QApplication(["native-return-backend-test"])
    assert app is not None
    with tempfile.TemporaryDirectory(prefix="mct-native-return-") as temporary:
        data = Path(temporary) / "data"
        data.mkdir()
        backend = None
        pipe = None
        try:
            with patch.object(bridge, "detect_installations", lambda: []), \
                 patch.object(bridge, "game_processes", lambda: []), \
                 patch.object(bridge, "native_launcher_pending", lambda: False):
                backend = bridge.Backend(data)
                backend.timer.stop()
                backend.setup_required = False
                backend.in_game = True
                backend.dispatch("new_career", {"team_name": "Native Return Test", "format": 1})

                pending_career = json.loads(json.dumps(backend.document))
                career_session = str(uuid.uuid4())
                pending_career["career"] = career.start_fixture(
                    pending_career["career"], career_session
                )
                backend._commit(pending_career)
                career_bytes = backend.store.path.read_bytes()

                activity = str(uuid.uuid4())
                payload = {"expected_session_id": activity,
                           "expected_fixture_id": "", "abandon": False}
                backend.request = {"session_id": activity, "lesson_id": "power-shots"}
                backend.session_id = activity
                backend.session_state = "training"
                pipe = FileBridge(data, backend.dispatch, lambda: backend.state,
                                  clock=lambda: 123.0)
                command_id = str(uuid.uuid4())
                command = {"protocol": 1, "id": command_id, "session": pipe.session,
                           "action": "return_hub", "payload": payload}
                command_path = pipe.commands / f"{command_id}.json"
                command_path.write_text(json.dumps(command), encoding="utf-8")
                pipe.poll()

                state = json.loads((pipe.directory / "state.json").read_text(encoding="utf-8"))
                pending = state["career"]["pending_session"]
                assert state["protocol"] == 1 and state["offline"] is True
                assert state["command_ack"]["ok"] is True
                assert state["native_return_ready"] == {
                    "session_id": activity, "fixture_id": ""
                }
                assert state["session"]["id"] is None
                assert state["session"]["state"] == "Idle"
                assert state["session"]["kind"] == "hub"
                assert pending["session_id"] == career_session
                assert pending["session_id"] != activity and pending["fixture_id"]
                assert backend.store.path.read_bytes() == career_bytes

                fixture_path = Path(temporary) / "backend-state-fixture.json"
                fixture_path.write_text(json.dumps({
                    "action": "return_hub", "payload": payload, "state": state,
                }, allow_nan=False), encoding="utf-8")
                subprocess.run([str(gate), str(fixture_path)], check=True, timeout=10)
        finally:
            if pipe is not None:
                pipe.close()
            if backend is not None:
                backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
