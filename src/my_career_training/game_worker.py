"""Isolated JSON-lines game process. SDK and native game imports are lazy.

The owned core is the only process this module may terminate. Rocket League
closure is delegated to the app's identity-scoped window-close transition.
"""
from __future__ import annotations

from collections import deque
import hashlib
import importlib
import json
import logging
import math
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
import uuid

PROTOCOL = 1
MAX_COMMAND = 28 * 1024 * 1024
HANDLER_NAMES = ("on_connect_handlers", "packet_handlers", "field_info_handlers", "match_config_handlers",
                 "match_comm_handlers", "ball_prediction_handlers", "controllable_team_info_handlers", "raw_handlers")


def isolated_relay(relay):
    """b56 defines mutable handler lists at class scope: never share them."""
    for name in HANDLER_NAMES:
        setattr(relay, name, [])
    return relay


def session_uuid(value):
    if not isinstance(value, str):
        raise ValueError("A valid session identifier is required.")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("A canonical session UUID is required.") from None
    return value


def persist_result(data_dir, result):
    """Crash receipt is durable before delivery. Parent deletes after save commit."""
    identity = session_uuid(result["session_id"])
    outbox = Path(data_dir).resolve() / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    target = outbox / f"{identity}.json"
    temporary = outbox / f".{identity}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        if os.name != "nt":
            descriptor = os.open(outbox, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def core_path():
    from .adapter import CORE_SHA256
    package = Path(__file__).resolve().parent
    candidates = [package / "runtime/RLBotServer.exe", package.parent.parent / "runtime/RLBotServer.exe"]
    for candidate in candidates:
        if candidate.is_file():
            with candidate.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != CORE_SHA256:
                raise RuntimeError("The bundled RLBot core failed its integrity check. Reinstall this build.")
            return candidate
    raise RuntimeError("The verified RLBot runtime is missing. Install the complete Windows package.")


def preflight(owned=None):
    import psutil
    if owned:
        from .bootstrap import verify_owned_offline
        if not verify_owned_offline(owned):
            raise RuntimeError("The owned game is not the verified offline session.")
    for process in psutil.process_iter(["name"]):
        try:
            name = (process.info.get("name") or "").lower()
            if owned and name == "rocketleague.exe" and process.pid == owned.pid:
                continue
            if name in {"rocketleague.exe", "rlbotserver.exe", "rlbotserver"}:
                raise RuntimeError("Close Rocket League and any RLBot session before starting a career or lesson.")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


class SessionInbox:
    """Bound high-rate telemetry, retain first terminal packet and event order.

    Each packet phase has one pending slot. Keeping separate phase slots retains
    Active evidence before Ended; replacing a slot moves it to its true arrival
    position. Commands remain ordered and terminal duplicates cannot overtake Stop.
    Coalesced physics frames are identified by the existing frame-gap detector.
    """
    def __init__(self):
        self._items = deque()
        self._pending = {}
        self._condition = threading.Condition()

    @staticmethod
    def key(kind, value):
        if kind == "packet":
            return kind, int(value.match_info.match_phase)
        if kind in {"prediction", "field"}:
            return kind,
        if kind == "mapping":
            return kind, value[0]
        return None

    def put(self, event):
        kind, value = event
        key = self.key(kind, value)
        with self._condition:
            previous = self._pending.get(key) if key is not None else None
            if previous is not None:
                if key == ("packet", 7):
                    return  # Preserve first authoritative Ended and its position.
                self._items.remove(previous)
            item = [kind, value, key]
            self._items.append(item)
            if key is not None:
                self._pending[key] = item
            self._condition.notify()

    def get(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not self._items:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise queue.Empty
                self._condition.wait(remaining)
            kind, value, key = self._items.popleft()
            if key is not None:
                del self._pending[key]
            return kind, value

    def qsize(self):
        with self._condition:
            return len(self._items)


def game_file_version(executable):
    """Read the running game's Windows file version without launching a helper."""
    if sys.platform != "win32":
        return "unknown"
    try:
        import ctypes
        from ctypes import wintypes
        version = ctypes.WinDLL("version", use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
        version.GetFileVersionInfoW.restype = wintypes.BOOL
        version.VerQueryValueW.argtypes = [wintypes.LPCVOID, wintypes.LPCWSTR,
                                          ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        version.VerQueryValueW.restype = wintypes.BOOL
        ignored = wintypes.DWORD()
        size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(ignored))
        if not size:
            return "unknown"
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
            return "unknown"
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
            return "unknown"
        fields = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD * 13)).contents
        if fields[0] != 0xFEEF04BD:
            return "unknown"
        return ".".join(str(value) for value in (fields[2] >> 16, fields[2] & 65535,
                                                fields[3] >> 16, fields[3] & 65535))
    except (OSError, AttributeError, ValueError):
        return "unknown"


def observed_hitbox(player):
    try:
        dimensions = [float(getattr(player.hitbox, key)) for key in ("length", "width", "height")]
        offset = [float(getattr(player.hitbox_offset, key)) for key in ("x", "y", "z")]
        if any(not math.isfinite(value) or value <= 0 for value in dimensions) or any(
                not math.isfinite(value) for value in offset):
            return "unknown"
        return {"dimensions": dimensions, "offset": offset, "source": "RLBot game packet"}
    except (AttributeError, TypeError, ValueError):
        return "unknown"


class SessionCancelled(Exception):
    """A queued stop cancelled bounded startup work."""


class GameSession:
    def __init__(self, request, emit):
        self.request = request
        self.session_id = session_uuid(request.get("session_id"))
        self.emit = emit
        self.events = SessionInbox()
        self.cancel_start = threading.Event()
        self.core_lock = threading.Lock()
        self.cleanup_complete = False
        self.core = None
        self.manager = None
        self.relays = {}
        self.threads = []
        self.mapping = {}
        self.ready_teams = set()
        self.controllers = {}
        self.prediction = self.field_info = None
        self.owned = None
        if request.get("owned_game"):
            from .platforms import ProcessIdentity
            self.owned = ProcessIdentity(**request["owned_game"])
        self.map_guard = None
        self.coach = None
        self.coach_snapshot = {}
        self.practice = None
        self.practice_snapshot = {}
        self.practice_support = {"supported": False, "reason": "Start a lesson to use ghost practice."}
        # True only while a legacy (no explicit recording_id) play command owns
        # the coach rendering. The new practice flow never falls back to it.
        self.legacy_playback = False
        self.coaching_preferences = request.get("coaching", {})
        self.engine = None
        # Development-only real bot capture. ``None`` for every ordinary session.
        self.capture = None
        self.capture_controller = None
        self.capture_ready = False
        self.capture_aborted = None
        self.capture_metadata = {}
        self.capture_arena = None
        self.capture_configuration = None
        self.capture_configuration_ack = None
        # The actor the training engine observes and state-sets. It is the Human
        # in every normal mode and the designated capture bot only in capture.
        self.training_actor_index = None
        from .review import MatchReview
        self.review = MatchReview()
        self.renderer = None
        self.recording = None
        self.playback_origin = None
        self.last_frame = None
        self.last_controls = -math.inf
        self.last_telemetry = -math.inf
        self.last_render = -math.inf
        self.seen_active = False
        self.result_sent = False
        self.attempt_sent = None
        self.attempt_acked = False
        # A pre-start failure has no samples and must not auto-retry in a busy
        # loop; only an attempt that actually ran may be retried automatically.
        self.attempt_retryable = False
        self.auto_reset_at = None
        self.applied_reset = False
        self.stop_id = None
        self.stopping = False
        self.stop_deadline = 0
        self.started = time.time()
        self.started_monotonic = time.monotonic()
        self.first_packet = False
        self.game_version = "unknown"
        self.thread = threading.Thread(target=self.run, name="game-session", daemon=True)

    def event(self, kind, **values):
        self.emit({"type": kind, "session_id": self.session_id, **values})

    def command(self, command):
        if command.get("type", command.get("command")) in {"stop", "shutdown"}:
            with self.core_lock:
                self.stop_id = command.get("id")
                self.cancel_start.set()
        self.events.put(("command", command))

    def check_cancel(self):
        if self.cancel_start.is_set():
            raise SessionCancelled()

    def spawn_core(self, runtime, port):
        # Cancellation and the only core creation share one lock. A stop that
        # wins this lock cannot be followed by a late Popen from the loader.
        with self.core_lock:
            self.check_cancel()
            if time.monotonic() - self.started_monotonic > 120:
                raise RuntimeError("Rocket League did not connect within two minutes. Check launcher setup and retry.")
            preflight(self.owned)
            executable = core_path()  # Recheck the pinned file after model loading.
            self.core = subprocess.Popen([str(executable), str(port)], cwd=runtime, shell=False,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return executable

    def stop_owned_core(self):
        with self.core_lock:
            if self.core is None or self.core.poll() is not None:
                return
            try:
                self.core.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.core.terminate()  # Only the exact Popen handle we created.
                try:
                    self.core.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.core.kill()
                    self.core.wait(timeout=2)

    def exit_blocked_pre_core_worker(self):
        # There cannot be a result writer before a core ever starts. Hold the
        # spawn lock until this worker exits so a returning loader cannot race
        # the confirmed stop. Never use this path after core creation.
        with self.core_lock:
            if self.core is not None or self.result_sent:
                return False
            self.cancel_start.set()
            try:
                self.event("stopped", id=self.stop_id)
            finally:
                os._exit(2)

    def connect(self, connector, relay, port, predictions=False):
        # b56's connector retries internally; short slices keep Stop responsive.
        deadline = time.monotonic() + 8
        while True:
            self.check_cancel()
            relay.connection_timeout = .5
            try:
                connector(wants_match_communications=False, wants_ball_predictions=predictions,
                          close_between_matches=bool(getattr(relay, "agent_id", "")), rlbot_server_port=port)
                self.check_cancel()
                return
            except (OSError, TimeoutError):
                if relay.socket:
                    relay.socket.close()
                relay.socket = None
                relay.is_connected = False
                if time.monotonic() >= deadline:
                    raise RuntimeError("The offline runtime did not accept a local connection. Retry the session.") from None

    def _relay_thread(self, relay):
        def receive():
            try:
                relay.run()
            finally:
                if not self.stopping:
                    self.events.put(("disconnected", None))
        thread = threading.Thread(target=receive, name="rlbot-relay", daemon=True)
        self.threads.append(thread)
        thread.start()

    @staticmethod
    def config_signature(config):
        return (config.game_map_upk, tuple((player.team, type(player.variety).__name__,
                    getattr(player.variety, "agent_id", ""), getattr(player.variety, "name", ""))
                    for player in config.player_configurations))

    def start_acknowledged_match(self, config, timeout=90):
        # StartMatch is asynchronous. rc18 closes close-between-matches bot
        # connections while processing it, so no team relay may connect until
        # the master receives the matching configuration from our fresh core.
        acknowledged = threading.Event()
        expected = self.config_signature(config)
        master = self.manager.rlbot_interface
        def on_config(received):
            if self.config_signature(received) == expected:
                if self.capture is not None:
                    from .reference_capture import configuration_snapshot
                    actual = configuration_snapshot(received)
                    if actual != self.capture_configuration:
                        return
                    self.capture_configuration_ack = actual
                acknowledged.set()
        master.match_config_handlers.append(on_config)
        deadline = time.monotonic() + timeout
        try:
            self.check_cancel()
            self.manager.start_match(config, wait_for_start=False, ensure_server_started=False)
            while not acknowledged.wait(.05):
                self.check_cancel()
                if self.core.poll() is not None:
                    raise RuntimeError("The offline runtime exited before acknowledging the requested match.")
                if time.monotonic() >= deadline:
                    raise RuntimeError("The game did not acknowledge the requested match. Check your launcher and retry.")
            self.check_cancel()
        finally:
            master.match_config_handlers.remove(on_config)

    def setup(self):
        from .map_guard import refuse_custom_map_launch
        refuse_custom_map_launch(self.request)
        if sys.platform != "win32":
            raise RuntimeError("Game sessions run on Windows. Use the Windows installer on your gaming PC.")
        from rlbot.interface import SocketRelay
        from rlbot.managers.match import MatchManager
        from rlbot.managers.rendering import Renderer
        from . import adapter
        from .bots.providers import create_controller
        from .training import TrainingEngine
        from .training.recordings import validate_recording
        from .reference_capture import validate_capture_request
        self.check_cancel()
        # The capture gate runs here as well as inside adapter.match_config, so
        # neither entry point alone can reach a capture session.
        self.capture = validate_capture_request(self.request)
        preflight(self.owned)
        if self.capture is not None and self.owned is not None:
            self.game_version = game_file_version(self.owned.executable)
        # Heal a journal an older build already wrote, only after preflight says no game is open.
        # This does not copy a custom map or write a new journal.
        if self.request.get("data_dir"):
            from .map_guard import MapGuard
            self.map_guard = MapGuard(self.request["data_dir"])
            self.map_guard.recover()
        core_path()
        config, descriptors, self.human_index = adapter.match_config(self.request)
        self.human_team = config.player_configurations[self.human_index].team
        self.descriptors = descriptors
        # Ordinary sessions observe the Human. Capture observes only the
        # designated bot, and only after the mapping and packet checks below.
        self.training_actor_index = self.human_index
        self.capture_arena = config.game_map_upk
        if self.capture is not None:
            from .training.bot_reference import SpeedFlipTrialController
            from .reference_capture import configuration_snapshot
            self.capture_configuration = configuration_snapshot(config)
            if self.human_index != self.capture["human_index"] or self.capture["target_index"] not in descriptors:
                raise RuntimeError("The capture match layout is unexpected. No controls were sent.")
            self.training_actor_index = self.capture["target_index"]
            self.capture_controller = SpeedFlipTrialController(
                self.capture["profile"], self.capture["parameters"] or None)
            self.capture_metadata = {
                "source": {
                    "kind": "actual_execution",
                    "actor": "bot",
                    "actor_index": self.capture["target_index"],
                    "origin": "project-controlled offline bot",
                    "profile": self.capture["profile"],
                    "trial_id": self.capture["trial_id"],
                    "controller_plan": self.capture_controller.controller_plan(),
                    "label": self.capture["label"],
                    "provenance": self.capture["provenance"],
                },
                "permission": {"distribute": False},
            }
        if self.request.get("lesson_id"):
            variants = self.request.get("variants") or {}
            allowed = {key: variants[key] for key in ("side", "target_zone", "angle", "simplified") if key in variants}
            engine_metadata = {"framework_version": adapter.SDK_VERSION}
            if self.capture is not None:
                engine_metadata.update(self.capture_metadata)
            self.engine = TrainingEngine(self.request["lesson_id"], self.request.get("preferences"),
                                         metadata=engine_metadata, strict_capture=self.capture is not None,
                                         **allowed)
        from .training import GhostPlayback, GhostPractice, practice_context, practice_support
        from .training import coaching_preferences
        self.coaching_preferences = coaching_preferences(self.coaching_preferences)
        self.coach = GhostPlayback(mode=self.coaching_preferences["mode"],
            lead_seconds=self.coaching_preferences["lead_seconds"],
            speed=self.coaching_preferences["playback_speed"], loop=self.coaching_preferences["loop"])
        # Ghost practice is lesson-only. A career fixture never gets a ghost.
        if self.engine is not None:
            self.practice_support = practice_support(self.request["lesson_id"])
            self.practice = GhostPractice(context=practice_context(self.engine.lesson, self.engine.metadata))
        if self.capture is not None:
            # Development capture owns the only ghost control path: no practice
            # ghost and no legacy playback may run alongside it.
            self.practice = None
            self.practice_snapshot = {}
            self.practice_support = {"supported": False,
                                     "reason": "Ghost practice is unavailable during development capture."}
            self.legacy_playback = False
            self.engine.set_preference("ghost", False)
            self.engine.set_preference("auto_reset", False)
        if self.request.get("recording") is not None:
            validate_recording(self.request["recording"])
            self.recording = self.request["recording"]
        self.event("session", state="starting", message="Loading the selected offline bots.")
        if self.capture is None:
            for index, descriptor in descriptors.items():
                self.check_cancel()
                self.controllers[index] = create_controller(self.request.get("provider", "mct-specialist-baseline"),
                    descriptor.get("role", "all-rounder"), descriptor["level"], descriptor["difficulty"], descriptor["seed"])
                self.check_cancel()
        runtime = Path(self.request["data_dir"]).resolve() / "runtime" / self.session_id
        runtime.mkdir(parents=True, exist_ok=True)
        port = free_port()
        # Recheck just before the core launches: the Epic launch route may close
        # game processes globally, so attaching to a preexisting game is forbidden.
        executable = self.spawn_core(runtime, port)
        self.event("session", state="starting", message="Connecting to the offline bot service.")
        self.manager = MatchManager(executable)
        self.manager.rlbot_interface = isolated_relay(self.manager.rlbot_interface)
        master = self.manager.rlbot_interface
        master.connection_timeout = 8
        master.packet_handlers.append(lambda packet: self.events.put(("packet", packet)))
        master.field_info_handlers.append(lambda field: self.events.put(("field", field)))
        master.ball_prediction_handlers.append(lambda prediction: self.events.put(("prediction", prediction)))
        self.connect(self.manager.connect, master, port, predictions=True)
        self._relay_thread(master)
        self.renderer = Renderer(master)
        self.renderer._used_group_ids = set()
        self.renderer._current_renders = []
        self.event("session", state="starting", message="Asking Rocket League to open the offline match.")
        self.start_acknowledged_match(config)
        for team in sorted({value["team"] for value in descriptors.values()}):
            relay = isolated_relay(SocketRelay(f"my-career-training/team-{team}", connection_timeout=8))
            relay.controllable_team_info_handlers.append(
                lambda info, expected=team: self.events.put(("mapping", (expected, info))))
            self.connect(relay.connect, relay, port)
            self.relays[team] = relay
            self._relay_thread(relay)
        self.event("session", state="starting", message="Waiting for Rocket League to start the offline session.")

    def _discover_game(self):
        from .platforms import owned_game_since
        if self.owned is None:
            self.owned = owned_game_since(self.started, self.request.get("settings", {}).get("install_path", ""))
            if self.owned:
                self.game_version = game_file_version(self.owned.executable)
                self.event("owned_game", identity=self.owned.as_dict())

    def map_team(self, team, info):
        expected = sorted(index for index, descriptor in self.descriptors.items() if descriptor["team"] == team)
        assigned = sorted(item.index for item in info.controllables)
        if info.team != team or assigned != expected or self.human_index in assigned:
            # Any invalid mapping withdraws capture control before the raise, so
            # no later packet can send inputs on a stale mapping.
            self._abort_capture("The game returned an unexpected bot-control mapping.")
            raise RuntimeError("The game returned an unexpected bot-control mapping. No human controls were sent.")
        if self.capture is not None:
            # Capture needs exactly the designated bot on its known team, and the
            # Human must never appear in a bot-control mapping.
            target = self.capture["target_index"]
            if team != self.descriptors[target]["team"] or assigned != [target]:
                self._abort_capture("The capture bot mapping changed.")
                raise RuntimeError("The game returned an unexpected capture mapping. No controls were sent.")
            if self.capture_ready and self.mapping.get(team) != assigned:
                self._abort_capture("The capture bot mapping changed.")
                raise RuntimeError("The capture bot mapping changed. No controls were sent.")
        self.mapping[team] = assigned
        if self.capture is not None and team == self.descriptors[self.capture["target_index"]]["team"]:
            self.capture_ready = True
        # rc18 records readiness only for agents already reserved by this mapping.
        # Sending InitComplete on socket-connect can arrive before reservation and
        # leave wait_for_agents pending forever.
        if team not in self.ready_teams and not self.cancel_start.is_set() and not self.stopping:
            from rlbot import flat
            self.relays[team].send_msg(flat.InitComplete())
            self.ready_teams.add(team)

    def reset(self):
        if self.cancel_start.is_set() or self.stopping:
            return
        if self.capture is not None:
            from .reference_capture import recheck_capture
            target = self.capture["target_index"]
            team = self.descriptors[target]["team"]
            if (self.capture_aborted is not None or not self.capture_ready
                    or self.mapping.get(team) != [target]):
                raise RuntimeError("Capture cannot reset after its bot mapping was lost or capture stopped.")
            recheck_capture(self.capture)
        from .adapter import desired_state
        if self.engine is None:
            raise RuntimeError("Retry is available during a training lesson.")
        if self.attempt_sent and not self.attempt_acked:
            raise RuntimeError("The previous attempt is still being saved. Wait before retrying.")
        settle_state = self.engine.reset()
        self.manager.rlbot_interface.send_msg(desired_state(settle_state, self.training_actor_index))
        self.applied_reset = True
        self.attempt_sent = None
        self.attempt_acked = False
        self.attempt_retryable = False
        self.auto_reset_at = None
        self.playback_origin = None
        if self.capture_controller is not None:
            # A retry restarts the candidate schedule from its beginning.
            self.capture_controller.reset()
            self.capture_aborted = None
        if self.coach:
            self.coach.restart()
        if self.practice is not None and self.practice.available and self.practice.enabled:
            # A retry restarts the demonstration from its beginning, anchored to
            # the reset pose the game is about to apply, not the pre-reset pose.
            reset_car = settle_state["car"]
            self.practice_snapshot = self.practice.set_enabled(
                True, player_pose={"position": reset_car.get("position"),
                                   "rotation": reset_car.get("rotation")})
        self.event("session", state="training", message="Settling the car before the drill.")

    def _player_pose(self):
        """Current human car pose from the last normalized frame, or None."""
        frame = self.last_frame
        car = (frame or {}).get("car")
        if not isinstance(car, dict):
            return None
        return {"position": car.get("position"), "rotation": car.get("rotation")}

    def _toggle_practice(self, enabled):
        """Deterministic ghost-practice toggle; lesson-only and recording-gated."""
        if self.practice is None:
            raise ValueError("Ghost practice is available only during a training lesson.")
        if enabled is None:
            enabled = not self.practice.enabled
        if not isinstance(enabled, bool):
            raise ValueError("Ghost practice must be on or off.")
        if enabled and not self.practice_support.get("supported"):
            raise ValueError(self.practice_support.get("reason")
                             or "This lesson does not support ghost practice.")
        if enabled and not self.practice.available:
            raise ValueError("Choose an available recording before turning on ghost practice.")
        self.practice_snapshot = self.practice.set_enabled(enabled, player_pose=self._player_pose())
        # The new practice toggle takes over from any legacy playback; Off must
        # never fall back to drawing the legacy coach ghost.
        self.legacy_playback = False
        # The training assistance ghost setting must agree with practice state.
        if self.engine is not None and self.engine.preferences.get("ghost") != enabled:
            self.engine.set_preference("ghost", enabled)
        return self.practice_snapshot

    def _ack_ghost(self, command, *, accepted, **fields):
        """Exact per-command acknowledgement for ghost commands.

        The bridge matches this id and session before changing any UI state, so
        a rejection can never leave an optimistic On behind.
        """
        command_id = command.get("id")
        if not isinstance(command_id, str) or not command_id:
            return
        self.event("ghost_ack", id=command_id, accepted=bool(accepted), **fields)

    def handle_command(self, command):
        kind = command.get("type", command.get("command"))
        if self.capture is not None and kind in {"ghost_control", "play_recording"}:
            # Development capture owns the only ghost control path. Reject the
            # command with an explicit failed acknowledgement before any
            # playback or practice state changes, so no double ghost control
            # can exist alongside the capture trial.
            message = "Ghost practice and recorded playback are unavailable during development capture."
            self._ack_ghost(command, accepted=False, error=message)
            # Mark the command so the run loop does not acknowledge it twice.
            command["_capture_ack"] = True
            raise ValueError(message)
        if kind in {"stop", "shutdown"}:
            self.stop_id = command.get("id")
            self.stopping = True
            self.stop_deadline = time.monotonic() + .2
        elif kind in {"retry", "retry_lesson"}:
            self.reset()
        elif kind == "attempt_ack":
            if command.get("attempt_id") == self.attempt_sent:
                self.attempt_acked = True
                if (self.engine and self.engine.preferences["auto_reset"]
                        and self.attempt_retryable and self.auto_reset_at is None):
                    # Keep the saved feedback visible for at least one second
                    # before the automatic reset, instead of resetting instantly.
                    # A repeated acknowledgement never postpones that deadline.
                    self.auto_reset_at = time.monotonic() + 1.0
        elif kind == "preferences" and self.engine:
            preferences = command.get("preferences", {})
            if "key" in command:
                preferences = {command["key"]: command["value"]}
            if self.capture is not None and (preferences.get("auto_reset") is True
                                             or preferences.get("ghost") is True):
                raise ValueError("Development capture requires explicit retries with playback disabled.")
            for key, value in preferences.items():
                self.engine.set_preference(key, value)
            # The assistance ghost setting and practice visibility stay in step.
            if "ghost" in preferences and self.practice is not None:
                if preferences["ghost"] is False:
                    self.practice_snapshot = self.practice.set_enabled(False)
                    self.legacy_playback = False
                elif self.practice.available and self.practice_support.get("supported"):
                    self.practice_snapshot = self.practice.set_enabled(True, player_pose=self._player_pose())
        elif kind == "coaching":
            from .training import coaching_preferences
            self.coaching_preferences = coaching_preferences(command.get("preferences", {}))
            self.coach.set_mode(self.coaching_preferences["mode"], self.coaching_preferences["lead_seconds"])
            self.coach.set_speed(self.coaching_preferences["playback_speed"])
            self.coach.set_loop(self.coaching_preferences["loop"])
        elif kind == "ghost_control":
            if not self.coach:
                raise ValueError("Start a lesson before controlling its ghost.")
            operation, value = command.get("operation"), command.get("value")
            if operation == "toggle":
                self._toggle_practice(command.get("enabled"))
                self._ack_ghost(command, accepted=True, enabled=self.practice_snapshot.get("enabled"))
                return
            elif operation == "pause":
                self.coach.pause()
            elif operation == "resume":
                self.coach.resume()
            elif operation == "stop":
                self.coach.stop()
                self.legacy_playback = False
                if self.practice is not None:
                    # Refresh immediately so no stale pose/lines/controller render.
                    self.practice_snapshot = self.practice.set_enabled(False)
            elif operation == "restart":
                self.coach.restart()
            elif operation == "seek":
                self.coach.seek(float(value))
            elif operation == "speed":
                self.coach.set_speed(float(value))
            elif operation == "loop":
                self.coach.set_loop(bool(value))
            elif operation == "mode":
                self.coach.set_mode(str(value))
            else:
                raise ValueError("Unknown ghost playback control.")
        elif kind == "play_recording":
            from .training.recordings import validate_recording
            if self.engine is None:
                raise ValueError("Recorded ghosts are available only during a training lesson.")
            # The bridge adds this internal flag: True only for an explicit
            # native recording_id, False for the legacy automatic best attempt.
            # Direct worker callers that omit it keep the new practice flow.
            practice = command.get("practice", True)
            if not isinstance(practice, bool):
                raise ValueError("Ghost practice must be on or off.")
            recording = command["recording"]
            validate_recording(recording)
            mode = command.get("mode", self.coaching_preferences["mode"])
            lead_seconds = float(command.get("lead_seconds", self.coaching_preferences["lead_seconds"]))
            # Validate the complete recording and its context on temporary
            # players first, so a rejection leaves both previously loaded
            # players and the practice snapshot exactly as they were.
            from .training import GhostPlayback, GhostPractice, practice_context
            context = practice_context(self.engine.lesson, self.engine.metadata)
            coach = GhostPlayback(mode=self.coach.mode if self.coach else "watch",
                lead_seconds=self.coach.lead_seconds if self.coach else .75,
                speed=self.coach.speed if self.coach else 1.0,
                loop=self.coach.loop if self.coach else False)
            coach.load(recording, kind="personal", context=context)
            coach.set_mode(mode, lead_seconds)
            practice_player = None
            if practice:
                practice_player = GhostPractice(context=context)
                practice_player.load(recording, kind="personal")
            self.recording = recording
            self.coach = coach
            self.coach.resume()
            self.playback_origin = self.last_frame["time"] if self.last_frame else None
            self.legacy_playback = not practice
            if practice_player is not None:
                # Selecting a recording makes practice available but leaves it
                # off until the player turns it on. The context is rebuilt from
                # the latest observed metadata, because the start-time context
                # may still have unknown game/hitbox values.
                self.practice = practice_player
                self.practice_snapshot = self.practice.snapshot()
                self.engine.set_preference("ghost", False)
            elif self.practice is not None:
                # Selecting legacy playback must not leave the previously active
                # practice recording in front of the newly selected coach.
                self.practice_snapshot = self.practice.set_enabled(False)
            self._ack_ghost(command, accepted=True,
                            available=self.practice.available
                            if practice and self.practice is not None else False,
                            label=(self.practice_snapshot.get("label", "Recording loaded")
                                   if practice else self.coach.snapshot().get("label", "Recording loaded")))
        else:
            raise ValueError("Unknown game-session command.")

    def _abort_capture(self, reason):
        """Stop capture control immediately; the Human is never moved."""
        if self.capture is None:
            return
        self.capture_ready = False
        self.mapping.clear()
        # With an invalid mapping we cannot safely send even a neutral input.
        # End this owned session so teardown stops its runtime instead of
        # leaving the last bot input held indefinitely.
        self.stopping = True
        self.stop_deadline = 0
        if self.capture_aborted is None:
            self.capture_aborted = reason
            if self.capture_controller is not None:
                self.capture_controller.finish()
            self.event("error", message=f"Reference capture stopped: {reason}")

    def _capture_actions(self, frame):
        """Neutral unless the engine is active with a known Go time."""
        from .reference_capture import neutral_actions
        if self.capture_aborted is not None or self.capture_controller is None:
            return neutral_actions()
        if self.engine is None or self.engine.state != "active" or self.engine.started_at is None:
            return neutral_actions()
        elapsed = frame["time"] - self.engine.started_at
        return self.capture_controller.step(elapsed, frame)

    def _capture_controls(self, frame, flat):
        """Send inputs only to the mapped capture bot, never to the Human.

        The marker, the mapping and the Human clearance are rechecked at every
        control boundary; any change aborts capture instead of sending inputs.
        """
        from .reference_capture import recheck_capture
        target = self.capture["target_index"]
        team = self.descriptors[target]["team"]
        if self.capture_aborted is not None or not self.capture_ready:
            return
        if self.mapping.get(team) != [target]:
            self._abort_capture("The capture bot mapping changed.")
            return
        car = frame["cars"][target]
        if car.get("is_bot") is not True or car.get("team") != team:
            self._abort_capture("The capture target is not the designated bot.")
            return
        if not self._capture_human_clear(frame):
            self._abort_capture("The Human entered the capture corridor.")
            return
        try:
            recheck_capture(self.capture)
        except ValueError as error:
            self._abort_capture(str(error))
            return
        actor_frame = dict(frame, car=car, actions=car["actions"])
        actions = self._capture_actions(actor_frame)
        if self.cancel_start.is_set() or self.stopping:
            return
        self.relays[team].send_msg(flat.PlayerInput(target, flat.ControllerState(**actions)))

    def _capture_human_clear(self, frame):
        """True while the Human stays outside the capture corridor."""
        from .reference_capture import HUMAN_CLEARANCE
        target = self.capture["target_index"]
        human = frame["cars"][self.human_index]
        bot = frame["cars"][target]
        dx = human["position"][0] - bot["position"][0]
        dy = human["position"][1] - bot["position"][1]
        return math.hypot(dx, dy) >= HUMAN_CLEARANCE

    def _capture_metadata(self, packet, frame):
        """Observed setup facts only; requested mutators are annotated as such."""
        from . import adapter
        target = self.capture["target_index"]
        lesson = getattr(self.engine, "lesson", None)
        starting_state = lesson.get("starting_state") if isinstance(lesson, dict) else None
        source = {
            "kind": "actual_execution",
            "actor": "bot",
            "actor_index": target,
            "origin": "project-controlled offline bot",
            "profile": self.capture["profile"],
            "trial_id": self.capture["trial_id"],
            "controller_plan": (self.capture_controller.controller_plan()
                                if self.capture_controller is not None else None),
            "label": self.capture["label"],
            "provenance": self.capture["provenance"],
        }
        return {
            "source": source,
            "permission": {"distribute": False},
            "game_version": self.game_version,
            "framework_version": adapter.SDK_VERSION,
            "car_hitbox": observed_hitbox(packet.players[target]),
            "map": self.capture_arena,
            "observed_game_speed": frame.get("game_speed"),
            "starting_state": starting_state,
            "mutators": {
                "source": "rlbot_match_configuration",
                "requested": self.capture_configuration,
                "acknowledged": self.capture_configuration_ack,
            },
        }

    def process_packet(self, packet):
        from rlbot import flat
        from . import adapter
        self._discover_game()
        if self.owned is None:
            return  # Never accept packets or control from an unowned game.
        phase = int(packet.match_info.match_phase)
        if not self.seen_active and phase == 0:
            return  # The owned game may still be loading the requested match.
        # Core spawns asynchronously. Inspect the cheap roster before normalizing
        # physics; incomplete pre-Active records may not contain usable bodies.
        players = getattr(packet, "players", None)
        if not self.seen_active and phase != 3 and players is not None and len(players) != len(self.descriptors) + 1:
            return
        frame = adapter.normalized_packet(packet, self.prediction, self.field_info)
        humans = [car for car in frame["cars"] if not car["is_bot"]]
        human_valid = (len(humans) == 1 and humans[0]["index"] == self.human_index
                       and humans[0]["team"] == self.human_team)
        count_valid = len(frame["cars"]) == len(self.descriptors) + 1
        bots_valid = count_valid and all(frame["cars"][index]["is_bot"]
            and frame["cars"][index]["team"] == descriptor["team"]
            for index, descriptor in self.descriptors.items())
        if not (human_valid and count_valid and bots_valid):
            if not self.seen_active and phase != 3:
                return  # Existing startup timeout still bounds this wait.
            self._abort_capture("The observed player layout changed.")
            if not human_valid:
                raise RuntimeError("The game has an unexpected human-player layout. Controls were withheld.")
            if not count_valid:
                raise RuntimeError("The game player count differs from the selected fixture.")
            raise RuntimeError("The game bot layout differs from the selected fixture.")
        if packet.match_info.match_phase == flat.MatchPhase.Active:
            self.seen_active = True
        if not self.first_packet:
            self.first_packet = True
            self.event("session", state="training" if self.engine else "running", message="Offline game connected.")
        now = time.monotonic()
        frame["match_ended"] = packet.match_info.match_phase == flat.MatchPhase.Ended
        if (phase in {2, 3} and not self.cancel_start.is_set() and not self.stopping
                and now - self.last_controls >= 1 / 120):
            if self.capture is not None:
                # Capture drives only the designated bot through its own relay.
                self._capture_controls(frame, flat)
            else:
                intents = [controller.intent for controller in self.controllers.values() if controller.intent]
                for team, indices in self.mapping.items():
                    for index in indices:
                        actions = self.controllers[index].step(frame, index, intents)
                        if not self.cancel_start.is_set() and not self.stopping:
                            self.relays[team].send_msg(flat.PlayerInput(index, flat.ControllerState(**actions)))
            self.last_controls = now
        human = humans[0]
        # The engine observes the Human in every normal mode and the designated
        # capture bot only in the development capture mode.
        actor = frame["cars"][self.training_actor_index] if self.capture is not None else human
        prior = self.last_frame
        # The shared classifier decides cadence once for the worker and the
        # engine. Normal human training accepts a continuous two-step (60 Hz)
        # sample; strict reference capture requires one physics step per packet.
        # An explicit transport gap is preserved, never reclassified.
        from .training.cadence import classify_cadence
        cadence = classify_cadence(
            prior, frame,
            max_packet_interval=(self.engine.tolerances["max_packet_interval"]
                                 if self.engine is not None else 0.05),
            strict=self.capture is not None)
        frame.update(car=actor, actions=actor["actions"],
                     dt=frame["time"] - prior["time"] if prior else 0,
                     packet_gap=bool(frame.get("packet_gap")) or cadence["gap"],
                     cadence=cadence["reason"])
        self.last_frame = frame
        if self.engine and not self.cancel_start.is_set() and not self.stopping:
            if self.capture is not None and (self.capture_aborted is not None or not self.capture_ready):
                return
            if self.capture is not None:
                metadata = self._capture_metadata(packet, frame)
            else:
                metadata = {"game_version": self.game_version,
                            "car_hitbox": observed_hitbox(packet.players[self.human_index])}
            self.engine.metadata.update(metadata)
            self.engine.recorder.metadata.update(metadata)
            if not self.applied_reset:
                self.reset()
            else:
                for event in self.engine.update(frame):
                    if event["type"] == "set_state" and not self.cancel_start.is_set():
                        self.manager.rlbot_interface.send_msg(
                            adapter.desired_state(event["state"], self.training_actor_index))
                    elif event["type"] == "completed":
                        self.publish_attempt()
                    else:
                        self.event("training_event", event=event)
            if self.engine.finished:
                self.publish_attempt()
            if now - self.last_render >= 1 / 30:
                self.render(frame)
                self.last_render = now
        observed_scores = adapter.observed_score(packet)
        if not self.engine and not self.request.get("workshop"):
            self.review.update(frame, observed_scores)
            scores = adapter.final_score(packet, self.seen_active)
            if scores is not None and not self.result_sent:
                result = {"type": "result", "session_id": self.session_id,
                          "fixture_id": self.request["fixture"]["id"], "home_score": scores[0],
                          "away_score": scores[1], "provenance": "game",
                          "calibration": bool(self.request.get("calibration", False)),
                          "review": self.review.summary()}
                persist_result(self.request["data_dir"], result)
                self.result_sent = True
                self.emit(result)
                self.event("session", state="completed", message="Final score received from the game.")
        if self.engine and self.coach and not self.cancel_start.is_set() and not self.stopping:
            self.coach_snapshot = self.coach.update(frame["time"], attempt_seconds=(
                None if self.engine.started_at is None else frame["time"] - self.engine.started_at))
        if self.practice is not None and not self.cancel_start.is_set() and not self.stopping:
            self.practice_snapshot = self.practice.update(frame["time"], player_pose=self._player_pose())
        if now - self.last_telemetry >= 1 / 30:
            capture_telemetry = None
            if self.capture is not None:
                from .reference_capture import telemetry as capture_telemetry_event
                capture_telemetry = capture_telemetry_event(
                    self.capture, active=self.capture_aborted is None and self.capture_ready,
                    target_index=self.capture["target_index"], aborted=self.capture_aborted)
                # Development-only observed facts for diagnosing a blocked
                # reset. These do not relax the lesson's verification gates.
                capture_telemetry.update(
                    engine_state=self.engine.state if self.engine else None,
                    applied_reset=self.applied_reset,
                    packet_gap=frame["packet_gap"], dt=frame["dt"],
                    frame_step=((frame["frame_num"] - prior["frame_num"]) % (2**32)
                                if prior is not None else None),
                    settle_start=getattr(self.engine, "settle_start", None),
                    actor={key: actor[key] for key in (
                        "position", "velocity", "rotation", "angular_velocity",
                        "boost", "wheel_contact", "air_state", "has_jumped",
                        "has_double_jumped", "has_dodged", "actions") if key in actor})
            self.event("telemetry", time=frame["time"], car=human, ball=frame["ball"], actions=human["actions"],
                       frame_num=frame["frame_num"], phase=str(packet.match_info.match_phase),
                       scores=list(observed_scores) if observed_scores is not None else [], ghost=self.coach_snapshot,
                       ghost_practice=self.practice_snapshot,
                       ghost_practice_support=dict(self.practice_support),
                       reference_capture=capture_telemetry,
                       coaching=(self.engine.summary().get("coaching", {}) if self.engine and not self.cancel_start.is_set() and not self.stopping else {}))
            self.last_telemetry = now

    def publish_attempt(self):
        summary = self.engine.summary()
        if self.attempt_sent == summary["id"]:
            return
        recording = self.engine.recording()
        # An interrupted pre-start attempt has no samples and cannot be replayed.
        if not recording.get("samples"):
            recording = None
        self.attempt_sent = summary["id"]
        self.attempt_acked = False
        # Only an attempt with observed samples may be retried automatically; a
        # pre-start interruption must not spin the reset path.
        self.attempt_retryable = bool(recording and recording.get("samples"))
        self.auto_reset_at = None
        if self.capture is not None and recording is not None and getattr(self.engine, "finished", False):
            # Persist only a trial the engine actually completed; an unfinished
            # or imported claim never becomes a candidate.
            self._persist_candidate(summary, recording)
        self.event("attempt", summary=summary, recording=recording)

    def _persist_candidate(self, summary, recording):
        from .reference_capture import persist_candidate
        try:
            receipt = persist_candidate(self.capture["data_dir"], self.capture, summary["id"],
                                        recording, summary, self.engine.recorder.metadata)
        except (ValueError, OSError) as error:
            self.event("error", message=f"The reference candidate was not saved: {error}")
            return None
        self.event("reference_candidate", receipt=receipt, label=self.capture["label"],
                   provenance=self.capture["provenance"], gate="not-evaluated")
        return receipt

    def render(self, frame):
        if self.cancel_start.is_set() or self.stopping or not self.renderer.can_render:
            return
        from rlbot import flat
        renderer, preferences = self.renderer, self.engine.preferences
        # One summary snapshot per render keeps the HUD consistent and cheap.
        summary = self.engine.summary()
        coaching = summary.get("coaching") or {}
        with renderer.context("my-career-training"):
            if preferences["explanations"]:
                renderer.draw_string_2d(self.engine.lesson["title"], .03, .05, 1.2)
                for index, step in enumerate(self.engine.lesson["steps"][:6]):
                    text = step if isinstance(step, str) else step.get("text", step.get("title", str(step)))
                    renderer.draw_string_2d(text, .03, .09 + index * .032, .8)
                for target in self.engine.lesson["targets"]:
                    self.draw_target(target)
            if preferences["actions"]:
                labels = [key.title() for key, value in frame["actions"].items() if abs(value) > .2]
                renderer.draw_string_2d("You: " + (", ".join(labels) or "neutral"), .03, .31, 1)
            if preferences["timing"]:
                # A completed attempt keeps its saved duration; a live attempt
                # uses the observed game clock. Before "go" the drill is
                # preparing, and an interrupted pre-start attempt says so.
                if self.engine.started_at is None:
                    label = "Interrupted" if self.engine.state == "interrupted" else "Preparing"
                    renderer.draw_string_2d(label, .03, .35, 1)
                elif self.engine.finished:
                    renderer.draw_string_2d(
                        f"{self.engine.state.title()}  {summary['duration']:.2f}s", .03, .35, 1)
                else:
                    duration = max(0, frame["time"] - self.engine.started_at)
                    renderer.draw_string_2d(f"{self.engine.state.title()}  {duration:.2f}s", .03, .35, 1)
            message = coaching.get("message")
            interrupted = self.engine.state == "interrupted"
            if interrupted:
                # The actual interruption reason is always actionable, even when
                # step-by-step explanations are turned off.
                message = coaching.get("interruption_reason") or summary.get("feedback") or message
            if message and (preferences["explanations"] or interrupted):
                renderer.draw_string_2d(str(message)[:110], .03, .40, .8)
            stages = coaching.get("stages") or []
            next_stage = coaching.get("next_stage")
            if (preferences["explanations"] and isinstance(next_stage, int)
                    and 0 <= next_stage < len(stages)):
                stage = stages[next_stage]
                renderer.draw_string_2d(
                    f"Stage {next_stage + 1}/{len(stages)}: {stage.get('title', '')}", .03, .44, .8)
            practice = self.practice_snapshot or {}
            if practice.get("visible"):
                # Render-only lines; no collision actor is created for the ghost.
                for line in practice.get("lines", []):
                    color = renderer.yellow if line["style"] == "front" else renderer.cyan
                    renderer.draw_line_3d(flat.Vector3(*line["start"]), flat.Vector3(*line["end"]), color)
                renderer.draw_string_2d("GHOST \u00b7 " + practice.get("label", "Recorded attempt"), .03, .49, .8)
                self.draw_ghost_actions(practice)
            elif (self.practice is None or self.legacy_playback) and preferences["ghost"] and self.coach_snapshot.get("visible"):
                for line in self.coach_snapshot.get("lines", []):
                    color = renderer.yellow if line["style"] == "front" else renderer.cyan
                    renderer.draw_line_3d(flat.Vector3(*line["start"]), flat.Vector3(*line["end"]), color)
                renderer.draw_string_2d(self.coach_snapshot.get("label", "Recorded attempt"), .03, .49, .8)

    def draw_ghost_actions(self, practice):
        """Ghost HUD from recorded logical actions; never raw DS4 axes/buttons."""
        renderer = self.renderer
        controller = practice.get("controller") or {}
        if not controller.get("observed"):
            renderer.draw_string_2d("GHOST inputs unavailable", .03, .53, .8)
            return
        parts = []
        for item in controller.get("active_actions") or []:
            # controller_display emits {action,label,control,value} records.
            if isinstance(item, dict):
                label, value = item.get("label"), item.get("value")
                if isinstance(label, str) and isinstance(value, (int, float)):
                    parts.append(f"{label} {value:+.2f}")
            elif isinstance(item, str):
                parts.append(item)
        renderer.draw_string_2d("GHOST inputs: " + (", ".join(parts) or "neutral"), .03, .53, .8)
        renderer.draw_string_2d("Recorded logical actions, not raw controller capture", .03, .57, .7)

    def draw_target(self, target):
        from rlbot import flat
        renderer = self.renderer
        lines = []
        if target["type"] == "gate":
            x, y, z = target["position"]
            radius = target["radius"]
            points = [[x + radius * math.cos(i * math.tau / 24), y,
                       z + radius * math.sin(i * math.tau / 24)] for i in range(25)]
            lines = list(zip(points, points[1:]))
        elif target["type"] == "goal":
            left, right = target["center_x"] - target["half_width"], target["center_x"] + target["half_width"]
            points = [[left, 5110, target["min_z"]], [right, 5110, target["min_z"]],
                      [right, 5110, target["max_z"]], [left, 5110, target["max_z"]]]
            lines = list(zip(points, points[1:] + points[:1]))
        elif target["type"] == "plane":
            axis = target["axis"]
            if axis == 1:
                half = target["width"] / 2
                points = [[-half, target["value"], 0], [half, target["value"], 0],
                          [half, target["value"], target["height"]], [-half, target["value"], target["height"]]]
                lines = list(zip(points, points[1:] + points[:1]))
        for start, end in lines:
            renderer.draw_line_3d(flat.Vector3(*start), flat.Vector3(*end), renderer.lime)

    def teardown(self):
        if self.manager and self.manager.rlbot_interface.is_connected:
            try:
                self.manager.rlbot_interface.stop_match(shutdown_server=True)
            except (OSError, AssertionError):
                pass
        self.stop_owned_core()
        relays = list(self.relays.values())
        if self.manager:
            relays.append(self.manager.rlbot_interface)
        for relay in relays:
            relay._running = False
            relay.is_connected = False
            if relay.socket:
                try:
                    relay.socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                relay.socket.close()
        for thread in self.threads:
            thread.join(timeout=.2)
        if self.map_guard:
            self.map_guard.recover()
        self.cleanup_complete = True

    def run(self):
        self.event("session", state="starting", message="Checking the game installation and offline runtime.")
        try:
            self.setup()
            while not self.stopping or time.monotonic() < self.stop_deadline:
                self._discover_game()
                if self.core.poll() is not None:
                    raise RuntimeError("The offline game runtime exited. Close the game and retry.")
                if not self.first_packet and time.monotonic() - self.started_monotonic > 120:
                    raise RuntimeError("Rocket League did not connect within two minutes. Check launcher setup and retry.")
                if self.auto_reset_at is not None and time.monotonic() >= self.auto_reset_at:
                    # The saved feedback stayed visible for at least one second.
                    self.auto_reset_at = None
                    if (self.engine and self.engine.preferences["auto_reset"]
                            and self.attempt_acked and self.attempt_retryable
                            and not self.cancel_start.is_set() and not self.stopping):
                        try:
                            self.reset()
                        except (ValueError, RuntimeError) as error:
                            self.event("error", message=str(error))
                try:
                    kind, value = self.events.get(timeout=.1)
                except queue.Empty:
                    continue
                if kind == "packet":
                    self.process_packet(value)
                elif kind == "mapping":
                    self.map_team(*value)
                elif kind == "field":
                    self.field_info = value
                elif kind == "prediction":
                    self.prediction = value
                elif kind == "command":
                    try:
                        self.handle_command(value)
                    except (ValueError, RuntimeError, KeyError) as error:
                        if (value.get("type", value.get("command")) in {"ghost_control", "play_recording"}
                                and not value.get("_capture_ack")):
                            # A safe rejection for exactly this command; the
                            # bridge reverts any optimistic state on it.
                            self._ack_ghost(value, accepted=False, error=str(error))
                        self.event("error", message=str(error))
                elif kind == "disconnected" and not self.stopping:
                    raise RuntimeError("The offline game connection ended. Your completed results remain saved.")
        except SessionCancelled:
            pass
        except Exception as error:
            if not self.cancel_start.is_set():
                self.event("error", message=str(error))
                self.event("session", state="error", message="The offline session could not continue.")
        finally:
            try:
                self.teardown()
            except Exception:
                logging.exception("Owned core cleanup failed")
                self.event("error", message="The offline helper did not confirm cleanup. Keep the app open and retry stopping.")
            else:
                self.event("stopped", id=self.stop_id)


class Worker:
    def __init__(self, output=None, session_factory=GameSession):
        self.output = output or sys.stdout
        self.session_factory = session_factory
        self.session = None
        self.lock = threading.Lock()
        self.closed = False

    def emit(self, event):
        with self.lock:
            self.output.write(json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n")
            self.output.flush()

    def command(self, command):
        if not isinstance(command, dict):
            raise ValueError("Worker commands must be JSON objects.")
        kind = command.get("type", command.get("command"))
        sid = self.session.session_id if self.session else None
        if kind == "ping":
            self.emit({"type": "pong", "id": command.get("id"), "session_id": sid})
        elif kind == "start":
            if self.session and self.session.thread.is_alive():
                raise RuntimeError("An offline session is already running.")
            from .map_guard import refuse_custom_map_launch
            # Before the session object, its thread, RLBot, or any game-file journal.
            refuse_custom_map_launch(command)
            self.session = self.session_factory(command, self.emit)
            self.session.thread.start()
        elif kind in {"stop", "shutdown"}:
            if command.get("session_id") not in (None, sid):
                raise ValueError("The command refers to a different session.")
            if self.session and self.session.thread.is_alive():
                self.session.command(command)
                if kind == "shutdown":
                    self.session.thread.join(timeout=28)
                    self.session.stop_owned_core()
                    if self.session.thread.is_alive():
                        self.session.exit_blocked_pre_core_worker()
                        # A post-core thread may still be persisting a real
                        # result. Keep it alive rather than cut off that write.
                        self.emit({"type": "error", "session_id": sid,
                            "message": "The worker is still finishing cleanup or saving a result. Keep the app open."})
                        return
                    if not self.session.cleanup_complete:
                        self.session.teardown()
                        self.emit({"type": "stopped", "id": command.get("id"), "session_id": sid})
            else:
                if self.session and not self.session.cleanup_complete:
                    self.session.teardown()
                self.emit({"type": "stopped", "id": command.get("id"), "session_id": sid})
            self.closed = kind == "shutdown"
        elif self.session and self.session.thread.is_alive():
            supplied = command.get("session_id")
            if supplied is not None and supplied != sid:
                raise ValueError("The command refers to a different session.")
            self.session.command(command)
        else:
            raise RuntimeError("Start an offline game session first.")

    def run(self, source=None):
        self.emit({"type": "ready", "protocol": PROTOCOL, "session_id": None})
        for line in source or sys.stdin:
            try:
                if len(line) > MAX_COMMAND:
                    raise ValueError("The worker command exceeds its size limit.")
                self.command(json.loads(line))
            except (ValueError, RuntimeError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
                self.emit({"type": "error", "session_id": self.session.session_id if self.session else None,
                           "message": str(error)})
            if self.closed:
                break
        if self.session and not self.closed:
            self.finish_after_eof()
        return 0

    def finish_after_eof(self):
        # The host cannot retry commands after EOF. Retain ownership until the
        # exact core is gone and any final receipt writer/cleanup has finished.
        # Do not emit acknowledgments onto a pipe the host may already close.
        self.session.command({"type": "shutdown"})
        self.session.thread.join(timeout=28)
        reported = False
        while not self.closed:
            try:
                self.session.stop_owned_core()
                if self.session.thread.is_alive():
                    self.session.exit_blocked_pre_core_worker()
                    self.session.thread.join()
                if not self.session.cleanup_complete:
                    self.session.teardown()
                self.closed = True
            except Exception:
                if not reported:
                    logging.exception("Waiting for owned worker cleanup after the host closed")
                    reported = True
                time.sleep(1)


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    if sys.platform == "win32":
        # NumPy's first Windows import can deadlock against a concurrent pipe
        # read (numpy/numpy#24290). Initialize only in this worker, before ready
        # and the stdin loop; model construction can then stay on its thread.
        importlib.import_module("numpy")
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
