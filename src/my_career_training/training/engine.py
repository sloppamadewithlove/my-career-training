"""Observed drills, never human control. All time measurements use game timestamps.

reset() -> normalized settle state for the adapter to apply once.
update(frame) -> events; handle type='set_state' by applying its normalized state.
The settle/ready/go sequence deliberately clears old input edges before recording.
"""

from copy import deepcopy
import math
import uuid

from .cadence import classify_cadence
from .catalog import assistance_preferences, configure_lesson
from .coaching import lesson_coaching
from .recordings import Recorder, euler_quaternion, _rotate

# A pre-start attempt that never reaches "go" is bounded in game seconds so the
# player gets one actionable interruption instead of an endless settle loop.
SETTLE_TIMEOUT_SECONDS = 5.0
_MATCH_PHASE_NAMES = {
    0: "MatchPhase.Inactive", 1: "MatchPhase.Countdown", 2: "MatchPhase.Kickoff",
    3: "MatchPhase.Active", 4: "MatchPhase.GoalScored", 5: "MatchPhase.Replay",
    6: "MatchPhase.Paused", 7: "MatchPhase.Ended",
}


class InvalidTrainingTelemetry(ValueError):
    """A packet cannot support truthful training observation."""

    def __init__(self, message, fields):
        super().__init__(message)
        self.fields = tuple(fields)


def _length(value):
    return math.sqrt(sum(x * x for x in value))


def _distance(a, b):
    return _length([x - y for x, y in zip(a, b)])


def _grounded(car):
    return car.get("wheel_contact") is True or car.get("air_state") in ("OnGround", "on_ground", 0)


def _holding_reset(car):
    flags = [car.get(key) for key in ("has_jumped", "has_double_jumped", "has_dodged")]
    return car.get("air_state") in ("InAir", "in_air", 4) and flags == [False, False, False]


def _finite_vector(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value)
    )


def _sampled_interval_ok(previous, frame, max_interval):
    """Finite, increasing observed interval within the documented maximum.

    The first observation of a preparation has no predecessor and is allowed.
    This is the ordinary sampled-preparation interval check only; it never
    replaces the shared cadence classification.
    """
    if not isinstance(previous, dict):
        return True
    before, now = previous.get("time"), frame.get("time")
    if (
        isinstance(before, bool)
        or not isinstance(before, (int, float))
        or not math.isfinite(before)
        or isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(now)
    ):
        return False
    dt = now - before
    return math.isfinite(dt) and 0 < dt <= max_interval


def _rotation_distance(first, second):
    a, b = euler_quaternion(first), euler_quaternion(second)
    dot = min(1.0, abs(sum(x * y for x, y in zip(a, b))))
    return 2 * math.acos(dot)


def _touch(car, ball):
    # The player's own latest_touch is attributed. A global ball touch needs actor identity.
    if car.get("latest_touch"):
        return car["latest_touch"]
    touch = ball.get("latest_touch")
    if touch and car.get("player_index") is not None and touch.get("player_index") == car["player_index"]:
        return touch
    return None


