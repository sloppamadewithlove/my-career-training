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
        self.controller = NativeCommunityController(
            session.directory, Path(bakkes_root), session.directory / "community-plugins",
            lease=lambda: self._observation()[0],
            runtime=lambda: self._observation()[1],
            heartbeat=lambda: self._observation()[2],
            movie_ready=lambda: self._observation()[2]["native_movie_trial"]["movie_ready"],
            game_running=lambda: bool(game_processes()), helper_pending=native_launcher_pending,
        )

    def _observation(self):
        from .bootstrap import verify_owned_offline

        owner = self.session.owner
        if (owner is None or owner.poll() != "ready" or self.session.prepared is None
                or not verify_owned_offline(owner.identity)
                or Path(owner.identity.executable).resolve() != self.session.executable
                or self.bridge.session != self.session.session):
            raise NativeCommunityError("The owned native offline session is not ready.")
        heartbeat = self.bridge.plugin_status()
        identity = owner.identity
        published = heartbeat.get("published_at")
        movie = heartbeat.get("native_movie_trial")
        if (type(heartbeat.get("protocol")) is not int or heartbeat["protocol"] != 1
                or type(heartbeat.get("pid")) is not int or heartbeat["pid"] != identity.pid
                or heartbeat.get("bridge_session") != self.session.session
                or type(published) not in (int, float) or not math.isfinite(published)
                or not -1 <= time.time() - published <= 5
                or heartbeat.get("online") is not False or heartbeat.get("in_game") is not False
                or heartbeat.get("in_replay") is not False or heartbeat.get("frontend") is not True
                or heartbeat.get("bakkesmod_version") != 229
                or heartbeat.get("game_build") != BUILD_IDENTITY
                or type(movie) is not dict or movie.get("trial_enabled") is not True
                or movie.get("movie_ready") is not True
                or movie.get("executable_sha256") != GAME_EXE_SHA256
                or movie.get("bakkes_core") != "229"
                or movie.get("game_build") != BUILD_IDENTITY):
            raise NativeCommunityError("Open the native Community menu in the matching offline session.")
        scope = OwnedTrialScope(self.session.session, identity.pid, owned_start_identity(identity.created),
                                True, True, True, True, True)
        return scope, RuntimeIdentity(GAME_EXE_SHA256, CORE_IDENTITY, BUILD_IDENTITY), heartbeat

    def refresh(self):
        try:
            _, _, heartbeat = self._observation()
        except (NativeCommunityError, OSError, ValueError) as exc:
            self._ready = False
            self._reason = str(exc)
            if self.controller.request() is not None:
                self._host_reason = "The offline connection changed before the plugin was confirmed. Close this session before retrying."
            return
        self._ready = True
        self._reason = ""
        if (self.controller.request() is not None and self._requested_at is not None
                and time.monotonic() - self._requested_at > 10):
            self._host_reason = "The plugin was not confirmed in time. Close this session before retrying."
            return
        if self._host_reason:
            return
        ack = heartbeat.get("native_community_status")
        if type(ack) is dict and ack.get("status") == "loaded":
            self.controller.accept_status(ack)
        elif type(ack) is dict and ack.get("status") in {"refused", "unknown"}:
            pending = self.controller.request()
            if pending and all(ack.get(key) == pending[key] for key in ("nonce", "pid", "stem", "start_identity")):
                # Only display a bounded host message; it never grants activation.
                self._host_reason = str(ack.get("reason", "The host could not confirm the plugin."))[:240]

    def state(self):
        state = self.controller.state()
        state.update(available=True, can_prepare=(self._ready and not state["outstanding"]
                     and state["status"] == "idle"))
        state["busy"] = self.pending()
        state["requires_restart"] = bool(self._host_reason)
        if self._host_reason:
            state["message"] = self._host_reason
            state["enabled"] = False
        elif not self._ready:
            state["message"] = self._reason
        return state

    def request(self):
        return self.controller.request() if self._ready and not self._host_reason else None

    def pending(self):
        return self.request() is not None

    def prepare(self, selected):
        if type(selected) is not dict or selected.get("id") != SITE_ID:
            raise NativeCommunityError("Choose the reviewed Speedflip Trainer release for this offline trial.")
        # Re-evaluate the full lease here, regardless of an earlier UI snapshot.
        self._observation()
        result = self.controller.prepare()
        self._requested_at = time.monotonic()
        self._host_reason = ""
        return result
