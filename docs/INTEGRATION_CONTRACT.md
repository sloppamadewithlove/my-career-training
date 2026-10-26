# Shared module contract

Root package: `my_career_training`. Python 3.12. Plain JSON-serializable dictionaries cross module/process boundaries. Each worker owns assigned modules and tests; parent owns `app.py`, `bridge.py`, `__main__.py`, `game_worker.py`, `adapter.py`, root dependency config. Preserve others' edits.

## Domain (`career.py`)
Pure functions returning NEW career dicts (never mutate caller on failure): `new_career(team_name, format=3, seed=None, recruits=None)`, `validate_career(career)`, `standings(career)`, `next_fixture(career)`, `start_fixture(career, session_id)`, `complete_fixture(career, fixture_id, session_id, home_score, away_score, provenance="game")`, `abandon_fixture(career)`, `set_lineup(career, recruit_ids)`, `replace_recruit(career, outgoing_id, incoming_id)`, `set_format(career, format)`, `set_difficulty(career, baseline, curve)`, `start_next_season(career)`. Export ROLES and DEFAULT_RECRUITS. Optional additional functions encouraged. User always club id `human` (home or away per fixture); recruit IDs anchor/shield/relay/comet/orbit. Fixture dict includes id, home, away, round, format integer 1..4, map, seed, difficulty, lineup list, status, result, session_id. Top career includes id, schema_version, team_name, format, recruits dict (all 5 records), squad list (four IDs), lineup list, seasons list, current_season integer index, pending_session dict or None, rewards list. Season includes clubs (id/name/strength), fixtures, playoffs, champion. Document additions.

## Persistence (`storage.py`)
`default_state()` -> {schema_version:1, career:None, settings:{launcher:"steam",install_path:"",text_scale:1.0,reduced_motion:false,binding_profile:"actions"}, lesson_preferences:{}, attempts:[], recordings:[]}. `Store(path, validator=None)` uses per-user directory, `load()`, `save(state)`, `export_file(path)`, `import_file(path)`, `backup()`, `close()`. It may receive validator(state). Concurrency lock and atomic validated writes; no mutation of valid state on failed import. `data_dir()` default system per-user location. Raise user-readable exceptions. Parent owns global validator, domain owns career validator.

## Training (`training/`)
`catalog()` returns eight lesson dicts with id,title,description,steps,starting_state,targets,timeout,assistance_defaults,reference_status. `TrainingEngine(lesson_id, preferences=None)` with `reset()`, `update(frame)`, `summary()`, `recording()`, state/finished properties if useful. Frame normalized: time, dt, car:{position:[x,y,z],velocity:[x,y,z],rotation:[pitch,yaw,roll],angular_velocity:[x,y,z],boost,wheel_contact,has_jumped,has_double_jumped,has_dodged,dodge_timeout,air_state,latest_touch?}, ball:{position,velocity,latest_touch?}, actions:{throttle,steer,pitch,yaw,roll,jump,boost,handbrake}, packet_gap boolean. Provide wireframe ghost line geometry independent of SDK and recording validation/interpolation. Assistance keys `ghost`, `explanations`, `actions`, `timing`, `auto_reset`, `playback_speed`. No fake expert recordings.

## Bots (`bots/`)
`SpecialistController(role="all-rounder", level=1, difficulty=0.5, seed=0)`; `step(frame, player_index, intents=None)` -> controls dict throttle/steer/pitch/yaw/roll/jump/boost/handbrake. Frame includes time, cars:[{index,team,position,velocity,rotation,boost,wheel_contact}], ball:{position,velocity}, prediction:[{time,position}], boosts:[{position,active,is_full}]. Roles keeper/defender/passer/attacker/all-rounder. Expose provider manifest/capabilities honestly experimental without rank certification. No RLBot imports in pure bot modules.

## Lifecycle (`lifecycle.py`, `platforms.py`)
Injectable `Lifecycle` callbacks save, stop worker, close owned game gracefully, check game state, restore temporary setup, and launch normally. The production backend always supplies the `restore` callback. Order: save, drain worker results, save, close owned game, wait until no Rocket League process remains, finish plugin-session restoration, recheck game state, normal launch. A restoration exception or deferred/conflicting result prevents online launch. The in-game service must not quit ahead of an active handoff when its owned game exits. Explicit states from spec. User confirmation is exact text. Process ownership uses PID + create_time, refuses pre-existing game, never global kill. `detect_installations()` returns list of {launcher,path,available}; `launch_online(launcher)` normal entry only. Windows-specific imports lazy.

