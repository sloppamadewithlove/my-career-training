# Runtime state-machine inventory and failed-retry repair

Source baseline: `26a8a5461c81f1e2766baf2abb5c9c0e82fc5c65`, 6 November 2026.
Mode: source inspection and isolated automated tests only. No game, Steam,
player saves, installed plugin, package, or published branch was changed.

## Confirmed defect and repair

`GameSession.reset()` reset the live `TrainingEngine` before validating the
native reset fence or dispatching actor state. A malformed/unavailable bridge
file or rejected `send_msg` therefore changed the attempt ID, discarded the
in-memory recorder and observations, and entered `settling` even though the
reset had not been sent. The worker's `attempt_sent` and `attempt_acked` still
referred to the previous attempt. Retrying after the error could then compare
inconsistent identities. This is a source-reproduced recovery defect; no claim
is made that it caused a previously observed live reset failure.

The shared reset function now prepares a replacement engine, sends the desired
actor state under the existing fence, and adopts the replacement only when the
send returns successfully. This follows the existing scenario-step transaction.
No transport schema, engine timing, normal Human input, or saved-result policy
changes. The old ghost generation is still invalidated before a reset write.

The shallow copy is intentional: `TrainingEngine.reset()` replaces every
attempt-owned collection and scalar, including its recorder. Its shared
configuration (`lesson`, `scenario`, `metadata`, preferences, tolerances and bot
indices) is read only during reset. `Recorder.__init__()` deep-copies its lesson
and supplied metadata; `_scenario_recording_metadata()` writes only the new
recorder's metadata. Copying the previous potentially 36,000-sample recording
would add unnecessary allocation. Regression snapshots compare the complete
original engine dictionary, including nested recorder data, before and after
both rejected and successful reset preparation for legacy and scenario engines.

Player-action contract:

1. Preconditions: owned training session, fresh required scope and acknowledged
   saved attempt when one is pending; normal capture/recovery gates still apply.
2. Input: existing `retry_lesson` command through `GameSession.handle_command`,
   including Power Shots' queued control route.
3. Outcome: a successful state dispatch commits a new settling attempt; a
   refusal keeps the original attempt and its in-memory trace.
4. Persistence: no new save operation. Existing attempt acknowledgements remain
   authoritative and are cleared only after a successful dispatch.
5. Failure/recovery: existing errors/notices and exception behavior are retained.
   The old native ghost generation loses authority; its playback cursors and
   attempt identity remain available for a later successful retry. A fence may
   have been published before a transport error; it does not establish an actor
   reset or authorize an old ghost. A send exception has no delivery receipt,
   so the repair does not assert that the game could not have received bytes.
6. Proof: four original regressions failed on the baseline; six new regression
   cases pass with the repair. They cover fence/dispatch failure in both legacy
   and scenario routes, full original-state snapshots, actual malformed fence
   JSON, fence-file publication before dispatch, preserved ACK/deadline and ghost
   cursors on failure, then successful retry with a new ID and matching fence.

### Independent review follow-up: Stop wins during reset preparation

Review of `6681c013258f6f7291c4d7c3e1ba459495a38ec0` found that the existing final
actor-state guard checked cancellation/stopping only for development capture.
An ordinary lesson could pass its initial retry/step gate, receive a real Stop
while constructing desired state or publishing the native fence, and still send
actor state and commit a new attempt or acknowledge a scenario step as accepted.

The final `_send_actor_state()` gate now checks cancellation and stopping in every
mode, with capture deadline enforcement still limited to capture. A stopped
scenario step keeps the original setup and returns a failed acknowledgement;
retry returns without adopting its prepared engine or clearing its saved-attempt
ACK, ghost cursor or feedback deadline. The fence still revokes old native ghost
authority. This does not withdraw an actor-state message already sent before Stop.

Six additional regressions use a real session thread and `Worker.command(stop)`
on the calling thread. Each ordinary speed-flip retry, Power Shots retry and
Power Shots step is interrupted at both desired-state construction and after
the actual atomic native-fence publication. All six reproduced the unwanted send
on `6681c01` before the follow-up repair, and pass with the universal gate.

## Inventory

