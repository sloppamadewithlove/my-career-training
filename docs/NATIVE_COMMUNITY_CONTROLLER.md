# Native community controller and binding

`NativeCommunityController` stages one pinned Speedflip Trainer trial.
`NativeCommunityBinding` reads the owned native session and is the only
caller that may prepare it. Neither one loads a DLL, launches a game, or
turns on a production flag. `game_verified`, `production_eligible`, and
`can_activate` stay false.

The host may leave the frontend after it has dispatched `plugin load`. An
owned offline local match can then publish the nine-key loaded
acknowledgement. That match is not a reason to withdraw the trial, and it is
not permission to stage.

## Two observation modes

`NativeCommunityBinding._observation(require_frontend=True)` is the staging
read. `require_frontend=False` is the ownership read used by `refresh` and by
the controller callbacks.

Both modes require all of the following, and a missing or non-boolean flag
is a refusal:

- The launcher owner is `ready`, `verify_owned_offline` passes, and the
  executable is the prepared one.
- The bridge nonce is the launch nonce.
- The heartbeat is protocol 1, the same pid, and at most five seconds old.
- `online` is false and `in_replay` is false.
- `frontend` is true exactly when `in_game` is false. A local match is
  `in_game` true and `frontend` false. Any other combination is refused.
- BakkesMod core is 229, the build is `261013.63066.530866`, and the movie
  record's executable hash is the pinned game hash.
- `native_movie_trial.trial_enabled` is true. `movie_ready` is a real
  boolean. The integer 1 is not ready.

The scope's `frontend` flag is the heartbeat's actual boolean. It is not
forced true. Staging additionally requires `frontend` true, `in_game` false,
and `movie_ready` true. `prepare` uses that stricter read and then
`NativeCommunityController._observe(True)`, including every `verify_scope`
call while the DLL is being staged. A local match raises before any trial
file is written.

## Receipt acceptance

`accept_status` calls `_observe(False)`. The owned pid, creation token,
nonce, fresh heartbeat, offline flag, and pinned runtime still have to
match. `frontend` may be false and `movie_ready` may be false while
`in_game` is true. The acknowledgement itself is still the nine keys:
`status=loaded`, `site_id`, `nonce`, `stem`, `filename`, `pid`,
`start_identity`, `member_sha256`, and `archive_sha256`. A stale pid, nonce,
or start identity, or a foreign hash, does not enable the trial.

`refresh` reads ownership first. While that read succeeds, it accepts an
exact loaded acknowledgement before it treats a frontend change as ordinary
menu loss. `can_prepare` is true only when that same refresh still sees the
frontend and `movie_ready`. Leaving the menu hides the pending request so it
is not published again. It does not set `requires_restart`.

These withdrawals stay in place and do not retry:

- The owner, nonce, heartbeat freshness, or pinned build no longer matches.
- Ten seconds pass without confirmation.
- The host reports `refused` or `unknown` for the same nonce, pid, stem, and
  start identity.
- A `loaded` acknowledgement does not match.

`requires_restart` stays true after any of those, and a later good
acknowledgement is ignored. Online play and replays are refused for both
staging and acknowledgement. Host error text is unchanged: an already loaded
plugin, a safeguard or gamespeed failure, a lost connection, and a timeout
each keep their existing sentence.
