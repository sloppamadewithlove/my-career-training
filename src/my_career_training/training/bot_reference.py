"""Bot teaching-reference foundation: a timed speed-flip candidate and its evidence gates.

This module is deliberately self-contained. It contains no SDK, network or game
calls, no learned weights and no third-party input arrays. The controller is an
original, parameterised timing candidate; it is not claimed to perform a clean
speed flip. The evaluator only reports provisional gates and never certifies an
expert or world-record attempt.

Nothing here chooses a player index, sends inputs, or manufactures a recording.
Runtime origin metadata is supplied by a real capture worker; this module only
reads it.
"""

from copy import deepcopy
import hashlib
import json
import math

from .catalog import configure_lesson as _configure_lesson
from .catalog import lesson as _catalog_lesson
from .recordings import _rotate, euler_quaternion, validate_recording

CONTROLLER_ID = "speedflip-timed-candidate"
# Revision 3: recovery ground steer aims at the canonical +Y travel heading
# instead of yaw 0, and the step docstring now states that the frame is read.
CONTROLLER_REVISION = 3
PROFILES = ("cancel", "baseline")
LESSON_ID = "speed-flip"

# These are the acknowledged runtime configuration, not measurements of every
# physics property. Game speed is also checked in every observed sample.
CAPTURE_CONFIGURATION = {
    "map": "Stadium_P", "game_mode": "Soccar", "freeplay": True,
    "mutators": {"game_speed": "Default", "gravity": "Default",
                 "boost_amount": "NormalBoost", "match_length": "Unlimited",
                 "max_score": "Unlimited", "multi_ball": "One", "overtime": "Unlimited"},
}

# One physics packet at the supported 120 Hz capture rate, plus a float epsilon.
PACKET_SECONDS = 1.0 / 120.0
PACKET_EPSILON = 1e-6
MIN_JUMP_RELEASE_SECONDS = PACKET_SECONDS

NEUTRAL_ACTIONS = {
    "throttle": 0.0,
    "steer": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "roll": 0.0,
    "jump": False,
    "boost": False,
    "handbrake": False,
}

# Original timing candidate. These are this project's own numbers, not a copy of
# any external input array, and they are not claimed to be a clean speed flip.
DEFAULT_PARAMETERS = {
    "accelerate_seconds": 0.30,
    "steer_compensation_seconds": 0.05,
    "steer_compensation": -0.35,
    "jump_hold_seconds": 0.05,
    # A real release gap is required between the two jumps; without it the
    # second jump would be contiguous with the first and no edge would exist.
    "jump_release_seconds": 0.025,
    "dodge_hold_seconds": 0.05,
    "cancel_delay_seconds": 0.02,
    "cancel_hold_seconds": 0.10,
    "recovery_seconds": 0.20,
    # Modest bounded recovery gain, following the repo's bots/driving.py
    # convention of countering observed rotation. PROVISIONAL behaviour: the
    # ground steer is the signed wrapped heading error towards the canonical
    # +Y travel heading, not towards yaw 0.
    "recovery_gain": 0.5,
    "dodge_pitch": -1.0,
    "dodge_yaw": 1.0,
    "cancel_pitch": 1.0,
    "phase_max_seconds": 3.0,
    "timeout_seconds": 10.0,
}

_DURATION_KEYS = (
    "accelerate_seconds",
    "steer_compensation_seconds",
    "jump_hold_seconds",
    "jump_release_seconds",
    "dodge_hold_seconds",
    "cancel_delay_seconds",
    "cancel_hold_seconds",
    "recovery_seconds",
)
_AXIS_KEYS = ("steer_compensation", "dodge_pitch", "dodge_yaw", "cancel_pitch")
_GAIN_KEYS = ("recovery_gain",)
MAX_PHASE_SECONDS = 3.0
MAX_TIMEOUT_SECONDS = 10.0

DEFAULT_GATES = {
    # Declared candidate window for the dodge-to-cancel delay.
    "max_cancel_delay_seconds": 0.05,
    # One packet at 120 Hz plus a small float epsilon, not a loose 0.05 s.
    "packet_tolerance_seconds": PACKET_SECONDS + PACKET_EPSILON,
    # A recorded sample interval above this is a capture gap.
    "max_sample_interval_seconds": 0.05,
    "crossing_half_width": 500.0,
    "crossing_max_height": 300.0,
    "grounded_height": 30.0,
    "airborne_height": 100.0,
    "min_landing_roof_up": 0.7,
    "min_forward_alignment": 0.7,
    "max_landing_angular_speed": 2.0,  # PROVISIONAL
    "diagonal_action": 0.15,
    "cancel_action": 0.3,
    "metric_tolerance_seconds": 0.05,
    "metric_tolerance_speed": 50.0,
    "metric_tolerance_alignment": 0.10,
    "metric_tolerance_angular_speed": 0.5,
    "event_tolerance_seconds": 0.10,
}

LABEL_UNVALIDATED = "Bot trial (unvalidated)"
LABEL_PASSING = "Passing bot trial (this setup)"
LABEL_BASELINE = "Baseline bot trial (unvalidated)"


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _finite_vector(value, length=3):
    return isinstance(value, (list, tuple)) and len(value) == length and all(_finite(x) for x in value)


