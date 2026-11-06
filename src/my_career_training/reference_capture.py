"""Development-only real bot capture; no candidate is a validated teaching ghost.

This module is the single gate for the private reference-capture path. It is
disabled unless the request carries an explicit ``reference_capture`` payload,
the process is a source checkout (never a frozen build), the environment names
exactly the requested private data directory, and that directory holds an
operator-written allow marker.

Nothing here launches a game, sends inputs, writes global environment variables
or fabricates a reference. The worker records only physics and ``last_input``
values that the game actually reported for the designated bot, and persists them
under the private data directory for a separate evaluator. No gate is claimed to
have passed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import uuid

MARKER_NAME = "reference-capture-allow.json"
ENV_PROFILE = "MCT_REFERENCE_CAPTURE_PROFILE"
MARKER_SCHEMA = 1
MARKER_PURPOSE = "bot-reference-development"
MARKER_FIELDS = frozenset({"schema", "purpose", "enabled"})
MAX_MARKER_BYTES = 4096

LESSON_ID = "speed-flip"
PROFILES = ("cancel", "baseline")
FLIP_PROFILE = "flip-reset-nexto"
FLIP_TRIAL_WALL_SECONDS = 120.0
PAYLOAD_FIELDS = frozenset({"profile", "parameters", "trial_id"})

# The capture layout is exactly one known CustomBot before the Human.
TARGET_INDEX = 0
HUMAN_INDEX = 1

LABEL = "Development bot trial; not validated"
PROVENANCE_LABEL = "Bot trial (unvalidated)"
CANDIDATE_DIRECTORY = "reference-candidates"

# The Human must stay clear of the capture corridor; capture aborts instead of
# ever moving or controlling the Human car.
HUMAN_CLEARANCE = 400.0

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


def neutral_actions():
    """All eight logical actions at rest."""
    return dict(NEUTRAL_ACTIONS)


def configuration_snapshot(config):
    """Bounded, nonpersonal fields received from the fresh runtime's config."""
    from .training.bot_reference import CAPTURE_CONFIGURATION
    def enum_name(value):
        # The pinned SDK enums expose repr/str, but no Python Enum .name.
        return str(value).rsplit(".", 1)[-1]
    return {
        "map": config.game_map_upk,
        "game_mode": enum_name(config.game_mode),
        "freeplay": config.freeplay,
        "mutators": {key: enum_name(getattr(config.mutators, key))
                     for key in CAPTURE_CONFIGURATION["mutators"]},
    }


def _refuse(message):
    raise ValueError(message)


def _resolved_directory(value):
    if not isinstance(value, str) or not value.strip():
        _refuse("Reference capture requires a private data directory.")
    return Path(value).resolve()


def _read_marker(directory):
    """Read the allow marker with a hard size bound before decoding it."""
    marker = directory / MARKER_NAME
    if marker.is_symlink() or not marker.is_file():
        _refuse("Reference capture is not enabled for this data directory.")
    if marker.parent.resolve() != directory:
        _refuse("The reference capture marker must sit directly inside the data directory.")
    try:
        with marker.open("rb") as stream:
            raw = stream.read(MAX_MARKER_BYTES + 1)
    except OSError:
        _refuse("The reference capture marker is unreadable.")
    if len(raw) > MAX_MARKER_BYTES:
        _refuse("The reference capture marker is too large.")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        _refuse("The reference capture marker is unreadable.")
    if not isinstance(document, dict) or set(document) != MARKER_FIELDS:
        _refuse("The reference capture marker has an unexpected shape.")
    if type(document["schema"]) is not int or document["schema"] != MARKER_SCHEMA:
        _refuse("The reference capture marker schema is not supported.")
    if document["purpose"] != MARKER_PURPOSE:
        _refuse("The reference capture marker purpose is not supported.")
    if document["enabled"] is not True:
        _refuse("Reference capture is disabled by its marker.")
    return hashlib.sha256(raw).hexdigest()


def _validate_parameters(profile, parameters):
    try:
        from .training.bot_reference import SpeedFlipTrialController
    except ImportError:  # pragma: no cover - defensive
        _refuse("The speed-flip candidate controller is unavailable.")
    try:
        SpeedFlipTrialController(profile, parameters)
    except (ValueError, TypeError) as error:
        _refuse(f"Reference capture parameters are invalid: {error}")


