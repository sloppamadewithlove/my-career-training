"""Bounded recordings and provenance checks. Imported claims are never independently certified."""

from bisect import bisect_right
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path

MAX_SAMPLES = 36_000
MAX_RECORDING_BYTES = 24 * 1024 * 1024
METADATA_KEYS = (
    "game_version",
    "framework_version",
    "car_hitbox",
    "map",
    "mutators",
    "starting_state",
    "time_base",
    "source",
    "permission",
    "success_evidence",
)
ACTION_KEYS = ("throttle", "steer", "pitch", "yaw", "roll", "jump", "boost", "handbrake")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vector(value, length):
    return isinstance(value, (list, tuple)) and len(value) == length and all(_finite(x) for x in value)


def validate_recording(value, *, require_reference=False):
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("Unsupported recording version; the original file is unchanged.")
    if not _finite(value.get("duration")) or value["duration"] < 0:
        raise ValueError("Recording duration must be finite and nonnegative.")
    metadata, samples = value.get("metadata"), value.get("samples")
    if not isinstance(metadata, dict) or any(key not in metadata for key in METADATA_KEYS):
        raise ValueError("Recording is missing source, permission, version, setup, or timing metadata.")
    if not isinstance(value.get("lesson_id"), str) or type(value.get("lesson_version")) is not int:
        raise ValueError("Recording is missing its lesson identity.")
    if (
        not isinstance(metadata["starting_state"], dict)
        or not isinstance(metadata["mutators"], dict)
        or not isinstance(metadata["success_evidence"], list)
    ):
        raise ValueError("Recording setup, mutators, and success evidence are malformed.")
    if not isinstance(metadata["source"], dict) or not isinstance(metadata["permission"], dict):
        raise ValueError("Recording source and distribution permission must be explicit.")
    if metadata["time_base"] != "game_seconds":
        raise ValueError("This recording does not use the supported game-time clock.")
    if not isinstance(samples, list) or not samples or len(samples) > MAX_SAMPLES:
        raise ValueError("Recording must contain a bounded set of actual samples.")
    previous = -math.inf
    for sample in samples:
        if (
            not isinstance(sample, dict)
            or not _finite(sample.get("time"))
            or sample["time"] < 0
            or sample["time"] <= previous
        ):
            raise ValueError("Recording sample times must increase and contain only finite values.")
        previous = sample["time"]
        if not _vector(sample.get("position"), 3) or not _vector(sample.get("rotation"), 3):
            raise ValueError("Recording is missing finite oriented car poses.")
        actions = sample.get("actions")
        if not isinstance(actions, dict) or any(key not in actions for key in ACTION_KEYS):
            raise ValueError("Recording is missing observed game actions.")
        for key in ACTION_KEYS:
            item = actions[key]
            if key in ("jump", "boost", "handbrake"):
                if not isinstance(item, bool):
                    raise ValueError("Button actions must be true or false.")
            elif not _finite(item) or not -1 <= item <= 1:
                raise ValueError("Analog actions must be finite and between −1 and 1.")
        for vector_key in ("velocity", "ball_position", "ball_velocity", "angular_velocity"):
            if vector_key in sample and not _vector(sample[vector_key], 3):
                raise ValueError(f"Invalid {vector_key} in recording.")
        if "game_speed" in sample and (not _finite(sample["game_speed"]) or sample["game_speed"] <= 0):
            raise ValueError("Invalid game speed in recording.")
        if "packet_gap" in sample and not isinstance(sample["packet_gap"], bool):
            raise ValueError("Invalid packet gap marker.")
        if "wheel_contact" in sample and not isinstance(sample["wheel_contact"], bool):
            raise ValueError("Invalid observed wheel contact in recording.")
    if len(json.dumps(value, allow_nan=False).encode("utf-8")) > MAX_RECORDING_BYTES:
        raise ValueError("Recording exceeds the supported file size.")
    warnings = []
    if require_reference:
        source, permission = metadata["source"], metadata["permission"]
        if (source.get("kind") != "actual_execution" or not isinstance(source.get("origin"), str)
                or not source["origin"].strip()):
            raise ValueError("A teaching reference must identify an actual successful execution.")
        if (permission.get("distribute") is not True or not isinstance(permission.get("basis"), str)
                or not permission["basis"].strip()):
            raise ValueError("A shared reference needs explicit distribution permission and its basis.")
        if not metadata["success_evidence"]:
            raise ValueError("A teaching reference must include its observed success evidence.")
        if value.get("outcome") != "success":
            raise ValueError("An unsuccessful attempt cannot be a teaching reference.")
        if value.get("truncated"):
            raise ValueError("A truncated recording cannot be a teaching reference.")
        if any(
            metadata.get(k) in (None, "unknown", "unavailable", {})
            for k in ("game_version", "framework_version", "car_hitbox", "map")
        ):
            raise ValueError("Reference compatibility details must be known.")
        warnings.append(
            "Imported success and permission are supplied claims; validate the execution in the real game before labeling it a validated demonstration."
        )
    return warnings