def _known(value):
    """A declared runtime value. Empty containers and 'unknown' are not known."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in ("unknown", "unavailable")
    if isinstance(value, (dict, list, tuple)):
        return bool(value)
    return True


def _neutral():
    return dict(NEUTRAL_ACTIONS)


def _clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


# The speed-flip lesson is authored on DFHStadium; these are the accepted
# aliases for that same arena. Mannfield and other maps are not this lesson.
MAP_ALIASES = {
    "dfhstadium": "DFHStadium",
    "dfhstadium_p": "DFHStadium",
    "stadium_p": "DFHStadium",
}

# Declared reset tolerances used to check the recorded first sample against the
# canonical lesson starting state (mirrors TrainingEngine's reset checks).
RESET_TOLERANCES = {
    "position": 120.0,
    "velocity": 40.0,
    "rotation": 0.15,
    "boost": 2.0,
}


def _canonical_map(value):
    if not isinstance(value, str):
        return None
    return MAP_ALIASES.get(value.strip().lower())


def _unknown_string(value):
    """True when a runtime string only acknowledges that nothing was measured."""
    text = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    if not text:
        return True
    if text in (
        "unknown",
        "unavailable",
        "n/a",
        "na",
        "none",
        "null",
        "tbd",
        "pending",
        "unmeasured",
        "unobserved",
        "unverified",
        "not measured",
        "not observed",
        "not verified",
        "not available",
        "not applicable",
        "not checked",
        "not captured",
        "not recorded",
        "not confirmed",
        "not tested",
    ):
        return True
    if text.startswith("not "):
        return True
    return any(
        token in text
        for token in (
            "not measured",
            "not observed",
            "not verified",
            "unmeasured",
            "unobserved",
            "unverified",
        )
    )


def _unknown_runtime_value(value):
    """Recursively reject unknown/unavailable/empty runtime mutator values.

    A string that only acknowledges the gap ("not measured", "not observed",
    "not verified", "n/a", ...) is not a declared runtime value, so it is
    rejected here rather than being treated as evidence. Real booleans stay
    valid; only string placeholders are refused.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return _unknown_string(value)
    if isinstance(value, dict):
        return not value or any(_unknown_runtime_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return not value or any(_unknown_runtime_value(item) for item in value)
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(value)
    return True


def _distance(first, second):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _rotation_distance(first, second):
    a, b = euler_quaternion(first), euler_quaternion(second)
    dot = min(1.0, abs(sum(x * y for x, y in zip(a, b))))
    return 2 * math.acos(dot)


def _canonical_starting_state(recording):
    """The exact canonical lesson starting state for the declared variation."""
    variant = recording.get("variant")
    if not isinstance(variant, dict):
        return None
    allowed = {"side", "angle", "target_zone", "simplified"}
    if set(variant) - allowed:
        return None
    try:
        return _configure_lesson(
            LESSON_ID,
            side=variant.get("side", "right"),
            target_zone=variant.get("target_zone"),
            angle=variant.get("angle", "center"),
            simplified=variant.get("simplified", False),
        )["starting_state"]
    except (ValueError, TypeError):
        return None


def _start_matches(recording, canonical):
    """The recorded first sample must match the canonical start, not just itself."""
    samples = recording["samples"]
    first = samples[0]
    car = canonical.get("car") or {}
    if not _finite_vector(first.get("position")) or not _finite_vector(first.get("rotation")):
        return False
    if not _finite_vector(car.get("position")) or not _finite_vector(car.get("rotation")):
        return False
    if _distance(first["position"], car["position"]) > RESET_TOLERANCES["position"]:
        return False
    if _rotation_distance(first["rotation"], car["rotation"]) > RESET_TOLERANCES["rotation"]:
        return False
    if _finite_vector(first.get("velocity")) and _finite_vector(car.get("velocity")):
        if _distance(first["velocity"], car["velocity"]) > RESET_TOLERANCES["velocity"]:
            return False
    observed = (recording.get("metadata") or {}).get("observed_start")
    if isinstance(observed, dict):
        observed_car = observed.get("car")
        if isinstance(observed_car, dict) and _finite_vector(observed_car.get("position")):
            if _distance(observed_car["position"], car["position"]) > RESET_TOLERANCES["position"]:
                return False
    return True


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _resolve_parameters(parameters):
    resolved = dict(DEFAULT_PARAMETERS)
    for key, value in (parameters or {}).items():
        if key not in resolved:
            raise ValueError(f"Unknown speed-flip candidate parameter: {key}")
        if key in _DURATION_KEYS:
            if not _finite(value) or value < 0:
                raise ValueError(f"{key} must be a finite nonnegative duration.")
        elif key in _AXIS_KEYS:
            if not _finite(value) or not -1 <= value <= 1:
                raise ValueError(f"{key} must be a finite action value between -1 and 1.")
        elif key in _GAIN_KEYS:
            if not _finite(value) or not 0 <= value <= 1:
                raise ValueError(f"{key} must be a finite gain between 0 and 1.")
        elif key in ("phase_max_seconds", "timeout_seconds"):
            if not _finite(value) or value <= 0:
                raise ValueError(f"{key} must be a finite positive bound.")
        else:  # pragma: no cover - defensive, keys are fixed above
            raise ValueError(f"Unknown speed-flip candidate parameter: {key}")
        resolved[key] = value
    if resolved["phase_max_seconds"] > MAX_PHASE_SECONDS:
        raise ValueError("The candidate phase bound may not exceed 3 seconds.")
    if resolved["timeout_seconds"] > MAX_TIMEOUT_SECONDS:
        raise ValueError("The candidate timeout may not exceed the lesson's 10 second limit.")
    if resolved["jump_release_seconds"] < MIN_JUMP_RELEASE_SECONDS:
        raise ValueError("The jump release gap must be at least one 120 Hz packet.")
    if resolved["dodge_pitch"] >= 0:
        raise ValueError("The candidate dodge pitch must be negative (nose down).")
    if resolved["cancel_pitch"] <= 0:
        raise ValueError("The candidate opposing pitch must be positive.")
    if resolved["dodge_yaw"] == 0:
        raise ValueError("The candidate dodge yaw must select a side.")
    if resolved["timeout_seconds"] <= resolved["phase_max_seconds"]:
        raise ValueError("The candidate timeout must exceed the phase bound.")
    return resolved


def _resolve_gates(gates):
    resolved = dict(DEFAULT_GATES)
    for key, value in (gates or {}).items():
        if key not in resolved:
            raise ValueError(f"Unknown bot-trial gate: {key}")
        if not _finite(value) or value < 0:
            raise ValueError("Bot-trial gates must be finite nonnegative numbers.")
        resolved[key] = value
    return resolved


class SpeedFlipTrialController:
    """Timed speed-flip candidate for a parallel capture worker.

    ``step(elapsed_seconds)`` takes GAME seconds since the engine's Go event.
    There is no wall-clock or step-count assumption. Invalid, non-finite or
    backward time returns neutral actions and marks the attempt interrupted.
    The controller never chooses a player index and never sends inputs.
    """

    def __init__(self, profile="cancel", parameters=None):
        if profile not in PROFILES:
            raise ValueError("Speed-flip candidate profile must be 'cancel' or 'baseline'.")
        self.profile = profile
        self.parameters = _resolve_parameters(parameters)
        p = self.parameters
        self._steer_start = p["accelerate_seconds"]
        self._jump_start = self._steer_start + p["steer_compensation_seconds"]
        self._jump_release = self._jump_start + p["jump_hold_seconds"]
        # A real release gap keeps the two jump presses as distinct edges.
        self._dodge_start = self._jump_release + p["jump_release_seconds"]
        self._dodge_release = self._dodge_start + p["dodge_hold_seconds"]
        self._cancel_start = self._dodge_start + p["cancel_delay_seconds"]
        self._cancel_end = self._cancel_start + p["cancel_hold_seconds"]
        self._recovery_end = self._cancel_end + p["recovery_seconds"]
        if self._recovery_end > p["phase_max_seconds"]:
            raise ValueError("Candidate phases must finish inside the declared phase bound.")
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self):
        self._last_elapsed = None
        self.interrupted = False
        self.timed_out = False
        self._finished = False
        return None

    def finish(self):
        """The caller observed the attempt end (for example a crossing)."""
        self._finished = True
        return None

    @property
    def finished(self):
        return self._finished

    # -- control -----------------------------------------------------------
    def step(self, elapsed_seconds, frame=None):
        """Return all eight logical actions for this game-time instant.

        ``frame`` is optional worker-supplied car state. The declared timing
        schedule always decides the phases; during the recovery phase the
        observed car rotation is read to bound roll counter-rotation and to
        steer towards the canonical +Y travel heading. The frame never chooses
        a player index and never overrides the declared schedule.
        """
        if self._finished:
            return _neutral()
        if (
            isinstance(elapsed_seconds, bool)
            or not _finite(elapsed_seconds)
            or elapsed_seconds < 0
            or (self._last_elapsed is not None and elapsed_seconds < self._last_elapsed)
        ):
            self.interrupted = True
            self._finished = True
            return _neutral()
        if elapsed_seconds > self.parameters["timeout_seconds"]:
            self.timed_out = True
            self._finished = True
            return _neutral()
        self._last_elapsed = elapsed_seconds
        return self._actions_at(elapsed_seconds, frame)

    def _actions_at(self, t, frame=None):
        p = self.parameters
        actions = _neutral()
        actions["throttle"] = 1.0
        actions["boost"] = True
        if t < self._steer_start:
            return actions
        if t < self._jump_start:
            actions["steer"] = p["steer_compensation"]
            return actions
        if t < self._dodge_start:
            # First jump, then a genuine release gap before the dodge press.
            actions["jump"] = t < self._jump_release
            return actions
        if t < self._cancel_start:
            actions["jump"] = t < self._dodge_release
            actions["pitch"] = p["dodge_pitch"]
            actions["yaw"] = p["dodge_yaw"]
            return actions
        if t < self._cancel_end:
            actions["pitch"] = p["cancel_pitch"] if self.profile == "cancel" else 0.0
            return actions
        if t < self._recovery_end:
            return self._recovery_actions(actions, frame)
        return actions

    def _recovery_actions(self, actions, frame):
        """Modest bounded recovery from the observed car rotation.

        Follows the repo's bots/driving.py convention of countering observed
        rotation, but deliberately uses roll only plus ground steering. No pitch
        is emitted here, so the baseline profile cannot accidentally introduce an
        opposing-pitch cancel while the flip is still ongoing. Ground steering
        aims at the canonical +Y travel heading (yaw pi/2), not yaw 0. PROVISIONAL.
        """
        gain = self.parameters["recovery_gain"]
        car = (frame or {}).get("car") if isinstance(frame, dict) else None
        if not isinstance(car, dict):
            return actions
        rotation = car.get("rotation")
        if not _finite_vector(rotation):
            return actions
        actions["roll"] = _clamp(-rotation[2] * gain)
        contact = car.get("wheel_contact")
        grounded = contact is True or (
            _finite_vector(car.get("position")) and car["position"][2] <= 30
        )
        if grounded:
            # The canonical speed-flip starts at yaw pi/2 and travels +Y, so the
            # ground steer is the signed wrapped heading error towards +Y, using
            # the same atan2(sin, cos) convention as bots/driving.py. Steering
            # towards yaw 0 would aim the car off the canonical travel axis.
            heading = math.pi / 2
            error = math.atan2(math.sin(heading - rotation[1]), math.cos(heading - rotation[1]))
            actions["steer"] = _clamp(error * gain)
        return actions

    # -- provenance --------------------------------------------------------
    def controller_plan(self):
        """JSON-safe identity, revision, default timing and bounds."""
        p = self.parameters
        phases = [
            ("accelerate_boost", 0.0, self._steer_start),
            ("steer_compensation", self._steer_start, self._jump_start),
            ("first_jump", self._jump_start, self._jump_release),
            ("jump_release", self._jump_release, self._dodge_start),
            ("diagonal_dodge", self._dodge_start, self._cancel_start),
            (
                "opposing_pitch" if self.profile == "cancel" else "no_cancel_control",
                self._cancel_start,
                self._cancel_end,
            ),
            ("grounded_recovery", self._cancel_end, self._recovery_end),
            ("boost_through_finish", self._recovery_end, p["timeout_seconds"]),
        ]
        return {
            "controller_id": CONTROLLER_ID,
            "revision": CONTROLLER_REVISION,
            "profile": self.profile,
            "lesson_id": LESSON_ID,
            "parameters": deepcopy(p),
            "phases": [
                {"name": name, "start_seconds": start, "end_seconds": end}
                for name, start, end in phases
            ],
            "bounds": {
                "phase_max_seconds": p["phase_max_seconds"],
                "timeout_seconds": p["timeout_seconds"],
            },
            "time_base": "game_seconds_since_go",
            "chooses_player_index": False,
            "sends_inputs": False,
            "claim": "Original timed candidate; not claimed to perform a clean speed flip.",
            "recovery": {
                "behavior": "roll-only counter-rotation plus ground steering towards the canonical +Y heading",
                "provisional": True,
                "emits_pitch": False,
                "ground_steer_target_yaw": math.pi / 2,
            },
            "external_weights": False,
        }