An implicit machine here means behavior depends on a retained combination of
flags, optional identities, counters, timestamps, collections or durable files.
An enum/string phase can still participate in an implicit composed machine.
This is a functional inventory, grouping small related latches under their owning
runtime boundary; it is not a claim that each flag needs its own class or enum.

The rows below identify inspected ownership, transitions and important invariant.
Except for the repaired retry transaction and final Stop gate, they are inventory and existing
controls, not new defects or comprehensive correctness certificates. Tests named
as anchors are existing coverage to consult; this audit did not execute every
listed native or Python test.

| Cluster | Owning source | Retained state and transition/invariant | Coverage anchor / disposition |
| --- | --- | --- | --- |
| Service activity | `src/my_career_training/bridge.py`: `Backend.state`, `_prepare_launch`, `_launch`, `_event` | Session phase + request + worker/process + result identity govern idle/start/play/results; unrelated saved results must not unlock an activity | `tests/test_bridge.py`; inventoried |
| Startup cancellation | `bridge.py`: `_tick`, `_event`, `_process_error`, `_process_finished` | Deadline, ready and cancelled-session latch; no start after pre-ready cancellation; late running telemetry must not erase cancellation | `tests/test_bridge.py`; inventoried |
| Stop/restart/Return/Quit | `bridge.py`: `_begin_stop`, `_close_after_stop`, `_drain_activity_results`, `_finish_native_return`, `_tick` | Reason, worker exit, game exit, deadline and pending launch; final score drains before abandonment or native navigation readiness | `tests/test_ingame_lifecycle.py`; live Quit completion remains open |
| Durable match results | `game_worker.py`: `process_packet`; `bridge.py`: `_commit_result`, `_recover_outbox` | Observed active/ended edge, outbox receipt, durable domain commit, acknowledgement; duplicate receipts cannot award twice | `tests/test_worker.py`, `tests/test_bridge_transport.py`; inventoried |
| Forfeit race | `bridge.py`: `_forfeit_match`, `_commit_result`; `career.py`: `forfeit_fixture` | Exact session/fixture/intent, natural finish drain, atomic forfeit and cleanup; saved natural finish or saved forfeit wins once | `tests/test_bridge_forfeit.py`; inventoried |
| Prepared next match | `bridge.py`: `_prepare_next_match`, `_cancel_prepared_next`, `_start_prepared_match` | Prepared/last request, old result, lineup and game identity; consume continuation before launch side effects | `tests/test_bridge_continuation.py`; inventoried |
| Fixture/season progression | `career.py`: `start_fixture`, `_commit_human_result`, `_advance`, `abandon_fixture`, validators | Scheduled/pending/completed, attempt list, pending session, bracket/rewards; abandon requeues, real completion advances once | `tests/test_career.py`, `tests/test_domain_adversarial.py`; inventoried |
| Official plugin job | `bridge.py`: `_community_job`, `_poll_community` | Busy flag, cancellation event, worker queue and validated selection; download remains distinct from enable/load | `tests/test_community_plugins.py`; inventoried |
| Catalog generations | `bridge.py`: `_catalog_job`, `_catalog_cancel_current`, `_poll_catalog` | Generation, outstanding count, append request, page/query/source; old/cancelled responses cannot replace the active list | `tests/test_community_discovery_bridge.py`; inventoried |
| Native pack activity | `training/native_packs.py`: `NativeTrainingPackController`; `bridge.py`: `_tick` | Pending/loaded/failed plus exact receipt and freshness deadline; permanent failure withdraws request, loaded status is continuously reverified | `tests/test_native_training_packs.py`; inventoried |
| Ghost command acknowledgement | `bridge.py`: `_remember_ghost_command`, `_ghost_ack`, `_expire_ghost_pending`, `_event` | Optimistic enable, ordered pending commands and deadline; late On cannot revive explicit Off | `tests/test_game_worker_ghost_practice.py`; inventoried |
| Ghost retry/recording availability | `bridge.py`: `_native_recording_rows`, retry/assistance actions, telemetry branch | Retry generation, command identity and validated recording cache; old pose hidden until matching observed reset | `tests/test_native_ghost_freshness.py`; source transport proof only |
| Worker process lifetime | `game_worker.py`: `Worker.command`, `run`, `finish_after_eof`; `GameSession.run`, `teardown` | Session/thread/core ownership, cancellation, stopping deadline and cleanup-complete; retain writer/core ownership until actual cleanup | `tests/test_worker.py`, `tests/test_worker_entry.py`; inventoried |
| Match configuration and team mapping | `game_worker.py`: `start_acknowledged_match`, `map_team`, `setup`, `process_packet` | Config signature, reservations, ready teams and observed roster; controls target designated bots and one expected Human | `tests/test_worker.py`; inventoried |
| Worker inbox/packet ordering | `game_worker.py`: `SessionInbox`, `receive_packet`, `process_packet` | Coalesced packet arrivals, receive sequence/time and event ordering; a fresh publication cannot rejuvenate an old packet | `tests/test_worker.py`, `tests/test_native_ghost_freshness.py`; inventoried |
| Telemetry recovery | `game_worker.py`: `_wait_for_training_telemetry`, `_reset_after_training_telemetry`, `_check_telemetry_recovery_timeout` | Interrupted attempt, invalid fields, freshness and deadline; no fabricated success or reset before prior save acknowledgement | `tests/test_worker.py`; inventoried |
| Training preparation/execution | `training/engine.py`: `reset`, `update`, `_interrupt`, `_finish` | Settling/ready/active/finished/interrupted, observed reset, cadence, elapsed time and events; actual reset observation starts attempts | `tests/test_training.py`, `tests/test_training_cadence.py`; inventoried |
| Retry dispatch transaction | `game_worker.py`: `reset`, `_send_actor_state`, `handle_command`, `_try_training_control` | New engine + native fence + actor send + ACK/ghost state; do not mutate the accepted attempt before dispatch succeeds; final Stop gate applies in all modes | **Two confirmed defects repaired here** |
| Scenario goal/timeout attribution | `training/engine.py`: `_scenario`, `_scenario_observe_touches`; `game_worker.py`: `_queue_goal_progression` | Attempt-bound score baseline/edge, actor touches and terminal outcome; later goal cannot reopen timed-out attempt | `tests/test_power_shot_scenarios.py`; original live transition cause remains open |
| Queued challenge step/retry | `game_worker.py`: `_queue_training_control`, `_try_training_control`, `_step_training_scenario` | One attempt-bound pending manual/automatic control, deadline, save and phase gate; prepared replacement commits coherently | `tests/test_power_shot_scenarios.py`, `tests/test_scenario_setup.py`; inventoried |
| Automatic retry feedback | `game_worker.py`: `handle_command(attempt_ack)`, `_check_auto_reset` | Published attempt, save ACK, retry eligibility and feedback deadline; wait through unavailable telemetry and respect Auto Reset Off | `tests/test_worker.py`; inventoried |
| Scenario and bot decisions | `training/scenarios.py`; `bots/__init__.py`; `bots/learned.py` | Reaction start time, delegate intents, decision cadence, kickoff/model state; retry resets actor controllers | `tests/test_power_shot_scenarios.py`, `tests/test_bots.py`; useful live exercise remains separate |
| Development reference capture | `reference_capture.py`; `game_worker.py`: capture helpers; `training/bot_reference.py` | Marker/config binding, mapping, one-attempt restriction, packet deadline, controller phase and abort; no Human control or unvalidated promotion | `tests/test_reference_capture.py`, `tests/test_bot_reference.py`; no teaching-reference acceptance claimed |
| Legacy ghost transport | `training/coach.py`: `GhostPlayback`; `game_worker.py`: ghost commands | Loaded recording, watch/lead mode, cursor, pause, loop, clock and origin; command validation precedes replacement | `tests/test_training_coach.py`, `tests/test_game_worker_ghost_practice.py`; inventoried |
| Practice ghost transport | `training/coach.py`: `GhostPractice` | Availability/enabled/playing, origin, anchor, last clock and cursor; On/retry restart; flip reset preserves paired world car/ball trace | `tests/test_training_ghost_practice.py`; native look/non-interference acceptance open |
| File-command bridge | `ingame.py`: `FileBridge`; `plugin/src/LocalBridge.cpp` | Nonce, consumed IDs, command ACK, cached heartbeat and atomic snapshot; scope/freshness authorize commands, sharing locks retry | `tests/test_ingame.py`; inventoried; single-ACK replay limits not resolved here |
| Native movie ownership/readiness | `NativeMovieHost.cpp`; `NativeMovieSession.h`; `NativeMovieProtocol.h` | Owned scope, nonce/surface/generation, hook/open/view/READY flags and queue; surface change invalidates readiness/callbacks | `plugin/tests/native_movie_session_tests.cpp`, `native_movie_protocol_tests.cpp`; inventoried |
| Native layout interaction | `NativeCareerLayout.h`, `NativeMatchLayout.h`, `NativeMenuDataBinding.h`, `NativeCareerMenu.h` | Current page, selection and revision-bound choices; callbacks must match the current producer/consumer view | `plugin/tests/native_career_layout_tests.cpp`, `native_match_movie_tests.cpp`; inventoried |
| Native Return handshake | `NativeReturnGate.h`; `NativeMovieHost.cpp` | Accepted intent, durable ready, consumed generation, execute publication/issued/arrival latches and hold deadline; never retry uncertain exit delivery | `plugin/tests/native_return_gate_tests.cpp`; exact live arrival still separate |
| Native continuation | `NativeContinuationGate.h`; `NativeMovieHost.cpp` | Ready/committed/arrived, saw-Return, attempted and send result; start once after fresh actual hub arrival and exact durable identity | `plugin/tests/native_continuation_gate_tests.cpp`; inventoried |
| Results timer/modal permission | `NativeResultsHold.h`; `NativeMovieHost.cpp` | Tracked game-event/activity, ended edge, exact saved result, fresh READY and modal permission; timer-only lease cannot authorize navigation | `plugin/tests/native_results_hold_tests.cpp`; typed timer live proof open |
| HUD/menu show/hide | `MenuLifecycle.h`; `MyCareerTraining.cpp` | Previous phase/session/pause/ended; request host visibility only on transitions, retain user dismissal | `plugin/tests/menu_lifecycle_tests.cpp`; inventoried |
| Training input debounce/bindings | `TrainingLessonInput.h`, `TrainingGhostInput.h`; `MyCareerTraining.cpp` | Held keys, arming/latch, action ACK/deadline, original bindings and restore-pending; one gesture, no Human input takeover | `plugin/tests/bridge_tests.cpp`; physical controller proof open |
| Native countdown lease | `TrainingClock.h`; `MyCareerTraining.cpp` | Event/scope, original clock and active lease; typed writes bounded to current owned offline event and restore on scope end | `plugin/tests/training_clock_tests.cpp`; visible zero remains live blocker |
| Timeout ball visibility lease | `TrainingBallVisibility.h`; `MyCareerTraining.cpp` | Event/ball/attempt and original flag; no restoration into a replacement actor; retain restoration ownership on error | `plugin/tests/training_ball_visibility_tests.cpp`; exact live zero/removal/reset proof open |
| Native ghost render authority | `NativeGhostHost.cpp`, `NativeGhostPlayback.h`, `NativeGhostRenderer.cpp` | Ordered packet receipt, boot age, attempt/reset fence, epoch, identity and render lease; no old/frozen pose rejuvenation | `plugin/tests/native_ghost_playback_tests.cpp`, `tests/test_native_ghost_freshness.py`; live rendering open |
| Cosmetic temporary override | `CosmeticOverrideState.h`; `NativeCareerHost.cpp`; `MyCareerTraining.cpp` | Original values and restore-pending; apply failure must restore or retain explicit recovery state | `plugin/tests/cosmetic_override_state_tests.cpp`; inventoried |
| Native community trial | `native_community.py`, `native_community_binding.py`; `NativeCommunityHost.h` | Staged/pending/loaded/enabled, expected scope, timeout/withdrawal and native side-effect restoration; load confirmation is distinct from request delivery | `tests/test_native_community.py`, `tests/test_native_community_binding.py`; inventoried |
| Native training pack host | `NativeTrainingPackHost.h`; `MyCareerTraining.cpp` | Idle/pending/loaded/failed, one attempted request and reverified pack code; wrong/stale scope fails closed | `plugin/tests/native_training_pack_host_tests.cpp`; inventoried |
| Workshop native launch | `NativeWorkshopLauncher.h`, `NativeWorkshopDispatch.h`; `workshop.py` | Selected fixed path, verified local context, accepted request and one host dispatch; fixed command derived locally | `plugin/tests/native_workshop_launcher_tests.cpp`; exact live arrival/return open |
| Native preparation/helper lifetime | `native_offline.py`; `native_launch.py`: `OwnedNativeLaunch` | Prepared/owner/uncertain and ready/reaping/degraded/exited; a possibly live child retains helper and blocks restoration | `tests/test_native_launch.py`; inventoried |
| Native launch commit | `native_launcher/src/LaunchCommit.cpp`, `WinLaunch.cpp` | Validate, suspended child, identity/payload/resume, retained handles and confirmed termination; failed uncertainty retains ownership | `native_launcher/tests/launcher_tests.cpp`; no helper executed in this audit |
| Service online handoff | `lifecycle.py`; `bootstrap.py`: service tick; `bridge.py`: `_restore_before_online` | Confirmation/frozen/phase/deadlines; save, drain, close, confirm all games gone, restore, recheck, normal launcher | `tests/test_lifecycle.py`, `tests/test_ingame_lifecycle.py`; no online operation performed |
| Temporary plugin journal | `plugin_session.py`: `begin`, `_restore`, `_restore_resource` | Prepared resource receipts, original/session bytes, partial unresolved restoration and running-game guard; preserve conflicts and backups | `tests/test_plugin_session.py`; inventoried |
| Community DLL journal | `community_session.py`: `stage`, `recover` | Prepared/staged plus exclusive file identity, scope checks, deferred/conflicting recovery; never delete a file based only on a path | `tests/test_community_session.py`; inventoried |
| Store/save ownership | `storage.py`: `Store`, `_atomic`, `save`, `import_file`; `map_guard.py` | App lock, current/backup/temporary files, import preservation and legacy recovery journal; no implicit damaged-save overwrite | `tests/test_storage.py`, `tests/test_game_preservation.py`; isolated data only |
| Native root UI/browser | `native_ui/menus/MctRootMenu.as` | Loader/busy/attached/READY, generation, page/focus, gesture and queued refresh; browser search/paging and preview idle/loading/ready/unavailable | Source inventory; compiled movie/live focus/image behavior not exercised |
| Pause/results authored UI | `native_ui/menus/MctPauseMenu.as`, `MctResultsMenu.as` | Local commitment/hold, consumption and navigation-issued, focus suppression, results preset modal and gesture state; controls recover without duplicate exit | Source inventory; exact compiled/live results and Career regressions open |
| Desktop management UI | `ui/Main.qml`; `bridge.py` | Page, drafts, open dialogs, dismissed errors and backend busy/lock; closing delegates to save/shutdown authority | Source inventory; UI smoke/interactive acceptance not run |

## Evidence and remaining work

The code repair is deliberately local; replacing all these machines with a new
framework would create a broad regression surface without proving player benefit.
The inventory exposes their ownership and recovery boundaries for subsequent
focused reviews. No second defect was promoted solely because it uses booleans.

Known unresolved player-visible issues remain those in `PROJECT_STATUS.md`: native
countdown at zero, whole reset/timeout ball behavior, authored Quit completion,
native End Training/results and Career regressions, native ghost rendering and
non-interference, physical controller behavior, and thumbnail/Workshop/Mods/
Garage/Options acceptance. Source correctness does not close those live gaps.

This bounded audit did not exhaustively enumerate every gesture, bot policy
substate, detector event, third-party SDK internal state or experimental probe.
Native file-view DLL internals, installed runtime compatibility and crash/power
loss interleavings need their own artifact/runtime evidence. In particular, no
exhaustive all-state-machine or live-readiness claim is justified.

Validation counts are recorded in the final worker handoff and main integration
receipt. This document is source inventory, not a binary or release receipt.