## UI (`ui/Main.qml` and components)
Context object `backend` has `state` QVariantMap and `dispatch(action, payload)` Slot(str,QVariantMap); stateChanged updates state. UI reads backend.state with defaults. Main state shape: page string, career dict/null, standings list, next_fixture dict/null, lessons list, selected_lesson dict/null, settings dict, lesson_preferences dict, session {state,message,busy}, error string, notice string, diagnostics dict, content list, garage list, latest_attempt dict/null. Main actions: navigate {page}, new_career {team_name,format,recruits?}, play_match {}, lineup {ids}, replace_recruit {outgoing,incoming}, rename_recruit {id,name}, set_format {format}, set_difficulty {baseline,curve}, next_season {}, abandon_fixture {}, select_lesson {id}, start_lesson {id}, retry_lesson {}, stop_session {}, assistance {id,key,value}, settings {key,value}, online_request {}, online_confirm {yes}, export_save {}, import_save {}, diagnostics {}, open_data {}, loadout {id,car_id,primary_color,secondary_color}, open_link {url}, import_map {}, restore_explanations {id}. Parent owns bridge behavior; notify parent of extra actions needed. Use QtQuick.Controls and Layouts. Avoid required JS accessing undefined. No placeholder actions; unavailable integration actions explain capability.

## Community plugin downloads

The separate public catalog and normal-speed ghost-practice contracts are
documented in [TRAINING_WORKSHOP_IMPLEMENTATION.md](TRAINING_WORKSHOP_IMPLEMENTATION.md).
Catalog rows do not grant installation or activation capability. The native
pause ghost controls use command/session acknowledgements and remain separate
from legacy recording playback. Do not remove either action from the native
host allowlist when merging independent Training and Workshop patches.

`community_plugins.py` owns official metadata lookup and bounded download into
the app's private `community-plugins` cache. It does not extract, execute, install
or load third-party plugins. `Backend` runs one cancellable background request at
a time and publishes `community_plugins` with `catalog`, `selected`, `downloaded`,
`busy`, `message`, and `can_activate:false`. Both bridge allowlists accept
`community_lookup {id}`, `community_download {}`, `community_library {}`, and
`community_cancel {}`. Download uses the last server-validated selection, never a
URL supplied by a UI command. There is no general community activation action. Site
verification, local artifact identity, and game compatibility are distinct facts.
Lookup accepts a numeric ID or an exact HTTPS `bakkesplugins.com/plugin/<id>`
page link (optional trailing slash). A page link is parsed locally to its numeric
ID; requests still use the fixed official metadata endpoint. Receipt IDs remain
strictly numeric. Queries, fragments, user info, alternate hosts and ports are
rejected before a network request.

`community_paste_link {}` reads clipboard text only after that explicit action
on the Qt thread, then uses the same bounded official-page lookup. It accepts
no caller payload and does not poll or persist clipboard contents. Empty or
oversized clipboard text is refused before starting a job.

The explicit native-menu developer candidate may attach `NativeCommunityBinding`
after its helper has returned the owned game identity. `community_trial_prepare {}`
stages only the selected, pinned site-286 trial through that capability; it accepts
no caller identity, URL, path, hash, or command. Normal startup has no capability
and rejects the action. The separate `native_community_trial` view remains
unverified; official download `can_activate:false` is unchanged.
`native_community_request` carries the controller's bounded request to the native
host. Only a fresh, exactly matching PluginManager acknowledgement can enable it.
The binding accepts movie heartbeat `movie_ready`, `executable_sha256`,
`bakkes_core:"229"`, and `game_build`, plus the top-level frontend/replay flags.
It maps only that verified core to the controller's `Bakkes229` identity. A pending
load blocks new activities but permits quitting. Scope loss, an attributed host
refusal, or ten seconds without confirmation withdraws the request permanently
for that session and sets `requires_restart`; it never silently resends later.
After dispatch, an exact loaded acknowledgement may be accepted in the same
owned offline match even if the frontend movie is no longer ready. Staging still
requires the frontend at every boundary. A transition hides the outgoing request
permanently while keeping the activity lock until acknowledgement or timeout.
Loss of actual owned/offline scope also revokes an already-loaded trial's enabled
status and requires closing that session.
Interrupted community journals are recovered before offline startup, final plugin
restoration, and normal online handoff. Game/helper presence or a changed file keeps
the journal and prevents handoff; no live community plugin unload is issued.
`session.can_exit` is independent of the community activity lock, so pending or
unconfirmed trials keep the native Exit control available. Actual game/worker
shutdown transitions still disable repeated exit requests.