def controller_plan(profile="cancel", parameters=None):
    """Module-level helper for the parallel capture worker."""
    return SpeedFlipTrialController(profile=profile, parameters=parameters).controller_plan()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _profile_of(recording, summary):
    for value in (
        (summary or {}).get("profile"),
        (recording.get("metadata") or {}).get("bot_profile"),
        ((recording.get("metadata") or {}).get("source") or {}).get("profile"),
        ((recording.get("metadata") or {}).get("source") or {}).get("control_profile"),
    ):
        if isinstance(value, str) and value:
            return value
    return None


def setup_fingerprint(recording):
    """Setup-only identity so a cancel trial and its no-cancel control compare.

    Deliberately excludes the actor, the control-script profile and any per-run
    hash, so a baseline and a candidate of the same setup share a fingerprint.
    """
    metadata = recording.get("metadata") or {}
    setup = {
        "lesson_id": recording.get("lesson_id"),
        "lesson_version": recording.get("lesson_version"),
        "variant": recording.get("variant"),
        "game_version": metadata.get("game_version"),
        "framework_version": metadata.get("framework_version"),
        "car_hitbox": metadata.get("car_hitbox"),
        # Canonical arena identity so accepted aliases compare as one setup.
        "map": _canonical_map(metadata.get("map")) or metadata.get("map"),
        "mutators": metadata.get("mutators"),
        "starting_state": metadata.get("starting_state"),
    }
    return _sha256(setup)


