"""Private, provisional adaptation of operator-supplied native input CSVs.

This module contains no third-party input data and never creates a recording.
Native fields without RLBot equivalents are discarded, so playback is lossy.
"""

import csv
import hashlib
import io
import math
from pathlib import Path

from .cadence import CLOCK_QUANTIZATION_SECONDS

INPUT_FILENAME = "reference-inputs.csv"
MAX_INPUT_BYTES = 1024 * 1024
MAX_INPUT_ROWS = 1200
TICK_RATE = 120
HEADER = (
    "Tick", "ActivateBoost", "DodgeForward", "DodgeStrafe", "Handbrake",
    "HoldingBoost", "Jump", "Jumped", "Pitch", "Roll", "Steer", "Throttle", "Yaw",
)
_FLAGS = {"ActivateBoost", "Handbrake", "HoldingBoost", "Jump", "Jumped"}
_MAPPING = {
    "throttle": "Throttle", "steer": "Steer", "pitch": "Pitch", "yaw": "Yaw",
    "roll": "Roll", "jump": "Jump", "boost": "HoldingBoost", "handbrake": "Handbrake",
}
_DISCARDED = ("ActivateBoost", "DodgeForward", "DodgeStrafe", "Jumped")


def _neutral():
    return {key: False if column in _FLAGS else 0.0 for key, column in _MAPPING.items()}


def load_controller(data_dir, expected_sha256):
    """Read one fixed private file once, bound its size, and pin exact bytes."""
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValueError("Prerecorded inputs require a lowercase SHA-256 digest.")
    directory = Path(data_dir).resolve()
    path = directory / INPUT_FILENAME
    try:
        if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
            raise ValueError("Prerecorded inputs must be a regular file directly in the private profile.")
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise ValueError("The private prerecorded input file is unreadable.") from None
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("The private prerecorded input file exceeds its size limit.")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("The private prerecorded input file does not match its pinned digest.")
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8")), strict=True)
        if tuple(next(reader, ())) != HEADER:
            raise ValueError("Prerecorded inputs have an unsupported header.")
        actions = []
        for tick, row in enumerate(reader):
            if tick >= MAX_INPUT_ROWS:
                raise ValueError("Prerecorded inputs exceed the ten-second row limit.")
            if len(row) != len(HEADER) or row[0] != str(tick):
                raise ValueError("Prerecorded inputs require contiguous zero-based ticks and exact columns.")
            values = {}
            for column, text in zip(HEADER[1:], row[1:]):
                if column in _FLAGS:
                    if text not in {"0", "1"}:
                        raise ValueError("Prerecorded input flags must be zero or one.")
                    values[column] = text == "1"
                else:
                    number = float(text)
                    if not math.isfinite(number) or not -1 <= number <= 1:
                        raise ValueError("Prerecorded input axes must be finite and between -1 and one.")
                    values[column] = number
            actions.append({key: values[column] for key, column in _MAPPING.items()})
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("The private prerecorded input CSV is unreadable.") from None
    except ValueError:
        # Never include operator-supplied cell contents in an error or log.
        raise ValueError("The private prerecorded input CSV is malformed or exceeds its bounds.") from None
    if not actions:
        raise ValueError("Prerecorded inputs require at least one input row.")
    return PrerecordedInputController(actions, expected_sha256)


class PrerecordedInputController:
    """One provisional 120 Hz dispatch per row; never choose an actor or send inputs."""

    def __init__(self, actions, sha256):
        self._actions = tuple(dict(action) for action in actions)
        self._sha256 = sha256
        self.reset()

    def reset(self):
        self._origin = None
        self._last_elapsed = None
        self._tick = -1
        self.interrupted = False
        self.finished = False

    def finish(self):
        self.finished = True

    def step(self, elapsed_seconds, frame=None):
        if self.finished:
            return _neutral()
        if (isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float))
                or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0
                or (isinstance(frame, dict) and frame.get("packet_gap") is True)):
            return self._interrupt()
        if self._origin is None:
            self._origin = elapsed_seconds
        tick = round((elapsed_seconds - self._origin) * TICK_RATE)
        if self._last_elapsed is not None:
            interval = elapsed_seconds - self._last_elapsed
            if (tick != self._tick + 1
                    or abs(interval - 1 / TICK_RATE) > CLOCK_QUANTIZATION_SECONDS):
                return self._interrupt()
        self._last_elapsed = elapsed_seconds
        self._tick = tick
        if tick >= len(self._actions):
            self.finish()
            return _neutral()
        return dict(self._actions[tick])

    def _interrupt(self):
        self.interrupted = True
        self.finish()
        return _neutral()

    def controller_plan(self):
        return {
            "controller_id": "private-prerecorded-input-adapter",
            "revision": 1,
            "profile": "prerecorded",
            "input_sha256": self._sha256,
            "rows": len(self._actions),
            "assumed_tick_rate": TICK_RATE,
            "tick_origin": "first_control_dispatch_after_engine_go",
            "mapping": dict(_MAPPING),
            "discarded_native_fields": list(_DISCARDED),
            "lossy": True,
            "chooses_player_index": False,
            "sends_inputs": False,
            "claim": "Provisional lossy input adaptation; no successful demonstration established.",
        }