def validate_capture_request(request):
    """Return the normalised capture plan, or ``None`` when capture is disabled.

    A request without a ``reference_capture`` key is an ordinary session and is
    never affected. A request that carries the key must satisfy every gate or it
    is refused; adding the flag alone can never enable capture.
    """
    if not isinstance(request, dict):
        _refuse("A game-session request must be a JSON object.")
    if "reference_capture" not in request:
        return None
    if getattr(sys, "frozen", False):
        _refuse("Reference capture is unavailable in a packaged build.")
    payload = request["reference_capture"]
    if not isinstance(payload, dict):
        _refuse("The reference capture payload must be a JSON object.")
    if set(payload) - PAYLOAD_FIELDS:
        _refuse("The reference capture payload has unsupported fields.")
    profile = payload.get("profile")
    if profile not in (*PROFILES, FLIP_PROFILE):
        _refuse("Choose a supported reference capture profile.")
    trial_id = payload.get("trial_id")
    if not isinstance(trial_id, str):
        _refuse("Reference capture requires a canonical trial UUID.")
    try:
        if str(uuid.UUID(trial_id)) != trial_id:
            raise ValueError
    except (ValueError, AttributeError):
        _refuse("Reference capture requires a canonical trial UUID.")
    parameters = payload.get("parameters")
    if parameters is not None:
        if not isinstance(parameters, dict):
            _refuse("Reference capture parameters must be a JSON object.")
        if profile == FLIP_PROFILE:
            if parameters:
                _refuse("The bounded flip-reset trial accepts no controller parameters.")
        else:
            _validate_parameters(profile, parameters)
    lesson_id = "flip-reset" if profile == FLIP_PROFILE else LESSON_ID
    if request.get("lesson_id") != lesson_id:
        _refuse("Reference capture profile does not match the lesson.")
    # Only the canonical lesson variant is a normal setup. Any explicit
    # variant selection is a nonstandard drill and is refused.
    if request.get("variants") not in (None, {}):
        _refuse("Reference capture requires the canonical lesson variant.")
    if request.get("fixture") or request.get("workshop") or request.get("calibration"):
        _refuse("Reference capture refuses fixture, workshop and calibration requests.")
    if request.get("scenario_id") is not None:
        _refuse("Reference capture refuses ball-launch scenarios.")
    if not request.get("owned_game"):
        _refuse("Reference capture requires an owned offline game session.")
    settings = request.get("settings")
    if not isinstance(settings, dict):
        _refuse("Reference capture requires normal launcher settings.")
    if settings.get("launcher") != "steam":
        _refuse("Reference capture currently supports the Steam source only.")
    directory = _resolved_directory(request.get("data_dir"))
    environment = os.environ.get(ENV_PROFILE)
    if not isinstance(environment, str) or not environment.strip():
        _refuse("Reference capture is not enabled for this process.")
    if Path(environment).resolve() != directory:
        _refuse("Reference capture is not enabled for this data directory.")
    digest = _read_marker(directory)
    return {
        "profile": profile,
        "parameters": dict(parameters or {}),
        "trial_id": trial_id,
        "data_dir": str(directory),
        "target_index": TARGET_INDEX,
        "human_index": HUMAN_INDEX,
        "marker_sha256": digest,
        "label": LABEL,
        "provenance": PROVENANCE_LABEL,
    }


class InstalledFlipResetTrialController:
    """API adapter for one unproven installed-policy trial, never a trace generator."""

    def __init__(self):
        from .bots.providers import create_controller
        from .training.catalog import configure_lesson
        self.policy = create_controller("nexto")
        self.game_limit = configure_lesson("flip-reset")["timeout"]
        self.reset()

    def reset(self):
        self.policy.reset()
        self.finished = False
        self.last_elapsed = None

    def finish(self):
        self.finished = True

    def controller_plan(self):
        from .bots.providers import MODELS, SOURCE_REVISION
        return {"id": "installed-nexto-flip-reset-trial", "revision": 1, "provider": "nexto",
                "provider_revision": SOURCE_REVISION, "model_sha256": MODELS["nexto"]["sha256"],
                "attempt_limit": 1, "wall_limit_seconds": FLIP_TRIAL_WALL_SECONDS,
                "game_limit_seconds": self.game_limit,
                "claim": "Unproven policy trial; no flip-reset capability or successful trace is claimed."}

    def step(self, elapsed_seconds, frame):
        if (self.finished or isinstance(elapsed_seconds, bool)
                or not isinstance(elapsed_seconds, (int, float)) or not math.isfinite(elapsed_seconds)
                or elapsed_seconds < 0 or elapsed_seconds >= self.game_limit
                or self.last_elapsed is not None and elapsed_seconds < self.last_elapsed):
            self.finish()
            return neutral_actions()
        self.last_elapsed = elapsed_seconds
        # Existing provider consumes the complete observed packet and an exact
        # mapped bot index, not an elapsed-time schedule or Human input.
        return self.policy.step(frame, TARGET_INDEX)


def create_capture_controller(capture):
    if capture["profile"] == FLIP_PROFILE:
        return InstalledFlipResetTrialController()
    from .training.bot_reference import SpeedFlipTrialController
    return SpeedFlipTrialController(capture["profile"], capture["parameters"] or None)