def _events_by_name(summary):
    observed = {}
    for event in (summary or {}).get("events") or []:
        if not isinstance(event, dict) or event.get("type") != "skill":
            continue
        # Only a plain "observed" confidence counts. Estimated, uncertain,
        # coaching-suggestion and any other string are not evidence.
        if event.get("confidence") != "observed":
            continue
        name = event.get("name")
        if isinstance(name, str) and name not in observed:
            observed[name] = event
    return observed


def _corroborate(recording, gates):
    """Re-derive the important claims from recorded pose/velocity/actions."""
    samples = recording["samples"]
    origin = samples[0]["time"]
    problems = []
    found = {
        "first_jump_time": None,
        "dodge_time": None,
        "dodge_pitch": None,
        "cancel_time": None,
        "cancel_delay": None,
        "crossing_time": None,
        "crossing_location": None,
        "crossing_speed": None,
        "landing_time": None,
        "landing_roof_up": None,
        "landing_forward_alignment": None,
        "landing_speed": None,
        "landing_angular_speed": None,
        "landing_ground_contact": None,
    }
    jump_edges = [
        index
        for index in range(1, len(samples))
        if samples[index]["actions"]["jump"] and not samples[index - 1]["actions"]["jump"]
    ]
    if len(jump_edges) < 2:
        problems.append("Recorded actions do not show a first jump followed by a second jump.")
        return found, problems
    found["first_jump_time"] = samples[jump_edges[0]]["time"] - origin
    dodge_index = jump_edges[1]
    dodge_actions = samples[dodge_index]["actions"]
    if (
        abs(dodge_actions["pitch"]) < gates["diagonal_action"]
        or abs(dodge_actions["yaw"]) < gates["diagonal_action"]
    ):
        problems.append("The second jump was not a recorded diagonal dodge.")
    found["dodge_time"] = samples[dodge_index]["time"] - origin
    found["dodge_pitch"] = dodge_actions["pitch"]
    for index in range(dodge_index + 1, len(samples)):
        actions = samples[index]["actions"]
        if actions["pitch"] * found["dodge_pitch"] < 0 and abs(actions["pitch"]) >= gates["cancel_action"]:
            found["cancel_time"] = samples[index]["time"] - origin
            found["cancel_delay"] = found["cancel_time"] - found["dodge_time"]
            break
    for index in range(1, len(samples)):
        previous, current = samples[index - 1], samples[index]
        if previous["position"][1] < 0 <= current["position"][1]:
            span = current["position"][1] - previous["position"][1]
            ratio = (0 - previous["position"][1]) / span if span else 0.0
            location = [
                a + ratio * (b - a) for a, b in zip(previous["position"], current["position"])
            ]
            found["crossing_time"] = previous["time"] + ratio * (current["time"] - previous["time"]) - origin
            found["crossing_location"] = location
            found["crossing_speed"] = math.sqrt(sum(x * x for x in current["velocity"]))
            break
    airborne = None
    for index in range(dodge_index, len(samples)):
        if samples[index]["position"][2] > gates["airborne_height"]:
            airborne = index
            break
    if airborne is not None:
        for index in range(airborne + 1, len(samples)):
            sample = samples[index]
            contact = sample.get("wheel_contact")
            grounded = contact is True or sample["position"][2] <= gates["grounded_height"]
            if not grounded:
                continue
            quaternion = euler_quaternion(sample["rotation"])
            roof = _rotate(quaternion, [0, 0, 1])
            forward = _rotate(quaternion, [1, 0, 0])
            velocity = sample["velocity"]
            speed = math.sqrt(sum(x * x for x in velocity))
            found["landing_time"] = sample["time"] - origin
            found["landing_roof_up"] = roof[2]
            found["landing_forward_alignment"] = (
                sum(a * b for a, b in zip(forward, velocity)) / speed if speed else 0.0
            )
            found["landing_speed"] = speed
            if _finite_vector(sample.get("angular_velocity")):
                found["landing_angular_speed"] = math.sqrt(
                    sum(x * x for x in sample["angular_velocity"])
                )
            if isinstance(contact, bool):
                found["landing_ground_contact"] = contact
            break
    return found, problems


