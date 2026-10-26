"""Desktop orchestration; all game work lives in the isolated worker."""
from __future__ import annotations

import copy
import json
import platform
import queue
import sys
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from . import __version__, career as domain
from .adapter import CORE_VERSION, SDK_VERSION
from .content import community_catalog, garage_catalog, import_map, validate_loadout
from . import community_discovery, community_plugins
from .lifecycle import Lifecycle
from .platforms import (ProcessIdentity, detect_installations, game_processes, graceful_close,
                        is_alive, launch_online, native_launcher_pending)
from .plugin_session import PluginSession, PluginSessionError
from .storage import Store, default_state
from .training import (assistance_preferences, catalog, configure_lesson, import_recording,
                       validate_recording)


_MAX_CATALOG_WORKERS = 2


def validate_document(state):
    if state.get("career"):
        domain.validate_career(state["career"])
    for lesson_id, preferences in state["lesson_preferences"].items():
        configure_lesson(lesson_id)
        assistance_preferences(preferences)


class Backend(QObject):
    stateChanged = Signal()
    exitRequested = Signal()

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.in_game = False
        self.telemetry = {}
        self._ghost_practice_enabled = False
        # True only while a legacy (no explicit recording_id) play command owns
        # the coach rendering. The new practice flow never falls back to it.
        self._legacy_playback = False
        # Bounded map of command id -> ghost command fields awaiting the worker's
        # exact acknowledgement. Nothing here is a general protocol queue.
        self._ghost_pending = {}
        self._ghost_seq = 0
        self._ghost_deadline = None
        self.plugin_status = {}
        self.native_community = None
        self.career_draft = {"team_name": "My Career Club"}
        self.workshop_state = {}
        self.community_state = {"catalog": community_plugins.curated_catalog(), "downloaded": [],
            "selected": None, "busy": False, "message": "Choose a plugin to check its current release.",
            "can_activate": False}
        self._community_results = queue.SimpleQueue()
        self._community_cancel = threading.Event()
        # Public catalog browsing is separate from the plugin download state.
        # Nothing here performs network access until an explicit browse action.
        self.catalog_state = {
            "source": "steam_maps", "page": 1, "query": "", "busy": False, "loading": False,
            "status": "idle", "message": "Choose a catalog source, then browse one public page.",
            "items": [], "has_next": False, "source_url": "", "page_item_count": 0,
            "query_scope": "none", "remote_query": False, "truncated": False,
            "fetched": False, "generation": 0, "catalog_only": True,
            "sources": list(community_discovery.SOURCES),
            "can_download": False, "can_activate": False,
        }
        self._catalog_results = queue.SimpleQueue()
        self._catalog_cancel = threading.Event()
        self._catalog_generation = 0
        self._catalog_outstanding = 0
        self.store = Store(directory, validate_document)
        self.error = ""
        try:
            self.document = self.store.load()
        except ValueError as exc:
            self.document = default_state()
            self.error = str(exc)
        self.page = "hub" if self.document["career"] else "home"
        self.notice = ""
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
        self.native_return_ready = None
        self.native_forfeit_rejected = None
        self.native_next_ready = None
        self.native_next_rejected = None
        self._prepared_next = None
        self._last_next = None
        self._forfeit_score_observation = None
        self._native_return_request = None
        self.close_deadline = None
        self.start_deadline = None
        self.startup_cancelled_session = None
        self.startup_stop_acknowledged = False
        self.worker_ready = False
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
            lambda: graceful_close(self.owned_game),
            lambda: is_alive(self.owned_game) or bool(game_processes()) or native_launcher_pending(),
            lambda: launch_online(self.document["settings"]["launcher"]), restore=self._restore_before_online)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)
        self._recover_outbox()
        if self.document["career"]:
            played = [f for season in self.document["career"]["seasons"]
                      for f in domain._fixtures(season)
                      if f["status"] == "completed" and "human" in (f["home"], f["away"])]
            if played:
                latest = max(played, key=lambda f: f["result"]["completed_at"])
                self.latest_result = dict(latest["result"], home=latest["home"], away=latest["away"])
                if latest["result"].get("outcome") == "forfeited":
                    self.latest_result["label"] = "Forfeited loss · observed score"

    def _restore_before_online(self):
        from .native_community_binding import recover_native_community
        recover_native_community(self.store.directory)
        result = PluginSession(self.store.directory, game_running=lambda: bool(game_processes())).finish()
        if result.get("status") not in {"idle", "restored"}:
            raise PluginSessionError("The temporary My Career setup is still active. Close Rocket League and wait for its offline helper to finish before retrying.")

    @Property("QVariantMap", notify=stateChanged)
    def state(self):
        career = self.document["career"]
        variants = self.document.get("lesson_variants", {}).get(self.selected_id, {})
        selected = configure_lesson(self.selected_id, **variants)
        active_lesson = (configure_lesson(self.request["lesson_id"], **self.request.get("variants", {}))
                         if self.request and self.request.get("lesson_id") else None)
        transition = self.lifecycle.frozen or self.lifecycle.state in ("Error/Recovery", "Online Launch Requested")
        state = self.lifecycle.state if transition else self.session_state
        message = self.lifecycle.message if transition else self.session_message
        return {"page": self.page, "career": career, "standings": domain.standings(career) if career else [],
            "next_fixture": domain.next_fixture(career) if career else None, "lessons": catalog(),
            "selected_lesson": selected, "settings": self.document["settings"],
            "lesson_preferences": self.document["lesson_preferences"], "setup_required": self.setup_required,
            "session": {"state": state, "message": message, "busy": self.lifecycle.frozen or
                bool(self.native_community and any(self.native_community.state().get(key)
                     for key in ("busy", "requires_restart"))) or
                self.session_state in ("Starting Career", "Stopping Career", "Waiting for Game Exit", "Waiting for Worker"),
                "kind": ("training" if (self.request or {}).get("lesson_id") else "workshop" if (self.request or {}).get("workshop") else "calibration" if (self.request or {}).get("calibration") else "career" if (self.request or {}).get("fixture") else "hub"),
                "fixture_id": (self.request or {}).get("fixture", {}).get("id"),
                "worker_running": self._worker_active(),
                "can_exit": not self.lifecycle.frozen and (self._prepared_next is not None or
                    self.session_state not in ("Starting Career", "Stopping Career", "Waiting for Game Exit", "Waiting for Worker")),
                "id": self.session_id,
                "can_retry": bool(self.lifecycle.last_error), "confirm_online": self.lifecycle.confirming},
            "error": self.error, "notice": self.notice, "diagnostics": self.diagnostics_info,
            "native_return_ready": copy.deepcopy(self.native_return_ready),
            "native_forfeit_rejected": copy.deepcopy(self.native_forfeit_rejected),
            "native_next_ready": copy.deepcopy(self.native_next_ready),
            "native_next_rejected": copy.deepcopy(self.native_next_rejected),
            "content": community_catalog(), "garage": garage_catalog(),
            "latest_attempt": self.latest_attempt, "latest_result": self.latest_result,
            "telemetry": dict(self.telemetry, lesson_id=(self.request or {}).get("lesson_id"),
                              lesson_variant=active_lesson["variant"] if active_lesson else None,
                              ghost_practice_pending=bool(self._ghost_pending)),
            "recordings": self.document["recordings"], "providers": self._providers(),
            "selected_provider": self.document["settings"].get("bot_provider", "mct-specialist-baseline"),
            "workshop": self.workshop_state, "plugin": self.plugin_status,
            "community_plugins": self.community_state,
            "community_catalog": self.catalog_state,
            "career_draft": dict(self.career_draft),
            "native_community_trial": self.native_community.state() if self.native_community else {},
            "native_community_request": self.native_community.request() if self.native_community else None,
            "owned_game": self.owned_game.as_dict() if self.owned_game else None,
            "offline": self.in_game, "human_team": (0 if not self.request or
                not self.request.get("fixture") or self.request["fixture"].get("home") == "human" else 1)}

    def _providers(self):
        from .bots.providers import provider_catalog
        return provider_catalog()

    def _refresh_workshop(self):
        from .workshop import library_state
        self.workshop_state = library_state(self.store.directory,
            launcher=self.document["settings"]["launcher"],
            install_path=self.document["settings"].get("install_path", ""),
            favorites=self.document.get("workshop_favorites", []),
            imported_maps=self.document.get("maps", []))

    def _save_current(self):
        self.store.save(self.document)

    def _community_job(self, operation, plugin_id=None):
        if self.community_state["busy"]:
            raise ValueError("Wait for the current plugin download or cancel it first.")
        record = copy.deepcopy(self.community_state["selected"])
        if operation == "download" and not record:
            raise ValueError("Check a plugin's current release before downloading it.")
        directory = self.store.directory / "community-plugins"
        cancelled = threading.Event()
        self._community_cancel = cancelled
        results = self._community_results
        self.community_state.update(busy=True, message={
            "lookup": "Checking the creator's current release…",
            "download": "Downloading into My Career's private library…",
            "library": "Checking downloaded files…"}[operation])
        if operation == "lookup":
            self.community_state["selected"] = None

        # The background job never touches Qt, the save, BakkesMod or the game.
        # One terminal result is consumed on the main thread's existing timer.
        def run():
            try:
                result = None
                if operation == "lookup":
                    result = community_plugins.lookup_plugin(plugin_id)
                elif operation == "download":
                    result = community_plugins.download_plugin(record, directory, cancelled=cancelled.is_set)
                # Once the service returns a receipt, the download was committed.
                # A late Cancel must not hide the package that now exists.
                if cancelled.is_set() and operation != "download":
                    results.put(("cancelled", operation, None, []))
                    return
                library = community_plugins.cached_plugins(directory)
                if cancelled.is_set() and operation != "download":
                    results.put(("cancelled", operation, None, []))
                    return
                results.put(("ok", operation, result, library))
            except community_plugins.DownloadCancelled:
                results.put(("cancelled", operation, None, []))
            except community_plugins.CommunityPluginError as error:
                results.put(("error", operation, str(error), []))
            except Exception:
                results.put(("error", operation, "Could not check the community plugin. Try again.", []))

        threading.Thread(target=run, name="community-plugin-download", daemon=True).start()

    def _poll_community(self):
        try:
            status, operation, result, library = self._community_results.get_nowait()
        except queue.Empty:
            return
        self.community_state["busy"] = False
        if status == "ok":
            # Archive manifests belong on disk, not in the game bridge payload.
            display_fields = {"id", "title", "creator", "version", "artifact_sha256", "status", "can_activate"}
            self.community_state["downloaded"] = [
                {key: value for key, value in item.items() if key in display_fields} for item in library]
            if operation == "lookup":
                self.community_state["selected"] = result
            self.community_state["message"] = (
                "Downloaded. Not enabled in the game; offline plugin loading still needs verification."
                if operation == "download" else "Current release found. Downloading does not enable it."
                if operation == "lookup" else "Downloaded library checked.")
        elif status == "cancelled":
            self.community_state["message"] = "Plugin request cancelled. Nothing was enabled in the game."
        else:
            self.community_state["message"] = result
            self.error = result
        self.stateChanged.emit()

    # -- public catalog browsing ------------------------------------------- #

    def _catalog_job(self, source, page, query):
        """Start one bounded public catalog read for an explicit browse action.

        The worker only reads one public HTML page. It never touches Qt, the
        save, BakkesMod, the game, or the plugin cache. Exactly one terminal
        result is consumed on the main thread's existing timer.
        """
        request = community_discovery.validate_request(source, query=query, page=page)
        if self.catalog_state["busy"]:
            raise ValueError("Wait for the current catalog page or cancel it first.")
        if self._catalog_outstanding >= _MAX_CATALOG_WORKERS:
            raise ValueError("Two catalog reads are still finishing. Wait a moment, then browse again.")
        self._catalog_generation += 1
        generation = self._catalog_generation
        cancelled = threading.Event()
        self._catalog_cancel = cancelled
        self._catalog_outstanding += 1
        results = self._catalog_results
        self.catalog_state.update(
            source=request["source"], page=request["page"], query=request["query"],
            busy=True, loading=True, status="loading", generation=generation,
            message="Reading one public catalog page\u2026",
            items=[], has_next=False, source_url="", page_item_count=0,
            query_scope="none", remote_query=False, truncated=False, fetched=False)

        def run():
            try:
                result = community_discovery.fetch_catalog(
                    request["source"], query=request["query"], page=request["page"],
                    cancel=cancelled.is_set)
                results.put(("ok", generation, result))
            except community_discovery.CatalogCancelled:
                results.put(("cancelled", generation, None))
            except community_discovery.CommunityCatalogError as error:
                results.put(("error", generation, str(error)))
            except Exception:
                results.put(("error", generation,
                             "Could not read the public catalog page. Try again."))

        threading.Thread(target=run, name="community-catalog-read", daemon=True).start()

    def _catalog_cancel_current(self):
        """Invalidate the current read immediately, without waiting for its thread.

        The generation bump makes any late result stale, so the tab is free at
        once and the abandoned worker can only be discarded by the timer.
        """
        self._catalog_generation += 1
        self._catalog_cancel.set()
        if self.catalog_state["busy"] or self.catalog_state["loading"]:
            self.catalog_state.update(
                busy=False, loading=False, status="cancelled", items=[], has_next=False,
                source_url="", page_item_count=0, fetched=False,
                message="Catalog read cancelled. Nothing was downloaded or enabled.")
            self.stateChanged.emit()

    def _poll_catalog(self):
        try:
            status, generation, result = self._catalog_results.get_nowait()
        except queue.Empty:
            return
        self._catalog_outstanding = max(0, self._catalog_outstanding - 1)
        if generation != self._catalog_generation:
            # A newer browse request or a cancel already replaced this tab; drop
            # the stale response instead of overwriting the newer catalog.
            return
        self.catalog_state.update(busy=False, loading=False)
        if status == "ok":
            self.catalog_state.update(
                items=result["items"], has_next=result["has_next"],
                source_url=result["source_url"], page_item_count=result["page_item_count"],
                query_scope=result["query_scope"], remote_query=result["remote_query"],
                truncated=result["truncated"], fetched=result["fetched"],
                status=result["status"], message=result["message"])
        elif status == "cancelled":
            self.catalog_state.update(
                status="cancelled", items=[], has_next=False, source_url="",
                page_item_count=0, fetched=False,
                message="Catalog read cancelled. Nothing was downloaded or enabled.")
        else:
            self.catalog_state.update(
                status="error", items=[], has_next=False, source_url="",
                page_item_count=0, fetched=False, message=result)
            self.error = result
        self.stateChanged.emit()

    def _catalog_item(self, source, item_id):
        """Return one currently displayed catalog row, or refuse the request."""
        if type(source) is not str or type(item_id) is not int or isinstance(item_id, bool):
            raise ValueError("Choose a catalog item from the displayed list.")
        for item in self.catalog_state["items"]:
            if item.get("source") == source and item.get("source_id") == item_id:
                return item
        raise ValueError("That item is not in the displayed catalog page. Browse again first.")

    def _catalog_open(self, payload):
        """Open the canonical public page for one displayed catalog row."""
        if not isinstance(payload, dict) or set(payload) != {"source", "id"}:
            raise ValueError("Choose a catalog item from the displayed list.")
        item = self._catalog_item(payload["source"], payload["id"])
        url = community_discovery.item_details_url(item["source"], item["source_id"])
        if url != item.get("details_url"):
            raise ValueError("That catalog link is not allowed.")
        QDesktopServices.openUrl(QUrl(url))

    def _catalog_select_plugin(self, payload):
        """Route one displayed BakkesPlugins row into the existing lookup."""
        if not isinstance(payload, dict) or set(payload) != {"source", "id"}:
            raise ValueError("Choose a plugin from the displayed catalog list.")
        if payload["source"] != "bakkes_plugins":
            raise ValueError("Only BakkesPlugins catalog rows can be checked as plugins.")
        item = self._catalog_item(payload["source"], payload["id"])
        self._community_job("lookup", str(item["source_id"]))

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
        return message["id"]

    def _require_editable(self, *, allow_community_pending=False):
        if self.lifecycle.frozen or self.stop_reason or self.session_state == "Starting Career":
            raise ValueError("Wait for the current game transition to finish.")
        if not allow_community_pending and self.native_community:
            trial = self.native_community.state()
            if trial.get("requires_restart"):
                raise ValueError("The plugin could not be confirmed. Close this My Career session before starting another activity.")
            if trial.get("busy"):
                raise ValueError("Wait for the community plugin confirmation before starting another activity.")

    @Slot(str, "QVariantMap")
    def dispatch(self, action, payload):
        try:
            self.error = ""
            if self.in_game and action.startswith("online_"):
                raise ValueError("My Career runs offline. Online features are not part of this mode.")
            if self._prepared_next and action not in {
                    "prepare_next_match", "start_prepared_match", "quit_game", "retry_result_save",
                    "navigate", "diagnostics", "open_data", "community_cancel",
                    "community_browse_cancel"}:
                raise ValueError("The next match is being prepared. Wait for it to start, or choose Quit My Career.")
            if action == "navigate":
                self.page = payload["page"]
                if self.page in ("community", "workshop"):
                    self._refresh_workshop()
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
                    "bot_provider": self.document["settings"].get("bot_provider", "mct-specialist-baseline"),
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
            elif action == "community_cancel":
                self._community_cancel.set()
                if self.community_state["busy"]:
                    self.community_state["message"] = "Cancelling the plugin request…"
            elif action == "forfeit_match":
                self._forfeit_match(payload)
            elif action == "prepare_next_match":
                self._prepare_next_match(payload)
            elif action == "start_prepared_match":
                self._start_prepared_match(payload)
            elif action == "quit_game" and self._prepared_next:
                self._cancel_prepared_next()
                self._begin_stop("exit")
            else:
                self._require_editable(allow_community_pending=action in {"quit_game", "stop_session", "return_hub"})
                self._action(action, payload)
        except Exception as exc:
            self.error = str(exc)
            if action == "forfeit_match":
                identity = self._forfeit_identity(payload)
                if identity and not self._stored_forfeit(identity["session_id"], identity["fixture_id"]):
                    # A generic error must never revoke a committed navigation.
                    # The host compares all three fields with its current intent.
                    self.native_forfeit_rejected = identity
            elif action == "prepare_next_match":
                identity = self._next_identity(payload, preparing=True)
                if identity:
                    rejection_keys = ("session_id", "fixture_id", "intent")
                    if self._prepared_next and all(self._prepared_next["identity"][key] == identity[key]
                                                   for key in rejection_keys):
                        if self._prepared_next["payload"] == payload:
                            self._prepared_next["error"] = str(exc)
                    elif not self._last_next or any(self._next_identity(
                            self._last_next["prepare"], preparing=True)[key] != identity[key] for key in rejection_keys):
                        self.native_next_rejected = {key: identity[key] for key in
                            ("session_id", "fixture_id", "intent")}
        self.stateChanged.emit()

    @staticmethod
    def _next_identity(payload, *, preparing=False):
        keys = {"expected_session_id", "expected_fixture_id", "expected_next_fixture_id", "continuation_intent"}
        if preparing:
            keys.add("lineup_ids")
        if not isinstance(payload, dict) or set(payload) != keys:
            return None
        values = [payload.get(key) for key in
                  ("expected_session_id", "expected_fixture_id", "expected_next_fixture_id")]
        intent = payload.get("continuation_intent")
        if (not all(isinstance(value, str) and 0 < len(value) <= 128 for value in values)
                or not isinstance(intent, str) or len(intent) != 32
                or any(character not in "0123456789abcdef" for character in intent)):
            return None
        return dict(zip(("session_id", "fixture_id", "next_fixture_id", "intent"), [*values, intent]))

    def _next_transition_clear(self):
        if (self.pending_launch is not None or self.stop_reason or self.stopping_worker
                or self.start_deadline is not None or self.lifecycle.frozen or self.lifecycle.confirming
                or self.lifecycle.state != "Idle"):
            raise ValueError("Wait for the current game transition to finish before continuing.")

    def _next_owned_game(self, expected=None):
        from .bootstrap import verify_owned_offline
        if (not self.in_game or not self.owned_game
                or (expected is not None and self.owned_game.as_dict() != expected)
                or not verify_owned_offline(self.owned_game)):
            raise ValueError("The same offline game is no longer available. Relaunch My Career.")
        return self.owned_game.as_dict()

    def _next_saved_result(self, identity):
        career = self.document.get("career")
        if not career or career.get("pending_session"):
            raise ValueError("Save the finished match before continuing.")
        fixture = next((item for item in domain._all_fixtures(career)
                        if item["id"] == identity["fixture_id"]), None)
        result = fixture and fixture.get("result")
        if (not fixture or fixture["status"] != "completed" or "human" not in (fixture["home"], fixture["away"])
                or not result or result.get("session_id") != identity["session_id"]
                or result.get("simulated") is not False or result.get("provenance") not in {"game", "forfeit"}):
            raise ValueError("The saved result does not match this finished match.")
        next_fixture = domain.next_fixture(career)
        if (not next_fixture or next_fixture["id"] != identity["next_fixture_id"]
                or next_fixture["status"] != "scheduled"):
            raise ValueError("The next fixture changed. Return to My Career to review the schedule.")
        return result

    def _prepare_next_match(self, payload):
        identity = self._next_identity(payload, preparing=True)
        if not identity:
            raise ValueError("Choose Play Next Match and confirm the current lineup again.")
        if self._prepared_next:
            if self._prepared_next["payload"] != payload:
                raise ValueError("Another next-match request is already being prepared.")
            if self._prepared_next.get("error"):
                raise ValueError(self._prepared_next["error"])
            return
        if self._last_next and self._last_next["prepare"] == payload:
            if self._last_next.get("error"):
                raise ValueError(self._last_next["error"])
            return
        self._next_transition_clear()
        self._require_editable()
        request = self.request or {}
        if (self.session_state != "Career Ready" or self.session_id != identity["session_id"]
                or request.get("fixture", {}).get("id") != identity["fixture_id"]
                or any(request.get(key) for key in ("lesson_id", "workshop", "calibration"))):
            raise ValueError("This is not the current finished career match.")
        owned = self._next_owned_game()
        result = copy.deepcopy(self._next_saved_result(identity))
        state = copy.deepcopy(self.document)
        state["career"] = domain.set_lineup(state["career"], payload["lineup_ids"])
        # One durable preference commit; no pending fixture, worker launch or
        # result award is created by preparation.
        self._commit(state)
        self._prepared_next = {"payload": copy.deepcopy(payload), "identity": identity,
            "owned": owned, "career_id": state["career"]["id"], "result": result}
        self.native_next_ready = None
        self.native_next_rejected = None
        self._action("return_hub", {"expected_session_id": identity["session_id"],
            "expected_fixture_id": identity["fixture_id"], "abandon": False})

    def _cancel_prepared_next(self):
        prepared = self._prepared_next
        if prepared:
            self._last_next = {"prepare": prepared["payload"], "start": {
                key: value for key, value in prepared["payload"].items() if key != "lineup_ids"},
                "error": "The next match was cancelled. Open Career to start a match manually."}
        self._prepared_next = None
        self.native_next_ready = None
        self.native_next_rejected = None
        self.native_return_ready = None
        self._native_return_request = None

    def _start_prepared_match(self, payload):
        identity = self._next_identity(payload)
        if not identity:
            raise ValueError("The prepared match request is invalid.")
        if self._last_next and self._last_next["start"] == payload:
            if self._last_next.get("error"):
                raise ValueError(self._last_next["error"])
            return
        prepared = self._prepared_next
        if not prepared or prepared["identity"] != identity:
            raise ValueError("This next-match request is no longer prepared.")
        self._next_transition_clear()
        self._require_editable()
        if (self._worker_active() or self.session_id is not None or self.request is not None
                or self.session_state != "Idle" or self.native_next_ready != identity
                or self.native_return_ready != {key: identity[key] for key in ("session_id", "fixture_id")}):
            raise ValueError("The finished activity has not completed cleanup yet.")
        self._next_owned_game(prepared["owned"])
        result = self._next_saved_result(identity)
        career = self.document["career"]
        if (career["id"] != prepared["career_id"] or result != prepared["result"]
                or career["lineup"] != prepared["payload"]["lineup_ids"]):
            raise ValueError("The confirmed career or lineup changed. Return to Career to choose again.")
        # Consume before any provider/save/launch side effect. Even if launch
        # fails or its reply is lost, this token cannot reserve a second fixture.
        self._last_next = {"prepare": prepared["payload"], "start": copy.deepcopy(payload)}
        self._prepared_next = None
        self.native_next_ready = None
        self.native_next_rejected = None
        try:
            self._prepare_launch("play_match", {"expected_career_id": prepared["career_id"],
                "expected_fixture_id": identity["next_fixture_id"]})
        except Exception as exc:
            self._last_next["error"] = f"The next match could not start: {exc}. Open Career to review the saved fixture."
            raise ValueError(self._last_next["error"]) from exc

    @staticmethod
    def _forfeit_identity(payload):
        if (not isinstance(payload, dict)
                or set(payload) != {"expected_session_id", "expected_fixture_id", "confirm", "return_intent"}
                or payload.get("confirm") is not True):
            return None
        session, fixture, intent = (payload.get(key) for key in
            ("expected_session_id", "expected_fixture_id", "return_intent"))
        if (not all(isinstance(value, str) and 0 < len(value) <= 128 for value in (session, fixture))
                or not isinstance(intent, str) or len(intent) != 32
                or any(character not in "0123456789abcdef" for character in intent)):
            return None
        return {"session_id": session, "fixture_id": fixture, "intent": intent}

    def _stored_forfeit(self, session_id, fixture_id):
        career = self.document.get("career")
        if not career:
            return None
        fixture = next((item for item in domain._all_fixtures(career)
                        if item["id"] == fixture_id), None)
        result = fixture and fixture.get("result")
        if (result and result.get("session_id") == session_id
                and result.get("provenance") == "forfeit"
                and result.get("outcome") == "forfeited"
                and result.get("forfeited_by") == "human"):
            return fixture
        return None

    def _forfeit_match(self, payload):
        identity = self._forfeit_identity(payload)
        if not identity:
            raise ValueError("Confirm forfeiting the current career match again.")
        self.native_forfeit_rejected = None
        request = self.request or {}
        if (not self.in_game or not self.session_id
                or identity["session_id"] != self.session_id
                or identity["fixture_id"] != request.get("fixture", {}).get("id")
                or request.get("lesson_id") or request.get("calibration") or request.get("workshop")):
            raise ValueError("The career match changed. Open its pause menu again before forfeiting.")
        committed = self._stored_forfeit(identity["session_id"], identity["fixture_id"])
        if committed:
            # A repeated click cannot rewrite the observed score or stop twice.
            if self.stop_reason:
                return
        else:
            self._require_editable()
            if not self._worker_active() or self.session_state != "Playing":
                raise ValueError("Only a running, unfinished career match can be forfeited.")
            # Drain both channels before choosing the result. A natural finish
            # already received is authoritative even when this click raced it.
            self._drain_activity_results()
            pending = (self.document.get("career") or {}).get("pending_session")
            if (not pending or pending.get("session_id") != self.session_id
                    or pending.get("fixture_id") != identity["fixture_id"]):
                raise ValueError("This match has already finished. Its saved result was kept.")
            observed = self._forfeit_score_observation
            if (not observed or observed["session_id"] != self.session_id
                    or observed["fixture_id"] != identity["fixture_id"]):
                raise ValueError("The current match score has not been observed. Resume briefly before forfeiting.")
            if observed["ended"]:
                raise ValueError("The final result is still being saved. Wait before returning to My Career.")
            state = copy.deepcopy(self.document)
            state["career"] = domain.forfeit_fixture(state["career"], identity["fixture_id"],
                self.session_id, *observed["scores"])
            self._commit(state)  # No shutdown, abandonment or ACK before this succeeds.
            committed = self._stored_forfeit(identity["session_id"], identity["fixture_id"])
        self.latest_result = dict(committed["result"], home=committed["home"], away=committed["away"],
            label="Forfeited loss · observed score")
        self._action("return_hub", {"expected_session_id": identity["session_id"],
            "expected_fixture_id": identity["fixture_id"], "abandon": False})

    def _action(self, action, p):
        if action == "retry_result_save":
            fixture_id = (self.request or {}).get("fixture", {}).get("id")
            if (set(p) != {"expected_session_id", "expected_fixture_id"}
                    or not self.session_id or not fixture_id
                    or p["expected_session_id"] != self.session_id
                    or p["expected_fixture_id"] != fixture_id):
                raise ValueError("The match changed. Open its results menu again before retrying the save.")
            canonical = str(uuid.UUID(self.session_id))
            path = self.store.directory / "outbox" / f"{canonical}.json"
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
                raise ValueError("The final score is not ready to save. Wait for the match to finish.")
            event = json.loads(path.read_text())
            if (not isinstance(event, dict) or event.get("type") != "result"
                    or event.get("session_id") != self.session_id
                    or event.get("fixture_id") != fixture_id or event.get("calibration")):
                raise ValueError("The saved score does not belong to this match.")
            self._event(event)
        elif action == "return_hub":
            if "expected_session_id" in p or "expected_fixture_id" in p:
                if (set(p) != {"expected_session_id", "expected_fixture_id", "abandon"}
                        or type(p["abandon"]) is not bool
                        or not self.session_id or p["expected_session_id"] != self.session_id
                        or p["expected_fixture_id"] != (self.request or {}).get("fixture", {}).get("id", "")):
                    raise ValueError("The activity changed. Open its menu again before returning to My Career.")
            pending = self.document["career"] and self.document["career"]["pending_session"]
            if pending and not p.get("abandon"):
                raise ValueError("This match is unfinished. Confirm leaving it; it will restart from kickoff.")
            self._native_return_request = ({"session_id": self.session_id,
                "fixture_id": (self.request or {}).get("fixture", {}).get("id", "")}
                if self.in_game and self.session_id else None)
            self.page = "hub"
            if self._worker_active():
                self._begin_stop("abandon" if pending else "return_hub")
            else:
                self._drain_activity_results()
                if self.document["career"] and self.document["career"]["pending_session"]:
                    self._career_change(domain.abandon_fixture)
                self._finish_native_return()
                self.request = None
                self.session_id = None
                self.telemetry = {}
                self._ghost_practice_enabled = False
                self._ghost_pending = {}
                self._ghost_deadline = None
                self.session_state = "Idle"
                self.session_message = "Career hub ready. Progress saved."
        elif action == "quit_game":
            self._begin_stop("exit")
        elif action == "refresh_workshop":
            self._refresh_workshop()
        elif action == "community_browse":
            if not isinstance(p, dict) or set(p) - {"source", "page", "query"}:
                raise ValueError("Choose a catalog source, page, and optional search text.")
            self._catalog_job(p.get("source"), p.get("page", 1), p.get("query", ""))
        elif action == "community_browse_cancel":
            if p:
                raise ValueError("Cancel the catalog read using the Catalog button.")
            self._catalog_cancel_current()
        elif action == "community_open_source":
            if not isinstance(p, dict) or set(p) != {"source"}:
                raise ValueError("Choose one catalog source to open in a browser.")
            url = community_discovery.catalog_page_url(p["source"], 1)
            QDesktopServices.openUrl(QUrl(url))
        elif action == "community_open_item":
            self._catalog_open(p)
        elif action == "community_select_plugin":
            self._catalog_select_plugin(p)
        elif action == "community_lookup":
            self._community_job("lookup", p.get("id"))
        elif action == "community_paste_link":
            # Read text only after this explicit user action, on the Qt thread.
            # lookup_plugin accepts only a numeric ID or the official page URL.
            from PySide6.QtGui import QGuiApplication
            if p:
                raise ValueError("Paste a plugin page link using the Community button.")
            clipboard = QGuiApplication.clipboard()
            text = clipboard.text().strip() if clipboard is not None else ""
            if not text or len(text) > 2048:
                raise ValueError("Copy a BakkesPlugins plugin page link, then choose Paste plugin link.")
            self._community_job("lookup", text)
        elif action == "community_download":
            self._community_job("download")
        elif action == "community_trial_prepare":
            if p or self.native_community is None:
                raise ValueError("This action requires the native offline developer trial.")
            if self.community_state["busy"] or self._worker_active() or self.lifecycle.frozen:
                raise ValueError("Wait for the current download or game transition to finish.")
            self.native_community.prepare(self.community_state["selected"])
        elif action == "community_library":
            self._community_job("library")
        elif action == "workshop_favorite":
            from .workshop import toggle_favorite
            self._refresh_workshop()
            state = copy.deepcopy(self.document)
            state["workshop_favorites"] = toggle_favorite(state.get("workshop_favorites", []),
                                                        p["id"], self.workshop_state["items"])
            self._commit(state)
            self._refresh_workshop()
        elif action == "play_workshop":
            self._prepare_launch(action, p)
        elif action in ("choose_provider", "install_provider"):
            from .bots.providers import ensure_provider
            if self.document["career"] and self.document["career"]["pending_session"]:
                raise ValueError("Change opponents between matches.")
            ensure_provider(p["id"], self.document["career"]["format"] if self.document["career"] else 3)
            state = copy.deepcopy(self.document)
            state["settings"]["bot_provider"] = p["id"]
            self._commit(state)
            self.notice = "Bot provider selected for the next match. Learned policies keep their original abilities."
        elif action == "training_settings":
            from .training import coaching_preferences
            prefs = coaching_preferences(self.document["settings"].get("training_display", {}))
            prefs[p["key"]] = p["value"]
            prefs = coaching_preferences(prefs)
            state = copy.deepcopy(self.document)
            state["settings"]["training_display"] = prefs
            self._commit(state)
            if self._worker_active() and self.request and self.request.get("lesson_id"):
                self._send("coaching", preferences=prefs)
        elif action in ("stop_ghost", "ghost_control"):
            if action == "ghost_control" and p.get("operation") == "toggle":
                # Validate the real boundary: only the toggle operation and an
                # optional boolean are accepted here.
                if set(p) - {"operation", "enabled"}:
                    raise ValueError("Use the ghost practice toggle without extra fields.")
                self._ghost_practice_toggle({"enabled": p.get("enabled")})
            else:
                operation = "stop" if action == "stop_ghost" else p.get("operation")
                self._send("ghost_control", operation=operation, value=p.get("value"))
                if operation == "stop":
                    # Hide the ghost and its controller depiction now; a packet
                    # sent before the worker processed Stop must not resurrect it.
                    self._clear_ghost_practice_state()
        elif action == "new_career":
            if self._worker_active() or (self.document["career"] and self.document["career"]["pending_session"]):
                raise ValueError("Finish or abandon the current session first.")
            if self.document["career"]:
                self.store.export_file(self.store.directory / f"career-{self.document['career']['id']}.json")
            state = copy.deepcopy(self.document)
            state["career"] = domain.new_career(p["team_name"], int(p.get("format", 3)), recruits=p.get("recruits"))
            self._commit(state)
            self.latest_result = None
            self.page = "hub"
        elif action in ("career_name_clipboard", "rename_recruit_clipboard"):
            from PySide6.QtGui import QGuiApplication
            expected = set() if action == "career_name_clipboard" else {"id"}
            if set(p) != expected:
                raise ValueError("Use the native menu's Paste name button.")
            clipboard = QGuiApplication.clipboard()
            name = clipboard.text().strip() if clipboard is not None else ""
            if not 1 <= len(name) <= 40 or not all(character.isprintable() for character in name):
                raise ValueError("Copy a name containing 1 to 40 visible characters, then choose Paste name.")
            if action == "career_name_clipboard":
                self.career_draft = {"team_name": name}
                self.notice = "Club name ready for the new career."
            else:
                self._career_change(domain.rename_recruit, p["id"], name)
                self.notice = "Recruit name saved."
        elif action == "backup_save":
            if p:
                raise ValueError("Use the Backup career button without a destination.")
            self._save_current()
            destination = self.store.directory / f"career-backup-{time.time_ns()}.json"
            self.store.export_file(destination)
            self.notice = "Career backup saved in your My Career data folder."
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
            key, value = p["key"], p["value"]
            if self._worker_active() and key in ("launcher", "install_path"):
                raise ValueError("Stop the current game session before changing its setup.")
            if key not in ("launcher", "install_path", "text_scale", "reduced_motion", "binding_profile"):
                raise ValueError("Unknown setting.")
            state = copy.deepcopy(self.document)
            state["settings"][key] = value
            self._commit(state)
        elif action == "setup_finish":
            state = copy.deepcopy(self.document)
            if sys.platform == "win32":
                selected = state["settings"]
                raw = selected.get("install_path", "").strip()
                if not raw:
                    candidate = next((i for i in detect_installations() if i["launcher"] == selected["launcher"]), None)
                    if not candidate:
                        raise ValueError("Rocket League was not found for this launcher. Enter its installed game folder or RocketLeague.exe path.")
                    raw = candidate["path"]
                path = Path(raw)
                if path.is_dir():
                    path = path / "Binaries/Win64/RocketLeague.exe"
                if not path.is_file() or path.name.lower() != "rocketleague.exe":
                    raise ValueError("Select the Rocket League installation folder or its Binaries/Win64/RocketLeague.exe file.")
                selected["install_path"] = str(path.resolve())
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
            if p and (set(p) != {"expected_session_id"} or p["expected_session_id"] != self.session_id):
                raise ValueError("The lesson changed. Open its menu again before retrying.")
            if not self._worker_active() or not (self.request or {}).get("lesson_id"):
                raise ValueError("Start a lesson before retrying it.")
            self._send("retry")
        elif action == "stop_session":
            self._begin_stop("stop")
        elif action == "abandon_fixture":
            if p:
                career = self.document["career"]
                pending = career and career.get("pending_session")
                expected = {"expected_career_id", "expected_fixture_id", "expected_session_id"}
                if (set(p) != expected or not pending or self._worker_active() or
                        p["expected_career_id"] != career["id"] or
                        p["expected_fixture_id"] != pending["fixture_id"] or
                        p["expected_session_id"] != pending["session_id"]):
                    raise ValueError("That unfinished match changed. Open My Career and review it again.")
            if self._worker_active():
                self._begin_stop("abandon")
            else:
                self._drain_activity_results()
                restarted = bool(self.document["career"] and self.document["career"]["pending_session"])
                if restarted:
                    self._career_change(domain.abandon_fixture)
                self.request = None
                self.session_id = None
                self.session_state = "Idle"
                self.session_message = ""
                self.notice = ("The unfinished match is ready to restart from kickoff. No result was added." if restarted
                               else "The completed match result is saved. Your next match is ready.")
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
            if self.in_game:
                path = Path(str(p.get("path", "")))
                if not path.is_absolute() or path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
                    raise ValueError("Select an existing JSON recording file with the import button.")
            else:
                path, _ = QFileDialog.getOpenFileName(None, "Import a permitted actual recording", "", "Recording (*.json)")
            if path:
                recording = import_recording(path)
                if isinstance(recording, tuple):
                    recording = recording[0]
                self._store_recording(recording)
                self.notice = "Recording imported with its provenance. Imported success claims are not independently certified."
        elif action == "play_recording":
            if not self._worker_active() or not (self.request or {}).get("lesson_id"):
                raise ValueError("Start this lesson before playing its recorded ghost.")
            if set(p) - {"id", "recording_id", "kind", "mode", "lead_seconds"}:
                raise ValueError("Choose a saved recording for this lesson.")
            if p.get("id") != self.request["lesson_id"]:
                raise ValueError("Start the selected lesson before playing its recorded ghost.")
            # Legacy callers send kind:"personal_best"; nothing else is accepted.
            if "kind" in p and p["kind"] != "personal_best":
                raise ValueError("Choose a saved recording for this lesson.")
            from .training.coach import coaching_preferences
            preferences = coaching_preferences(self.document["settings"].get("training_display", {}))
            if "mode" in p:
                if p["mode"] not in ("watch", "lead"):
                    raise ValueError("Ghost mode must be watch or lead.")
                preferences["mode"] = p["mode"]
            if "lead_seconds" in p:
                preferences["lead_seconds"] = p["lead_seconds"]
            # Re-validate the whole display preference set, including the bound
            # on lead_seconds, before any worker command is sent.
            preferences = coaching_preferences(preferences)
            variant = configure_lesson(p["id"], **self.request.get("variants", {}))["variant"]
            selected_id = p.get("recording_id")
            if selected_id:
                entry = next((item for item in self.document["recordings"]
                              if item["id"] == selected_id and item["lesson_id"] == p["id"]), None)
                if entry is None or Path(entry["filename"]).name != entry["filename"]:
                    raise ValueError("Choose a recording from this lesson's saved attempts.")
                best = import_recording(self.store.directory / "recordings" / entry["filename"])
                if best.get("variant") != variant:
                    raise ValueError("This recording uses a different lesson setup. Choose the matching variation.")
                practice = True
            else:
                # Legacy automatic best selection, scoped to the active lesson
                # and its exact variant. No arbitrary path is ever read.
                from .training.recordings import personal_best
                best = personal_best([item for item in self._recordings(p["id"])
                                      if item.get("variant") == variant])
                if best is None:
                    raise ValueError("No successful recording matches this lesson setup yet.")
                practice = False
            command_id = self._send("play_recording", recording=best, mode=preferences["mode"],
                                    lead_seconds=float(preferences["lead_seconds"]), practice=practice)
            self._remember_ghost_command(command_id, "play_recording", p["id"], practice=practice)
            self._legacy_playback = not practice
            if practice:
                # Loading a recording never turns practice on by itself.
                self._ghost_practice_enabled = False
                self._clear_ghost_practice_state(lesson_id=p["id"])
                self.notice = "Loading the saved recording. Ghost practice stays off until you turn it on."
            else:
                # Legacy playback keeps the original watch/lead transport and the
                # ghost display preference; it never touches practice state.
                self.notice = "Loading your best recorded attempt for this lesson."
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _ghost_practice_toggle(self, payload):
        """Lesson-only ghost practice toggle with deterministic UI state.

        Career fixtures cannot toggle or load a ghost. Availability comes from
        the worker's loaded practice state, not from files on disk, so the UI
        never claims a ghost the worker cannot actually enable. Repeated presses
        collapse to one input edge: a request matching the known state is a no-op.

        On is optimistic only until the worker's exact acknowledgement arrives;
        a rejection or a lost session reverts it to Off.
        """
        if set(payload) - {"enabled"}:
            raise ValueError("Use the ghost practice toggle without extra fields.")
        enabled = payload.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("Ghost practice must be on or off.")
        if not self._worker_active() or not (self.request or {}).get("lesson_id"):
            raise ValueError("Ghost practice is available only during a training lesson.")
        lesson_id = self.request["lesson_id"]
        practice = self.telemetry.get("ghost_practice") or {}
        support = self.telemetry.get("ghost_practice_support") or {}
        if enabled is None:
            enabled = not self._ghost_practice_enabled
        if enabled and support.get("supported") is False:
            raise ValueError(support.get("reason") or "This lesson does not support ghost practice.")
        if enabled and practice.get("available") is not True:
            raise ValueError("Choose an available recording before turning on ghost practice.")
        if enabled == self._ghost_practice_enabled:
            return  # Single edge; no duplicate command for a repeated press.
        command_id = self._send("ghost_control", operation="toggle", enabled=enabled)
        self._remember_ghost_command(command_id, "ghost_control", lesson_id, enabled)
        self._ghost_practice_enabled = enabled
        # The new practice toggle takes over from any legacy playback; Off must
        # never fall back to the legacy coach ghost.
        self._legacy_playback = False
        self._sync_ghost_assistance(lesson_id, enabled)
        if not enabled:
            self._clear_ghost_practice_state(lesson_id=lesson_id)
        self.stateChanged.emit()

    def _remember_ghost_command(self, command_id, kind, lesson_id, enabled=None, practice=None):
        """Track one bounded ghost command until the worker answers it."""
        self._ghost_seq += 1
        self._ghost_pending[command_id] = {"kind": kind, "lesson_id": lesson_id,
            "enabled": enabled, "practice": practice,
            "session_id": self.session_id, "seq": self._ghost_seq}
        self._ghost_deadline = time.monotonic() + 5.0
        while len(self._ghost_pending) > 8:
            self._ghost_pending.pop(next(iter(self._ghost_pending)))

    def _ghost_ack(self, event):
        """Apply only the exact acknowledgement for the current session/command.

        The session must be an exact, non-empty match before any pending entry is
        consumed. An acknowledgement older than a newer command for the same
        lesson is obsolete and cannot change state, so a late On answer after a
        local Off never resurrects the ghost.
        """
        command_id = event.get("id")
        session_id = event.get("session_id")
        if not isinstance(command_id, str) or not command_id:
            return
        if not isinstance(session_id, str) or not session_id or session_id != self.session_id:
            return
        pending = self._ghost_pending.get(command_id)
        if pending is None or pending["session_id"] != session_id:
            return
        self._ghost_pending.pop(command_id, None)
        if not self._ghost_pending:
            self._ghost_deadline = None
        if any(item["seq"] > pending["seq"] and item["kind"] == pending["kind"]
               and item["lesson_id"] == pending["lesson_id"]
               for item in self._ghost_pending.values()):
            return  # A newer command for this lesson already superseded it.
        lesson_id = pending["lesson_id"]
        if event.get("accepted") is not True:
            # Never leave an optimistic On behind a worker rejection.
            self._ghost_practice_enabled = False
            self._clear_ghost_practice_state(lesson_id=lesson_id)
            self.error = str(event.get("error") or "The game worker did not accept that ghost command.")
            return
        if pending["kind"] == "play_recording":
            if pending.get("practice") is False:
                # Legacy playback owns the coach transport only; practice state
                # and the ghost display preference are left exactly as they were.
                self.notice = str(event.get("label") or "Recording loaded.")
                return
            # A loaded recording is available but practice stays Off.
            self._ghost_practice_enabled = False
            self._clear_ghost_practice_state(lesson_id=lesson_id)
            self.notice = str(event.get("label") or "Recording loaded. Ghost practice is off.")
            return
        if pending["enabled"] is True and not self._ghost_practice_enabled:
            return  # Local Off already won; a late On answer cannot revive it.
        self._ghost_practice_enabled = pending["enabled"] is True
        self._sync_ghost_assistance(lesson_id, self._ghost_practice_enabled)
        if not self._ghost_practice_enabled:
            self._clear_ghost_practice_state(lesson_id=lesson_id)

    def _expire_ghost_pending(self):
        """Bounded wait: a lost worker answer must not leave practice pending."""
        if not self._ghost_pending or self._ghost_deadline is None:
            return
        if time.monotonic() < self._ghost_deadline:
            return
        self._ghost_pending = {}
        self._ghost_deadline = None
        if self._ghost_practice_enabled:
            self._ghost_practice_enabled = False
            self._clear_ghost_practice_state()
            self.error = "The game worker did not confirm the ghost command. Ghost practice is off."
            self.stateChanged.emit()

    def _clear_ghost_practice_state(self, *, lesson_id=None):
        """Hide the ghost, lines and controller depiction immediately.

        Used by both the practice toggle and the legacy stop paths so a packet
        sent before the worker processed the command cannot resurrect a visible
        ghost. It sends no worker command and is safe without a recording.
        """
        practice = self.telemetry.get("ghost_practice") or {}
        self._ghost_practice_enabled = False
        self._legacy_playback = False
        self.telemetry["ghost_practice"] = {
            "available": practice.get("available") is True, "enabled": False, "playing": False,
            "visible": False, "status": "off", "pose": None, "lines": [], "coach_actions": None,
            "controller": {"observed": False, "source": "ghost", "actions": None, "controls": {},
                           "label": "Controller actions unavailable"},
            "label": "Ghost practice off", "message": "Ghost practice off",
            "player_input_applied": False,
        }
        if lesson_id is None:
            lesson_id = (self.request or {}).get("lesson_id")
        if lesson_id:
            self._sync_ghost_assistance(lesson_id, False)
        self.stateChanged.emit()

    def _sync_ghost_assistance(self, lesson_id, enabled):
        """Keep the persisted lesson assistance ghost setting in step.

        The per-lesson assistance record is what starts and runs the lesson, so
        it must agree with practice state; the display preferences follow too.
        """
        from .training import assistance_preferences, coaching_preferences
        state = copy.deepcopy(self.document)
        values = assistance_preferences(state["lesson_preferences"].get(lesson_id))
        values["ghost"] = enabled
        state["lesson_preferences"][lesson_id] = values
        prefs = coaching_preferences(state["settings"].get("training_display", {}))
        prefs["ghost"] = enabled
        state["settings"]["training_display"] = prefs
        self._commit(state)

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
                   "data_dir": str(self.store.directory), "in_game": self.in_game,
                   "coaching": copy.deepcopy(self.document["settings"].get("training_display", {})),
                   "provider": self.document["settings"].get("bot_provider", "mct-specialist-baseline")}
        if action == "play_match":
            if not career:
                raise ValueError("Create a career first.")
            # Native dialog callbacks may arrive after the displayed fixture
            # changed. Validate their snapshot before provider/save side effects.
            if "expected_career_id" in payload or "expected_fixture_id" in payload:
                fixture = domain.next_fixture(career)
                if (payload.get("expected_career_id") != career["id"] or not fixture or
                        payload.get("expected_fixture_id") != fixture["id"]):
                    raise ValueError("That match changed while the menu was open. Reopen Career and choose the current fixture.")
            from .bots.providers import ensure_provider
            ensure_provider(request["provider"], career["format"])
            self._career_change(domain.set_policy, request["provider"])
            self._career_change(domain.start_fixture, request["session_id"])
            request["fixture"] = domain.next_fixture(self.document["career"])
        elif action == "calibration":
            temp = domain.new_career("Calibration", career["format"] if career else 3)
            request["fixture"] = domain.next_fixture(temp)
            request["calibration"] = True
        elif action == "play_workshop":
            from .workshop import prepare_launch
            request["workshop"] = prepare_launch(payload["id"], self.store.directory,
                launcher=self.document["settings"]["launcher"],
                install_path=self.document["settings"].get("install_path", ""),
                imported_maps=self.document.get("maps", []))
        else:
            lesson_id = payload["id"]
            configure_lesson(lesson_id)
            request.update(lesson_id=lesson_id, preferences=assistance_preferences(
                self.document["lesson_preferences"].get(lesson_id)),
                variants=self.document.get("lesson_variants", {}).get(lesson_id, {}))
        self._save_current()
        if self._worker_active() or (is_alive(self.owned_game) and not self.in_game):
            self.pending_launch = request
            self._begin_stop("restart")
        else:
            self._launch(request)

    def _launch(self, request):
        self.startup_cancelled_session = None
        self._ghost_practice_enabled = False
        self._legacy_playback = False
        self._ghost_pending = {}
        self._ghost_deadline = None
        self.startup_stop_acknowledged = False
        self.worker_ready = False
        self.native_return_ready = None
        self.native_forfeit_rejected = None
        self._forfeit_score_observation = None
        self._native_return_request = None
        self.lifecycle.state = "Idle"
        self.lifecycle.last_error = ""
        if self.in_game:
            from .bootstrap import verify_owned_offline
            if not self.owned_game or not verify_owned_offline(self.owned_game):
                raise ValueError("The owned offline game is no longer available. Relaunch My Career.")
            request["owned_game"] = self.owned_game.as_dict()
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
            program = str(Path(sys.executable).parent / "_internal" / "MyCareerTrainingWorker.exe")
            arguments = ["--worker"]
        else:
            program, arguments = sys.executable, ["-m", "my_career_training", "--worker"]
        self.process.start(program, arguments)

    def _process_error(self, _):
        if self.startup_cancelled_session == self.session_id and self.session_id:
            return  # Killing a timed-out, not-yet-ready worker is expected.
        self.error = "The game worker could not start. Open Diagnostics and check the installed package."
        self.session_state = "Error/Recovery"
        self.stateChanged.emit()

    def _process_finished(self, exit_code, _):
        self.start_deadline = None
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
        cancelled = bool(self.session_id and self.startup_cancelled_session == self.session_id)
        if kind == "ready":
            if cancelled:
                return  # No start can be sent after pre-ready cancellation.
            self.worker_ready = True
            self._send("start", **self.request)
            return
        if event.get("session_id") not in (None, self.session_id):
            return
        if kind == "owned_game":
            self.owned_game = ProcessIdentity(**event["identity"])
        elif kind == "session":
            if cancelled:
                return  # Only an actually saved result can leave recovery.
            if self.stop_reason:
                return  # Late running/completed messages cannot undo cleanup.
            worker_state = event.get("state")
            if self.session_state == "Career Ready" and worker_state in ("starting", "running", "training"):
                return
            self.session_state = {"starting": "Starting Career", "running": "Playing", "training": "training",
                "completed": "Career Ready", "error": "Error/Recovery"}.get(worker_state, worker_state)
            self.session_message = event.get("message", "")
            if self.session_state != "Starting Career":
                self.start_deadline = None
        elif kind == "telemetry":
            if cancelled:
                return
            self.telemetry = {key: value for key, value in event.items() if key not in ("type", "session_id")}
            practice = self.telemetry.get("ghost_practice")
            if isinstance(practice, dict):
                if not self._ghost_practice_enabled and practice.get("visible"):
                    # A packet sent before the Off command must not resurrect the
                    # hidden ghost or its controller depiction.
                    self.telemetry["ghost_practice"] = dict(practice, enabled=False, playing=False,
                        visible=False, status="off", pose=None, lines=[], coach_actions=None,
                        controller={"observed": False, "source": "ghost", "actions": None,
                                    "controls": {}, "label": "Controller actions unavailable"},
                        label="Ghost practice off", message="Ghost practice off")
                elif practice.get("enabled") is True and any(
                        item["kind"] == "ghost_control" and item["enabled"] is True
                        and item["session_id"] == self.session_id
                        for item in self._ghost_pending.values()):
                    # Only an outstanding, acknowledged-pending On may adopt the
                    # worker's enabled flag; stale telemetry cannot resurrect it.
                    self._ghost_practice_enabled = True
                elif practice.get("enabled") is not True and not any(
                        item["kind"] == "ghost_control" and item["enabled"] is True
                        for item in self._ghost_pending.values()):
                    # A loaded-but-off recording (or a worker Off) clears the
                    # internal flag so no later packet can imply practice is on.
                    self._ghost_practice_enabled = False
            scores = event.get("scores")
            if event.get("session_id") == self.session_id:
                self._forfeit_score_observation = None
            if (event.get("session_id") == self.session_id and self.session_id
                    and isinstance(scores, list) and len(scores) == 2
                    and event.get("phase") in {"MatchPhase.Countdown", "MatchPhase.Kickoff",
                        "MatchPhase.Active", "MatchPhase.GoalScored", "MatchPhase.Replay",
                        "MatchPhase.Paused", "MatchPhase.Ended"}
                    and all(type(score) is int and 0 <= score <= 999 for score in scores)):
                self._forfeit_score_observation = {"session_id": self.session_id,
                    "fixture_id": (self.request or {}).get("fixture", {}).get("id"),
                    "scores": list(scores), "ended": "Ended" in str(event.get("phase", ""))}
            self.start_deadline = None
            if (not self.stop_reason and self.session_state != "Career Ready"
                    and (not self.latest_result or self.latest_result.get("session_id") != self.session_id)):
                self.session_state = "training" if self.request.get("lesson_id") else "Playing"
        elif kind == "result":
            if self.request.get("calibration"):
                self.latest_result = dict(event, label="Calibration exhibition · no league points")
                self.notice = "Calibration complete. Adjust the visible difficulty setting before a league fixture."
                self._ack_outbox(event["session_id"])
            else:
                self._commit_result(event)
            if not self.stop_reason:
                self.session_state = "Career Ready"
                self.session_message = "Match complete. Your result is saved. Continue when you are ready."
            if cancelled:
                self.error = ""
            self.page = "hub"
        elif kind == "ghost_ack":
            if cancelled:
                return
            self._ghost_ack(event)
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
            elif cancelled and not self.startup_stop_acknowledged:
                self.startup_stop_acknowledged = True
                # A receipt writer may have outlived the worker's bounded join.
                # Once it confirms cleanup, let the waiting stdin loop exit.
                if self._worker_active():
                    self._send("shutdown", session_id=self.session_id)

    def _commit_result(self, event, note=None):
        forfeited = self._stored_forfeit(event.get("session_id"), event.get("fixture_id"))
        if forfeited:
            # The worker may finish between our drain and the durable forfeit.
            # Only an exact, valid natural result receipt may be acknowledged;
            # it cannot replace the chosen outcome or award progression twice.
            if (event.get("type") != "result" or event.get("calibration")
                    or event.get("provenance", "game") != "game"
                    or not all(type(event.get(key)) is int and 0 <= event[key] <= 999
                               for key in ("home_score", "away_score"))
                    or event["home_score"] == event["away_score"]):
                raise ValueError("The late result receipt does not match a valid completed game.")
            if (not self.latest_result or self.latest_result.get("session_id") == event["session_id"]
                    or self.session_id == event["session_id"]):
                self.latest_result = dict(forfeited["result"], home=forfeited["home"], away=forfeited["away"],
                    label="Forfeited loss · observed score")
            self._ack_outbox(event["session_id"])
            return
        state = copy.deepcopy(self.document)
        state["career"] = domain.complete_fixture(state["career"], event["fixture_id"], event["session_id"],
            event["home_score"], event["away_score"], event.get("provenance", "game"))
        from .review import bounded_summary
        review = bounded_summary(event.get("review"))
        fixture = next(f for f in domain._all_fixtures(state["career"]) if f["id"] == event["fixture_id"])
        if "review" not in fixture["result"]:
            fixture["result"]["review"] = review
        if note:
            state.setdefault("recovery_notes", []).append({"fixture_id": event["fixture_id"], "note": str(note)[:1000]})
        self._commit(state)
        returning = self._native_return_request or self.native_return_ready
        presented = self.latest_result or {}
        keep_return_proof = (returning
            and presented.get("session_id") == returning["session_id"]
            and presented.get("fixture_id") == returning["fixture_id"]
            and (event["session_id"], event["fixture_id"]) !=
                (returning["session_id"], returning["fixture_id"]))
        # An older valid duplicate may be acknowledged, but cannot hide the
        # current activity's durable result while its native Return is pending.
        if not keep_return_proof:
            self.latest_result = dict(fixture["result"], home=fixture["home"], away=fixture["away"])
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
                kept_forfeit = bool(self._stored_forfeit(event.get("session_id"), event.get("fixture_id")))
                self._commit_result(event)
                self.notice = ("Kept the saved forfeited loss and acknowledged the late game result."
                    if kept_forfeit else "Recovered a completed match from the game worker's durable result receipt.")
                if (self.session_id and event.get("session_id") == self.session_id
                        and event.get("fixture_id") == (self.request or {}).get("fixture", {}).get("id")
                        and not self.stop_reason):
                    self.session_state = "Career Ready"
                    self.session_message = "Match complete. Your result is saved. Continue when you are ready."
                    self.error = ""
                    self.page = "hub"
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
                "filename": path.name, "label": recording.get("label", "Your attempt"),
                "outcome": recording.get("outcome", "unknown"), "variant": recording.get("variant"),
                "source": recording.get("metadata", {}).get("source", {})})
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
        self.start_deadline = None
        self.stop_reason = "online"
        self.stopping_worker = True
        if self._worker_active():
            self._send("shutdown")
        else:
            QTimer.singleShot(0, self.lifecycle.worker_stopped)

    def _begin_stop(self, reason):
        self._save_current()
        self.start_deadline = None
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
        if self.in_game and self.stop_reason in ("restart", "return_hub", "abandon"):
            self.session_state = "Waiting for Worker"
            self.close_deadline = time.monotonic() + 15
            return
        graceful_close(self.owned_game)
        self.session_state = "Waiting for Game Exit"
        self.close_deadline = time.monotonic() + 30

    def _drain_activity_results(self):
        """Keep a stopped worker's final score ahead of an abandonment."""
        self._read_worker()
        self._recover_outbox()
        pending = (self.document.get("career") or {}).get("pending_session") or {}
        for identity in (self.session_id, pending.get("session_id")):
            try:
                canonical = str(uuid.UUID(identity))
            except (ValueError, TypeError, AttributeError):
                continue
            if (self.store.directory / "outbox" / f"{canonical}.json").exists():
                raise ValueError("The final score still needs recovery. Retry saving before leaving this activity.")
        self._save_current()

    def _finish_native_return(self):
        """Authorize game navigation only after the stopped activity is saved."""
        expected = {"session_id": self.session_id,
                    "fixture_id": (self.request or {}).get("fixture", {}).get("id", "")}
        if (self.in_game and self.session_id and not self.pending_launch
                and self._native_return_request == expected):
            self.native_return_ready = dict(expected)
            prepared = self._prepared_next
            if prepared and all(prepared["identity"][key] == value for key, value in expected.items()):
                prepared.pop("error", None)
                self.native_next_ready = dict(prepared["identity"])
            self.error = ""
        self._native_return_request = None

    def _tick(self):
        self._poll_community()
        self._poll_catalog()
        self._expire_ghost_pending()
        before = (self.lifecycle.state, self.lifecycle.message)
        self.lifecycle.tick()
        if self.stop_reason == "online" and self.lifecycle.state in ("Online Launch Requested", "Error/Recovery"):
            self.stop_reason = None
        if before != (self.lifecycle.state, self.lifecycle.message):
            self.stateChanged.emit()
        if self.start_deadline and time.monotonic() > self.start_deadline:
            self.start_deadline = None
            self.startup_cancelled_session = self.session_id
            self.stopping_worker = True
            self.pending_launch = None
            self.error = "Starting the offline session took too long. This attempt is stopping; unfinished progress is kept."
            self.session_state = "Error/Recovery"
            if self._worker_active():
                if self.worker_ready:
                    self._send("shutdown", session_id=self.session_id)
                else:
                    # We have never sent start, so this worker cannot own a
                    # core or a game. In particular, native imports before
                    # ready may be blocked and unable to read shutdown.
                    self.process.kill()
            self.stateChanged.emit()
        if self.stop_reason and self.stop_reason != "online":
            if self.session_state == "Waiting for Worker" and not self._worker_active():
                # QProcess can stop before its final readyRead/finished signal is
                # handled. Commit any late score before clearing the activity or
                # abandoning its still-unfinished fixture.
                reason = self.stop_reason
                try:
                    self._drain_activity_results()
                    if reason == "abandon" and self.document["career"] and self.document["career"]["pending_session"]:
                        self._career_change(domain.abandon_fixture)
                except Exception as exc:
                    self.error = str(exc)
                    self.session_state = "Error/Recovery"
                    self.stop_reason = None
                    self.stateChanged.emit()
                    return
                self.stop_reason = None
                self.session_state = "Idle"
                self.telemetry = {}
                self._ghost_practice_enabled = False
                self._ghost_pending = {}
                self._ghost_deadline = None
                self.session_message = "Career hub ready. Progress saved."
                self._finish_native_return()
                self.request = None
                self.session_id = None
                self.stopping_worker = False
                if self.pending_launch:
                    request, self.pending_launch = self.pending_launch, None
                    self._launch(request)
                self.stateChanged.emit()
            elif self.session_state == "Waiting for Game Exit" and not is_alive(self.owned_game) and not self._worker_active():
                reason = self.stop_reason
                try:
                    self._drain_activity_results()
                    if reason == "abandon" and self.document["career"] and self.document["career"]["pending_session"]:
                        self._career_change(domain.abandon_fixture)
                except Exception as exc:
                    self.error = str(exc)
                    self.session_state = "Error/Recovery"
                    self.stop_reason = None
                    self.stateChanged.emit()
                    return
                self.stop_reason = None
                self.owned_game = None
                self.native_return_ready = None
                self._native_return_request = None
                self.request = None
                self.session_id = None
                self.stopping_worker = False
                self.session_state = "Idle"
                self.session_message = "Game session closed. Progress is saved."
                if reason == "exit":
                    self.exitRequested.emit()
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

    @Slot(result=bool)
    def request_close(self):
        try:
            self._save_current()
            if self.lifecycle.frozen or self.stop_reason:
                self.error = "Wait for the game transition to finish before closing the app."
                self.stateChanged.emit()
                return False
            if self._worker_active() or is_alive(self.owned_game):
                self._begin_stop("exit")
                self.stateChanged.emit()
                return False
            return True
        except Exception as exc:
            self.error = "The save could not be completed. Keep the app open and retry: " + str(exc)
            self.stateChanged.emit()
            return False

    def close(self):
        self._community_cancel.set()
        self._catalog_cancel.set()
        self._save_current()
        if self._worker_active():
            self._send("shutdown")
            self.process.waitForFinished(30000)
            self._read_worker()
        self.store.close()
