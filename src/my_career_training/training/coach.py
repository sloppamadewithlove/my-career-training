"""Render-only recorded coaching with explicit provenance and a scrubbable clock.

No recording is generated here. A ghost is a depiction of captured car poses and
sample-held logical actions. It cannot control the human car, collide, grant a
skill result, or turn an imported success claim into a verified demonstration.
"""

from copy import deepcopy
import hashlib
import json
import math

from .catalog import assistance_preferences, lesson
from .controller import controller_bindings, controller_display
from .recordings import (compatible_recordings, ghost_lines, interpolate_pose, relative_placement,
                         validate_recording)

PLAYBACK_SPEEDS = (0.25, 0.5, 0.75, 1.0)
# Owner default: the ghost sits slightly in front of the player's car.
PRACTICE_FORWARD_OFFSET = 300.0
# Targets that describe the car's own route. Anything else depends on the ball
# or a wall, where a translated car-only path would misrepresent the scenario.
CAR_ONLY_TARGETS = ("plane", "gate", "recovery")
BALL_DEPENDENT_EVENTS = ("ball_contact", "goal_target", "carry_sustained", "flick", "reset_acquired")
NO_REFERENCE = (
    "No permitted successful teaching recording is installed for this setup. "
    "Record your own attempt or import a permitted actual execution. "
    "A reference needs observed actions, compatible setup and success evidence."
)
COACHING_DEFAULTS = {
    "mode": "lead", "lead_seconds": 0.75, "loop": True,
    "controller_layout": "playstation", "controller_position": "bottom_right",
    "controller_scale": 1.0, "bindings": controller_bindings(), "ghost_view": "player",
}


def _number(value, label, minimum=0, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < minimum or maximum is not None and value > maximum):
        raise ValueError(f"{label} must be a finite number in the supported range.")
    return float(value)


def coaching_preferences(values=None):
    """Training display settings separate from engine assistance and gameplay bindings."""
    if values is not None and not isinstance(values, dict):
        raise ValueError("Coaching preferences must be an object.")
    result = deepcopy(COACHING_DEFAULTS)
    legacy = {key: value for key, value in (values or {}).items() if key in assistance_preferences()}
    result.update(assistance_preferences(legacy))
    for key, value in (values or {}).items():
        if key in legacy:
            continue
        if key == "lead_seconds":
            value = _number(value, "Ghost lead", maximum=5)
        elif key == "controller_scale":
            value = _number(value, "Controller size", minimum=0.5, maximum=2)
        elif key == "bindings":
            value = controller_bindings(value)
        elif key == "loop":
            if not isinstance(value, bool):
                raise ValueError("Ghost loop must be on or off.")
        elif key == "mode" and value in ("watch", "lead"):
            pass
        elif key == "controller_layout" and value == "playstation":
            pass
        elif key == "controller_position" and value in ("bottom_left", "bottom_right", "top_left", "top_right"):
            pass
        elif key == "ghost_view" and value in ("player", "chase", "side", "top"):
            pass
        else:
            raise ValueError(f"Unknown or unsupported coaching setting: {key}")
        result[key] = value
    return result