def _evaluate(recording, summary, gates, *, require_cancel):
    reasons = []
    notes = []
    metrics = {}
    result = {
        "eligible": False,
        "reasons": reasons,
        "metrics": metrics,
        "label": LABEL_UNVALIDATED,
        "recording_sha256": None,
        "setup_fingerprint": None,
        "provisional": True,
        "certification": "none",
        "gates": deepcopy(gates),
        "notes": notes,
    }
    if not isinstance(recording, dict) or not isinstance(summary, dict):
        reasons.append("A bot trial needs a recording object and its engine summary.")
        return result
    try:
        validate_recording(recording)
    except ValueError as exc:
        reasons.append(str(exc))
        return result
    result["recording_sha256"] = _sha256(recording)
    result["setup_fingerprint"] = setup_fingerprint(recording)

    lesson = _catalog_lesson(LESSON_ID)
    if recording.get("lesson_id") != LESSON_ID or recording.get("lesson_version") != lesson["version"]:
        reasons.append("The recording is not the current speed-flip lesson version.")
    if not isinstance(recording.get("variant"), dict):
        reasons.append("The recording does not declare its lesson variation.")

    metadata = recording["metadata"]
    source = metadata.get("source") or {}
    if source.get("kind") != "actual_execution":
        reasons.append("Only an actual bot execution can be a bot teaching reference.")
    if source.get("actor") != "bot":
        reasons.append("The recording source actor is not a bot.")
    if not isinstance(source.get("origin"), str) or not source["origin"].strip():
        reasons.append("The recording does not identify its capture origin.")

    for key in ("game_version", "framework_version", "car_hitbox"):
        if not _known(metadata.get(key)):
            reasons.append(f"Runtime metadata {key} must be known.")
    if _canonical_map(metadata.get("map")) is None:
        reasons.append("The map must be this lesson's arena (DFHStadium).")
    if "mutators" not in metadata or not isinstance(metadata["mutators"], dict) or not metadata["mutators"]:
        reasons.append("Runtime mutators must be declared exactly.")
    elif _unknown_runtime_value(metadata["mutators"]):
        reasons.append("Runtime mutators contain unknown, unavailable or empty values.")
    mutators = metadata.get("mutators") or {}
    if (mutators.get("source") != "rlbot_match_configuration"
            or mutators.get("requested") != CAPTURE_CONFIGURATION
            or mutators.get("acknowledged") != CAPTURE_CONFIGURATION):
        reasons.append("The runtime must acknowledge the exact canonical capture configuration and mutators.")
    starting_state = metadata.get("starting_state")
    if not isinstance(starting_state, dict) or not starting_state:
        reasons.append("The exact starting state must be declared.")
    else:
        canonical = _canonical_starting_state(recording)
        if canonical is None:
            reasons.append("The lesson variation is not a supported speed-flip setup.")
        else:
            if starting_state != canonical:
                reasons.append("The declared starting state does not match the canonical lesson starting state.")
            if not _start_matches(recording, canonical):
                reasons.append("The recorded start does not match the canonical lesson starting state.")

    # Outcome: a candidate must succeed. A no-cancel baseline cannot succeed in
    # the real engine (it requires opposing_pitch), so a genuine timeout is
    # accepted only when the crossing and landing are independently complete.
    outcome = recording.get("outcome")
    if require_cancel:
        if outcome != "success":
            reasons.append("The attempt did not record a successful outcome.")
    else:
        if outcome not in ("success", "timeout"):
            reasons.append("A baseline must record a success or a genuine timeout.")
        elif outcome == "timeout":
            notes.append("Baseline ended by timeout; completeness is checked from the samples.")
    if recording.get("truncated"):
        reasons.append("A truncated capture cannot be a bot teaching reference.")

    if isinstance(starting_state, dict) and starting_state:
        if "game_speed" not in starting_state:
            reasons.append("The starting state must declare normal game speed.")
        elif not _finite(starting_state["game_speed"]) or starting_state["game_speed"] != 1.0:
            reasons.append("Only normal game speed is supported.")
    samples = recording["samples"]
    for sample in samples:
        if "game_speed" not in sample:
            reasons.append("Every sample must declare its game speed.")
            break
        if not _finite(sample["game_speed"]) or sample["game_speed"] != 1.0:
            reasons.append("Only normal game speed is supported.")
            break
    if any(sample.get("packet_gap") for sample in samples):
        reasons.append("The capture contains packet gaps.")
    for index in range(1, len(samples)):
        if samples[index]["time"] - samples[index - 1]["time"] > gates["max_sample_interval_seconds"]:
            reasons.append("The capture contains a sample gap.")
            break
    summary_metrics = summary.get("metrics") or {}
    if summary_metrics.get("packet_gaps") not in (0, None):
        reasons.append("The engine summary reports packet gaps.")

    profile = _profile_of(recording, summary)
    expected_profile = "cancel" if require_cancel else "baseline"
    if profile != expected_profile:
        reasons.append(f"The trial profile must be '{expected_profile}'.")

    found, problems = _corroborate(recording, gates)
    reasons.extend(problems)

    events = _events_by_name(summary)
    required = ["first_jump", "diagonal_dodge", "target_crossed", "landed"]
    if require_cancel:
        required.insert(2, "opposing_pitch")
    for name in required:
        if name not in events:
            reasons.append(f"The engine summary does not report an observed {name} event.")

    if not problems and all(name in events for name in required):
        jump = events["first_jump"]["time"]
        dodge = events["diagonal_dodge"]["time"]
        crossing = events["target_crossed"]["details"].get("crossing_time", events["target_crossed"]["time"])
        landing = events["landed"]["time"]
        if not (jump <= dodge):
            reasons.append("The first jump did not precede the diagonal dodge.")
        if require_cancel:
            cancel = events["opposing_pitch"]["time"]
            if not (dodge < cancel <= crossing and cancel <= landing):
                reasons.append("The opposing pitch was not observed between the dodge and the crossing.")
            delay = events["opposing_pitch"]["details"].get("delay_seconds", cancel - dodge)
            if not _finite(delay) or delay < 0:
                reasons.append("The dodge-to-cancel delay is not a finite nonnegative value.")
            else:
                declared = DEFAULT_PARAMETERS["cancel_delay_seconds"]
                if delay > gates["max_cancel_delay_seconds"]:
                    reasons.append("The dodge-to-cancel delay exceeds the declared candidate window.")
                if delay > declared + gates["packet_tolerance_seconds"]:
                    reasons.append("The dodge-to-cancel delay exceeds the candidate window plus one packet.")
            # The cancel metric must be corroborated by the recorded actions at
            # packet precision, not excused by the loose event tolerance.
            if found["cancel_time"] is None:
                reasons.append("Recorded actions do not corroborate the opposing pitch.")
            elif abs(found["cancel_time"] - cancel) > gates["packet_tolerance_seconds"]:
                reasons.append("The recorded actions do not corroborate the reported cancel time.")
            elif found["cancel_delay"] > gates["max_cancel_delay_seconds"]:
                reasons.append("The recorded dodge-to-cancel delay exceeds the declared window.")
        else:
            if not (dodge <= crossing and dodge <= landing):
                reasons.append("The baseline dodge did not precede its crossing and landing.")
            # A no-cancel control must not contain an actual cancel anywhere.
            if "opposing_pitch" in events:
                reasons.append("The baseline summary reports an opposing pitch; it is not a no-cancel control.")
            if found["cancel_time"] is not None:
                reasons.append("The baseline samples contain an opposing pitch input.")

        for name, value in (
            ("first_jump", found["first_jump_time"]),
            ("diagonal_dodge", found["dodge_time"]),
            ("target_crossed", found["crossing_time"]),
            ("landed", found["landing_time"]),
        ):
            if value is None:
                reasons.append(f"Recorded samples do not corroborate the {name} event.")
            elif abs(events[name]["time"] - value) > gates["event_tolerance_seconds"]:
                reasons.append(f"The reported {name} time is not corroborated by the recorded samples.")

        location = found["crossing_location"]
        if found["crossing_time"] is None or found["crossing_time"] <= 0:
            reasons.append("The recorded crossing time must be positive.")
        if found["crossing_speed"] is None or found["crossing_speed"] <= 0:
            reasons.append("The recorded crossing speed must be positive.")
        if location is None:
            reasons.append("No positive-Y crossing of the finish plane was recorded.")
        elif (
            abs(location[0]) > gates["crossing_half_width"]
            or location[2] > gates["crossing_max_height"]
        ):
            reasons.append("The recorded crossing was outside the finish rectangle.")

        if found["landing_roof_up"] is None:
            reasons.append("No grounded recovery after the dodge was recorded.")
        else:
            if found["landing_roof_up"] < gates["min_landing_roof_up"]:
                reasons.append("The recorded landing was not roof-up.")
            if found["landing_forward_alignment"] < gates["min_forward_alignment"]:
                reasons.append("The recorded landing was not forward-aligned.")
            if found["landing_speed"] <= 0:
                reasons.append("The recorded landing speed must be positive.")
            # Physical landing evidence must come from the samples themselves.
            if found["landing_angular_speed"] is None:
                reasons.append(
                    "Recorded samples do not carry angular velocity; landing angular speed is not corroborated."
                )
            elif found["landing_angular_speed"] > gates["max_landing_angular_speed"]:
                reasons.append("The recorded landing angular speed exceeds the provisional threshold.")
            if found["landing_ground_contact"] is not True:
                reasons.append("Recorded samples do not show actual wheel contact at the landing.")

        for key in (
            "crossing_seconds",
            "crossing_speed",
            "landing_roof_up",
            "landing_forward_alignment",
            "landing_speed",
            "landing_angular_speed",
        ):
            if not _finite(summary_metrics.get(key)):
                reasons.append(f"The engine summary metric {key} must be finite.")
        if _finite(summary_metrics.get("crossing_seconds")) and found["crossing_time"] is not None:
            if abs(summary_metrics["crossing_seconds"] - found["crossing_time"]) > gates[
                "metric_tolerance_seconds"
            ]:
                reasons.append("The reported crossing time does not match the recorded samples.")
        if _finite(summary_metrics.get("crossing_speed")) and found["crossing_speed"] is not None:
            if abs(summary_metrics["crossing_speed"] - found["crossing_speed"]) > gates[
                "metric_tolerance_speed"
            ]:
                reasons.append("The reported crossing speed does not match the recorded samples.")
        if _finite(summary_metrics.get("landing_roof_up")) and found["landing_roof_up"] is not None:
            if abs(summary_metrics["landing_roof_up"] - found["landing_roof_up"]) > gates[
                "metric_tolerance_alignment"
            ]:
                reasons.append("The reported landing roof-up value does not match the recorded samples.")
        if _finite(summary_metrics.get("landing_forward_alignment")) and found["landing_forward_alignment"] is not None:
            if abs(summary_metrics["landing_forward_alignment"] - found["landing_forward_alignment"]) > gates[
                "metric_tolerance_alignment"
            ]:
                reasons.append("The reported forward alignment does not match the recorded samples.")
        if _finite(summary_metrics.get("landing_speed")) and found["landing_speed"] is not None:
            if abs(summary_metrics["landing_speed"] - found["landing_speed"]) > gates[
                "metric_tolerance_speed"
            ]:
                reasons.append("The reported landing speed does not match the recorded samples.")
        if _finite(summary_metrics.get("landing_angular_speed")) and found["landing_angular_speed"] is not None:
            if abs(summary_metrics["landing_angular_speed"] - found["landing_angular_speed"]) > gates[
                "metric_tolerance_angular_speed"
            ]:
                reasons.append("The reported landing angular speed does not match the recorded samples.")

    metrics.update(
        {
            "crossing_seconds": found["crossing_time"],
            "crossing_speed": found["crossing_speed"],
            "crossing_location": found["crossing_location"],
            "dodge_to_cancel_seconds": found["cancel_delay"],
            "landing_roof_up": found["landing_roof_up"],
            "landing_forward_alignment": found["landing_forward_alignment"],
            "landing_speed": found["landing_speed"],
            "landing_angular_speed": found["landing_angular_speed"],
            "landing_ground_contact": found["landing_ground_contact"],
            "packet_gaps": summary_metrics.get("packet_gaps"),
            "duration": recording.get("duration"),
        }
    )
    result["eligible"] = not reasons
    result["label"] = LABEL_PASSING if result["eligible"] else LABEL_UNVALIDATED
    notes.append("Provisional gates only; this is not an expert or world-record certification.")
    return result


