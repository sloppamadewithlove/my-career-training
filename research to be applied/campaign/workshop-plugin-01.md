# WORKSHOP-PLUGIN-01: legacy BakkesMod WorkshopPlugin vs. MCT Workshop maps

## Finding

The pinned `WorkshopPlugin` “Workshop” means the deprecated BakkesMod JSON shot/playlist exchange, not Steam Workshop maps. The plugin does not load a map, browse Steam items, or download an archive itself. It sends `sendback` requests to an external RCON-side peer; a response notifier writes shot JSON to BakkesMod’s local shot cache, then delegates load/generate/reset to `TrainingPlugin`. That delegated path can change the ball and cars, so it would conflict with MCT-owned lesson state if enabled alongside the MCT worker.

MCT’s map route is separate: its native Steam Workshop launcher prepares an installed package and dispatches `load_workshop "<canonical path>"` in a guarded offline frontend. As MAP-ARRIVAL-01 documents, callback return is not proof the selected map arrived, and the Python Workshop browser remains browse/favorites only. DOWNLOAD-01 covers community plugin ZIP caching; that path ends `downloaded_not_enabled` and is not a map or plugin activation route. These existing reports remain the source for the full MCT map-arrival and community-download state machines; this report adds the legacy plugin semantics and conflict.

## Pinned source behavior

Public source is `work/research/bakkesmod-default-plugins` at `f412cd66ce0735be4aeb21ca41325337eb959aa0`.

- Plugin declaration: `PLUGINTYPE_FREEPLAY | PLUGINTYPE_CUSTOM_TRAINING | PLUGINTYPE_REPLAY` (`WorkshopPlugin.cpp:14`). This declaration does not override the explicit command-context checks in the sibling TrainingPlugin.
- The only active cvar is `workshop_shot_random`, default `1` (`WorkshopPlugin.cpp:184–187`). With it true, playlist-next chooses a random shot index; otherwise it advances and wraps (`:29–41`). A playlist-random cvar is commented out (`:184–185`).
- `workshop_shot_load <shot_id>` is marked deprecated and registered `PERMISSION_ALL` (`:104–120`). If `./bakkesmod/shots/cache/<id>.json` exists, it invokes `shot_load "cache/<id>"`, `shot_generate`, then `shot_reset` (`:108–114`). If it is absent, it sends `sendback requestshot "<id>"` and stores one pending `load_after_request` value (`:115–119`). The plugin itself contains no HTTP/network/archive download code.
- `requestshot_ans <id> <content>` is a deprecated, all-permission response notifier. It replaces `|` with `"`, writes the result directly to `./bakkesmod/shots/cache/<id>.json`, and retries the pending load if one exists (`:135–150`). This handler shows no ID/path or JSON validation and no acknowledgement/timeout/cancel path. The trust and transport behavior of the external RCON peer are outside this plugin source. `JsonShot` also reads an `options.script` field, which `shot_reset` later passes to `executeCommand`; this legacy content path therefore must not be adapted as a map loader or treated as inert data (`JsonShot.cpp:78–101`; `TrainingPlugin.cpp:168–170`).
- `workshop_playlist_load <playlist_id>` sends `sendback requestplaylist ...`; `requestplaylist_ans` splits the returned shot IDs and calls `next_shot()` (`:122–134`, `:171–183`). `workshop_playlist_next` advances only when its in-memory list is nonempty (`:129–134`). The code calls `shotList.empty()` without using its result before splitting; the `split` helper implementation is not present in this checkout, so whether a later playlist replaces or extends the prior list is unverified. `workshop_playlist_load` does not itself fetch or persist the playlist.
- The plugin also offers deprecated replay-snapshot notifiers, guarded by `IsInReplay()`, that read the replay view target and ball and serialize a template into `./bakkesmod/shots/replay/replay_<n>.json` (`:45–90`, `:151–168`). This is file output, not map loading or ball/car mutation. `getSafeFileName` scans for the next unused numbered JSON name (`:18–26`).
- `WorkshopPlugin::onUnload()` is empty (`:190–192`); it has no timer or game-state cleanup in this file. A response may be pending in `load_after_request`; whether host notifier teardown prevents a late response is not established.

## Delegated shot-load effects and context

The commands above delegate to the pinned `TrainingPlugin` and `JsonShot` source; they are not map-loader commands:

1. `TrainingPlugin` registers `shot_load`, `shot_generate`, and `shot_reset` with `PERMISSION_FREEPLAY`; each is documented deprecated (`TrainingPlugin.cpp:137–140, 212–225`). `shot_load` requires an in-game state and an argument, then loads a `JsonShot` and marks it loaded (`:213–220`). `shot_generate` requires in-game, loaded, and not in custom training (`:221–225`). `shot_reset` has the same in-game/loaded/not-custom-training guard (`:137–140`). Thus the plugin-type declaration does not establish that these commands work in the custom-training browser or in an MCT-created Soccar match. The host’s Freeplay permission semantics in MCT remain runtime-unknown.
2. `shot_load "cache/<id>"` passes that relative stem to `JsonShot`. Its constructor first accepts the argument as a file if it exists; otherwise it tries `./bakkesmod/shots/<argument>.json`, then falls back to `./bakkesmod/data/emptyshot.json` (`JsonShot.cpp:230–250`). Under the cache-miss response path, the expected second resolution is `./bakkesmod/shots/cache/<id>.json`; fallback behavior means command return alone would not prove the intended shot loaded.
3. `shot_generate` calls `currentShot.set()`, which sets `shot_initial_ball_*` cvars for location, orientation, torque, and either authored velocity or generated velocity; it sets the mirror cvar too (`JsonShot.cpp:170–207`).
4. `shot_reset` reads shot data from those cvars, stops and repositions the ball, then loops over all server cars; it skips car indices with no shot player entries and otherwise stops/repositions each car from the shot’s per-player start data (`TrainingPlugin.cpp:141–166`). It runs the optional `options.script` string as a console command (`JsonShot.cpp:99–101`; `TrainingPlugin.cpp:168–170`) and schedules a delayed callback after `max(0, shot_waitbeforeshot)` (default cvar `0.2`) to set ball velocity, angular velocity, and rotation (`TrainingPlugin.cpp:134–135, 184–202`). This is direct shared-world state mutation, not an overlay. The timeout handle is not stored/cancelled here, and `TrainingPlugin::onUnload()` is also empty (`:228–230`); callback teardown behavior is unknown. The delayed callback rechecks only `IsInGame()`, obtains the current server/ball and reads the mutable `currentShot` and cvars again. It does not bind the original shot, actor, map, session or attempt identity, and it recomputes mirroring at execution. A new shot or session between reset and callback is therefore not excluded by this source path.

These commands can also leave persistent shot cvars and cache files. No restoration of pre-shot car/ball state is implemented in the inspected handlers. If another owner (including MCT) writes car/ball state during the pending timeout or after reset, there is no source-level coordination or acknowledgement.

## MCT distinction and bounded adapter contract

The MCT candidate’s Python Workshop browser is local discovery/favorites; launch preparation is unavailable, and its RLBot adapter rejects custom maps before building a match. The separate native map flow selects one installed Steam Workshop package, validates/pins it, then hands a canonical-path `load_workshop` command to BakkesMod; this does not invoke `workshop_shot_load` or `shot_load`. MAP-ARRIVAL-01 already records that dispatch callback return is not a map-arrival receipt and that current lesson `set_state` has no Workshop map identity/geometry gate.

For an eventual MCT Workshop map adapter, keep map package identity and arrival proof separate from any legacy shot IDs or cache files. Do not use `workshop_shot_load` as a map action. If a distinct future feature reuses shot JSON, it needs an exclusive, owned-session mode that prevents concurrent MCT `set_state`, verifies Freeplay and roster compatibility, validates and pins the exact shot content, rejects `options.script`, confirms each `shot_load`/`shot_generate`/`shot_reset` phase, cancels or drains delayed work before Return, and never attributes plugin-created ball/car changes as player performance. Its cache-miss protocol would also need request correlation, timeout/cancel, path-safe IDs, content validation, and a truthful visible failure state.

Minimum acceptance before any such future shot adapter: a wrong-context request changes nothing; missing/invalid/stale response writes nothing and cannot satisfy another pending request; the resolved file is the selected content; car/ball writes are confined to the owned actors and acknowledged; a delayed callback cannot cross attempt reset, session change, or Return; and restored/neutral state is observed before MCT resumes outcome measurement. None of this is established by the pinned legacy plugin.

## Evidence and limits

Static inspection only; no RCON command, network request, game action, plugin load, download, build, or test was performed. The source does not establish current availability of the legacy remote Workshop service, exact host permission behavior, callback lifetime after unload, cache filesystem layout on an installed client, or actual MCT compatibility. The literal `WorkshopPlugin` name and its plugin-type mask are not evidence of Steam Workshop map support.

## Source hashes

Pinned public checkout: `f412cd66ce0735be4aeb21ca41325337eb959aa0`.

| Inspected source | SHA-256 |
|---|---|
| `WorkshopPlugin/WorkshopPlugin.cpp` | `26ea783e428977037461467d0c02341aeab7c4e66255aef458dcd95b48bdcdc1` |
| `WorkshopPlugin/WorkshopPlugin.h` | `9f2418c93c306a4d38b16e29386b3fa5db0369af78cf0608e9f84edbffcbff80` |
| `TrainingPlugin/TrainingPlugin.cpp` | `ed1d66c8fbebad80bd4233140b129eee24887c32fe4eda377e96b54dd283cbef` |
| `TrainingPlugin/JsonShot.cpp` | `b59c2e30bed710b2e8db520e79a2d7a0f274e336613dc9b5e28e249ca43b634c` |

MCT references use `work/reviewed-training`, based on `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. Hashes of relevant files at inspection: `src/my_career_training/workshop.py` `4dea4b359f612389d6186c6fed640c2ee207bf92b4ad1bd6b4e4d56bfb9eb945`; `src/my_career_training/adapter.py` `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` (modified in the working snapshot); `plugin/include/WorkshopLoadPlan.h` `d7266e99106d468699607a1b792d5185311e9715f2341dad8fb3e8860e66f7bf`; `plugin/include/NativeWorkshopLauncher.h` `a8ce39f52c4d9c1aabc30aa6a70d7331d3ca87f71e1772939ad941f7952f6a32`. See `work/campaign/map-arrival-01.md` and `work/campaign/download-01.md` for their broader MCT path evidence and references.
