"""Desktop orchestration; all game work lives in the isolated worker."""
from __future__ import annotations

import copy
import json
import platform
import sys
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from . import __version__, career as domain
from .adapter import CORE_VERSION, SDK_VERSION
from .content import community_catalog, garage_catalog, import_map, validate_loadout
from .lifecycle import Lifecycle
from .platforms import ProcessIdentity, detect_installations, game_processes, graceful_close, is_alive, launch_online
from .storage import Store, default_state
from .training import (assistance_preferences, catalog, configure_lesson, import_recording,
                       personal_best, validate_recording)


def validate_document(state):
    if state.get("career"):
        domain.validate_career(state["career"])
    for lesson_id, preferences in state["lesson_preferences"].items():
        configure_lesson(lesson_id)
        assistance_preferences(preferences)


class Backend(QObject):
    stateChanged = Signal()

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.store = Store(directory, validate_document)
        self.error = ""
        try:
            self.document = self.store.load()
        except ValueError as exc:
            self.document = default_state()
            self.error = str(exc)
        self.page = "hub" if self.document["career"] else "home"
        self.notice = "Testing preview: Steam/Epic gameplay and expert demonstrations still need validation."
        self.selected_id = "speed-flip"
        self.latest_attempt = None
        self.latest_result = None
        self.owned_game = None
        self.process = None
        self.buffer = b""
        self.request = None
        self.session_id = None
        self.session_state = "Idle"
        self.session_message = ""
        self.stop_reason = None
        self.pending_launch = None
        self.close_deadline = None
        self.start_deadline = None
        self.stopping_worker = False
        self.diagnostics_info = {}
        self.installations = detect_installations()
        self.setup_required = not self.document["settings"].get("setup_complete", False)
        if self.setup_required and sys.platform == "win32":
            self.page = "settings"
            self.notice = "Choose your launcher once, then select Use selected launcher."
            if len(self.installations) == 1:
                found = self.installations[0]
                self.document["settings"].update(launcher=found["launcher"], install_path=found["path"])
            elif len(self.installations) > 1:
                self.notice = "Both launchers were found. Choose Steam or Epic below; Steam is selected initially."
        self.lifecycle = Lifecycle(self._save_current, self._stop_for_online,
            lambda: graceful_close(self.owned_game), lambda: is_alive(self.owned_game) or bool(game_processes()),
            lambda: launch_online(self.document["settings"]["launcher"]))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)
        self._recover_outbox()

    @Property("QVariantMap", notify=stateChanged)
    def state(self):
        career = self.document["career"]
        variants = self.document.get("lesson_variants", {}).get(self.selected_id, {})
        selected = configure_lesson(self.selected_id, **variants)
        transition = self.lifecycle.frozen or self.lifecycle.state in ("Error/Recovery", "Online Launch Requested")
        state = self.lifecycle.state if transition else self.session_state
        message = self.lifecycle.message if transition else self.session_message
        return {"page": self.page, "career": career, "standings": domain.standings(career) if career else [],
            "next_fixture": domain.next_fixture(career) if career else None, "lessons": catalog(),
            "selected_lesson": selected, "settings": self.document["settings"],
            "lesson_preferences": self.document["lesson_preferences"], "setup_required": self.setup_required,
            "session": {"state": state, "message": message, "busy": self.lifecycle.frozen or
                self.session_state in ("Starting Career", "Stopping Career", "Waiting for Game Exit"),
                "can_retry": bool(self.lifecycle.last_error), "confirm_online": self.lifecycle.confirming},
            "error": self.error, "notice": self.notice, "diagnostics": self.diagnostics_info,
            "content": community_catalog(), "garage": garage_catalog(),
            "latest_attempt": self.latest_attempt, "latest_result": self.latest_result}

    def _save_current(self):
        self.store.save(self.document)

    def _commit(self, document):
        self.store.save(document)
        self.document = document

    def _career_change(self, function, *args):
        if not self.document["career"]:
            raise ValueError("Create a career first.")
        state = copy.deepcopy(self.document)
        state["career"] = function(state["career"], *args)
        self._commit(state)

    def _send(self, kind, **fields):
        if not self.process or self.process.state() == QProcess.NotRunning:
            raise ValueError("There is no active game connection. Start a match or lesson first.")
        message = {"id": str(uuid.uuid4()), "type": kind, **fields}
        self.process.write((json.dumps(message, allow_nan=False) + "\n").encode())

    def _require_editable(self):
        if self.lifecycle.frozen or self.stop_reason or self.session_state == "Starting Career":
            raise ValueError("Wait for the current game transition to finish.")

    @Slot(str, "QVariantMap")
    def dispatch(self, action, payload):
        try:
            self.error = ""
            if action == "navigate":
                self.page = payload["page"]
            elif action == "online_request":
                self.lifecycle.request_online()
            elif action == "online_confirm":
                self.lifecycle.confirm_online(payload.get("yes") is True)
            elif action == "online_retry":
                if not self.lifecycle.last_error:
                    raise ValueError("There is no online transition to retry.")
                self.lifecycle.request_online()
                self.lifecycle.last_error = ""
                self.lifecycle.confirm_online(True)
            elif action == "diagnostics":
                self.diagnostics_info = {"app": __version__, "operating_system": platform.platform(),
                    "python": platform.python_version(), "rlbot_interface": SDK_VERSION, "core": CORE_VERSION,
                    "steam_game_test": "Not yet tested", "epic_game_test": "Not yet tested",
                    "installed_game_version": "Read by worker during a supported session",
                    "bot_provider": "Original baseline specialists 0.1.0; experimental, unranked",
                    "game_processes": len(game_processes()), "worker_running": bool(self.process and
                        self.process.state() != QProcess.NotRunning), "save_status": "Loaded and validated",
                    "teaching_references": "No validated expert demonstrations bundled"}
                path = self.store.directory / "diagnostics.json"
                Store._atomic(path, json.dumps(self.diagnostics_info, indent=2).encode())
                self.notice = "Diagnostics saved beside your career. No platform credentials are included."
            elif action == "open_data":
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.directory)))
            elif action == "open_link":
                allowed = {x.get("source_url", x.get("url")) for x in community_catalog()}
                if payload["url"] not in allowed or not payload["url"].startswith("https://"):
                    raise ValueError("Only catalog source links can be opened here.")
                QDesktopServices.openUrl(QUrl(payload["url"]))
            else:
                self._require_editable()
                self._action(action, payload)
        except Exception as exc:
            self.error = str(exc)
        self.stateChanged.emit()

    def _action(self, action, p):
        if action == "new_career":
            if self._worker_active() or (self.document["career"] and self.document["career"]["pending_session"]):
                raise ValueError("Finish or abandon the current session first.")
            if self.document["career"]:
                self.store.export_file(self.store.directory / f"career-{self.document['career']['id']}.json")
            state = copy.deepcopy(self.document)
            state["career"] = domain.new_career(p["team_name"], int(p.get("format", 3)), recruits=p.get("recruits"))
            self._commit(state)
            self.page = "hub"
        elif action == "lineup":
            self._career_change(domain.set_lineup, list(p["ids"]))
        elif action == "replace_recruit":
            self._career_change(domain.replace_recruit, p["outgoing"], p["incoming"])
        elif action == "rename_recruit":
            self._career_change(domain.rename_recruit, p["id"], p["name"])
        elif action == "set_format":
            self._career_change(domain.set_format, int(p["format"]))
        elif action == "set_difficulty":
            self._career_change(domain.set_difficulty, float(p["baseline"]), p["curve"].lower())
        elif action == "next_season":
            self._career_change(domain.start_next_season)
        elif action == "loadout":
            loadout = validate_loadout({k: p[k] for k in ("car_id", "primary_color", "secondary_color")})
            self._career_change(domain.set_loadout, p["id"], loadout)
            self.notice = "Bot preset saved. Your human car keeps its normal garage appearance."
        elif action == "settings":
            if self._worker_active():
                raise ValueError("Stop the current game session before changing its setup.")
            key, value = p["key"], p["value"]
            if key not in ("launcher", "install_path", "text_scale", "reduced_motion", "binding_profile"):
                raise ValueError("Unknown setting.")
            state = copy.deepcopy(self.document)
            state["settings"][key] = value
            self._commit(state)
        elif action == "setup_finish":
            state = copy.deepcopy(self.document)
            state["settings"]["setup_complete"] = True
            self._commit(state)
            self.setup_required = False
            self.notice = "Setup saved. Choose a career fixture or lesson when you are ready."
        elif action in ("export_save", "import_save"):
            if action == "import_save" and (self._worker_active() or is_alive(self.owned_game)):
                raise ValueError("Stop the game session before importing another save.")
            if action == "export_save":
                path, _ = QFileDialog.getSaveFileName(None, "Export career", "MyCareerTraining-backup.json", "Career files (*.json)")
                if path:
                    self.store.export_file(path)
                    self.notice = "Career exported, including lesson settings and attempt history."
            else:
                path, _ = QFileDialog.getOpenFileName(None, "Import career or last-good backup", str(self.store.directory), "Career files (*.json)")
                if path:
                    self.document = self.store.import_file(path)
                    self.page = "hub" if self.document["career"] else "home"
                    self.notice = "Validated save restored. The previous file was preserved."
        elif action == "select_lesson":
            configure_lesson(p["id"])
            self.selected_id = p["id"]
        elif action in ("assistance", "restore_explanations"):
            lesson_id = p["id"]
            configure_lesson(lesson_id)
            values = assistance_preferences(self.document["lesson_preferences"].get(lesson_id))
            key, value = ("explanations", True) if action == "restore_explanations" else (p["key"], p["value"])
            values[key] = value
            values = assistance_preferences(values)
            state = copy.deepcopy(self.document)
            state["lesson_preferences"][lesson_id] = values
            self._commit(state)
            if self._worker_active() and self.request.get("lesson_id") == lesson_id:
                self._send("preferences", preferences=values)
        elif action == "lesson_variant":
            if self._worker_active():
                raise ValueError("Stop the lesson before changing its starting setup.")
            state = copy.deepcopy(self.document)
            variants = state.setdefault("lesson_variants", {}).setdefault(p["id"], {})
            variants[p["key"]] = p["value"]
            configure_lesson(p["id"], **variants)
            self._commit(state)
        elif action in ("play_match", "start_lesson", "calibration"):
            self._prepare_launch(action, p)
        elif action == "retry_lesson":
            self._send("retry")
        elif action == "stop_session":
            self._begin_stop("stop")
        elif action == "abandon_fixture":
            if self._worker_active():
                self._begin_stop("abandon")
            else:
                self._career_change(domain.abandon_fixture)
        elif action == "recover_result":
            if self._worker_active() or game_processes():
                raise ValueError("Close the game before entering a manual recovery result.")
            career = self.document["career"]
            if not career or not career["pending_session"]:
                raise ValueError("There is no missing result to repair.")
            if len(str(p.get("note", "")).strip()) < 5:
                raise ValueError("Add a short note describing the result you observed.")
            pending = career["pending_session"]
            self._commit_result({**pending, "home_score": int(p["home_score"]),
                "away_score": int(p["away_score"]), "provenance": "manual_recovery"}, note=p["note"])
        elif action == "import_map":
            path, _ = QFileDialog.getOpenFileName(None, "Import a creator's local map", "", "Unreal maps (*.upk *.udk)")
            if path:
                result = import_map(path, self.store.directory, self.document["settings"]["launcher"])
                state = copy.deepcopy(self.document)
                state.setdefault("maps", []).append(result)
                self._commit(state)
                self.notice = "Map copied and identified. Custom-map loading awaits game validation; core lessons remain available."
        elif action == "import_recording":
            path, _ = QFileDialog.getOpenFileName(None, "Import a permitted actual recording", "", "Recording (*.json)")
            if path:
                recording = import_recording(path)
                if isinstance(recording, tuple):
                    recording = recording[0]
                self._store_recording(recording)
                self.notice = "Recording imported with its provenance. Imported success claims are not independently certified."
        elif action == "play_recording":
            if not self._worker_active() or not self.request.get("lesson_id"):
                raise ValueError("Start this lesson before playing its recorded ghost.")
            recordings = self._recordings(p["id"])
            best = personal_best(recordings)
            if best is None:
                # Imported references retain their labels and uncertainty.
                best = next((r for r in reversed(recordings) if r.get("outcome") == "success"), None)
            if best is None:
                raise ValueError("No successful recording exists for this lesson yet. Complete an attempt or import a permitted recording.")
            if best.get("variant") != configure_lesson(p["id"], **self.request.get("variants", {})).get("variant"):
                raise ValueError("This recording uses a different lesson setup. Choose the matching variation.")
            self._send("play_recording", recording=best)
            self.notice = best.get("label", "Imported recording; success claim not independently verified")
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _worker_active(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def _prepare_launch(self, action, payload):
        if sys.platform != "win32":
            raise ValueError("Game sessions require the Windows package on your gaming PC. Career management works here.")
        if self.setup_required:
            self.page = "settings"
            raise ValueError("Choose your launcher in Settings and select Use selected launcher first.")
        if game_processes() and not is_alive(self.owned_game):
            raise ValueError("Rocket League is already running outside this app. Close it before starting a career session.")
        career = self.document["career"]
        if career and career["pending_session"]:
            raise ValueError("An unfinished fixture is saved. Abandon that attempt to restart from kickoff, or recover a missing final result.")
        request = {"session_id": str(uuid.uuid4()), "settings": copy.deepcopy(self.document["settings"]),
                   "data_dir": str(self.store.directory)}
        if action == "play_match":
            if not career:
                raise ValueError("Create a career first.")
            self._career_change(domain.start_fixture, request["session_id"])
            request["fixture"] = domain.next_fixture(self.document["career"])
        elif action == "calibration":
            temp = domain.new_career("Calibration", career["format"] if career else 3)
            request["fixture"] = domain.next_fixture(temp)
            request["calibration"] = True
        else:
            lesson_id = payload["id"]
            configure_lesson(lesson_id)
            request.update(lesson_id=lesson_id, preferences=assistance_preferences(
                self.document["lesson_preferences"].get(lesson_id)),
                variants=self.document.get("lesson_variants", {}).get(lesson_id, {}))
        self._save_current()
        if self._worker_active() or is_alive(self.owned_game):
            self.pending_launch = request
            self._begin_stop("restart")
        else:
            self._launch(request)

    def _launch(self, request):
        self.lifecycle.state = "Idle"
        self.lifecycle.last_error = ""
        self.request = request
        self.session_id = request["session_id"]
        self.session_state = "Starting Career"
        self.session_message = "Opening the supported offline game session…"
        self.start_deadline = time.monotonic() + 100
        self.buffer = b""
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.store.directory))
        self.process.readyReadStandardOutput.connect(self._read_worker)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._process_finished)
        if getattr(sys, "frozen", False):
            program, arguments = str(Path(sys.executable).with_name("MyCareerTrainingWorker.exe")), []
        else:
            program, arguments = sys.executable, ["-m", "my_career_training", "--worker"]
        self.process.start(program, arguments)

    def _process_error(self, _):
        self.error = "The game worker could not start. Open Diagnostics and check the installed package."
        self.session_state = "Error/Recovery"
        self.stateChanged.emit()

    def _process_finished(self, exit_code, _):
        self._read_worker()
        if not self.stopping_worker and self.session_state not in ("Idle", "Career Ready"):
            self.error = "The game connection closed. Completed results are safe; an unfinished fixture can restart."
            self.session_state = "Error/Recovery"
        self.stopping_worker = False
        self._recover_outbox()
        self.stateChanged.emit()

    def _read_worker(self):
        if not self.process:
            return
        self.buffer += bytes(self.process.readAllStandardOutput())
        if len(self.buffer) > 32 * 1024 * 1024:
            self.error = "The worker message exceeded the supported recording limit. Stop the session."
            return
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                self._event(json.loads(line))
            except Exception as exc:
                self.error = str(exc)
        self.stateChanged.emit()

    def _event(self, event):
        kind = event.get("type")
        if kind == "ready":
            self._send("start", **self.request)
            return
        if event.get("session_id") not in (None, self.session_id):
            return
        if kind == "owned_game":
            self.owned_game = ProcessIdentity(**event["identity"])
        elif kind == "session":
            worker_state = event.get("state")
            self.session_state = {"starting": "Starting Career", "running": "Playing", "training": "training",
                "completed": "Career Ready", "error": "Error/Recovery"}.get(worker_state, worker_state)
            self.session_message = event.get("message", "")
            if self.session_state != "Starting Career":
                self.start_deadline = None
        elif kind == "telemetry":
            self.start_deadline = None
            if self.session_state != "Career Ready" and (not self.latest_result or self.latest_result.get("session_id") != self.session_id):
                self.session_state = "training" if self.request.get("lesson_id") else "Playing"
        elif kind == "result":
            if self.request.get("calibration"):
                self.latest_result = dict(event, label="Calibration exhibition · no league points")
                self.notice = "Calibration complete. Adjust the visible difficulty setting before a league fixture."
                self._ack_outbox(event["session_id"])
            else:
                self._commit_result(event)
            self.session_state = "Career Ready"
            self.session_message = "Match complete. Your result is saved. Continue when you are ready."
        elif kind == "attempt":
            self.latest_attempt = event["summary"]
            recording = event.get("recording")
            self._store_recording(recording, summary=event["summary"])
            self._send("attempt_ack", attempt_id=event["summary"]["id"])
        elif kind == "error":
            self.error = event.get("message", "Game connection error.")
            self.session_state = "Error/Recovery"
            self.start_deadline = None
        elif kind == "stopped":
            if self.lifecycle.state == "Stopping Career":
                self.lifecycle.worker_stopped()
            elif self.stop_reason:
                self._close_after_stop()

    def _commit_result(self, event, note=None):
        state = copy.deepcopy(self.document)
        state["career"] = domain.complete_fixture(state["career"], event["fixture_id"], event["session_id"],
            event["home_score"], event["away_score"], event.get("provenance", "game"))
        if note:
            state.setdefault("recovery_notes", []).append({"fixture_id": event["fixture_id"], "note": str(note)[:1000]})
        self._commit(state)
        self.latest_result = dict(event)
        self._ack_outbox(event["session_id"])

    def _ack_outbox(self, session_id):
        try:
            canonical = str(uuid.UUID(session_id))
        except ValueError:
            return
        (self.store.directory / "outbox" / f"{canonical}.json").unlink(missing_ok=True)

    def _recover_outbox(self):
        for path in (self.store.directory / "outbox").glob("*.json"):
            try:
                if path.stat().st_size > 65536:
                    continue
                event = json.loads(path.read_text())
                if event.get("calibration"):
                    continue
                self._commit_result(event)
                self.notice = "Recovered a completed match from the game worker's durable result receipt."
            except Exception as exc:
                self.error = "A saved result receipt needs recovery: " + str(exc)

    def _store_recording(self, recording, summary=None):
        state = copy.deepcopy(self.document)
        if recording and recording.get("samples"):
            validate_recording(recording)
            record_id = str(uuid.uuid4())
            path = self.store.directory / "recordings" / f"{record_id}.json"
            Store._atomic(path, json.dumps(recording, allow_nan=False).encode())
            state["recordings"].append({"id": record_id, "lesson_id": recording["lesson_id"],
                "filename": path.name, "label": recording.get("label", "Your attempt")})
            state["recordings"] = state["recordings"][-100:]
        if summary:
            ids = {x.get("id") for x in state["attempts"]}
            if summary.get("id") not in ids:
                state["attempts"].append(summary)
                state["attempts"] = state["attempts"][-1000:]
        self._commit(state)

    def _recordings(self, lesson_id):
        values = []
        for entry in self.document["recordings"][-30:]:
            if entry["lesson_id"] != lesson_id:
                continue
            filename = entry.get("filename", "")
            if Path(filename).name != filename:
                continue
            path = self.store.directory / "recordings" / filename
            if path.is_file():
                values.append(import_recording(path))
        return values

    def _stop_for_online(self):
        self.stop_reason = "online"
        self.stopping_worker = True
        if self._worker_active():
            self._send("shutdown")
        else:
            QTimer.singleShot(0, self.lifecycle.worker_stopped)

    def _begin_stop(self, reason):
        self._save_current()
        self.stop_reason = reason
        self.stopping_worker = True
        self.session_state = "Stopping Career"
        self.session_message = "Stopping bot control and saving completed progress…"
        self.close_deadline = time.monotonic() + 35
        if self._worker_active():
            self._send("shutdown")
        else:
            self._close_after_stop()

    def _close_after_stop(self):
        self._save_current()
        graceful_close(self.owned_game)
        self.session_state = "Waiting for Game Exit"
        self.close_deadline = time.monotonic() + 30

    def _tick(self):
        before = (self.lifecycle.state, self.lifecycle.message)
        self.lifecycle.tick()
        if self.stop_reason == "online" and self.lifecycle.state in ("Online Launch Requested", "Error/Recovery"):
            self.stop_reason = None
        if before != (self.lifecycle.state, self.lifecycle.message):
            self.stateChanged.emit()
        if self.start_deadline and time.monotonic() > self.start_deadline:
            self.start_deadline = None
            self.error = "No live game telemetry arrived. Close the game and retry; your fixture remains unfinished."
            self.session_state = "Error/Recovery"
            self.stateChanged.emit()
        if self.stop_reason and self.stop_reason != "online":
            if self.session_state == "Waiting for Game Exit" and not is_alive(self.owned_game) and not self._worker_active():
                reason, self.stop_reason = self.stop_reason, None
                self.owned_game = None
                self.session_state = "Idle"
                self.session_message = "Game session closed. Progress is saved."
                if reason == "abandon":
                    self._career_change(domain.abandon_fixture)
                if self.pending_launch:
                    request, self.pending_launch = self.pending_launch, None
                    self._launch(request)
                self.stateChanged.emit()
            elif self.close_deadline and time.monotonic() > self.close_deadline:
                self.close_deadline = None
                self.stop_reason = None
                self.session_state = "Error/Recovery"
                self.error = "The session is still closing. Close the game window, then retry. No second game was launched."
                self.pending_launch = None
                self.stateChanged.emit()

    def close(self):
        self._save_current()
        if self._worker_active():
            self._send("shutdown")
            self.process.waitForFinished(30000)
            self._read_worker()
        self.store.close()
