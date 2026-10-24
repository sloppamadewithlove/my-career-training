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

`community_plugins.py` owns official metadata lookup and bounded download into
the app's private `community-plugins` cache. It does not extract, execute, install
or load third-party plugins. `Backend` runs one cancellable background request at
a time and publishes `community_plugins` with `catalog`, `selected`, `downloaded`,
`busy`, `message`, and `can_activate:false`. Both bridge allowlists accept
`community_lookup {id}`, `community_download {}`, `community_library {}`, and
`community_cancel {}`. Download uses the last server-validated selection, never a
URL supplied by a UI command. There is no community activation action. Site
verification, local artifact identity, and game compatibility are distinct facts.
Lookup accepts a numeric ID or an exact HTTPS `bakkesplugins.com/plugin/<id>`
page link (optional trailing slash). A page link is parsed locally to its numeric
ID; requests still use the fixed official metadata endpoint. Receipt IDs remain
strictly numeric. Queries, fragments, user info, alternate hosts and ports are
rejected before a network request.

## Packaging
Entry `python -m my_career_training`, flags `--worker` (JSON lines stdin/stdout), `--self-test` (headless package contracts), `--smoke-test` (QML load then quit), optional `--data-dir`. Resources under package. `runtime/RLBotServer.exe` build-only downloaded verified core; packaged under runtime. Mac UI/domain tests omit RLBot dependency, Windows includes exact versions. Original SVG/ICO icon generated by UI worker. Version 0.1.0 testing prerelease; never mark full V1 complete without game tests and real references.