def evaluate_bot_trial(recording, summary, *, gates=None):
    """Evaluate one candidate bot attempt. Never mutates the recording."""
    return _evaluate(recording, summary, _resolve_gates(gates), require_cancel=True)


def evaluate_bot_baseline(recording, summary, *, gates=None):
    """Evaluate a no-cancel control: completeness, crossing and recovery only."""
    result = _evaluate(recording, summary, _resolve_gates(gates), require_cancel=False)
    result["label"] = LABEL_BASELINE if result["eligible"] else LABEL_UNVALIDATED
    return result


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        return None
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def select_bot_benchmark(trials, baselines, *, minimum_repeats=3):
    """Choose the fastest passing candidate against same-setup no-cancel controls.

    Returns ``status='eligible_for_review'`` only. Distribution permission stays
    separate and defaults to false; nothing is promoted to a teaching bundle.
    """
    if isinstance(minimum_repeats, bool) or not isinstance(minimum_repeats, int) or minimum_repeats < 1:
        raise ValueError("minimum_repeats must be a positive integer.")
    reasons = []
    notes = []
    candidate_results = []
    for item in trials or []:
        if not isinstance(item, dict):
            reasons.append("Each candidate trial must be a recording/summary object.")
            continue
        candidate_results.append(evaluate_bot_trial(item.get("recording"), item.get("summary")))
    baseline_results = []
    for item in baselines or []:
        if not isinstance(item, dict):
            reasons.append("Each baseline trial must be a recording/summary object.")
            continue
        baseline_results.append(evaluate_bot_baseline(item.get("recording"), item.get("summary")))

    passing = [result for result in candidate_results if result["eligible"]]
    complete = [result for result in baseline_results if result["eligible"]]
    # A repeated recording hash is the same execution, not an independent repeat.
    distinct_passing = {result["recording_sha256"] for result in passing}
    distinct_complete = {result["recording_sha256"] for result in complete}
    if len(distinct_passing) < len(passing):
        reasons.append("Duplicate candidate recordings are not independent repetitions.")
    if len(distinct_complete) < len(complete):
        reasons.append("Duplicate baseline recordings are not independent repetitions.")
    if len(distinct_passing) < minimum_repeats:
        reasons.append(
            f"Only {len(distinct_passing)} distinct passing candidate repetitions; "
            f"{minimum_repeats} are required."
        )
    if len(distinct_complete) < minimum_repeats:
        reasons.append(
            f"Only {len(distinct_complete)} distinct complete no-cancel baselines; "
            f"{minimum_repeats} are required."
        )

    fingerprints = {result["setup_fingerprint"] for result in passing + complete}
    if len(fingerprints) > 1:
        reasons.append("Candidate and baseline trials do not share one exact setup fingerprint.")
    fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None

    candidate_median = _median([result["metrics"]["crossing_seconds"] for result in passing])
    baseline_median = _median([result["metrics"]["crossing_seconds"] for result in complete])
    improvement = None
    if candidate_median is not None and baseline_median is not None:
        improvement = baseline_median - candidate_median
        if improvement <= 0:
            reasons.append("The candidate median crossing time does not improve on the baseline median.")

    chosen = None
    if passing:
        best = min(passing, key=lambda result: result["metrics"]["crossing_seconds"])
        chosen = {
            "recording_sha256": best["recording_sha256"],
            "crossing_seconds": best["metrics"]["crossing_seconds"],
            "duration": best["metrics"]["duration"],
            "label": best["label"],
            "metrics": deepcopy(best["metrics"]),
        }

    eligible = not reasons
    notes.append("Status is review eligibility only; no teaching bundle is promoted.")
    notes.append("Distribution permission is separate and defaults to false.")
    return {
        "status": "eligible_for_review" if eligible else "not_eligible",
        "eligible": eligible,
        "reasons": reasons,
        "notes": notes,
        "setup_fingerprint": fingerprint,
        "profile": "cancel",
        "minimum_repeats": minimum_repeats,
        "candidate_repetitions": len(passing),
        "baseline_repetitions": len(complete),
        "candidate_median_crossing_seconds": candidate_median,
        "baseline_median_crossing_seconds": baseline_median,
        "improvement_seconds": improvement,
        "candidate": chosen,
        "distribution_permission": False,
        "certification": "none",
        "provisional": True,
    }