class TrainingEngine:
    def __init__(
        self,
        lesson_id,
        preferences=None,
        metadata=None,
        *,
        side="right",
        target_zone=None,
        angle="center",
        simplified=False,
        max_samples=36000,
        tolerances=None,
        strict_capture=False,
        scenario_id=None,
        difficulty="gold",
    ):
        if not isinstance(strict_capture, bool):
            raise ValueError("Strict capture cadence must be an explicit boolean.")
        self.strict_capture = strict_capture
        self.lesson = configure_lesson(
            lesson_id, side=side, target_zone=target_zone, angle=angle, simplified=simplified
        )
        # An explicit scenario is validated before any match or core launch.
        # Reference capture never runs a scenario, and no scenario_id preserves
        # every legacy lesson/capture behaviour exactly.
        self.scenario = None
        if scenario_id is not None:
            if strict_capture:
                raise ValueError("Reference capture cannot run a ball-launch scenario.")
            from .scenarios import scenario_definition
            definition = scenario_definition(lesson_id, scenario_id, difficulty)
            self.scenario = definition
            self.lesson = {
                **self.lesson,
                "title": definition["title"],
                "description": definition["description"],
                "steps": deepcopy(definition["steps"]),
                "starting_state": deepcopy(definition["starting_state"]),
                "settle_state": deepcopy(definition["settle_state"]),
                "targets": deepcopy(definition["targets"]),
                "success_events": [],
                "timeout": definition["timeout"],
            }
            self.bot_indices = sorted(definition["starting_state"]["bots"])
            self.human_index = definition["roles"]["human"]
        else:
            self.bot_indices = []
            self.human_index = None
        self.preferences = assistance_preferences(preferences)
        if strict_capture:
            # Reference capture is one physics step per packet and never retries
            # itself; the worker also refuses these preferences explicitly.
            self.preferences["auto_reset"] = False
        self.metadata = deepcopy(metadata or {})
        self.max_samples = max_samples
        self.tolerances = {
            "max_packet_interval": 0.05,
            "diagonal_action": 0.15,
            "cancel_action": 0.3,
            "contact_window": 0.08,
            "reset_height": 300,
            "reset_surface_margin": 250,
            # Observation tolerances accommodate physics between state request and receipt.
            # These are configurable reset checks, not universal skill/timing pass criteria.
            "reset_position": 120,
            "reset_ball_position": 200,
            "reset_velocity": 40,
            "reset_rotation": 0.15,
            "reset_angular_velocity": 0.25,
            "reset_boost": 2,
        }
        if tolerances:
            for key, value in tolerances.items():
                if (
                    key not in self.tolerances
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                ):
                    raise ValueError("Detector tolerances must be known positive finite values.")
            self.tolerances.update(tolerances)
        self.reset()

    @property
    def finished(self):
        return self.state in ("finished", "interrupted")

    @property
    def starting_state(self):
        return deepcopy(self.lesson["starting_state"])

    def set_preference(self, key, value):
        self.preferences = assistance_preferences({**self.preferences, key: value})
        return deepcopy(self.preferences)

    def reset(self):
        self.attempt_id = uuid.uuid4().hex
        self.state = "settling"
        self.started_at = None
        self.active_elapsed = 0.0
        self.match_phase = None
        self.last_frame = None
        self.settle_start = None
        self.settle_first_time = None
        self.settle_samples = 0
        self.preparation = {
            "samples": 0,
            "gaps": 0,
            "valid_samples": 0,
            # Ordinary preparation is sampled pose readiness, not expert
            # recording certification; strict capture keeps the exact gate.
            "sampled": not self.strict_capture,
        }
        self.reset_requested_at = None
        self.events = []
        self.observations = []
        self.metrics = {"carry_seconds": 0.0, "gates": 0, "boost_seconds": 0.0, "packet_gaps": 0}
        self.outcome = "unfinished"
        self.recorder = Recorder(self.lesson, self.metadata, max_samples=self.max_samples)
        self._scenario_recording_metadata()
        self.last_touch_time = None
        self.spent_flip_time = None
        self.last_surface_time = None
        self.last_gap_time = None
        self.acquisition_evidence = None
        self.dodge_pitch = None
        self.dodge_time = None
        self.was_airborne = False
        self.next_gate = 0
        self.carry_streak = 0.0
        self.previous_carry = False
        self.contact_pending = None
        self._recent_frames = []
        self._emitted = set()
        # Scenario bookkeeping is cleared on every retry so no old launch,
        # touch, score baseline or controller state can be counted again.
        self.scenario_state = {
            "launch_baseline": None,
            "human_touch": None,
            "keeper_touch": None,
            "ball_out": False,
            "score_baseline": None,
            "score_after": None,
            # A new observed team0 score edge is recorded once, with its own
            # time, so an earlier goal can never complete a later chain.
            "score_edge": None,
            "goal_evidence": None,
            # Absolute time of the goal-target crossing that belongs to this
            # attempt; a stale crossing before the shot is never reused.
            "goal_target_time": None,
            # Latest touch observed per actor before the attempt started. Any
            # touch equal to these is pre-reset and never counted.
            "seen_touch": {},
            "baseline_touch": {},
            # Latest attributed in-attempt touch for every actor, so a fresh
            # keeper contact can invalidate an older Human touch.
            "latest_touch": {},
            "chain_valid": True,
        }
        return deepcopy(self.lesson["settle_state"])

    def _scenario_recording_metadata(self):
        """Retain scenario identity in the recording metadata, scenario runs only.

        Legacy lesson/capture recordings keep exactly their previous metadata;
        nothing is added when no scenario is active.
        """
        if self.scenario is None:
            return
        self.recorder.metadata["scenario_id"] = self.scenario["id"]
        self.recorder.metadata["difficulty"] = self.scenario["difficulty"]
        self.recorder.metadata["scenario_version"] = self.scenario["version"]

    def _event(self, name, frame, *, confidence="observed", details=None):
        event = {
            "type": "skill",
            "name": name,
            "time": frame["time"] - self.started_at,
            "precision": [
                max(0, (self.last_frame or frame)["time"] - self.started_at),
                frame["time"] - self.started_at,
            ],
            "confidence": confidence,
            "details": deepcopy(details or {}),
        }
        if len(self.events) < 12000:
            self.events.append(event)
        else:
            self.recorder.truncated = True
        return event

    def cadence(self, previous, frame):
        """Classify cadence with the shared helper; strict capture is one step."""
        observed = frame.get("cadence_details") if isinstance(frame, dict) else None
        if isinstance(observed, dict):
            return deepcopy(observed)
        return classify_cadence(
            previous,
            frame,
            max_packet_interval=self.tolerances["max_packet_interval"],
            strict=self.strict_capture,
        )

    def _interrupt(self, message):
        self.state, self.outcome = "interrupted", "interrupted"
        self.observations.append(message)
        return [{"type": "completed", "summary": self.summary()}]

    def _once(self, name, frame, **kwargs):
        if name in self._emitted:
            return None
        self._emitted.add(name)
        return self._event(name, frame, **kwargs)

    def _validate_frame(self, frame):
        if (
            not isinstance(frame, dict)
            or not isinstance(frame.get("time"), (int, float))
            or not math.isfinite(frame["time"])
            or frame["time"] < 0
        ):
            raise InvalidTrainingTelemetry("Training requires a finite game timestamp.", ("time",))
        car, ball = frame.get("car", {}), frame.get("ball", {})
        invalid_bodies = [
            f"car.{key}" for key in ("position", "velocity", "rotation")
            if not _finite_vector(car.get(key))
        ] + [
            f"ball.{key}" for key in ("position", "velocity")
            if not _finite_vector(ball.get(key))
        ]
        if invalid_bodies:
            raise InvalidTrainingTelemetry(
                "Training requires actual finite car and ball telemetry.", invalid_bodies
            )
        if "angular_velocity" in car and not _finite_vector(car["angular_velocity"]):
            raise InvalidTrainingTelemetry(
                "Training requires finite angular velocity.", ("car.angular_velocity",)
            )
        actions = frame.get("actions", {})
        invalid_actions = []
        for key in ("throttle", "steer", "pitch", "yaw", "roll"):
            value = actions.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not -1 <= value <= 1
            ):
                invalid_actions.append(f"actions.{key}")
        if invalid_actions:
            raise InvalidTrainingTelemetry(
                "Training requires observed analog game actions.", invalid_actions
            )
        invalid_buttons = [
            f"actions.{key}" for key in ("jump", "boost", "handbrake")
            if not isinstance(actions.get(key), bool)
        ]
        if invalid_buttons:
            raise InvalidTrainingTelemetry(
                "Training requires observed jump, boost, and handbrake actions.", invalid_buttons
            )

    def interrupt_unavailable_telemetry(self, fields):
        """Invalidate the current attempt without accepting the bad packet."""
        was_active = self.state == "active"
        already_finished = self.finished
        if not already_finished:
            self.state, self.outcome = "interrupted", "interrupted"
            self.observations.append(
                "Live telemetry became unavailable. This attempt was interrupted and received no credit."
            )
        return {
            "type": "telemetry_interrupted",
            "attempt_id": self.attempt_id,
            "outcome": self.outcome,
            "attempt_started": was_active,
            "attempt_interrupted": not already_finished,
            "invalid_fields": list(fields),
            "message": "Telemetry was interrupted; waiting for fresh live data before resetting the whole situation.",
        }

    def _scenario_bot(self, frame, index):
        cars = frame.get("cars")
        if not isinstance(cars, (list, tuple)) or index >= len(cars):
            return None
        car = cars[index]
        if not isinstance(car, dict):
            return None
        if any(not _finite_vector(car.get(key)) for key in ("position", "velocity", "rotation")):
            return None
        return car

    def _bots_ready(self, frame, target, elapsed=0.0, tolerance=None):
        """Every scenario bot must be observed in its expected pose.

        A missing or stale actor never passes preparation: the whole situation
        is retried instead of starting with a fictional actor.
        """
        if not self.bot_indices:
            return True
        tolerance = tolerance or self.tolerances["reset_position"]
        for index in self.bot_indices:
            car = self._scenario_bot(frame, index)
            expected = target["bots"][index]
            if car is None:
                return False
            predicted = [p + v * elapsed for p, v in zip(expected["position"], expected["velocity"])]
            if _distance(car["position"], predicted) >= tolerance:
                return False
            if _distance(car["velocity"], expected["velocity"]) >= self.tolerances["reset_velocity"]:
                return False
            if _rotation_distance(car["rotation"], expected["rotation"]) >= self.tolerances["reset_rotation"]:
                return False
            if not _finite_vector(car.get("angular_velocity")):
                return False
            if _distance(car["angular_velocity"], expected["angular_velocity"]) >= self.tolerances[
                    "reset_angular_velocity"]:
                return False
            boost = car.get("boost")
            if (isinstance(boost, bool) or not isinstance(boost, (int, float))
                    or not math.isfinite(boost)
                    or abs(boost - expected.get("boost", 100)) >= self.tolerances["reset_boost"]):
                return False
        return True

    def _scenario_touch(self, frame, index):
        """Latest attributed touch for one actor, or None."""
        car = self._scenario_bot(frame, index)
        if car is None:
            return None
        touch = _touch(car, frame.get("ball") or {})
        if not touch:
            return None
        stamp = touch.get("game_seconds", touch.get("time"))
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
            return None
        return stamp

    def _scenario_observe_touches(self, frame):
        """Track the latest observed touch per scenario actor.

        Called during preparation as well as during the attempt, so a touch
        that happened before the reset can never be counted as this attempt's
        pass, shot or save.
        """
        if self.scenario is None:
            return
        seen = self.scenario_state["seen_touch"]
        for index in list(self.bot_indices) + [self.human_index]:
            stamp = self._scenario_touch(frame, index)
            if stamp is not None:
                seen[index] = stamp

    def _scenario_ball_ready(self, frame, target):
        """Confirm the parked ball as part of the whole-situation settle."""
        if self.scenario is None:
            return True
        ball = frame.get("ball") or {}
        expected = target["ball"]
        return (
            _finite_vector(ball.get("position"))
            and _finite_vector(ball.get("velocity"))
            and _distance(ball["position"], expected["position"])
            < self.tolerances["reset_ball_position"]
            and _distance(ball["velocity"], expected["velocity"])
            < self.tolerances["reset_velocity"]
        )

    def _scenario(self, frame, previous, gap):
        """Observed launch -> human shot -> authoritative goal chain.

        Success needs the verified one-shot launch baseline, the Human's own NEW
        touch as the latest observed touch, and an unambiguous observed +team0
        score with goal-target/ball-movement evidence. A ball
        crossing the target alone is never an authoritative goal, and a
        telemetry gap permanently invalidates the attribution chain.
        """
        if self.scenario is None:
            return
        state = self.scenario_state
        if any(self._scenario_bot(frame, index) is None for index in self.bot_indices):
            # Production validates the whole roster too; keep direct engine use
            # fail-closed when a configured opponent disappears mid-attempt.
            state["chain_valid"] = False
            return
        self._scenario_observe_touches(frame)
        if gap:
            # A gap can hide an intervening touch, so the chain cannot be
            # proven continuous. No later score may resurrect it.
            state["chain_valid"] = False
        scores = frame.get("scores")
        if (isinstance(scores, (list, tuple)) and len(scores) == 2
                and all(isinstance(x, int) and not isinstance(x, bool) for x in scores)):
            if state["score_baseline"] is None:
                state["score_baseline"] = list(scores)
            state["score_after"] = list(scores)
        baseline = state["baseline_touch"] or {}
        now = frame["time"]
        actor_keys = [(self.human_index, "human_touch")]
        keeper_index = self.scenario["roles"].get("keeper")
        if keeper_index is not None:
            actor_keys.append((keeper_index, "keeper_touch"))
        for index, key in actor_keys:
            stamp = self._scenario_touch(frame, index)
            if stamp is None:
                continue
            if stamp == baseline.get(index):
                continue  # Pre-reset touch, not this attempt.
            # Strictly observed: a touch stamped after this packet is not yet
            # evidence, and no tolerance is added.
            if not (self.started_at <= stamp <= now):
                continue
            # Track the latest attributed touch for every actor, not only the
            # first one seen, so a later keeper contact is visible.
            if stamp > (state["latest_touch"].get(index) or -math.inf):
                state["latest_touch"][index] = stamp
            if state[key] is None:
                state[key] = stamp
                self._once(key, frame, details={"contact_time": stamp})
        ball = frame.get("ball") or {}
        position = ball.get("position")
        if _finite_vector(position) and (
                abs(position[0]) > 4096 or abs(position[1]) > 5120 or position[2] > 2044):
            state["ball_out"] = True
        before, after = state["score_baseline"], state["score_after"]
        scored = (
            before is not None and after is not None
            and after[0] == before[0] + 1 and after[1] == before[1]
        )
        if gap:
            if scored:
                self._interrupt("A team goal was observed, but the shot trace was incomplete. No technique credit.")
            return
        if scored and state["score_edge"] is None:
            # Record the observed score edge once, with its own time.
            state["score_edge"] = {
                "time": now,
                "team0_before": before[0],
                "team0_after": after[0],
            }
            state["goal_evidence"] = {
                "team0_before": before[0],
                "team0_after": after[0],
                "score_edge_time": now,
                "target_hit": self.metrics.get("target_hit"),
                "ball_speed": _length(ball.get("velocity") or [0, 0, 0]),
            }
        human = state["human_touch"]
        latest = state["latest_touch"]
        human_latest = latest.get(self.human_index)
        # The Human must be the latest attributed touch of every actor: a fresh
        # keeper contact after the shot invalidates the chain.
        # Strictly later: an equal timestamp is an ambiguous tie, so a non-human
        # contact stamped at the same instant can never be treated as older.
        latest_is_human = human_latest is not None and all(
            human_latest > stamp for index, stamp in latest.items() if index != self.human_index
        )
        edge = state["score_edge"]
        target_time = state["goal_target_time"]
        chain = (
            state["chain_valid"]
            and state["launch_baseline"] is not None
            and human is not None
            and state["launch_baseline"]["time"] <= human
            and latest_is_human
            and target_time is not None
            and human <= target_time
            and edge is not None
            and edge["time"] >= target_time
        )
        if chain and "goal_target" in self._emitted:
            self._once("scenario_success", frame, details=deepcopy(state["goal_evidence"]))
            self._finish("success")
        elif scored:
            self._interrupt("A team goal was observed without a verified player-shot chain. No technique credit.")

    def update(self, frame):
        self._validate_frame(frame)
        if self.finished:
            return []
        now, car = frame["time"], frame["car"]
        phase = frame.get("phase")
        if self.scenario is not None and phase is not None and phase != 3:
            # Countdown, kickoff, goal replay and pauses are not attempt time.
            # In particular, READY's two-second confirmation budget begins only
            # after actual Active play resumes.
            self.match_phase = frame.get("phase_name", _MATCH_PHASE_NAMES.get(phase, str(phase)))
            if self.state == "settling":
                self.settle_start = None
                self.settle_first_time = None
                self.settle_samples = 0
            elif self.state == "ready":
                self.reset_requested_at = now
            elif self.state == "active":
                previous = self.last_frame
                if phase == 4 and previous is not None:
                    cadence = self.cadence(previous, frame)
                    terminal = deepcopy(frame)
                    terminal["packet_gap"] = cadence["gap"]
                    terminal["cadence"] = cadence["reason"]
                    self.recorder.append(terminal)
                    self._contacts(terminal, previous, cadence["gap"])
                    self._targets(terminal, previous, cadence["gap"], cadence["dt"] or 0.0)
                    self._scenario(terminal, previous, cadence["gap"])
                    self.last_frame = terminal
                    if self.finished:
                        return [{"type": "completed", "summary": self.summary(),
                                 "auto_reset": self.preferences["auto_reset"]}]
                self.scenario_state["chain_valid"] = False
                return self._interrupt(
                    f"The attempt was interrupted by {self.match_phase}. Retry to establish a clean start."
                )
            self.last_frame = None
            return []
        if self.scenario is not None:
            self.match_phase = frame.get("phase_name", _MATCH_PHASE_NAMES.get(phase, "MatchPhase.Active"))
        if self.last_frame and now == self.last_frame["time"]:
            return []
        if self.last_frame and now < self.last_frame["time"]:
            self.state, self.outcome = "interrupted", "interrupted"
            self.observations.append("The game clock restarted. Retry to establish a clean starting state.")
            return [{"type": "completed", "summary": self.summary()}]
        if self.state == "settling":
            target = self.lesson["settle_state"]["car"]
            flags_clean = all(
                car.get(key) is False for key in ("has_jumped", "has_double_jumped", "has_dodged")
            )
            cadence = self.cadence(self.last_frame, frame)
            self.preparation.update(
                samples=self.preparation["samples"] + 1,
                gaps=self.preparation["gaps"] + int(cadence["gap"]),
                cadence=deepcopy(cadence), grounded=_grounded(car), flags_clean=flags_clean,
                position_error=_distance(car["position"], target["position"]),
                speed=_length(car["velocity"]),
                spin=_length(car.get("angular_velocity", [0, 0, 0])),
            )
            if cadence["gap"]:
                self.preparation["last_gap"] = deepcopy(cadence)
            valid = (
                _grounded(car)
                and flags_clean
                and _distance(car["position"], target["position"]) < 60
                and _length(car["velocity"]) < 25
                and _length(car.get("angular_velocity", [0, 0, 0])) < 0.2
                and (not cadence["gap"] if self.strict_capture else
                     _sampled_interval_ok(self.last_frame, frame, 0.05))
                and self._bots_ready(frame, self.lesson["settle_state"])
                and self._scenario_ball_ready(frame, self.lesson["settle_state"])
            )
            if valid:
                if self.settle_start is None:
                    self.settle_start = now
                self.settle_samples += 1
            else:
                self.settle_start = None
                self.settle_samples = 0
            self.preparation["valid_samples"] = self.settle_samples
            self._scenario_observe_touches(frame)
            if self.settle_first_time is None:
                self.settle_first_time = now
            self.last_frame = deepcopy(frame)
            if (self.settle_start is not None and now - self.settle_start >= 0.25
                    and (self.strict_capture or self.settle_samples >= 3)):
                self.state = "ready"
                self.reset_requested_at = now
                return [
                    {"type": "set_state", "state": self.starting_state},
                    {"type": "ready", "message": "Ready — the next verified packet starts the drill."},
                ]
            if now - self.settle_first_time >= SETTLE_TIMEOUT_SECONDS:
                # One actionable interruption instead of an endless settle loop.
                if cadence["gap"] or (self.preparation["gaps"] and valid):
                    return self._interrupt(
                        "No continuous telemetry cadence was observed while preparing the drill "
                        f"({self.preparation.get('last_gap', cadence)['reason']}). Check the game connection, then retry."
                    )
                return self._interrupt(
                    "The car did not settle in the starting pose within "
                    f"{SETTLE_TIMEOUT_SECONDS:.0f} game seconds. Release held controls and retry."
                )
            return []
        if self.state == "ready":
            # Confirm the game applied the reset. No confirmation means no fictional attempt.
            # The launch is normally confirmed by the next continuous packet (<= .05 s),
            # before the low bouncing launch reaches the floor. The 2 s bound below is
            # only a failure deadline; this check does not model or certify a bounce.
            target = self.lesson["starting_state"]
            elapsed = now - self.reset_requested_at
            expected_ball = [
                p + v * elapsed for p, v in zip(target["ball"]["position"], target["ball"]["velocity"])
            ]
            expected_ball_velocity = list(target["ball"]["velocity"])
            if target["ball"]["position"][2] > 100 or target["ball"]["velocity"][2] != 0:
                expected_ball[2] -= 325 * elapsed * elapsed
                expected_ball_velocity[2] -= 650 * elapsed
            expected_car = [
                p + v * elapsed for p, v in zip(target["car"]["position"], target["car"]["velocity"])
            ]
            boost = car.get("boost")
            cadence = self.cadence(self.last_frame, frame)
            observed_state_applied = (
                _distance(car["position"], expected_car) < self.tolerances["reset_position"]
                and _rotation_distance(car["rotation"], target["car"]["rotation"])
                < self.tolerances["reset_rotation"]
                and _distance(car["velocity"], target["car"]["velocity"]) < self.tolerances["reset_velocity"]
                and _finite_vector(car.get("angular_velocity"))
                and _distance(car["angular_velocity"], target["car"]["angular_velocity"])
                < self.tolerances["reset_angular_velocity"]
                and isinstance(boost, (int, float))
                and not isinstance(boost, bool)
                and math.isfinite(boost)
                and abs(boost - target["car"]["boost"]) < self.tolerances["reset_boost"]
                and _grounded(car)
                and all(car.get(key) is False for key in ("has_jumped", "has_double_jumped", "has_dodged"))
                and _distance(frame["ball"]["position"], expected_ball)
                < self.tolerances["reset_ball_position"]
                and _distance(frame["ball"]["velocity"], expected_ball_velocity)
                < self.tolerances["reset_velocity"]
                and elapsed < 2.0
                and self._bots_ready(frame, target, elapsed)
            )
            # Ordinary play may coalesce packets under load. A complete observed
            # actor/ball state can confirm the reset only for those known gaps;
            # strict capture still requires continuous one-step cadence.
            ordinary_coalescing = cadence["reason"] in {
                "step_count_exceeded", "interval_exceeded"
            }
            applied = observed_state_applied and (
                not cadence["gap"] or (not self.strict_capture and ordinary_coalescing)
            )
            self.preparation["ready"] = {
                "elapsed": round(elapsed, 6),
                "phase": frame.get("phase"),
                "cadence": deepcopy(cadence),
                "expected_car": {"position": expected_car, "velocity": target["car"]["velocity"]},
                "observed_car": {"position": list(car["position"]), "velocity": list(car["velocity"])},
                "expected_ball": {"position": expected_ball, "velocity": expected_ball_velocity},
                "observed_ball": {"position": list(frame["ball"]["position"]),
                                  "velocity": list(frame["ball"]["velocity"])},
                "observed_state_applied": observed_state_applied,
            }
            if not applied:
                if elapsed >= 2.0:
                    return self._interrupt(
                        "The starting position could not be confirmed. Retry when play resumes."
                    )
                self.last_frame = deepcopy(frame)
                self._scenario_observe_touches(frame)
                return []
            self.state, self.started_at = "active", now
            self.active_elapsed = 0.0
            if self.scenario is not None:
                # Freeze the pre-attempt touch and score baselines at "go".
                self.scenario_state["baseline_touch"] = dict(self.scenario_state["seen_touch"])
                self.scenario_state["chain_valid"] = True
                self.scenario_state["latest_touch"] = {}
                self.scenario_state["score_edge"] = None
                self.scenario_state["goal_target_time"] = None
                self.scenario_state["launch_baseline"] = {
                    "time": now,
                    "position": list(frame["ball"]["position"]),
                    "velocity": list(frame["ball"]["velocity"]),
                }
                self._once(
                    "launch_observed", frame,
                    details=deepcopy(self.scenario_state["launch_baseline"]),
                )
                scores = frame.get("scores")
                if (isinstance(scores, (list, tuple)) and len(scores) == 2
                        and all(isinstance(x, int) and not isinstance(x, bool) for x in scores)):
                    self.scenario_state["score_baseline"] = list(scores)
                    self.scenario_state["score_after"] = list(scores)
            self.last_frame = None
            self.recorder = Recorder(self.lesson, self.metadata, max_samples=self.max_samples)
            self._scenario_recording_metadata()
            self.last_touch_time = (_touch(car, frame["ball"]) or {}).get(
                "game_seconds", (_touch(car, frame["ball"]) or {}).get("time")
            )
            self.recorder.append(frame)
            self.last_frame = deepcopy(frame)
            return [{"type": "go", "message": "Go", "attempt_id": self.attempt_id}]
        previous = self.last_frame
        if previous is None:
            # First packet after a non-play phase establishes a fresh cadence
            # baseline without inventing contact, target, or score evidence.
            self.recorder.append(frame)
            self.last_frame = deepcopy(frame)
            return []
        cadence = self.cadence(previous, frame)
        dt = cadence["dt"] if cadence["dt"] is not None else now - previous["time"]
        if self.scenario is not None:
            self.active_elapsed += max(0.0, now - previous["time"])
        gap = cadence["gap"]
        frame = deepcopy(frame)
        frame["packet_gap"] = gap
        frame["cadence"] = cadence["reason"]
        if gap:
            self.metrics["packet_gaps"] += 1
            self.last_gap_time = now
            self.carry_streak = 0.0
        self.recorder.append(frame)
        before = len(self.events)
        self._recent_frames.append(deepcopy(frame))
        self._recent_frames = [x for x in self._recent_frames if now - x["time"] < 0.5]
        if frame["actions"]["boost"] and not gap:
            self.metrics["boost_seconds"] += dt
        self._actions(frame, previous, gap)
        self._contacts(frame, previous, gap)
        self._targets(frame, previous, gap, dt)
        self._scenario(frame, previous, gap)
        if self.finished:
            # A scenario success decided above is final for this packet.
            pass
        elif ((self.active_elapsed if self.scenario is not None else now - self.started_at)
              >= self.lesson["timeout"]):
            self._finish("timeout")
        elif self.scenario is not None:
            # Scenario success is decided only by the observed launch -> human
            # shot -> authoritative score chain, never by target crossing alone.
            pass
        else:
            needed = set(self.lesson["success_events"])
            if self.lesson["id"] == "speed-flip":
                needed.update(("diagonal_dodge", "opposing_pitch"))
            if needed.issubset(self._emitted) and self._ordered_success():
                self._finish("success")
        result = deepcopy(self.events[before:])
        self.last_frame = frame
        if self.finished:
            result.append(
                {"type": "completed", "summary": self.summary(), "auto_reset": self.preferences["auto_reset"]}
            )
        return result

    @staticmethod
    def _bracket(event):
        """Observed sample bracket [earliest, latest] for an event, in seconds."""
        precision = event.get("precision")
        if (
            isinstance(precision, (list, tuple))
            and len(precision) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in precision)
        ):
            return (min(precision), max(precision))
        return (event["time"], event["time"])

    def _ordered_success(self):
        if self.lesson["id"] != "speed-flip":
            return True
        # The same events in a different order are a different attempt. Landing can
        # precede the line or follow it, but neither may precede the technique.
        observed = {event["name"]: event for event in self.events if event["confidence"] != "uncertain"}
        if any(
            key not in observed
            for key in ("first_jump", "diagonal_dodge", "opposing_pitch", "target_crossed", "landed")
        ):
            return False
        jump, dodge, cancel, crossing, landing = [
            observed[key]
            for key in ("first_jump", "diagonal_dodge", "opposing_pitch", "target_crossed", "landed")
        ]
        # Ordering uses the actual observed sample brackets, never an invented
        # interpolation. Touching boundaries are allowed because the earlier
        # event's latest sample edge is the later event's earliest sample edge.
        # Two events collapsed into one coarse packet share a bracket and cannot
        # prove their order, so that attempt is not claimed as a valid sequence.
        jump_bracket, dodge_bracket = self._bracket(jump), self._bracket(dodge)
        cancel_bracket, landing_bracket = self._bracket(cancel), self._bracket(landing)
        crossing_time = crossing["details"].get("crossing_time", crossing["time"])
        crossing_bracket = self._bracket(crossing)
        if isinstance(crossing_time, (int, float)) and not isinstance(crossing_time, bool):
            crossing_bracket = (min(crossing_bracket[0], crossing_time),
                                max(crossing_bracket[1], crossing_time))
        return (
            self._precedes(jump_bracket, dodge_bracket)
            and self._precedes(dodge_bracket, cancel_bracket)
            and self._precedes(cancel_bracket, crossing_bracket)
            and self._precedes(cancel_bracket, landing_bracket)
        )

    @staticmethod
    def _precedes(first, second):
        """True only when two distinct observed brackets prove the order.

        Touching boundaries are allowed: the earlier event's latest sample edge
        may equal the later event's earliest sample edge. Two events collapsed
        into the same observed sample share one bracket and cannot prove their
        order, so a same-packet jump plus dodge is never claimed as valid.
        """
        if first == second:
            return False
        return first[1] <= second[0]

    def _actions(self, frame, previous, gap):
        car, old, actions, old_actions = frame["car"], previous["car"], frame["actions"], previous["actions"]
        if actions["jump"] and not old_actions["jump"]:
            self._event("jump_pressed", frame, confidence="uncertain" if gap else "observed")
        if car.get("has_jumped") is True and old.get("has_jumped") is False:
            self._once("first_jump", frame, confidence="uncertain" if gap else "observed")
        if car.get("has_double_jumped") is True and old.get("has_double_jumped") is False:
            self._once("second_jump", frame, confidence="uncertain" if gap else "observed")
        if car.get("has_dodged") is True and old.get("has_dodged") is False:
            self.spent_flip_time, self.dodge_time = frame["time"], frame["time"]
            self.dodge_pitch = actions["pitch"]
            self._event(
                "dodge",
                frame,
                confidence="uncertain" if gap else "observed",
                details={
                    "direction": car.get("dodge_dir"),
                    "input_pitch": actions["pitch"],
                    "input_yaw": actions["yaw"],
                },
            )
            direction = car.get("dodge_dir")
            diagonal_direction = (
                isinstance(direction, (list, tuple))
                and len(direction) == 2
                and all(isinstance(x, (int, float)) and math.isfinite(x) for x in direction)
                and all(abs(x) >= self.tolerances["diagonal_action"] for x in direction)
            )
            diagonal_actions = (
                abs(actions["pitch"]) >= self.tolerances["diagonal_action"]
                and abs(actions["yaw"]) >= self.tolerances["diagonal_action"]
            )
            if not gap and (diagonal_direction or diagonal_actions):
                self._once(
                    "diagonal_dodge",
                    frame,
                    details={
                        "basis": "Observed dodge direction"
                        if diagonal_direction
                        else "Observed diagonal game actions"
                    },
                )
            if not gap and actions["pitch"] > 0.3:
                self._once(
                    "possible_backflip",
                    frame,
                    confidence="coaching suggestion",
                    details={
                        "reason": "A dodge began while nose-up pitch was held; verify its direction in playback."
                    },
                )
            if self.acquisition_evidence is not None:
                self._once("reset_used", frame, confidence="uncertain" if gap else "observed")
        if (
            self.dodge_time is not None
            and self.dodge_pitch
            and not gap
            and actions["pitch"] * self.dodge_pitch < 0
            and abs(actions["pitch"]) >= self.tolerances["cancel_action"]
        ):
            self._once(
                "opposing_pitch",
                frame,
                details={
                    "delay_seconds": frame["time"] - self.dodge_time,
                    "note": "Opposing pitch input observed; cancellation effectiveness is not independently proven.",
                },
            )
        if not _grounded(car):
            self.was_airborne = True
        if _grounded(car) and not _grounded(old) and self.was_airborne:
            self._event("landing", frame, confidence="uncertain" if gap else "observed")
            if not gap:
                self._once("landed", frame)
                q = euler_quaternion(car["rotation"])
                roof = _rotate(q, [0, 0, 1])
                forward = _rotate(q, [1, 0, 0])
                velocity = car["velocity"]
                speed = _length(velocity)
                alignment = sum(a * b for a, b in zip(forward, velocity)) / speed if speed else 0
                self.metrics["landing_roof_up"] = roof[2]
                self.metrics["landing_forward_alignment"] = alignment
                self.metrics["landing_speed"] = speed
                self.metrics["landing_angular_speed"] = _length(car.get("angular_velocity", [0, 0, 0]))
        # In the central high-air reset drill a transient grounded state may be ball-wheel contact.
        x, y, z = car["position"]
        if _grounded(car) and (
            z < self.tolerances["reset_height"] or abs(x) > 2800 or abs(y) > 3800 or z > 1750
        ):
            self.last_surface_time = frame["time"]

    def _contacts(self, frame, previous, gap):
        car, ball, now = frame["car"], frame["ball"], frame["time"]
        touch = _touch(car, ball)
        fresh = False
        if touch:
            touch_time = touch.get("game_seconds", touch.get("time"))
            if (
                isinstance(touch_time, (int, float))
                and math.isfinite(touch_time)
                and touch_time != self.last_touch_time
                and previous["time"] - 0.02 <= touch_time <= now + 0.02
            ):
                fresh = True
                self.last_touch_time = touch_time
                self._once(
                    "ball_contact",
                    frame,
                    confidence="uncertain" if gap else "observed",
                    details={
                        "contact_time": touch_time,
                        "location": touch.get("location", touch.get("position")),
                    },
                )
                self._event(
                    "touch",
                    frame,
                    confidence="uncertain" if gap else "observed",
                    details={"contact_time": touch_time},
                )
                self.contact_pending = now
                if (
                    "carry_sustained" in self._emitted
                    and (car.get("has_dodged") or car.get("has_double_jumped"))
                    and not gap
                ):
                    self._once("flick", frame, details={"ball_speed": _length(ball["velocity"])})
        if self.contact_pending is not None and now - self.contact_pending <= 0.1:
            self.metrics["sampled_outgoing_ball_speed"] = _length(ball["velocity"])
            self.metrics["outgoing_speed_sample_after_contact_seconds"] = now - self.contact_pending
        if self.lesson["id"] != "flip-reset":
            return
        # Availability must actually change. Already holding a flip is not a successful reset.
        transition = _holding_reset(car) and not _holding_reset(previous["car"])
        if not transition:
            return
        if not fresh:
            fresh = (
                self.last_touch_time is not None
                and 0 <= now - self.last_touch_time <= self.tolerances["contact_window"]
            )
        x, y, z = car["position"]
        central = abs(x) < 2800 and abs(y) < 3800 and 300 < z < 1750
        q = euler_quaternion(car["rotation"])
        underside = _rotate(q, [0, 0, -1])
        delta = [b - a for a, b in zip(car["position"], ball["position"])]
        dist = _length(delta)
        under_ball = dist > 0 and sum(a * b for a, b in zip(underside, delta)) / dist > 0.5
        nearby = dist < 230
        consumed = self.spent_flip_time is not None and self.spent_flip_time < now
        contact_after_consumption = (
            self.last_touch_time is not None
            and self.spent_flip_time is not None
            and self.last_touch_time > self.spent_flip_time
        )
        surface_clear = self.last_surface_time is None or (
            self.spent_flip_time is not None and self.last_surface_time < self.spent_flip_time
        )
        gap_clear = self.last_gap_time is None or (
            self.spent_flip_time is not None and self.last_gap_time < self.spent_flip_time
        )
        evidence = {
            "fresh_ball_touch": fresh,
            "underside_aligned": under_ball,
            "ball_near": nearby,
            "consumed_flip_observed": consumed,
            "ball_touch_after_flip_consumed": contact_after_consumption,
            "central_airspace": central,
            "arena_surface_excluded": surface_clear,
            "continuous_packets": gap_clear and not gap,
        }
        if all(evidence.values()):
            self.acquisition_evidence = evidence
            self._once(
                "reset_acquired",
                frame,
                confidence="strong telemetry evidence",
                details={**evidence, "note": "No direct per-wheel contact event is exposed by the packet."},
            )
        elif fresh:
            self._event("reset_uncertain", frame, confidence="uncertain", details=evidence)
            self.observations.append(
                "Ball contact and flip availability were observed, but the reset could not be confirmed. Retry with a clear airborne approach and continuous telemetry."
            )

    def _targets(self, frame, previous, gap, dt):
        car, ball = frame["car"], frame["ball"]
        targets = self.lesson["targets"]
        gates = [x for x in targets if x["type"] == "gate"]
        if self.next_gate < len(gates):
            target = gates[self.next_gate]
            if (
                not gap
                and car["position"][2] > 120
                and _distance(car["position"], target["position"]) <= target["radius"]
            ):
                self._once(f"gate_{self.next_gate}", frame, details={"speed": _length(car["velocity"])})
                self.next_gate += 1
                self.metrics["gates"] = self.next_gate
        for target in targets:
            if target["type"] == "plane":
                axis, boundary = target["axis"], target["value"]
                old, new = previous["car"]["position"], car["position"]
                if old[axis] < boundary <= new[axis] and not gap:
                    ratio = (boundary - old[axis]) / (new[axis] - old[axis])
                    location = [a + ratio * (b - a) for a, b in zip(old, new)]
                    if abs(location[0]) <= target["width"] / 2 and location[2] <= target["height"]:
                        self._once(
                            "target_crossed",
                            frame,
                            details={
                                "crossing_time": previous["time"] + ratio * dt - self.started_at,
                                "speed": _length(car["velocity"]),
                            },
                        )
                        self.metrics["crossing_seconds"] = previous["time"] + ratio * dt - self.started_at
                        self.metrics["crossing_speed"] = _length(car["velocity"])
            elif target["type"] == "carry":
                q = euler_quaternion(car["rotation"])
                local = _rotate(
                    [q[0], -q[1], -q[2], -q[3]], [a - b for a, b in zip(ball["position"], car["position"])]
                )
                inside = (
                    abs(local[0]) <= target["forward"]
                    and abs(local[1]) <= target["side"]
                    and target["height"][0] <= local[2] <= target["height"][1]
                    and _grounded(car)
                )
                if inside and self.previous_carry and not gap:
                    self.carry_streak += dt
                    self.metrics["carry_seconds"] += dt
                elif not inside:
                    if self.previous_carry:
                        self._event("carry_dropped", frame)
                    self.carry_streak = 0.0
                self.previous_carry = inside
                if self.carry_streak >= target["seconds"]:
                    self._once("carry_sustained", frame)
            elif target["type"] == "goal":
                old, new = previous["ball"]["position"], ball["position"]
                if old[1] < 5120 <= new[1] and not gap:
                    ratio = (5120 - old[1]) / (new[1] - old[1])
                    location = [a + ratio * (b - a) for a, b in zip(old, new)]
                    hit = (
                        abs(location[0] - target["center_x"]) <= target["half_width"]
                        and target["min_z"] <= location[2] <= target["max_z"]
                    )
                    self.metrics["shot_location"] = location
                    self.metrics["target_hit"] = hit
                    self._event(
                        "shot_location",
                        frame,
                        details={
                            "location": location,
                            "hit": hit,
                            "criterion": "Ball center crosses marked zone; separate from authoritative match score.",
                        },
                    )
                    if hit and "ball_contact" in self._emitted:
                        emitted = self._once("goal_target", frame)
                        if emitted is not None and self.scenario is not None:
                            # Absolute time of this attempt's own crossing, so a
                            # stale pre-shot crossing can never be reused.
                            self.scenario_state["goal_target_time"] = frame["time"]
            elif target["type"] == "recovery":
                x, y, _ = car["position"]
                if (
                    "landed" in self._emitted
                    and self.next_gate == len(gates)
                    and _grounded(car)
                    and abs(x - target["center_x"]) <= target["half_width"]
                    and target["min_y"] <= y <= target["max_y"]
                ):
                    self._once(
                        "recovered",
                        frame,
                        details={
                            "roof_up": self.metrics.get("landing_roof_up"),
                            "forward_alignment": self.metrics.get("landing_forward_alignment"),
                        },
                    )

    def _finish(self, outcome):
        self.state, self.outcome = "finished", outcome
        lesson_id = self.lesson["id"]
        if self.scenario is not None:
            self._scenario_feedback(outcome)
            if self.metrics["packet_gaps"]:
                self.observations.append(
                    "Telemetry gaps limit technique/timing conclusions; missing actions were not invented."
                )
            return
        if outcome == "success":
            self.observations.append(
                "You completed the drill's observed target. Repeat the same setup to compare your next attempt."
            )
        elif lesson_id == "speed-flip":
            if "diagonal_dodge" not in self._emitted:
                self.observations.append(
                    "A clear diagonal dodge was not observed. Try the jump and diagonal dodge step before focusing on time."
                )
            elif "opposing_pitch" not in self._emitted:
                self.observations.append(
                    "No clear opposing pitch after your dodge was observed. Try reversing pitch after the diagonal dodge."
                )
            else:
                self.observations.append(
                    "The dodge and opposing pitch were observed. Aim to cross the marked line and land in the corridor."
                )
        elif lesson_id == "flip-reset" and "reset_acquired" not in self._emitted:
            self.observations.append(
                "A newly gained ball reset was not confirmed. Use your original flip first, then meet the ball with your underside away from arena surfaces."
            )
        elif lesson_id == "fast-aerial" and "possible_backflip" in self._emitted:
            self.observations.append(
                "Your second action may have been a backward dodge. Release the directional input for the second jump and review the recorded pose."
            )
        elif lesson_id == "dribble-flick":
            self.observations.append(
                f"Observed carry time: {self.metrics['carry_seconds']:.2f} seconds. Keep the ball within the marked roof zone before the flick."
            )
        elif lesson_id in ("shot-placement", "power-shots"):
            self.observations.append(
                "Aim the next contact toward the marked goal rectangle. Review the measured crossing location when one was observed."
            )
        else:
            self.observations.append(
                f"You reached {self.metrics['gates']} ordered gates. Aim through the next gate, then recover on your wheels."
            )
        if self.metrics["packet_gaps"]:
            self.observations.append(
                "Telemetry gaps limit technique/timing conclusions; missing actions were not invented."
            )

    def _scenario_feedback(self, outcome):
        """Honest feedback: only observed facts, never invented causes."""
        state = self.scenario_state
        if outcome == "success":
            self.observations.append(
                "Observed the configured launch, your touch and a team score increase. "
                "Repeat the same situation to compare your next attempt."
            )
            return
        if (state["keeper_touch"] is not None and state["human_touch"] is not None
                and state["keeper_touch"] > state["human_touch"]):
            self.observations.append(
                "The keeper touched the ball after your shot. The attempt was not scored."
            )
            return
        if state["ball_out"]:
            self.observations.append("The ball left the playable area. Retry the situation.")
            return
        if state["launch_baseline"] is None:
            self.observations.append(
                "The configured ball launch was not observed, so this attempt received no credit."
            )
            return
        if state["human_touch"] is None:
            self.observations.append(
                "The launch was observed but no fresh touch by you was observed before the attempt ended."
            )
            return
        if outcome == "timeout":
            self.observations.append(
                "The attempt ended without an observed team score increase. Retry the whole situation."
            )
            return
        self.observations.append("The attempt ended without an observed team score increase.")

    def summary(self):
        duration = (
            0
            if self.started_at is None
            else (self.active_elapsed if self.scenario is not None
                  else max(0, (self.last_frame or {"time": self.started_at})["time"] - self.started_at))
        )
        return {
            "id": self.attempt_id,
            "lesson_id": self.lesson["id"],
            "lesson_title": self.lesson["title"],
            "state": self.state,
            "outcome": self.outcome,
            "duration": duration,
            "metrics": deepcopy(self.metrics),
            "events": deepcopy(self.events),
            "observations": list(dict.fromkeys(self.observations)),
            "feedback": self.observations[0] if self.observations else "Complete the next marked step.",
            "reference_status": self.lesson["reference_status"],
            "timing_comparison": "No validated equivalent teaching reference is installed.",
            "preferences": deepcopy(self.preferences),
            "coaching": self._coaching(),
            "scenario": (
                None if self.scenario is None else {
                    "lesson_id": self.scenario["lesson_id"],
                    "id": self.scenario["id"],
                    "title": self.scenario["title"],
                    "difficulty": self.scenario["difficulty"],
                    "rank_title": self.scenario["rank_title"],
                    "version": self.scenario["version"],
                    "planned_total": self.scenario["planned_total"],
                    "implemented_total": self.scenario["implemented_total"],
                    "scenario_index": self.scenario["implemented_scenarios"].index(self.scenario["id"]) + 1,
                    "scenario_total": self.scenario["implemented_total"],
                    "rank_note": "Intended difficulty only; not a certified bot rank.",
                    "evidence": deepcopy(self.scenario_state),
                }
            ),
        }

    def _coaching(self):
        coaching = lesson_coaching(self.lesson, self.events, state=self.state, outcome=self.outcome)
        coaching["preparation"] = deepcopy(self.preparation)
        if self.state == "settling":
            # Before "go" the drill is preparing, not settling a measured attempt.
            coaching["message"] = "Preparing the drill. Wait for READY before pressing anything."
            coaching["label"] = "Preparing"
        elif self.state == "interrupted":
            # The actual interruption reason is actionable; never a generic retry.
            reason = next((text for text in self.observations if isinstance(text, str) and text), None)
            if reason:
                coaching["message"] = reason
                coaching["interruption_reason"] = reason
        if self.scenario is not None:
            scenario_index = self.scenario["implemented_scenarios"].index(self.scenario["id"]) + 1
            phase = {"settling": "settle", "ready": "ready", "active": "active",
                     "finished": "finished", "interrupted": "interrupted"}.get(
                         self.state, self.state)
            coaching.update(
                attempt_id=self.attempt_id,
                outcome=self.outcome,
                scenario_index=scenario_index,
                scenario_total=self.scenario["implemented_total"],
                scenario_title=self.scenario["title"],
                rank_title=self.scenario["rank_title"],
                time_limit_seconds=self.scenario["timeout"],
                time_remaining_seconds=round(max(
                    0.0, self.scenario["timeout"] - self.active_elapsed), 3),
                phase=phase,
                countdown={"settle": "SETTLE", "ready": "READY", "active": "GO"}.get(phase),
                match_phase=self.match_phase,
            )
        return coaching

    def recording(self):
        summary = self.summary()
        return self.recorder.export(outcome=self.outcome, events=self.events, duration=summary["duration"])