Native career setup uses ephemeral `career_draft.team_name`, initially `My Career
Club`. `career_name_clipboard {}` reads a 1–40-character printable name only after
an explicit click; it changes the draft, not the existing career. Normal
`new_career {team_name,format}` creates it and preserves an existing career export.
`rename_recruit_clipboard {id}` reads the name through the same bounds and uses
the existing domain edit checks. Neither action accepts caller text or a path.
`backup_save {}` saves and exports to a distinct timestamped file in the app's
data folder without a dialog; arbitrary destination payloads are refused.

Native Career exposes an explicit confirmation before restarting an unfinished
fixture. Its `abandon_fixture` payload binds `expected_career_id`,
`expected_fixture_id` and `expected_session_id`. The backend rejects partial,
extra, changed or live-worker confirmations without writing the save. A valid
restart returns that fixture to the schedule without awarding a result; existing
completed matches and squad data remain. Legacy empty-payload abandon calls keep
their existing worker-stop behavior.

The native movie host derives `frontend`, `pause`, or `results` from the owned
offline game's SDK state. Bridge JSON and movie messages cannot select a surface.
Surface changes clear queued callbacks and readiness. The common view includes
`surface`; pause/results commands include it and the current generation/revision.
Their ready message is exactly `protocol`, `session`, `surface`, `generation`,
`event:"ready"`. The legacy three-field frontend ready message and five-field
frontend command are accepted only while the actual frontend is active.
The rebuilt frontend sends surface and generation in READY too; legacy READY
must not satisfy Return arrival.

Pause Resume and Game options are fixed stock callbacks in the authored movie.
Retry lesson dispatches `retry_lesson {expected_session_id}`. Return dispatches
`return_hub {expected_session_id,expected_fixture_id,abandon}` after an explicit
confirmation for an unfinished fixture. Stale activity identities are rejected
before saving or stopping. Results Return is disabled until the backend reports
the saved result for the current session and fixture. No movie invokes a raw
match restart or console navigation command.

After the worker stops, the service drains final output and durable result
receipts before abandoning a still-unfinished fixture or clearing its request.
An uncommitted final score prevents that cleanup. A completed cleanup publishes
the hub activity and retains the owned game for the next lesson or fixture.
These contracts require separate live pause/results acceptance for the exact
packaged movies; passing the pure host tests is not gameplay verification.

After a requested native Return has drained and saved the stopped activity,
`native_return_ready` is `{session_id,fixture_id}` for that old activity.
Its fixture string is empty for a lesson. At this point `session.id` and
`session.fixture_id` are JSON null, `session.kind` is `hub`, the state is `Idle`,
and `worker_running` and `busy` are false. An error or uncommitted result prevents
readiness. The receipt persists for the host's final game navigation and is
cleared before a new activity starts; result recovery alone does not issue it.
The host must match an accepted native Return request, retain the pending
navigation across a resumed/unloaded pause menu, and observe the actual frontend
before declaring the game navigation complete.

The Return repair uses the fixed typed ActionScript `Shell.ExitToMainMenu`
route, with the pause movie's stock `m_bExitingMatch` behavior. It must not use
SDK `disconnect`, which reached the title screen in the recorded game test.
The navigation intent is bound to the accepted bridge nonce, activity, fixture,
and one-shot intent token. A service acknowledgement authorizes navigation;
it does not prove navigation was attempted or that the hub was reached.

`DevUtil.Log` has no success return value. The movie therefore must not exit
immediately after sending a rejectable consumption event. The required exchange
is an `authorize` view, a matching `return_navigation_consumed` event, and a
separate host `execute` view carrying the consumed generation. The movie can
execute only with its matching local consumption latch. Both phases participate
in view generation. `return_navigation_issued` records an attempt immediately
before the typed call; it is not an arrival receipt.

The host separately latches a successfully published execute grant. Publication
is not proof of an attempted call. If readiness or the movie is lost after that
publication, the host cannot know whether the call ran and its log was dropped;
it must not offer another exit or reopen attempt. Preserve the pending intent
and uncertain-delivery diagnostic until actual arrival or scope replacement.
Loss of readiness before execute publication revokes consumption and permits a
fresh authorization handshake. An explicit fresh view without navigation must
never later resume its old consumed generation.

Unloading the pause/results movie invalidates its consumption grant but retains
the accepted Return intent. A changed activity, nonce, owned process, build, or
offline scope revokes the intent. New native activities remain blocked while
Return is pending. Completion requires a new authored frontend READY after the
surface transition and the fresh SDK menu stack reporting `RootMenuMovie` in
the same owned offline game. Idle, a title screen, and stale readiness are not
completion. A bounded live test of `OnOpenPauseMenu` did not open the pause
movie; the host no longer calls it. An externally unloaded pause retains intent
and reports that the player must reopen pause with Escape or Start.

