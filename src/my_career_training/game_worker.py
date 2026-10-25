"""Isolated JSON-lines game process. SDK and native game imports are lazy.

The owned core is the only process this module may terminate. Rocket League
closure is delegated to the app's identity-scoped window-close transition.
"""
from __future__ import annotations

from collections import deque
import hashlib
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
        self.coaching_preferences = request.get("coaching", {})
        self.engine = None
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
            self.stop_id = command.get("id")
            self.cancel_start.set()
        self.events.put(("command", command))

    def check_cancel(self):
        if self.cancel_start.is_set():
            raise SessionCancelled()

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
        self.check_cancel()
        preflight(self.owned)
        # Heal a journal an older build already wrote, only after preflight says no game is open.
        # This does not copy a custom map or write a new journal.
        if self.request.get("data_dir"):
            from .map_guard import MapGuard
            self.map_guard = MapGuard(self.request["data_dir"])
            self.map_guard.recover()
        executable = core_path()
        config, descriptors, self.human_index = adapter.match_config(self.request)
        self.human_team = config.player_configurations[self.human_index].team
        self.descriptors = descriptors
        if self.request.get("lesson_id"):
            variants = self.request.get("variants") or {}
            allowed = {key: variants[key] for key in ("side", "target_zone", "angle", "simplified") if key in variants}
            self.engine = TrainingEngine(self.request["lesson_id"], self.request.get("preferences"),
                                         metadata={"framework_version": adapter.SDK_VERSION}, **allowed)
        from .training import GhostPlayback
        from .training import coaching_preferences
        self.coaching_preferences = coaching_preferences(self.coaching_preferences)
        self.coach = GhostPlayback(mode=self.coaching_preferences["mode"],
            lead_seconds=self.coaching_preferences["lead_seconds"],
            speed=self.coaching_preferences["playback_speed"], loop=self.coaching_preferences["loop"])
        if self.request.get("recording") is not None:
            validate_recording(self.request["recording"])
            self.recording = self.request["recording"]
        runtime = Path(self.request["data_dir"]).resolve() / "runtime" / self.session_id
        runtime.mkdir(parents=True, exist_ok=True)
        port = free_port()
        # Recheck just before the core launches: the Epic launch route may close
        # game processes globally, so attaching to a preexisting game is forbidden.
        self.check_cancel()
        preflight(self.owned)
        self.core = subprocess.Popen([str(executable), str(port)], cwd=runtime, shell=False,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
        self.event("session", state="starting", message="Loading the selected offline bots.")
        for index, descriptor in descriptors.items():
            self.controllers[index] = create_controller(self.request.get("provider", "mct-specialist-baseline"), descriptor.get("role", "all-rounder"),
                descriptor["level"], descriptor["difficulty"], descriptor["seed"])
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
            raise RuntimeError("The game returned an unexpected bot-control mapping. No human controls were sent.")
        self.mapping[team] = assigned
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
        from .adapter import desired_state
        if self.engine is None:
            raise RuntimeError("Retry is available during a training lesson.")
        if self.attempt_sent and not self.attempt_acked:
            raise RuntimeError("The previous attempt is still being saved. Wait before retrying.")
        self.manager.rlbot_interface.send_msg(desired_state(self.engine.reset(), self.human_index))
        self.applied_reset = True
        self.attempt_sent = None
        self.attempt_acked = False
        self.playback_origin = None
        if self.coach:
            self.coach.restart()
        self.event("session", state="training", message="Settling the car before the drill.")

    def handle_command(self, command):
        kind = command.get("type", command.get("command"))
        if kind in {"stop", "shutdown"}:
            self.stop_id = command.get("id")
            self.stopping = True
            self.stop_deadline = time.monotonic() + .2
        elif kind in {"retry", "retry_lesson"}:
            self.reset()
        elif kind == "attempt_ack":
            if command.get("attempt_id") == self.attempt_sent:
                self.attempt_acked = True
                if self.engine and self.engine.preferences["auto_reset"]:
                    self.reset()
        elif kind == "preferences" and self.engine:
            preferences = command.get("preferences", {})
            if "key" in command:
                preferences = {command["key"]: command["value"]}
            for key, value in preferences.items():
                self.engine.set_preference(key, value)
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
            if operation == "pause":
                self.coach.pause()
            elif operation == "resume":
                self.coach.resume()
            elif operation == "stop":
                self.coach.stop()
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
            validate_recording(command["recording"])
            self.recording = command["recording"]
            self.coach.load(self.recording, kind="personal")
            self.coach.set_mode(command.get("mode", self.coaching_preferences["mode"]),
                                float(command.get("lead_seconds", self.coaching_preferences["lead_seconds"])))
            self.coach.resume()
            self.playback_origin = self.last_frame["time"] if self.last_frame else None
        else:
            raise ValueError("Unknown game-session command.")

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
            intents = [controller.intent for controller in self.controllers.values() if controller.intent]
            for team, indices in self.mapping.items():
                for index in indices:
                    actions = self.controllers[index].step(frame, index, intents)
                    if not self.cancel_start.is_set() and not self.stopping:
                        self.relays[team].send_msg(flat.PlayerInput(index, flat.ControllerState(**actions)))
            self.last_controls = now
        human = humans[0]
        prior = self.last_frame
        frame.update(car=human, actions=human["actions"],
                     dt=frame["time"] - prior["time"] if prior else 0,
                     packet_gap=bool(prior and (frame["frame_num"] - prior["frame_num"]) % (2**32) != 1))
        self.last_frame = frame
        if self.engine and not self.cancel_start.is_set() and not self.stopping:
            metadata = {"game_version": self.game_version,
                        "car_hitbox": observed_hitbox(packet.players[self.human_index])}
            self.engine.metadata.update(metadata)
            self.engine.recorder.metadata.update(metadata)
            if not self.applied_reset:
                self.reset()
            else:
                for event in self.engine.update(frame):
                    if event["type"] == "set_state" and not self.cancel_start.is_set():
                        self.manager.rlbot_interface.send_msg(adapter.desired_state(event["state"], self.human_index))
                    elif event["type"] == "completed":
                        self.publish_attempt()
                    else:
                        self.event("training_event", event=event)
            if self.engine.finished:
                self.publish_attempt()
            if now - self.last_render >= 1 / 30:
                self.render(frame)
                self.last_render = now
        if not self.engine and not self.request.get("workshop"):
            self.review.update(frame, {team.team_index: team.score for team in packet.teams})
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
        if now - self.last_telemetry >= 1 / 30:
            self.event("telemetry", time=frame["time"], car=human, ball=frame["ball"], actions=human["actions"],
                       frame_num=frame["frame_num"], phase=str(packet.match_info.match_phase),
                       scores=[team.score for team in packet.teams], ghost=self.coach_snapshot,
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
        self.event("attempt", summary=summary, recording=recording)

    def render(self, frame):
        if self.cancel_start.is_set() or self.stopping or not self.renderer.can_render:
            return
        from rlbot import flat
        renderer, preferences = self.renderer, self.engine.preferences
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
                renderer.draw_string_2d("Actions: " + (", ".join(labels) or "neutral"), .03, .31, 1)
            if preferences["timing"]:
                duration = 0 if self.engine.started_at is None else max(0, frame["time"] - self.engine.started_at)
                renderer.draw_string_2d(f"{self.engine.state.title()}  {duration:.2f}s", .03, .35, 1)
            if preferences["ghost"] and self.coach_snapshot.get("visible"):
                for line in self.coach_snapshot.get("lines", []):
                    color = renderer.yellow if line["style"] == "front" else renderer.cyan
                    renderer.draw_line_3d(flat.Vector3(*line["start"]), flat.Vector3(*line["end"]), color)
                renderer.draw_string_2d(self.coach_snapshot.get("label", "Recorded attempt"), .03, .39, .8)

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
        if self.core:
            try:
                self.core.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.core.terminate()  # only the exact Popen handle we created
                try:
                    self.core.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.core.kill()
                    self.core.wait(timeout=2)
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
                        self.event("error", message=str(error))
                elif kind == "disconnected" and not self.stopping:
                    raise RuntimeError("The offline game connection ended. Your completed results remain saved.")
        except SessionCancelled:
            pass
        except Exception as error:
            self.event("error", message=str(error))
            self.event("session", state="error", message="The offline session could not continue.")
        finally:
            try:
                self.teardown()
            except Exception:
                logging.exception("Owned core cleanup failed")
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
            if self.session and self.session.thread.is_alive():
                self.session.command(command)
                if kind == "shutdown":
                    self.session.thread.join(timeout=28)
            else:
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
            except (ValueError, RuntimeError, KeyError, TypeError) as error:
                self.emit({"type": "error", "session_id": self.session.session_id if self.session else None,
                           "message": str(error)})
            if self.closed:
                break
        if self.session and self.session.thread.is_alive() and not self.closed:
            self.session.command({"type": "stop"})
            self.session.thread.join(timeout=28)
        return 0


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