def recording_provenance(recording, *, context=None):
    """Metadata is a supplied claim. This function never independently certifies it."""
    validate_recording(recording)
    metadata = recording["metadata"]
    source = metadata["source"]
    personal = source.get("kind") == "local_player"
    reason = None
    try:
        validate_recording(recording, require_reference=True)
        eligible = True
    except ValueError as exc:
        eligible, reason = False, str(exc)
    compatible, differences = (compatible_recordings(recording, context)
                               if context is not None else (None, []))
    digest = hashlib.sha256(json.dumps(recording, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode()).hexdigest()
    return {
        "sha256": digest, "source": deepcopy(source),
        "permission": deepcopy(metadata["permission"]), "personal": personal,
        "reference_eligible": eligible, "reference_unavailable_reason": reason,
        "independently_validated": False,
        "verification": "Recorded personal attempt; source metadata is not an independent validation"
                        if personal else "Imported claims; real-game validation pending",
        "label": "Your recorded attempt" if personal else "Imported recording — unverified",
        "compatibility": compatible, "compatibility_differences": differences,
        "outcome": recording.get("outcome", "unknown"),
        "success_evidence": deepcopy(metadata["success_evidence"]),
        "game_version": metadata["game_version"], "framework_version": metadata["framework_version"],
        "car_hitbox": metadata["car_hitbox"], "map": metadata["map"],
        "time_base": metadata["time_base"],
    }


def reference_availability(recordings=(), *, lesson_id=None, context=None):
    """Describe usable imports without treating a video link as a pose/input capture."""
    references, personal, rejected = [], 0, 0
    for recording in recordings:
        if not isinstance(recording, dict):
            rejected += 1
            continue
        if lesson_id is not None and recording.get("lesson_id") != lesson_id:
            continue
        try:
            provenance = recording_provenance(recording, context=context)
        except (ValueError, TypeError):
            rejected += 1
            continue
        if provenance["compatibility"] is False:
            continue
        personal += int(provenance["personal"])
        if provenance["reference_eligible"]:
            references.append(provenance)
    return {
        "available": bool(references), "validated_demo_available": False,
        "references": references, "personal_recordings": personal, "rejected_recordings": rejected,
        "message": "Imported teaching recording available; supplied success and permission are unverified."
                   if references else NO_REFERENCE,
    }


class GhostPlayback:
    """Explicit transport for a pose-only ghost. Use update with game time, never wall time.

    watch: independent timeline with pause/seek/rate/loop.
    lead: follows attempt_seconds at the chosen rate plus lead_seconds, so a
    retry automatically places the demonstration ahead of the new attempt.
    Pausing freezes either mode. Seeking in lead mode changes its timeline offset.
    """

    def __init__(self, recording=None, *, mode="watch", lead_seconds=0.75, speed=1.0, loop=False):
        self.recording = None
        self.provenance = None
        self._times = []
        self.cursor = 0.0
        self.playing = False
        self._last_clock = None
        self._last_attempt = None
        self._lead_offset = 0.0
        self._lead_reanchor = False
        self.status = "unavailable"
        self.set_mode(mode, lead_seconds=lead_seconds)
        self.set_speed(speed)
        self.set_loop(loop)
        if recording is not None:
            self.load(recording)

    def load(self, recording, *, kind="personal", context=None):
        if kind not in ("personal", "reference"):
            raise ValueError("Choose a personal or teaching reference recording.")
        validate_recording(recording, require_reference=kind == "reference")
        provenance = recording_provenance(recording, context=context)
        if provenance["compatibility"] is False:
            raise ValueError("Recording does not match this lesson setup: "
                             + ", ".join(provenance["compatibility_differences"]))
        self.recording = deepcopy(recording)
        self.provenance = provenance
        self.kind = kind
        self._times = [sample["time"] for sample in self.recording["samples"]]
        self.restart()
        return self.snapshot()

    @property
    def duration(self):
        # Recording.duration can include time after capture was truncated. Only
        # the actual sampled interval is seekable, never invented tail motion.
        return self._times[-1] if self._times else 0.0

    def set_mode(self, mode, lead_seconds=None):
        if mode not in ("watch", "lead"):
            raise ValueError("Ghost mode must be watch or lead.")
        self.mode = mode
        if lead_seconds is not None:
            self.lead_seconds = _number(lead_seconds, "Ghost lead", maximum=5)
        self._lead_offset = 0.0
        self._last_clock = self._last_attempt = None

    def set_speed(self, speed):
        if isinstance(speed, bool) or speed not in PLAYBACK_SPEEDS:
            raise ValueError("Ghost speed must be ¼, ½, ¾, or normal speed.")
        self.speed = float(speed)
        # Start a fresh anchor so a UI rate change cannot retroactively scale
        # already elapsed game time.
        self._last_clock = self._last_attempt = None
        self._lead_reanchor = self.recording is not None

    def set_loop(self, loop):
        if not isinstance(loop, bool):
            raise ValueError("Ghost loop must be on or off.")
        self.loop = loop

    def pause(self):
        self.playing = False
        self.status = "paused" if self.recording else "unavailable"
        self._last_clock = self._last_attempt = None

    def resume(self):
        if self.recording is None:
            raise ValueError(NO_REFERENCE)
        if self.cursor >= self.duration and not self.loop:
            self.cursor = self._times[0]
        self.playing, self.status = True, "playing"
        self._last_clock = self._last_attempt = None
        self._lead_reanchor = True

    def restart(self):
        if self.recording is None:
            return
        self.cursor = self._times[0]
        self._lead_offset = 0.0
        self._lead_reanchor = False
        self.playing, self.status = True, "playing"
        self._last_clock = self._last_attempt = None

    def stop(self):
        self.pause()
        self.cursor = self._times[0] if self._times else 0.0
        self.status = "stopped" if self.recording else "unavailable"

    def seek(self, seconds):
        target = _number(seconds, "Ghost timeline position")
        if not self.recording:
            raise ValueError(NO_REFERENCE)
        target = max(self._times[0], min(self.duration, target))
        self._lead_offset += target - self.cursor
        self.cursor = target
        self._last_clock = self._last_attempt = None
        self.status = "playing" if self.playing else "paused"
        return self.snapshot()

    def _bounded(self, cursor):
        beginning = self._times[0]
        if cursor >= self.duration and self.loop and self.duration > beginning:
            return beginning + (cursor - beginning) % (self.duration - beginning)
        if cursor >= self.duration:
            self.playing, self.status = False, "ended"
        return min(self.duration, max(beginning, cursor))

    def update(self, game_seconds, *, attempt_seconds=None):
        now = _number(game_seconds, "Game clock")
        attempt = (_number(attempt_seconds, "Attempt clock") if attempt_seconds is not None else None)
        if not self.recording:
            return self.snapshot()
        if self._last_clock is not None and now < self._last_clock:
            self.pause()
            self.status = "clock_restarted"
        else:
            if (self.mode == "lead" and attempt is not None and self._last_attempt is not None
                    and attempt < self._last_attempt):
                self._lead_offset = 0.0
                self._lead_reanchor = False
                # A completed ghost follows a fresh retry; an intentionally
                # paused/stopped ghost stays paused until the player resumes.
                if self.status == "ended":
                    self.playing, self.status = True, "playing"
        if self.playing:
            if self.mode == "lead":
                if attempt is None:
                    self.status = "waiting_for_attempt"
                else:
                    if self._last_attempt is not None and attempt < self._last_attempt:
                        self._lead_offset = 0.0
                        self._lead_reanchor = False
                    if self._lead_reanchor:
                        self._lead_offset = self.cursor - attempt * self.speed - self.lead_seconds
                        self._lead_reanchor = False
                    self.cursor = self._bounded(attempt * self.speed + self.lead_seconds + self._lead_offset)
                    if self.playing:
                        self.status = "playing"
            elif self._last_clock is not None:
                self.cursor = self._bounded(self.cursor + (now - self._last_clock) * self.speed)
        self._last_clock, self._last_attempt = now, attempt
        return self.snapshot()

    def snapshot(self, *, bindings=None):
        pose = (interpolate_pose(self.recording, self.cursor, sample_times=self._times)
                if self.recording else None)
        visible = self.status not in ("unavailable", "stopped") and pose is not None
        gap = self.recording is not None and pose is None
        actions = deepcopy(pose["actions"]) if visible else None
        return {
            "available": self.recording is not None, "playing": self.playing,
            "visible": visible, "status": "capture_gap" if gap else self.status,
            "cursor": self.cursor, "duration": self.duration, "speed": self.speed,
            "mode": self.mode, "lead_seconds": self.lead_seconds, "loop": self.loop,
            "pose": deepcopy(pose) if visible else None, "lines": ghost_lines(pose) if visible else [],
            "coach_actions": actions,
            "controller": controller_display(actions, bindings, observed=visible, source="ghost"),
            "provenance": deepcopy(self.provenance),
            "label": self.provenance["label"] if self.provenance else "Teaching demonstration unavailable",
            "message": "Capture gap; no motion or coach inputs are invented." if gap
                       else NO_REFERENCE if self.recording is None else "Render-only recorded ghost",
            "controls": ["watch", "lead", "pause", "resume", "seek", "speed", "loop", "restart", "stop"],
            "view_targets": self._view_targets(pose) if visible else {},
            "camera_control": "Target suggestions only; runtime camera support must be checked.",
            "player_input_applied": False,
        }

    @staticmethod
    def _view_targets(pose):
        from .recordings import _rotate

        target = pose["position"]
        views = {}
        for name, offset in (("chase", [-450, 0, 170]), ("side", [0, 650, 160]), ("top", [0, 0, 1100])):
            # Overhead remains in world space while the ghost flips upside down.
            rotated = offset if name == "top" else _rotate(pose["quaternion"], offset)
            views[name] = {"position": [x + y for x, y in zip(target, rotated)], "look_at": list(target)}
        return views


def practice_support(lesson_id):
    """Whether a translated car-only ghost is an honest depiction of this drill.

    Ball- and wall-contact drills depend on the demonstration's spatial
    relationship to the ball, so a car-only path moved in front of the player
    would imply a scenario that is not actually set up. Those lessons stay
    unsupported until a compatible placement or a ghost ball exists.
    """
    value = lesson(lesson_id)
    target_types = {target.get("type") for target in value["targets"]}
    events = set(value["success_events"])
    if target_types - set(CAR_ONLY_TARGETS) or events & set(BALL_DEPENDENT_EVENTS):
        return {
            "supported": False,
            "reason": "This drill depends on the ball or a wall. A translated car-only ghost "
                      "would not reproduce the recorded scenario, so ghost practice stays off "
                      "until a compatible placement or ghost ball is available.",
        }
    return {"supported": True, "reason": ""}


def practice_context(lesson_value, metadata=None):
    """Build the compatibility context for a lesson so a wrong setup is refused.

    Unknown values stay ``"unknown"``; ``compatible_recordings`` treats unknown
    as a mismatch rather than a silent equivalence.
    """
    metadata = metadata or {}
    return {
        "lesson_id": lesson_value["id"],
        "lesson_version": lesson_value["version"],
        "variant": deepcopy(lesson_value.get("variant")),
        "metadata": {
            "game_version": metadata.get("game_version", "unknown"),
            "framework_version": metadata.get("framework_version", "unknown"),
            "car_hitbox": metadata.get("car_hitbox", "unknown"),
            "map": lesson_value.get("map", "unknown"),
            "mutators": deepcopy(metadata.get("mutators", {})),
            "starting_state": deepcopy(lesson_value["starting_state"]),
            "time_base": "game_seconds",
        },
    }


class GhostPractice:
    """Normal-speed looping ghost practice placed slightly ahead of the player.

    This is the owner's practice flow, not the legacy watch/lead transport. It
    has no pause, seek or slow-motion control. Enabling restarts the recording
    from its first sample and anchors the recorded start pose onto the player's
    current pose plus a forward offset. Later poses keep their recorded relative
    motion; the ghost is never dragged to follow the player. Disabling hides the
    pose, lines and coach controller state immediately, before any new packet.
    """

    def __init__(self, recording=None, *, forward_offset=PRACTICE_FORWARD_OFFSET, context=None):
        self.forward_offset = _number(forward_offset, "Ghost placement distance",
                                      minimum=0, maximum=2000)
        self.context = deepcopy(context)
        self.recording = None
        self.provenance = None
        self.kind = None
        self.enabled = False
        self.playing = False
        self.status = "unavailable"
        self.cursor = 0.0
        self._times = []
        self._last_clock = None
        self._anchor = None
        self._origin = None
        if recording is not None:
            self.load(recording)

    def load(self, recording, *, kind="personal", context=None):
        """Validate and select a recording. Playback stays off until enabled.

        A supplied context is enforced; when the caller omits one, the context
        given to this practice instance is used so a wrong lesson/setup cannot
        slip through with ``context=None``.
        """
        if kind not in ("personal", "reference"):
            raise ValueError("Choose a personal or teaching reference recording.")
        validate_recording(recording, require_reference=kind == "reference")
        context = self.context if context is None else context
        provenance = recording_provenance(recording, context=context)
        if provenance["compatibility"] is False:
            raise ValueError("Recording does not match this lesson setup: "
                             + ", ".join(provenance["compatibility_differences"]))
        self.recording = deepcopy(recording)
        self.provenance = provenance
        self.kind = kind
        self.context = deepcopy(context)
        self._times = [sample["time"] for sample in self.recording["samples"]]
        self._origin = {"position": list(self.recording["samples"][0]["position"]),
                        "rotation": list(self.recording["samples"][0]["rotation"])}
        self._anchor = None
        self._last_clock = None
        self.cursor = self._times[0]
        self.enabled = False
        self.playing = False
        self.status = "ready"
        return self.snapshot()

    @property
    def duration(self):
        return self._times[-1] if self._times else 0.0

    @property
    def available(self):
        return self.recording is not None

    def set_enabled(self, enabled, *, player_pose=None):
        """Deterministic toggle. On restarts from the beginning; Off hides at once."""
        if not isinstance(enabled, bool):
            raise ValueError("Ghost practice must be on or off.")
        if enabled:
            if self.recording is None:
                raise ValueError(NO_REFERENCE)
            self.enabled = True
            self.playing = True
            self.status = "playing"
            self.cursor = self._times[0]
            self._last_clock = None
            # A fresh On re-anchors to the player's current pose. A loop repeat
            # keeps this anchor so relative motion is preserved.
            self._anchor = self._anchor_from(player_pose)
            if self._anchor is None:
                self.status = "waiting_for_player"
        else:
            self.enabled = False
            self.playing = False
            self.status = "off" if self.recording is not None else "unavailable"
            self._last_clock = None
        return self.snapshot()

    def toggle(self, *, player_pose=None):
        return self.set_enabled(not self.enabled, player_pose=player_pose)

    def _anchor_from(self, player_pose):
        if not isinstance(player_pose, dict):
            return None
        position = player_pose.get("position")
        if not (isinstance(position, (list, tuple)) and len(position) == 3
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                        for x in position)):
            return None
        rotation = player_pose.get("rotation")
        if not (isinstance(rotation, (list, tuple)) and len(rotation) == 3
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                        for x in rotation)):
            return None
        return {"position": [float(x) for x in position],
                "rotation": [float(x) for x in rotation]}

    def _bounded(self, cursor):
        beginning = self._times[0]
        if cursor >= self.duration and self.duration > beginning:
            # Repeat from the recorded beginning with the same anchor.
            return beginning + (cursor - beginning) % (self.duration - beginning)
        return min(self.duration, max(beginning, cursor))

    def update(self, game_seconds, *, player_pose=None):
        """Advance at normal speed only. Uses game time, never wall time."""
        now = _number(game_seconds, "Game clock")
        if not self.enabled or self.recording is None:
            return self.snapshot()
        if self._anchor is None:
            self._anchor = self._anchor_from(player_pose)
            if self._anchor is None:
                self.status = "waiting_for_player"
                return self.snapshot()
            self.status = "playing"
        if self._last_clock is not None and now < self._last_clock:
            # A restarted game clock restarts the demonstration from its start.
            self.cursor = self._times[0]
        elif self._last_clock is not None:
            self.cursor = self._bounded(self.cursor + (now - self._last_clock))
        self._last_clock = now
        return self.snapshot()

    def snapshot(self, *, bindings=None):
        pose = None
        if self.enabled and self.recording is not None and self._anchor is not None:
            recorded = interpolate_pose(self.recording, self.cursor, sample_times=self._times)
            if recorded is not None:
                pose = relative_placement(recorded, origin=self._origin, anchor=self._anchor,
                                          forward_offset=self.forward_offset)
        gap = self.enabled and self.recording is not None and self._anchor is not None and pose is None
        visible = pose is not None
        actions = deepcopy(pose["actions"]) if visible else None
        return {
            "available": self.available, "enabled": self.enabled, "playing": self.playing,
            "visible": visible, "status": "capture_gap" if gap else self.status,
            "cursor": self.cursor, "duration": self.duration, "speed": 1.0,
            "mode": "practice", "loop": True, "forward_offset": self.forward_offset,
            "pose": deepcopy(pose) if visible else None,
            "lines": ghost_lines(pose) if visible else [],
            "coach_actions": actions,
            "controller": controller_display(actions, bindings, observed=visible, source="ghost"),
            "provenance": deepcopy(self.provenance),
            "label": self.provenance["label"] if self.provenance else "Teaching demonstration unavailable",
            "message": ("Capture gap; no motion or coach inputs are invented." if gap
                        else NO_REFERENCE if self.recording is None
                        else "Ghost practice off" if not self.enabled
                        else "Waiting for your car's pose to place the ghost." if self._anchor is None
                        else "Render-only recorded ghost, slightly ahead of your car"),
            "controls": ["toggle"],
            "player_input_applied": False,
        }