def import_recording(path, *, require_reference=False):
    path = Path(path)
    if path.stat().st_size > MAX_RECORDING_BYTES:
        raise ValueError("Recording file is too large.")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_RECORDING_BYTES + 1)
        if len(data) > MAX_RECORDING_BYTES:
            raise ValueError("Recording file is too large.")
        value = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Choose a valid UTF-8 recording JSON file.") from exc
    warnings = validate_recording(value, require_reference=require_reference)
    result = deepcopy(value)
    result["import_status"] = (
        "Requires real-game reference validation" if require_reference else "Imported personal recording"
    )
    result["import_warnings"] = warnings
    return result


def compatible_recordings(first, second):
    """Unknown compatibility is a mismatch, never a silent equivalence."""
    differences = []
    if (first.get("lesson_id"), first.get("lesson_version")) != (
        second.get("lesson_id"),
        second.get("lesson_version"),
    ):
        differences.append("lesson version")
    a, b = first.get("metadata", {}), second.get("metadata", {})
    for key in (
        "game_version",
        "framework_version",
        "car_hitbox",
        "map",
        "mutators",
        "starting_state",
        "time_base",
    ):
        if (
            key not in a
            or key not in b
            or a.get(key) in (None, "unknown", "unavailable")
            or a.get(key) != b.get(key)
        ):
            differences.append(key)
    if first.get("variant") != second.get("variant"):
        differences.append("lesson variation")
    return not differences, differences


def personal_best(recordings, candidate=None):
    """Choose only compatible normal-speed successes; never call a player attempt expert."""
    values = list(recordings)
    if candidate is not None:
        values.append(candidate)
    eligible = []
    for item in values:
        try:
            validate_recording(item)
        except ValueError:
            continue
        if item.get("outcome") != "success" or item.get("truncated"):
            continue
        if candidate is not None and not compatible_recordings(item, candidate)[0]:
            continue
        if item["metadata"]["starting_state"].get("game_speed", 1.0) != 1.0 or any(
            sample.get("game_speed", 1.0) != 1.0 for sample in item["samples"]
        ):
            continue
        if item["metadata"].get("source", {}).get("kind") != "local_player":
            continue
        eligible.append(item)
    if not eligible:
        return None
    best = deepcopy(min(eligible, key=lambda item: item.get("duration", item["samples"][-1]["time"])))
    best["label"] = "Your Best Attempt"
    return best


