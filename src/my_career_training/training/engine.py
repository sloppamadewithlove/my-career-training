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
    ):
        if not isinstance(strict_capture, bool):
            raise ValueError("Strict capture cadence must be an explicit boolean.")
        self.strict_capture = strict_capture
        self.lesson = configure_lesson(
            lesson_id, side=side, target_zone=target_zone, angle=angle, simplified=simplified
        )
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
        return deepcopy(self.lesson["settle_state"])

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
            raise ValueError("Training requires a finite game timestamp.")
        car, ball = frame.get("car", {}), frame.get("ball", {})
        if any(not _finite_vector(car.get(k)) for k in ("position", "velocity", "rotation")) or any(
            not _finite_vector(ball.get(k)) for k in ("position", "velocity")
        ):
            raise ValueError("Training requires actual finite car and ball telemetry.")
        if "angular_velocity" in car and not _finite_vector(car["angular_velocity"]):
            raise ValueError("Training requires finite angular velocity.")
        actions = frame.get("actions", {})
        for key in ("throttle", "steer", "pitch", "yaw", "roll"):
            value = actions.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not -1 <= value <= 1
            ):
                raise ValueError("Training requires observed analog game actions.")
        if any(not isinstance(actions.get(key), bool) for key in ("jump", "boost", "handbrake")):
            raise ValueError("Training requires observed jump, boost, and handbrake actions.")

    def update(self, frame):
        self._validate_frame(frame)
        if self.finished:
            return []
        now, car = frame["time"], frame["car"]
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
            )
            if valid:
                if self.settle_start is None:
                    self.settle_start = now
                self.settle_samples += 1
            else:
                self.settle_start = None
                self.settle_samples = 0
            self.preparation["valid_samples"] = self.settle_samples
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
            applied = (
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
                and not cadence["gap"]
                and elapsed < 2.0
            )
            if not applied:
                if elapsed >= 2.0:
                    return self._interrupt(
                        "The starting state was not confirmed. Enable state setting and retry."
                    )
                self.last_frame = deepcopy(frame)
                return []
            self.state, self.started_at = "active", now
            self.last_frame = None
            self.recorder = Recorder(self.lesson, self.metadata, max_samples=self.max_samples)
            self.last_touch_time = (_touch(car, frame["ball"]) or {}).get(
                "game_seconds", (_touch(car, frame["ball"]) or {}).get("time")
            )
            self.recorder.append(frame)
            self.last_frame = deepcopy(frame)
            return [{"type": "go", "message": "Go", "attempt_id": self.attempt_id}]
        previous = self.last_frame
        cadence = self.cadence(previous, frame)
        dt = cadence["dt"] if cadence["dt"] is not None else now - previous["time"]
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
        if now - self.started_at >= self.lesson["timeout"]:
            self._finish("timeout")
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
                        self._once("goal_target", frame)
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

    def summary(self):
        duration = (
            0
            if self.started_at is None
            else max(0, (self.last_frame or {"time": self.started_at})["time"] - self.started_at)
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
        return coaching

    def recording(self):
        summary = self.summary()
        return self.recorder.export(outcome=self.outcome, events=self.events, duration=summary["duration"])