def _validate_flip_success(recording, summary, attempt_id):
    """Keep a success label from replacing the actual engine event contract."""
    from .training.catalog import configure_lesson
    from .training.recordings import flip_reset_practice_eligible, validate_recording
    validate_recording(recording)
    lesson = configure_lesson("flip-reset")
    if (recording.get("lesson_id") != "flip-reset" or recording.get("lesson_version") != lesson["version"]
            or recording.get("variant") != lesson["variant"] or summary.get("id") != attempt_id
            or summary.get("lesson_id") != "flip-reset" or summary.get("state") not in ("finished", "interrupted")
            or summary.get("outcome") != recording.get("outcome")):
        raise ValueError("The flip-reset capture does not match the completed lesson attempt.")
    if recording.get("outcome") != "success":
        return
    fields = ("fresh_ball_touch", "underside_aligned", "ball_near", "consumed_flip_observed",
              "ball_touch_after_flip_consumed", "central_airspace", "arena_surface_excluded", "continuous_packets")
    events = [event for event in recording.get("events", []) if isinstance(event, dict)
              and event.get("name") == "reset_acquired" and event.get("confidence") == "strong telemetry evidence"
              and isinstance(event.get("details"), dict)
              and all(event.get("details", {}).get(key) is True for key in fields)]
    if (not flip_reset_practice_eligible(recording) or summary.get("state") != "finished" or len(events) != 1
            or events[0] not in summary.get("events", [])
            or events[0] not in recording["metadata"].get("success_evidence", [])):
        raise ValueError("A flip-reset success needs the matching observed acquisition event.")


def recheck_capture(capture):
    """Re-verify the marker at a control boundary; raises when it changed."""
    directory = Path(capture["data_dir"]).resolve()
    environment = os.environ.get(ENV_PROFILE)
    if not isinstance(environment, str) or not environment.strip():
        _refuse("Reference capture is no longer enabled for this process.")
    if Path(environment).resolve() != directory:
        _refuse("Reference capture is no longer enabled for this data directory.")
    if _read_marker(directory) != capture["marker_sha256"]:
        _refuse("The reference capture marker changed during the trial.")
    return True


def telemetry(capture, *, active, target_index, aborted=None):
    """JSON-safe capture status for the ordinary telemetry event."""
    return {
        "active": bool(active),
        "target_index": target_index,
        "profile": capture["profile"],
        "trial_id": capture["trial_id"],
        "label": capture["label"],
        "aborted": aborted,
    }


def _atomic_write(directory, name, payload):
    target = directory / name
    temporary = directory / f".{name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _bounded(document, limit):
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    if len(payload) > limit:
        raise ValueError("The reference candidate exceeds the recording size limit.")
    return payload


def persist_candidate(data_dir, capture, attempt_id, recording, summary, metadata):
    """Write the observed trial and its identity receipt to private storage.

    The file name is the attempt UUID, so retries never overwrite each other.
    The write is atomic, both documents are bounded, and the receipt carries the
    SHA-256 of the exact bytes. Nothing here claims that the trial passed a gate.
    """
    from .training.recordings import MAX_RECORDING_BYTES
    if not isinstance(recording, dict) or not recording.get("samples"):
        raise ValueError("A reference candidate needs recorded samples.")
    if capture["profile"] == FLIP_PROFILE:
        _validate_flip_success(recording, summary, attempt_id)
    if not isinstance(attempt_id, str) or not attempt_id:
        raise ValueError("A reference candidate needs an attempt identifier.")
    try:
        canonical = str(uuid.UUID(attempt_id))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("A reference candidate needs a valid attempt identifier.") from None
    if attempt_id not in (canonical, canonical.replace("-", "")):
        raise ValueError("A reference candidate needs a valid attempt identifier.")
    root = Path(data_dir).resolve() / CANDIDATE_DIRECTORY
    root.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": 1,
        "kind": "bot-reference-candidate",
        "trial_id": capture["trial_id"],
        "attempt_id": attempt_id,
        "profile": capture["profile"],
        "label": capture["label"],
        "provenance": capture["provenance"],
        "permission": {"distribute": False},
        "gate": "not-evaluated",
        "metadata": metadata,
        "summary": summary,
        "recording": recording,
    }
    payload = _bounded(document, MAX_RECORDING_BYTES)
    _atomic_write(root, f"{attempt_id}.json", payload)
    receipt = {
        "schema": 1,
        "kind": "bot-reference-candidate-receipt",
        "trial_id": capture["trial_id"],
        "attempt_id": attempt_id,
        "file": f"{attempt_id}.json",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "label": capture["label"],
        "permission": {"distribute": False},
        "gate": "not-evaluated",
    }
    _atomic_write(root, f"{attempt_id}.receipt.json",
                  _bounded(receipt, MAX_MARKER_BYTES))
    return receipt
