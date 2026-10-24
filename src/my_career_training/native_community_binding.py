"""Bind a developer community trial to the actual owned native session."""
from __future__ import annotations

import math
from pathlib import Path
import time

from .community_session import CommunitySession, CommunitySessionError, OwnedTrialScope, RuntimeIdentity
from .native_community import (
    BUILD_IDENTITY, CORE_IDENTITY, GAME_EXE_SHA256, SITE_ID,
    NativeCommunityController, NativeCommunityError, owned_start_identity,
)
from .platforms import game_processes, native_launcher_pending


def _host_message(reason):
    if reason == "duplicate_loaded":
        return "Speedflip Trainer is already loaded. Close My Career and disable the existing copy before trying this offline trial."
    if reason in {"safeguards_missing", "safeguards_rejected", "gamespeed_restore_failed", "gamespeed_unreadable"}:
        return "The plugin could not be enabled with the current game settings. Close this session before trying again."
    return "The game could not confirm this plugin for the current session. Close My Career before trying again."


def recover_native_community(directory):
    """Complete an interrupted trial before any normal online launch.

    No journal means no BakkesMod discovery or file changes. A journal whose
    root cannot be rediscovered remains present and prevents the handoff.
    """
    directory = Path(directory)
    receipt = directory / "community-session" / "active.json"
    if not receipt.exists() and not receipt.is_symlink():
        return
    from .bootstrap import bakkes_directory

    root = bakkes_directory()
    if root is None:
        raise CommunitySessionError("Community trial recovery needs the original BakkesMod folder.")
    session = CommunitySession(directory, root,
        game_running=lambda: bool(game_processes()) or native_launcher_pending())
    report = session.recover()
    if report.journal_kept or report.status not in {"idle", "recovered"}:
        raise CommunitySessionError(report.reason)