The view binds `return_pending` and `return_hold` into its generation. Each
control has a `return_commit` boolean, true only for actual Return or confirmed Forfeit dispatch,
not for opening an unfinished-match confirmation. The movie covers the initial
click-to-host gap for at most two seconds. A fresh accepted hold then retains
the menu, disables Resume/Options, and consumes closing input while displaying
Leaving. Cancel remains available before commitment. The host hold ends after
15 monotonic seconds without resetting on heartbeat or reauthorization; errors,
stale views and uncertain execution also release controls. Release does not
discard the intent or permit a second exit. Existing safe Quit and save-retry
dispatch remain available when their service gates permit them. Quit must not
receive automatic focus from the preceding confirmation. The permanent
navigation-issued latch guards the exit call, not all recovery controls.

Career pause also offers a red Forfeit Match action, with a separate confirmation
whose default selection is Back. It requires a current owned unfinished career
match and exact session/fixture binding; training, calibration and finished results
cannot forfeit. The movie effect carries
`forfeit_match {expected_session_id,expected_fixture_id,confirm:true}`. The trusted
host adds a fresh 32-character lowercase hexadecimal `return_intent`; the service
accepts exactly those four fields. The host rechecks the actual server's
`GetbMatchEnded` immediately before dispatch.

The service drains already received natural results before choosing a forfeit.
An already saved natural finish wins that race. Otherwise `forfeit_fixture`
atomically records `provenance:forfeit`, `outcome:forfeited`,
`forfeited_by:human`, and the opponent as winner, retaining the observed goals.
Ties and human leads still count as losses; table points, progression and brackets
follow the explicit winner. No goals are invented. The pending fixture clears
and the schedule advances once. A late matching natural result receipt cannot
overwrite or award the saved forfeit again.

Only after that durable save does worker cleanup begin. Navigation still requires
the exact `native_return_ready` acknowledgement and the existing typed Return
handshake; the host additionally checks the matching saved forfeit. A failed
precommit attempt publishes `native_forfeit_rejected {session_id,fixture_id,intent}`.
Only an exact matching rejection releases that host intent for another attempt;
generic errors and old rejection records cannot do so. A postcommit cleanup
failure must not publish a rejection. Regular unfinished Return still requeues
the fixture without recording a loss.

The native results host separately retains a saved natural result against the
observed automatic next-map countdown. It must have tracked the exact game event
while its bound career fixture was Playing. Refreshing the finished-state timer
requires that same event, an ended match, actual EndGameMenuMovie with fresh
authored results READY, matching persisted result, cleared pending fixture and
fresh owned offline scope. It refreshes only a positive countdown at 30 seconds
or below to 60 seconds, with at least five seconds between attempts. It never
revives an expired timer or writes the Soccar match clock. The typed SDK setter
still needs live acceptance. `IsFinished()` is not used as evidence: the observed
build returned false even while the real results screen counted down.
After earning fresh results READY, the timer-only permission also covers
`OptionsMenuMovie` while the SDK stack still contains `EndGameMenuMovie`
underneath it. Unknown screens do not receive timer writes and revoke that
modal permission; a loading gap performs no writes. Returning to results must
earn fresh READY again. This permission never authorizes shell navigation.
A stale bridge or unavailable game event discards the timer binding because the
gap could hide a map transition and object-address reuse. Accepted Return intent
is still retained separately. The host checks the current results generation and
READY again immediately before a results-screen timer write.

These are the repair's acceptance requirements. Exact source, compiled movies,
and live-game evidence must be recorded separately before release.

The next results-flow change is defined in
[RESULTS_CONTINUATION_CONTRACT.md](RESULTS_CONTINUATION_CONTRACT.md). It adds
separate prepare/start commands, exact continuation acknowledgements and the
five requested results controls. Treat that contract as implementation work in
progress until current status records the corresponding source and live checks.
Results Exit returns to the hub; the home close-app control is Quit My Career.

## Packaging

Entry `python -m my_career_training`, flags `--worker` (JSON lines stdin/stdout), `--self-test` (headless package contracts), `--smoke-test` (QML load then quit), optional `--data-dir`. Resources under package. `runtime/RLBotServer.exe` build-only downloaded verified core; packaged under runtime. Mac UI/domain tests omit RLBot dependency, Windows includes exact versions. Original SVG/ICO icon generated by UI worker. Version 0.1.0 testing prerelease; never mark full V1 complete without game tests and real references.
