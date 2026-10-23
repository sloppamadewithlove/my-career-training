"""Local, nonce-bound file bridge between the in-game plugin and career service."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .storage import Store

ALLOWED_ACTIONS = frozenset({
    "navigate", "new_career", "play_match", "lineup", "replace_recruit", "rename_recruit",
    "set_format", "set_difficulty", "next_season", "abandon_fixture", "select_lesson",
    "start_lesson", "retry_lesson", "stop_session", "assistance", "settings", "setup_finish",
    "diagnostics", "loadout", "restore_explanations", "lesson_variant", "play_recording",
    "return_hub", "quit_game", "workshop_favorite", "play_workshop", "choose_provider",
    "install_provider", "import_recording", "stop_ghost", "training_settings", "ghost_control", "refresh_workshop",
})


class FileBridge:
    def __init__(self, directory, dispatch, snapshot, clock=time.time):
        self.directory = Path(directory) / "bridge"
        self.commands = self.directory / "commands"
        self.commands.mkdir(parents=True, exist_ok=True)
        self.session = str(uuid.uuid4())
        self.dispatch, self.snapshot, self.clock = dispatch, snapshot, clock
        self.ack = {}
        self.seen = set()
        self.started = clock()

    def poll(self):
        for path in sorted(self.commands.glob("*.json"))[:32]:
            command_id = ""
            try:
                if path.is_symlink() or path.stat().st_size > 65536:
                    raise ValueError("Invalid command file.")
                command = json.loads(path.read_text(encoding="utf-8"))
                command_id = command.get("id", "")
                if str(uuid.UUID(command_id)) != command_id or path.stem != command_id:
                    raise ValueError("Invalid command identity.")
                if command_id in self.seen:
                    continue
                if command.get("protocol") != 1 or command.get("session") != self.session:
                    raise ValueError("The menu connection expired. Reopen My Career.")
                if command.get("action") not in ALLOWED_ACTIONS or not isinstance(command.get("payload", {}), dict):
                    raise ValueError("Unsupported in-game command.")
                self.seen.add(command_id)
                self.dispatch(command["action"], command.get("payload", {}))
                error = self.snapshot().get("error", "")
                self.ack = {"id": command_id, "ok": not bool(error), "error": error}
            except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
                self.ack = {"id": command_id, "ok": False, "error": str(exc)}
            finally:
                path.unlink(missing_ok=True)
        if len(self.seen) > 4096:
            # Commands are consumed; retaining recent identities protects retransmission.
            self.seen = set(list(self.seen)[-2048:])
        state = dict(self.snapshot(), protocol=1, bridge_session=self.session,
                     published_at=self.clock(), offline=True, command_ack=self.ack)
        Store._atomic(self.directory / "state.json", json.dumps(state, allow_nan=False).encode())

    def plugin_status(self):
        path = self.directory / "plugin-status.json"
        try:
            if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or path.stat().st_mtime < self.started
                    or value.get("bridge_session") != self.session
                    or not isinstance(value.get("published_at"), (int, float))
                    or not -1 <= self.clock() - value["published_at"] <= 5):
                return {}
            return value
        except (OSError, ValueError):
            return {}

    def close(self):
        Store._atomic(self.directory / "state.json", json.dumps({"protocol":1,"offline":True,
            "bridge_session":"", "published_at":0,"error":"My Career is closed."}).encode())