class NativeCommunityBinding:
    """Only bootstrap can attach this capability after a native owned launch.

    Movie/bridge commands carry no identity, path, hash, or enable boolean.
    The callbacks read the launcher identity and a fresh FileBridge heartbeat
    again at every staging boundary.
    """

    def __init__(self, session, bridge, bakkes_root):
        self.session = session
        self.bridge = bridge
        self._ready = False
        self._reason = "Waiting for the native Community menu."
        self._host_reason = ""
        self._requested_at = None
        self._hold_request = False
        self.controller = NativeCommunityController(
            session.directory, Path(bakkes_root), session.directory / "community-plugins",
            lease=lambda: self._observation(False)[0],
            runtime=lambda: self._observation(False)[1],
            heartbeat=lambda: self._observation(False)[2],
            movie_ready=self._movie_ready,
            game_running=lambda: bool(game_processes()), helper_pending=native_launcher_pending,
        )

    def _movie_ready(self):
        ready = self._observation(False)[2]["native_movie_trial"]["movie_ready"]
        if type(ready) is not bool:
            raise NativeCommunityError("Open the native Community menu in the matching offline session.")
        return ready

    def _observation(self, require_frontend=True):
        """Return the live owner, runtime, and heartbeat.

        ``require_frontend`` is for staging. Receipt acceptance uses false and
        can report ``frontend`` false during an owned offline local match.
        The returned scope uses that actual flag. It is never forced true.
        """
        from .bootstrap import verify_owned_offline

        owner = self.session.owner
        if (owner is None or owner.poll() != "ready" or self.session.prepared is None
                or not verify_owned_offline(owner.identity)
                or Path(owner.identity.executable).resolve() != self.session.executable
                or self.bridge.session != self.session.session):
            raise NativeCommunityError("The owned native offline session is not ready.")
        heartbeat = self.bridge.plugin_status()
        if type(heartbeat) is not dict:
            raise NativeCommunityError("Open the native Community menu in the matching offline session.")
        identity = owner.identity
        published = heartbeat.get("published_at")
        movie = heartbeat.get("native_movie_trial")
        online = heartbeat.get("online")
        in_game = heartbeat.get("in_game")
        in_replay = heartbeat.get("in_replay")
        frontend = heartbeat.get("frontend")
        ready = movie.get("movie_ready") if type(movie) is dict else None
        menu = "Open the native Community menu in the matching offline session."
        if (type(heartbeat.get("protocol")) is not int or heartbeat["protocol"] != 1
                or type(heartbeat.get("pid")) is not int or heartbeat["pid"] != identity.pid
                or heartbeat.get("bridge_session") != self.session.session
                or type(published) is bool or type(published) not in (int, float) or not math.isfinite(published)
                or not -1 <= time.time() - published <= 5
                or type(online) is not bool or online is not False
                or type(in_game) is not bool or type(in_replay) is not bool or type(frontend) is not bool
                or in_replay is not False or frontend is not (in_game is False)
                or heartbeat.get("bakkesmod_version") != 229
                or heartbeat.get("game_build") != BUILD_IDENTITY
                or type(movie) is not dict or movie.get("trial_enabled") is not True
                or type(ready) is not bool
                or movie.get("executable_sha256") != GAME_EXE_SHA256
                or movie.get("bakkes_core") != "229"
                or movie.get("game_build") != BUILD_IDENTITY):
            raise NativeCommunityError(menu)
        if require_frontend and (frontend is not True or in_game is not False or ready is not True):
            raise NativeCommunityError(menu)
        scope = OwnedTrialScope(
            self.session.session, identity.pid, owned_start_identity(identity.created),
            True, True, True, frontend, True,
        )
        return scope, RuntimeIdentity(GAME_EXE_SHA256, CORE_IDENTITY, BUILD_IDENTITY), heartbeat

    def refresh(self):
        try:
            scope, _, heartbeat = self._observation(False)
        except (NativeCommunityError, OSError, ValueError) as exc:
            self._ready = False
            self._reason = str(exc)
            if self.controller.request() is not None or self.controller.state().get("enabled") is True:
                self._hold_request = True
                self._host_reason = "The offline connection changed during the plugin trial. Close this session before retrying."
            return
        if (self.controller.request() is not None and self._requested_at is not None
                and time.monotonic() - self._requested_at > 10):
            self._hold_request = True
            self._host_reason = "The plugin was not confirmed in time. Close this session before retrying."
            return
        if self._host_reason:
            return
        ack = heartbeat.get("native_community_status")
        pending = self.controller.request()
        if pending is not None and type(ack) is dict and ack.get("status") == "loaded":
            result = self.controller.accept_status(ack)
            if result.get("accepted") is not True:
                self._hold_request = True
                self._host_reason = _host_message(ack.get("reason"))
        elif pending is not None and type(ack) is dict and ack.get("status") in {"refused", "unknown"}:
            if all(ack.get(key) == pending[key] for key in ("nonce", "pid", "stem", "start_identity")):
                # Only display a bounded host message; it never grants activation.
                self._hold_request = True
                self._host_reason = _host_message(ack.get("reason"))
        movie = heartbeat.get("native_movie_trial")
        movie_ready = type(movie) is dict and movie.get("movie_ready") is True
        self._ready = scope.frontend is True and movie_ready is True and heartbeat.get("in_game") is False
        if self._ready:
            self._reason = ""
        else:
            self._reason = "Open the native Community menu in the matching offline session."
            if self.controller.request() is not None:
                self._hold_request = True

    def state(self):
        state = self.controller.state()
        state.update(available=True, can_prepare=(self._ready and not state["outstanding"]
                     and state["status"] == "idle"))
        state["busy"] = self.pending()
        state["requires_restart"] = bool(self._host_reason)
        if self._host_reason:
            state["message"] = self._host_reason
            state["enabled"] = False
        elif not self._ready and state["enabled"] is not True:
            state["message"] = self._reason
        return state

    def request(self):
        if self._hold_request or self._host_reason or not self._ready:
            return None
        return self.controller.request()

    def pending(self):
        # Hiding a request after leaving the menu prevents redispatch; it does
        # not settle the already-issued load or release the activity lock.
        return self.controller.request() is not None and not self._host_reason

    def prepare(self, selected):
        if type(selected) is not dict or selected.get("id") != SITE_ID:
            raise NativeCommunityError("Choose the reviewed Speedflip Trainer release for this offline trial.")
        if self._host_reason:
            raise NativeCommunityError(self._host_reason)
        # Staging reads the frontend again. A local match is not a menu grant.
        self._observation(True)
        result = self.controller.prepare()
        self._requested_at = time.monotonic()
        self._host_reason = ""
        self._hold_request = False
        return result
