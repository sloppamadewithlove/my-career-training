"""Developer-only staging controller for one pinned community trial.

This module does not download, launch a game, load a DLL, or write BakkesMod
config. ``prepare`` journals one staged file through ``CommunitySession``.
The native host derives and performs the load. ``enabled`` stays false until
``accept_status`` sees an exact PluginManager confirmation for the same owned
process. Recovery deletes nothing while a game or the native helper may still
be running.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .community_session import (
    CommunitySession,
    CommunitySessionError,
    OwnedTrialScope,
    RecoveryReport,
    ReviewedPluginProfile,
    RuntimeIdentity,
    derived_plugin_commands,
)

SITE_ID = "286"
API_VERSION = 3
ARCHIVE_SHA256 = "b75ff28a86e4d54b0083b4ea09068a93b409bc18746b150b70030cab1d4f795d"
MEMBER = "plugins/SpeedFlipTrainer.dll"
MEMBER_SHA256 = "2203874a6921df54d06c1042a4281c7694d3e415b9c6b0618e33769db401ef11"
PLUGIN_NAME = "SpeedFlipTrainer"
SOURCE_URL = "https://github.com/tynidev/SpeedFlipTrainer"
SOURCE_COMMIT = "8a4a94fc120db4919c3155052dbd7099ef834ba7"
LICENSE = "GPL-3.0"
DOWNLOAD_URL = (
    "https://cdn.bakkesplugins.com/uploads/"
    "4_3af4e39dddc7eb76e136f32052d7b3dfdaf152719074cef7cd01347c6a08a478.zip"
)
GAME_EXE_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
CORE_IDENTITY = "Bakkes229"
BUILD_IDENTITY = "261013.63066.530866"

_STATE_KEYS = (
    "enabled", "status", "message", "site_id", "production_eligible",
    "game_verified", "can_activate", "outstanding",
)
_REQUEST_KEYS = (
    "site_id", "nonce", "stem", "archive_sha256", "member_sha256",
    "pid", "start_identity", "game_exe_sha256", "core_identity", "build_identity",
)
_ACK_KEYS = frozenset({
    "status", "site_id", "nonce", "stem", "filename",
    "pid", "start_identity", "member_sha256", "archive_sha256",
})
_LOCKED_FIELDS = (
    "site_id", "api_version", "member", "plugin_name", "source_url",
    "source_commit", "license", "game_exe_sha256", "core_identity", "build_identity",
)
_RUNNING = "The owned game or native helper is still running. The staged plugin was left in place."


class NativeCommunityError(RuntimeError):
    """The native community trial could not be staged, confirmed, or recovered."""


def pinned_profile() -> ReviewedPluginProfile:
    """Return the only Speedflip Trainer profile this candidate may stage."""
    return ReviewedPluginProfile(
        site_id=SITE_ID,
        api_version=API_VERSION,
        archive_sha256=ARCHIVE_SHA256,
        member=MEMBER,
        member_sha256=MEMBER_SHA256,
        plugin_name=PLUGIN_NAME,
        source_url=SOURCE_URL,
        source_commit=SOURCE_COMMIT,
        license=LICENSE,
        download_url=DOWNLOAD_URL,
        game_exe_sha256=GAME_EXE_SHA256,
        core_identity=CORE_IDENTITY,
        build_identity=BUILD_IDENTITY,
    )


def owned_start_identity(created: float) -> str:
    """Format an owned process creation time for the scope and the status ack.

    Root uses this same string in ``OwnedTrialScope.start_identity`` and in
    the PluginManager ack. A different rendering does not confirm the load.
    """
    if type(created) is bool or type(created) not in (int, float):
        raise NativeCommunityError("Owned process creation time is not valid.")
    if created != created or created in (float("inf"), float("-inf")) or created <= 0:
        raise NativeCommunityError("Owned process creation time is not valid.")
    text = format(float(created), ".3f")
    if len(text) > 128:
        raise NativeCommunityError("Owned process creation time is not valid.")
    return text


def _use_synthetic_profile(controller: NativeCommunityController, profile: object) -> None:
    """Install a site-286 profile whose archive bytes are a test fixture.

    Production and the player bridge must not call this. Locked provenance,
    member name, and runtime pins still have to match ``pinned_profile``.
    """
    if not isinstance(controller, NativeCommunityController):
        raise NativeCommunityError("A native community controller is required.")
    if controller._loaded or controller._pending is not None or controller._session.outstanding():
        raise NativeCommunityError("A community trial is already staged.")
    if isinstance(profile, (str, Path, bytes, os.PathLike)):
        raise NativeCommunityError("A reviewed profile must come from developer code, not a path or URL.")
    if not isinstance(profile, ReviewedPluginProfile):
        raise NativeCommunityError("A complete reviewed profile is required.")
    pinned = pinned_profile()
    for name in _LOCKED_FIELDS:
        if getattr(profile, name) != getattr(pinned, name):
            raise NativeCommunityError("Only the pinned Speedflip Trainer profile can be staged.")
    controller._profile = profile


@dataclass(frozen=True, slots=True)
class _Observation:
    scope: OwnedTrialScope
    runtime: RuntimeIdentity


@dataclass(frozen=True, slots=True)
class _Pending:
    site_id: str
    nonce: str
    stem: str
    archive_sha256: str
    member_sha256: str
    pid: int
    start_identity: str
    game_exe_sha256: str
    core_identity: str
    build_identity: str

    def as_dict(self) -> dict:
        body = {
            "site_id": self.site_id,
            "nonce": self.nonce,
            "stem": self.stem,
            "archive_sha256": self.archive_sha256,
            "member_sha256": self.member_sha256,
            "pid": self.pid,
            "start_identity": self.start_identity,
            "game_exe_sha256": self.game_exe_sha256,
            "core_identity": self.core_identity,
            "build_identity": self.build_identity,
        }
        if tuple(body) != _REQUEST_KEYS:
            raise NativeCommunityError("The load request is not valid.")
        return body


class NativeCommunityController:
    """Stage the pinned trial and record whether the native host loaded it.

    ``lease``, ``runtime``, ``heartbeat``, and ``movie_ready`` are root
    callbacks. Each call must read the live owned session. ``prepare`` takes
    no site, path, URL, command, or enable flag.
    """

    def __init__(
        self,
        app_state: Path,
        bakkes_root: Path,
        cache_directory: Path,
        *,
        lease: Callable[[], OwnedTrialScope],
        runtime: Callable[[], RuntimeIdentity],
        heartbeat: Callable[[], dict],
        movie_ready: Callable[[], bool],
        game_running: Callable[[], bool],
        helper_pending: Callable[[], bool],
    ) -> None:
        for name, callback in (
            ("lease", lease), ("runtime", runtime), ("heartbeat", heartbeat),
            ("movie_ready", movie_ready), ("game_running", game_running),
            ("helper_pending", helper_pending),
        ):
            if not callable(callback):
                raise NativeCommunityError(f"The {name} callback is required.")
        self._lease = lease
        self._runtime = runtime
        self._heartbeat = heartbeat
        self._movie_ready = movie_ready
        self._game_running = game_running
        self._helper_pending = helper_pending
        self._cache = cache_directory
        self._profile = pinned_profile()
        self._pending: _Pending | None = None
        self._expected: _Observation | None = None
        self._loaded = False
        self._enabled = False
        try:
            self._session = CommunitySession(app_state, bakkes_root, game_running=self._game_for_session)
        except CommunitySessionError as exc:
            raise NativeCommunityError(str(exc)) from exc
        if self._session.outstanding():
            self._status = "outstanding"
            self._message = "A community trial journal is still present."
        else:
            self._status = "idle"
            self._message = "Community trial is disabled."

    def prepare(self) -> dict:
        """Stage the current profile when the live lease still matches.

        Returns ``state``. A staged trial is not enabled and is not loaded.
        """
        if self._loaded or self._pending is not None or self._session.outstanding():
            raise NativeCommunityError("A community trial is already staged.")
        observed = self._observe()
        profile = self._profile
        command = derived_plugin_commands(profile.site_id, observed.scope.nonce)
        self._expected = observed
        try:
            try:
                staged = self._session.stage(
                    profile, observed.scope, observed.runtime, self._cache,
                    verify_scope=self._verify_scope,
                )
            except CommunitySessionError as exc:
                self._note_failure(exc)
                raise NativeCommunityError(str(exc)) from exc
        finally:
            self._expected = None
        if (staged.command.stem != command.stem or staged.filename != f"{command.stem}.dll"
                or staged.member_sha256 != profile.member_sha256
                or staged.production_eligible is not False or staged.autoload_modified is not False):
            self._status = "outstanding"
            self._message = "The staged plugin does not match the pinned trial."
            self._enabled = False
            raise NativeCommunityError(self._message)
        self._pending = _Pending(
            site_id=profile.site_id,
            nonce=observed.scope.nonce,
            stem=command.stem,
            archive_sha256=profile.archive_sha256,
            member_sha256=profile.member_sha256,
            pid=observed.scope.pid,
            start_identity=observed.scope.start_identity,
            game_exe_sha256=observed.runtime.game_exe_sha256,
            core_identity=observed.runtime.core_identity,
            build_identity=observed.runtime.build_identity,
        )
        self._loaded = False
        self._enabled = False
        self._status = "staged"
        self._message = "The reviewed plugin is staged. It is not loaded."
        return self.state()

    def state(self) -> dict:
        """Return the plain trial view. It has no command and no path."""
        body = {
            "enabled": self._enabled,
            "status": self._status,
            "message": self._message,
            "site_id": SITE_ID,
            "production_eligible": False,
            "game_verified": False,
            "can_activate": False,
            "outstanding": self._session.outstanding(),
        }
        if tuple(body) != _STATE_KEYS or body["enabled"] is not self._enabled:
            raise NativeCommunityError("The trial view is not valid.")
        return body

    def request(self) -> dict | None:
        """Return the host load request, or None when there is nothing to load.

        The host derives ``plugin load`` plus ``stem`` itself. This dictionary
        is not a movie click and is not a bridge action.
        """
        pending = self._pending
        if pending is None or self._loaded or self._enabled:
            return None
        return pending.as_dict()

    def accept_status(self, ack: object) -> dict:
        """Mark the trial loaded only when ``ack`` matches the pending request.

        The result includes ``state`` plus ``accepted`` and ``reason``.
        ``reason`` is ``loaded``, ``duplicate``, ``stale``, ``foreign``, or
        ``unknown``. A refusal leaves ``enabled`` false.
        """
        if self._loaded:
            return self._decision(False, "duplicate")
        pending = self._pending
        parsed = self._parse_ack(ack)
        if pending is None or parsed is None:
            return self._decision(False, "unknown")
        if (parsed["pid"] != pending.pid or parsed["nonce"] != pending.nonce
                or parsed["start_identity"] != pending.start_identity):
            return self._decision(False, "stale")
        if (parsed["site_id"] != pending.site_id or parsed["stem"] != pending.stem
                or parsed["filename"] != f"{pending.stem}.dll"
                or parsed["member_sha256"] != pending.member_sha256
                or parsed["archive_sha256"] != pending.archive_sha256):
            return self._decision(False, "foreign")
        try:
            current = self._observe()
        except NativeCommunityError:
            return self._decision(False, "unknown")
        if (current.scope.pid != pending.pid or current.scope.nonce != pending.nonce
                or current.scope.start_identity != pending.start_identity):
            return self._decision(False, "stale")
        expected = RuntimeIdentity(pending.game_exe_sha256, pending.core_identity, pending.build_identity)
        if current.runtime != expected:
            return self._decision(False, "unknown")
        self._loaded = True
        self._enabled = True
        self._pending = None
        self._status = "loaded"
        self._message = "The native host confirmed the staged plugin."
        return self._decision(True, "loaded")

    def recover(self) -> dict:
        """Recover the community journal after the game and helper are gone.

        Any other probe result leaves the journal in place. This method does
        not read the lease and does not issue a plugin unload. The result
        includes ``state`` plus ``dll_removed`` and ``journal_kept``.
        """
        blocked = self._block_reason()
        if blocked is not None:
            self._status = "deferred"
            self._message = blocked
            return self._recovery_view(False, self._session.outstanding())
        try:
            report = self._session.recover()
        except CommunitySessionError as exc:
            self._hold(str(exc))
            return self._recovery_view(False, self._session.outstanding())
        except Exception:
            self._hold("Process state could not be checked. Files were left in place.")
            return self._recovery_view(False, self._session.outstanding())
        self._apply_report(report)
        return self._recovery_view(report.dll_removed, report.journal_kept)

    def _game_for_session(self) -> bool:
        # CommunitySession repeats this probe immediately before deleting the
        # staged file/journal. Recheck the helper each time, not just at entry.
        for callback in (self._game_running, self._helper_pending):
            result = callback()
            if result is True:
                return True
            if result is not False:
                raise CommunitySessionError("Process state could not be checked. Files were left in place.")
        return False

    def _observe(self) -> _Observation:
        try:
            scope = self._lease()
            runtime = self._runtime()
            heartbeat = self._heartbeat()
            ready = self._movie_ready()
        except NativeCommunityError:
            raise
        except Exception as exc:
            raise NativeCommunityError("The owned offline lease is not active.") from exc
        if not isinstance(scope, OwnedTrialScope):
            raise NativeCommunityError("The owned offline lease is not active.")
        if (scope.development_trial is not True or scope.fresh is not True or scope.offline is not True
                or scope.steam is not True or scope.frontend is not True):
            raise NativeCommunityError("The owned offline lease is not active.")
        pinned = pinned_profile()
        if not isinstance(runtime, RuntimeIdentity):
            raise NativeCommunityError("Runtime identity does not match the pinned trial.")
        if (runtime.game_exe_sha256 != pinned.game_exe_sha256 or runtime.core_identity != pinned.core_identity
                or runtime.build_identity != pinned.build_identity):
            raise NativeCommunityError("Runtime identity does not match the pinned trial.")
        self._require_heartbeat(heartbeat, scope)
        if ready is not True:
            raise NativeCommunityError("The native movie is not ready.")
        if (self._profile.game_exe_sha256 != runtime.game_exe_sha256
                or self._profile.core_identity != runtime.core_identity
                or self._profile.build_identity != runtime.build_identity):
            raise NativeCommunityError("Runtime identity does not match the pinned trial.")
        return _Observation(scope, runtime)

    def _require_heartbeat(self, heartbeat: object, scope: OwnedTrialScope) -> None:
        if type(heartbeat) is not dict:
            raise NativeCommunityError("The plugin heartbeat does not match the owned session.")
        published = heartbeat.get("published_at")
        pid = heartbeat.get("pid")
        protocol = heartbeat.get("protocol")
        if (type(protocol) is not int or protocol != 1 or heartbeat.get("bridge_session") != scope.nonce
                or type(pid) is not int or pid != scope.pid
                or heartbeat.get("online") is not False or heartbeat.get("in_game") is not False
                or type(published) is bool or type(published) not in (int, float)):
            raise NativeCommunityError("The plugin heartbeat does not match the owned session.")

    def _verify_scope(self, scope: OwnedTrialScope) -> bool:
        expected = self._expected
        if expected is None:
            return False
        try:
            current = self._observe()
        except NativeCommunityError:
            return False
        return current.scope == scope and current == expected

    def _parse_ack(self, ack: object) -> dict | None:
        if type(ack) is not dict or set(ack) != _ACK_KEYS or ack.get("status") != "loaded":
            return None
        pid = ack.get("pid")
        texts = (
            ack.get("site_id"), ack.get("nonce"), ack.get("stem"), ack.get("filename"),
            ack.get("start_identity"), ack.get("member_sha256"), ack.get("archive_sha256"),
        )
        if type(pid) is not int or any(type(value) is not str for value in texts):
            return None
        filename = ack["filename"]
        if "/" in filename or "\\" in filename or not filename:
            return None
        return ack

    def _decision(self, accepted: bool, reason: str) -> dict:
        view = self.state()
        view["accepted"] = accepted
        view["reason"] = reason
        return view

    def _recovery_view(self, dll_removed: bool, journal_kept: bool) -> dict:
        view = self.state()
        view["dll_removed"] = dll_removed is True
        view["journal_kept"] = journal_kept is True
        return view

    def _block_reason(self) -> str | None:
        game = self._probe(self._game_running)
        if game is not None:
            return game
        return self._probe(self._helper_pending)

    def _probe(self, callback: Callable[[], bool]) -> str | None:
        try:
            result = callback()
        except Exception:
            return "Process state could not be checked. Files were left in place."
        if result is False:
            return None
        if result is True:
            return _RUNNING
        return "Process state could not be checked. Files were left in place."

    def _note_failure(self, exc: CommunitySessionError) -> None:
        self._pending = None
        self._loaded = False
        self._enabled = False
        self._status = "outstanding" if self._session.outstanding() else "refused"
        self._message = str(exc)

    def _hold(self, message: str) -> None:
        self._pending = None
        self._loaded = False
        self._enabled = False
        self._status = "retained"
        self._message = message

    def _apply_report(self, report: RecoveryReport) -> None:
        self._status = report.status
        self._message = report.reason
        if report.status in {"recovered", "idle"}:
            self._pending = None
            self._loaded = False
            self._enabled = False
        elif report.status in {"retained", "ambiguous"}:
            self._pending = None
            self._loaded = False
            self._enabled = False
