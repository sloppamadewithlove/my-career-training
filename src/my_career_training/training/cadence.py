"""Shared packet-cadence classification for training telemetry.

Normal human training may observe the game at 60 Hz or 120 Hz while physics
runs at 120 Hz, so one observed packet can legitimately cover one or two
physics steps. A two-step sample is coarse but continuous, not a telemetry gap.
Strict reference capture requires exactly one physics step per packet so a
candidate recording never mixes cadences.

This module is the single source of truth for both the worker and the engine.
Neither may invent a gap nor hide one on its own.

Frames that carry frame numbers must show one or two physics steps (one in
strict capture) and a clock interval matching that step count within the
documented clock quantization tolerance. Legacy frames are accepted from the
game clock alone only when BOTH frames omit a frame number; a partially or
invalidly numbered pair is a gap, never a clock-only acceptance. Real
duplicates, backwards clocks, larger steps, mismatches and over-interval gaps
stay gaps. An explicit transport gap is never reclassified as continuous.
"""

import math

PHYSICS_STEP_SECONDS = 1 / 120
# The game clock is quantized, so an exact 1/120 s or 1/60 s step can be
# reported a few milliseconds off. This is the documented tolerance.
CLOCK_QUANTIZATION_SECONDS = 0.002
MAX_NORMAL_STEPS = 2
FRAME_NUMBER_MODULUS = 2 ** 32


def _frame_number(frame):
    """Return the frame number, or None when the frame carries no usable one."""
    value = frame.get("frame_num") if isinstance(frame, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def classify_cadence(previous, frame, *, max_packet_interval=0.05, strict=False):
    """Classify the observed cadence between two normalized frames.

    Returns ``gap`` (bool), ``reason`` (str), ``dt`` (float or None),
    ``steps`` (int or None) and ``coarse`` (bool). ``coarse`` marks a
    continuous two-step sample that ordinary training accepts and strict
    capture rejects.
    """
    if not isinstance(strict, bool):
        raise ValueError("Cadence strictness must be an explicit boolean.")
    if (
        isinstance(max_packet_interval, bool)
        or not isinstance(max_packet_interval, (int, float))
        or not math.isfinite(max_packet_interval)
        or max_packet_interval <= 0
    ):
        raise ValueError("The maximum packet interval must be a positive finite number.")
    if not isinstance(frame, dict):
        raise ValueError("Cadence classification requires a normalized frame.")
    result = {"gap": False, "reason": "first_frame", "dt": None, "steps": None, "coarse": False}
    # An explicit gap from the transport is never reclassified as continuous.
    if frame.get("packet_gap") is True:
        result.update(gap=True, reason="explicit_packet_gap")
        return result
    if not isinstance(previous, dict):
        return result
    now, before = frame.get("time"), previous.get("time")
    if (
        isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(now)
        or isinstance(before, bool)
        or not isinstance(before, (int, float))
        or not math.isfinite(before)
    ):
        result.update(gap=True, reason="missing_clock")
        return result
    dt = now - before
    result["dt"] = dt
    if dt <= 0:
        # Duplicate or backwards game clocks cannot prove continuity.
        result.update(gap=True, reason="non_increasing_clock")
        return result
    if dt > max_packet_interval:
        result.update(gap=True, reason="interval_exceeded")
        return result
    old_number, new_number = _frame_number(previous), _frame_number(frame)
    if (("frame_num" in previous and old_number is None)
            or ("frame_num" in frame and new_number is None)):
        result.update(gap=True, reason="invalid_frame_number")
        return result
    if old_number is None and new_number is None:
        if strict:
            # Strict capture cannot prove a single physics step without frame
            # numbers, so an unavailable cadence is a gap rather than a guess.
            result.update(gap=True, reason="cadence_unavailable")
            return result
        # Legacy frames carry no frame number: the clock alone decides, and a
        # positive interval within the documented maximum is continuous.
        result["reason"] = "legacy_clock_continuous"
        return result
    if old_number is None or new_number is None:
        # A partially numbered pair is corrupt telemetry, not a legacy frame.
        result.update(gap=True, reason="frame_number_unavailable")
        return result
    observed = (new_number - old_number) % FRAME_NUMBER_MODULUS
    result["steps"] = observed
    limit = 1 if strict else MAX_NORMAL_STEPS
    if observed < 1 or observed > limit:
        result.update(gap=True, reason="step_count_exceeded")
        return result
    expected = observed * PHYSICS_STEP_SECONDS
    if abs(dt - expected) > CLOCK_QUANTIZATION_SECONDS:
        result.update(gap=True, reason="physics_step_mismatch")
        return result
    result["coarse"] = observed > 1
    result["reason"] = "coarse_continuous" if observed > 1 else "continuous"
    return result
