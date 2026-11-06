"""Private developer intent, routed by the same-user bridge; never authentication."""
import copy
import math
import time
import uuid


class NativeResetObservation:
    ACK_GRACE_SECONDS = 1.0  # Existing native heartbeats publish at 0.5-second intervals.

    def __init__(self, observe, *, enabled=False, clock=time.monotonic, wall=time.time):
        self._observe, self._enabled, self._clock, self._wall = observe, enabled is True, clock, wall
        self._request = None
        self._deadline = None
        self._last_clock = None
        self._spent = False
        self._status = {"status": "idle", "enabled": self._enabled}

    def start(self):
        if not self._enabled or self._spent:
            raise ValueError("The private native reset diagnostic is disabled or already spent.")
        self._spent = True
        observed = self._observe(False)
        if observed.get("frontend") is not False:
            raise ValueError("Enter the owned offline native training session first.")
        wall, steady = self._wall(), self._clock()
        if not math.isfinite(wall) or not math.isfinite(steady):
            raise ValueError("Invalid diagnostic clock.")
        self._request = {"request_id": str(uuid.uuid4()), "nonce": observed["nonce"],
                         "pid": observed["pid"], "start_identity": observed["start_identity"],
                         "issued_at": wall, "expires_at": wall + 5}
        self._deadline = steady + 5
        self._last_clock = steady
        self._status = {"status": "pending", "enabled": True}

    def refresh(self):
        if self._request is None:
            return
        try:
            now = self._clock()
            if (not math.isfinite(now) or now < self._last_clock
                    or now >= self._deadline + self.ACK_GRACE_SECONDS):
                raise ValueError("deadline")
            self._last_clock = now
            observed = self._observe(False)
            if observed.get("frontend") is not False or any(
                observed.get(key) != self._request[key] for key in ("nonce", "pid", "start_identity")
            ):
                raise ValueError("scope_changed")
            report = observed.get("heartbeat", {}).get("native_reset_observation")
            if isinstance(report, dict) and all(report.get(key) == self._request[key]
                                               for key in ("request_id", "nonce", "pid", "start_identity")):
                # Diagnostic acknowledgement only; no raw data becomes a recording.
                phase = report.get("status")
                if phase in {"complete", "failed"}:
                    self._status = {"status": phase, "enabled": True}
                    self._request = None
                    return
                if phase == "observing":
                    self._status = {"status": phase, "enabled": True}
            if now >= self._deadline:
                # Keep identical intent available for delivery only. Neither its
                # expires_at nor the native observer's first deadline is renewed.
                self._status = {"status": "awaiting_ack", "enabled": True}
        except Exception:
            self._request = None
            self._status = {"status": "stopped", "enabled": True}

    def request(self):
        self.refresh()
        return copy.deepcopy(self._request)

    def state(self):
        return dict(self._status)
