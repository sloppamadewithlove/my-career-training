"""Session-bound controller for fixed native Custom Training packs.

The controller never accepts a pack code, command, path, or process identity
from an in-game action.  Bootstrap's existing native-community capability is
the source of the current owned process and fresh, verified movie heartbeat.

The exact request stays published while the activity is pending *and* loaded so
the native host can keep re-verifying the actual Custom Training pack on every
tick.  It is withdrawn only by ``clear_for_return`` (which clears the request
and the session identity together) or by ``clear_after_exit``.
"""
from __future__ import annotations

import copy
import time
import uuid

from .packs import LESSON_ID, get_training_pack

# A loaded activity tolerates a short heartbeat gap (surface/status race) but
# must never claim "loaded" indefinitely without a fresh owned heartbeat.
LOADED_FRESHNESS = 2.0


class NativeTrainingPackError(ValueError):
    """A native pack cannot safely start or continue in this game session."""


class NativeTrainingPackController:
    """Publish one fixed request and accept only its exact native receipt."""

    def __init__(self, observe, *, clock=time.monotonic, timeout=20.0,
                 freshness=LOADED_FRESHNESS):
        self._observe = observe
        self._clock = clock
        self._timeout = float(timeout)
        self._freshness = float(freshness)
        self._activity = None
        self._request = None
        self._requested_at = None
        self._last_good_at = None

    def active(self):
        return self._activity is not None

    def state(self):
        if self._activity is None:
            return {
                "active": False,
                "status": "idle",
                "busy": False,
                "requires_restart": False,
                "message": "Choose a featured Custom Training pack.",
            }
        value = copy.deepcopy(self._activity)
        value["active"] = True
        # Only a confirmed load releases the activity lock; pending and failed
        # activities keep the native Return control disabled.
        value["busy"] = value["status"] != "loaded"
        return value

    def request(self):
        """The exact request, published while pending and while loaded."""
        if self._activity is None:
            return None
        if self._activity["status"] not in ("pending", "loaded"):
            return None
        return copy.deepcopy(self._request)

    def start(self, pack_id):
        if self._activity is not None:
            raise NativeTrainingPackError(
                "Finish or exit the current Custom Training pack before starting another activity."
            )
        pack = get_training_pack(pack_id)
        try:
            observation = self._observe(True)
        except Exception as exc:
            raise NativeTrainingPackError(
                "Open the verified native My Career frontend in the owned offline game before starting this pack."
            ) from exc
        if observation.get("frontend") is not True:
            raise NativeTrainingPackError(
                "Open the verified native My Career frontend in the owned offline game before starting this pack."
            )
        session_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        self._request = {
            "pack_id": pack["id"],
            "session_id": session_id,
            "request_id": request_id,
            "nonce": observation["nonce"],
            "pid": observation["pid"],
            "start_identity": observation["start_identity"],
        }
        self._activity = {
            "status": "pending",
            "requires_restart": False,
            "message": f"Opening {pack['title']} in Custom Training\u2026",
            "session_id": session_id,
            "request_id": request_id,
            "pack_id": pack["id"],
            "training_pack": copy.deepcopy(pack),
        }
        self._requested_at = self._clock()
        self._last_good_at = None
        return {
            "session_id": session_id,
            "request_id": request_id,
            "lesson_id": LESSON_ID,
            "training_pack": copy.deepcopy(pack),
        }

    def _fail(self, message):
        if self._activity is None:
            return
        self._activity.update(
            status="failed", requires_restart=True, message=message
        )
        # A failed activity is permanent for this session: the request is
        # withdrawn and never resent.
        self._request = None
        self._last_good_at = None

    def _scope_changed(self):
        self._fail(
            "The owned offline connection changed during Custom Training. Close this My Career session before retrying."
        )

    def _bad_receipt(self):
        self._fail(
            "The game did not confirm the selected Custom Training pack. Close this My Career session before retrying."
        )

    def _stale_loaded(self):
        self._fail(
            "The game stopped reporting the loaded Custom Training pack. Close this My Career session before retrying."
        )

    def refresh(self):
        if self._activity is None:
            return False
        before = self.state()
        if self._activity["requires_restart"]:
            return False
        if (self._activity["status"] == "pending"
                and (self._requested_at is None or self._clock() - self._requested_at > self._timeout)):
            self._fail(
                "The Custom Training load was not confirmed in time. Close this My Career session before retrying."
            )
            return before != self.state()
        try:
            observation = self._observe(False)
        except Exception:
            self._scope_changed()
            return before != self.state()
        expected = self._request
        if expected is None or any(
            observation.get(key) != expected[key]
            for key in ("nonce", "pid", "start_identity")
        ):
            self._scope_changed()
            return before != self.state()
        heartbeat = observation.get("heartbeat")
        reported = heartbeat.get("native_training_pack") if type(heartbeat) is dict else None
        identity_keys = (
            "pack_id", "session_id", "request_id", "nonce", "pid", "start_identity"
        )
        attributed = type(reported) is dict and all(
            reported.get(key) == expected[key] for key in identity_keys
        )
        expected_code = self._activity["training_pack"]["code"]
        phase = reported.get("status") if attributed else None
        code = reported.get("code") if attributed else None
        if self._activity["status"] == "pending":
            if attributed and phase == "loaded" and code == expected_code:
                self._activity.update(
                    status="loaded",
                    requires_restart=False,
                    message=f"{self._activity['training_pack']['title']} is loaded in Custom Training.",
                )
                self._last_good_at = self._clock()
            elif attributed and (phase == "failed" or phase == "loaded"):
                self._bad_receipt()
            return before != self.state()
        # Loaded: re-verify the actual pack on every tick.
        if attributed and phase == "loaded" and code == expected_code:
            self._last_good_at = self._clock()
            return before != self.state()
        if attributed and (phase == "failed" or phase == "loaded"):
            # Attributed but wrong code, or an attributed failure.
            self._bad_receipt()
            return before != self.state()
        # Absent, unattributed, or idle heartbeat: tolerate a bounded status
        # race, then fail closed rather than claiming "loaded" forever.
        now = self._clock()
        if self._last_good_at is None:
            self._last_good_at = now
            return before != self.state()
        if now - self._last_good_at > self._freshness:
            self._stale_loaded()
        return before != self.state()

    def clear_for_return(self, session_id):
        if (self._activity is None or self._activity["status"] != "loaded"
                or self._activity["session_id"] != session_id):
            raise NativeTrainingPackError(
                "The Custom Training activity changed. Open its pause menu again."
            )
        self._activity = None
        self._request = None
        self._requested_at = None
        self._last_good_at = None

    def clear_after_exit(self):
        self._activity = None
        self._request = None
        self._requested_at = None
        self._last_good_at = None


__all__ = ["NativeTrainingPackController", "NativeTrainingPackError"]