class Recorder:
    def __init__(self, lesson, metadata=None, max_samples=MAX_SAMPLES):
        self.limit = min(MAX_SAMPLES, max(2, int(max_samples)))
        self.samples = []
        self.truncated = False
        self.lesson = deepcopy(lesson)
        supplied = deepcopy(metadata or {})
        self.metadata = {
            "game_version": "unknown",
            "framework_version": "unknown",
            "car_hitbox": "unknown",
            "map": lesson["map"],
            "mutators": {},
            "starting_state": lesson["starting_state"],
            "time_base": "game_seconds",
            "source": {"kind": "local_player", "origin": "Observed human game telemetry"},
            "permission": {"distribute": False, "basis": "Private player recording"},
            "success_evidence": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.metadata.update(supplied)
        self.origin = None

    def append(self, frame):
        if len(self.samples) >= self.limit:
            self.truncated = True
            return
        time = float(frame["time"])
        if self.origin is None:
            self.origin = time
        relative = time - self.origin
        if not self.samples:
            self.metadata["observed_start"] = {"car": deepcopy(frame["car"]), "ball": deepcopy(frame["ball"])}
        if self.samples and relative <= self.samples[-1]["time"]:
            return
        car, ball = frame["car"], frame["ball"]
        sample = {
            "time": relative,
            "position": deepcopy(car["position"]),
            "rotation": deepcopy(car["rotation"]),
            "velocity": deepcopy(car["velocity"]),
            "ball_position": deepcopy(ball["position"]),
            "ball_velocity": deepcopy(ball["velocity"]),
            "actions": deepcopy(frame["actions"]),
            "packet_gap": bool(frame.get("packet_gap", False)),
            "game_speed": float(
                frame.get("game_speed", self.metadata["starting_state"].get("game_speed", 1.0))
            ),
        }
        # Optional observed physics for validating new bot references. Older
        # personal recordings remain readable; missing evidence is not invented.
        for key in ("angular_velocity", "wheel_contact"):
            if key in car:
                sample[key] = deepcopy(car[key])
        self.samples.append(sample)

    def export(self, *, outcome="unfinished", events=None, duration=0):
        metadata = deepcopy(self.metadata)
        metadata["success_evidence"] = deepcopy(events or []) if outcome == "success" else []
        return {
            "schema_version": 1,
            "lesson_id": self.lesson["id"],
            "lesson_version": self.lesson["version"],
            "variant": deepcopy(self.lesson.get("variant")),
            "metadata": metadata,
            "outcome": outcome,
            "duration": duration,
            "events": deepcopy(events or []),
            "samples": deepcopy(self.samples),
            "truncated": self.truncated,
            "label": "Your Attempt",
        }


def euler_quaternion(rotation):
    """Rocket League pitch/yaw/roll to a quaternion: Rz(yaw) Ry(-pitch) Rx(-roll)."""
    pitch, yaw, roll = rotation
    a, b, c = -roll / 2, -pitch / 2, yaw / 2
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [
        ca * cb * cc + sa * sb * sc,
        sa * cb * cc - ca * sb * sc,
        ca * sb * cc + sa * cb * sc,
        ca * cb * sc - sa * sb * cc,
    ]


def _slerp(first, second, amount):
    dot = sum(a * b for a, b in zip(first, second))
    if dot < 0:
        second, dot = [-x for x in second], -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        value = [a + amount * (b - a) for a, b in zip(first, second)]
        length = math.sqrt(sum(x * x for x in value))
        return [x / length for x in value]
    theta = math.acos(dot)
    a, b = math.sin((1 - amount) * theta) / math.sin(theta), math.sin(amount * theta) / math.sin(theta)
    return [a * x + b * y for x, y in zip(first, second)]


def interpolate_pose(recording, time, *, speed=1.0, max_gap=0.1, sample_times=None):
    """No extrapolation or invented motion across packet gaps. Actions are sample-held."""
    if not _finite(time) or not _finite(speed) or speed <= 0:
        raise ValueError("Playback time and speed must be finite and nonnegative.")
    samples = recording.get("samples", [])
    if not samples:
        return None
    target = time * speed
    if target < samples[0]["time"] or target > samples[-1]["time"]:
        return None
    index = bisect_right(sample_times if sample_times is not None else [x["time"] for x in samples], target) - 1
    a = samples[index]
    b = samples[min(index + 1, len(samples) - 1)]
    span = b["time"] - a["time"]
    if span and (span > max_gap or b.get("packet_gap")) and target != a["time"]:
        return None
    fraction = (target - a["time"]) / span if span else 0
    return {
        "time": target,
        "position": [x + fraction * (y - x) for x, y in zip(a["position"], b["position"])],
        "quaternion": _slerp(euler_quaternion(a["rotation"]), euler_quaternion(b["rotation"]), fraction),
        "actions": deepcopy(a["actions"]),
    }


def _rotate(quaternion, point):
    w, x, y, z = quaternion
    px, py, pz = point
    tx, ty, tz = 2 * (y * pz - z * py), 2 * (z * px - x * pz), 2 * (x * py - y * px)
    return [px + w * tx + y * tz - z * ty, py + w * ty + z * tx - x * tz, pz + w * tz + x * ty - y * tx]


def _pose_quaternion(pose):
    """Accept an interpolated pose (quaternion) or a game frame pose (euler)."""
    if not isinstance(pose, dict):
        raise ValueError("A ghost placement needs a recorded pose.")
    if _vector(pose.get("quaternion"), 4):
        return [float(x) for x in pose["quaternion"]]
    if _vector(pose.get("rotation"), 3):
        return euler_quaternion(pose["rotation"])
    raise ValueError("A ghost placement needs an oriented pose.")


def _yaw_of(quaternion):
    """Z-up yaw of a quaternion built as Rz(yaw) Ry(-pitch) Rx(-roll).

    Rocket League is Z-up, so yaw is the rotation about z. The Y-up formula
    would report 180 degrees for a pure 90-degree z yaw.
    """
    w, x, y, z = quaternion
    length = math.sqrt(w * w + x * x + y * y + z * z)
    if not length or not math.isfinite(length):
        raise ValueError("A ghost placement needs a finite orientation.")
    w, x, y, z = w / length, x / length, y / length, z / length
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _yaw_quaternion(yaw):
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def _quaternion_product(first, second):
    aw, ax, ay, az = first
    bw, bx, by, bz = second
    return [
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ]


def relative_placement(pose, *, origin, anchor, forward_offset=300.0):
    """Pure spatial transform: place a recorded pose relative to the player.

    The recorded start pose (``origin``) is mapped onto the player's pose at the
    start of playback (``anchor``), shifted ``forward_offset`` game units along
    the player's heading. Every later pose keeps its recorded relative motion and
    orientation, rotated by the yaw difference only. Nothing is dragged to follow
    the player after the anchor is taken, and no input is mutated.
    """
    if not _finite(forward_offset):
        raise ValueError("Ghost placement distance must be finite.")
    origin_quaternion = _pose_quaternion(origin)
    anchor_quaternion = _pose_quaternion(anchor)
    if not _vector(origin.get("position"), 3) or not _vector(anchor.get("position"), 3):
        raise ValueError("A ghost placement needs recorded and player positions.")
    delta_yaw = _yaw_of(anchor_quaternion) - _yaw_of(origin_quaternion)
    turn = _yaw_quaternion(delta_yaw)
    offset = _rotate(anchor_quaternion, [float(forward_offset), 0.0, 0.0])
    delta = [float(b) - float(a) for a, b in zip(origin["position"], pose["position"])]
    moved = _rotate(turn, delta)
    return {
        "time": pose.get("time"),
        "position": [float(a) + b + c for a, b, c in zip(anchor["position"], offset, moved)],
        "quaternion": _quaternion_product(turn, _pose_quaternion(pose)),
        "actions": deepcopy(pose.get("actions")),
    }


def ghost_lines(pose, *, dimensions=(118, 84, 36)):
    """Oriented render-only car outline. No collision actor is ever created.

    The body box is kept, but a nose arrow, a raised roof cage and four wheel
    loops make the ghost read as a car instead of an unlabeled rectangle.
    """
    if not pose:
        return []
    length, width, height = [float(x) / 2 for x in dimensions]
    corners = [(x, y, z) for x in (-length, length) for y in (-width, width) for z in (-height, height)]
    lines = []

    def world(point):
        local = _rotate(pose["quaternion"], point)
        return [a + b for a, b in zip(local, pose["position"])]

    def add(start, end, style):
        lines.append({"start": world(start), "end": world(end), "style": style})

    def add_loop(points, style):
        for index, start in enumerate(points):
            add(start, points[(index + 1) % len(points)], style)

    for i, start in enumerate(corners):
        for end in corners[i + 1 :]:
            if sum(a != b for a, b in zip(start, end)) == 1:
                add(start, end, "outline")
    # Nose arrow: the only "front" cue, so the heading stays readable.
    add((0, 0, height), (length + 30, 0, height), "front")
    add((length + 30, 0, height), (length, -15, height), "front")
    add((length + 30, 0, height), (length, 15, height), "front")
    # Roof cage: a smaller raised rectangle with four struts.
    roof_z = height + 12
    roof = [(-length * .5, -width * .5, roof_z), (length * .3, -width * .5, roof_z),
            (length * .3, width * .5, roof_z), (-length * .5, width * .5, roof_z)]
    add_loop(roof, "roof")
    for x, y in ((-length * .5, -width * .5), (length * .3, -width * .5),
                 (length * .3, width * .5), (-length * .5, width * .5)):
        add((x, y, height), (x, y, roof_z), "roof")
    # Underside cross keeps roll orientation visible.
    add((-length, -width, -height), (length, width, -height), "underside")
    add((-length, width, -height), (length, -width, -height), "underside")
    # Four wheel loops, just outside the body.
    wheel_z, wheel_half_x, wheel_half_z = -height * .5, 9.0, 7.0
    for x in (length * .62, -length * .62):
        for y in (-(width + 4), width + 4):
            add_loop([(x - wheel_half_x, y, wheel_z - wheel_half_z),
                      (x + wheel_half_x, y, wheel_z - wheel_half_z),
                      (x + wheel_half_x, y, wheel_z + wheel_half_z),
                      (x - wheel_half_x, y, wheel_z + wheel_half_z)], "wheel")
    return lines
    return lines


def compare_attempts(attempt, reference):
    """Observed event-time differences; a successful alternative is never graded against a script."""
    validate_recording(attempt)
    validate_recording(reference)
    compatible, reasons = compatible_recordings(attempt, reference)
    if not compatible:
        return {
            "compatible": False,
            "mismatches": reasons,
            "timing": [],
            "message": "These attempts use different or unknown setups; timing comparison is unavailable.",
        }
    a_events, b_events = {}, {}
    for recording, output in ((attempt, a_events), (reference, b_events)):
        for event in recording.get("events", []):
            if event.get("confidence") in ("uncertain", "coaching suggestion"):
                continue
            if not _finite(event.get("time")):
                continue
            output.setdefault(event.get("name"), event)
    timing = []
    for name in a_events.keys() & b_events.keys():
        first, second = a_events[name], b_events[name]
        a = first.get("precision", [first["time"], first["time"]])
        b = second.get("precision", [second["time"], second["time"]])
        if not _vector(a, 2) or not _vector(b, 2):
            continue
        timing.append(
            {
                "event": name,
                "difference_seconds": first["time"] - second["time"],
                "difference_interval": [a[0] - b[1], a[1] - b[0]],
                "observation": "Later"
                if a[0] > b[1]
                else "Earlier"
                if a[1] < b[0]
                else "Within sampling uncertainty",
            }
        )
    return {
        "compatible": True,
        "mismatches": [],
        "timing": sorted(timing, key=lambda item: item["event"]),
        "attempt_label": "Your Attempt",
        "reference_label": reference.get("label", "Imported recording"),
        "message": "Measured timing differences are observations; successful alternative execution is allowed.",
    }
