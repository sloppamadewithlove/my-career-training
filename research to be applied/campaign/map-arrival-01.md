# MAP-ARRIVAL-01 — Workshop launch and arrival boundary

Date: 2026-10-27
Scope: static source audit of the frozen `work/reviewed-training` candidate. This follows `map-01`, `content-01`, and `build-01`; it narrows in on the native Workshop row → command handoff → external offline activity → Return path.

## Finding

The candidate has a development-only route that selects and pins one installed Steam Workshop package, then hands a derived `load_workshop` command to BakkesMod. A successful callback means only that the callback returned. The native launcher explicitly leaves game verification, game testing, and production authorization false (`NativeWorkshopLauncher.h:4-14, 50-55`; `WorkshopLoadPlan.h:757-789`).

There is no request-bound map-arrival check. The later external-activity bridge reports only the current bridge-session ID after it observes an otherwise idle, in-game session (`bridge.py:299-310`). It does not carry the selected Workshop row, package hash, map asset/name, or geometry. That generic state can support the native Return handshake, but it cannot prove that the selected package became the active map. The Python Workshop browser remains browse/favorites only and its launch preparation throws; the RLBot adapter also rejects custom-map requests before building a match config (`workshop.py:171-244, 258-282`; `map_guard.py:76-81`; `adapter.py:40-43`).

So the current candidate does not establish a safe path from “map row selected” to “lesson may write a set_state.” The prior `map-01` covers package discovery/identity and `content-01` covers lesson coordinate assumptions; this report records the missing arrival and integration proof.

## Source-backed path

1. **Row selection is bound to a package.** `NativeCareerLayout::bindWorkshop` accepts installed `steam_workshop` entries whose numeric Workshop ID and canonical path fit the verified Steam Workshop tree. Catalog aliases are admitted only when `launch_id` resolves to exactly one package (`NativeCareerLayout.h:697-754`). `chooseBrowser(primary)` rechecks the current published row and package path, content root, Workshop ID, nonce, and generation, then emits a local `LocalWorkshop` effect; it does not emit a lesson action or lesson-state payload (`NativeCareerLayout.h:569-695`).
2. **The launch scope is the owned offline Steam frontend.** `ownedOfflineNow` checks the live bridge/session identity against the running executable and Steam ownership (`MyCareerTraining.cpp:580-588`). `workshopScope` additionally records freshness, online/in-game/replay/busy state, verified executable/Bakkes/game-build identity, nonce, and generation; `nativeWorkshopContext` exposes readiness only while fresh, verified, offline, and at the frontend (`MyCareerTraining.cpp:841-894`). The loader is constructed under `MCT_ENABLE_NATIVE_MOVIE_TRIAL`; `NativeWorkshopLauncher` identifies itself as development-only and its game-tested/production flags are false (`MyCareerTraining.cpp:175-191`; `NativeWorkshopLauncher.h:4-14, 50-55`). The source audit does not establish which compile flag a particular binary used.
3. **Preparation validates bytes, then dispatches on the game thread.** `WorkshopLoadPlan::scopeReason` rejects unowned, stale, online, non-offline, non-Steam-frontend, in-game, replay, busy, or mismatched-build scopes and mismatched nonce/generation (`WorkshopLoadPlan.h:320-339`). `prepare` validates the rooted path, reads and hashes the selected package, then derives `load_workshop "<canonical path>"` while keeping `gameTested` and `productionAllowed` false (`WorkshopLoadPlan.h:757-789`). `NativeWorkshopLauncher::begin` snapshots scope and starts preparation; `prepareAway` pins the package/directories and rechecks the plan; `poll` rechecks authority and the held file before committing the pin and invoking the executor (`NativeWorkshopLauncher.h:504-562, 564-609, 611-686`). The final dispatcher checks command framing and canonical path (`NativeWorkshopDispatch.h:9-29`). `maintainWorkshop` cancels pending work on bridge-nonce change or loss of ownership/online scope, then polls (`MyCareerTraining.cpp:926-944`).
4. **The bridge does not verify map arrival.** `NativeMovieHost::apply(LocalWorkshop)` only starts preparation; dispatch is deferred to the game-thread poll (`NativeMovieHost.cpp:631-639`). The launcher comments and result flags define `requested`/`callbackReturned` as callback state, not proof of a loaded map (`NativeWorkshopLauncher.h:4-14, 611-686`). In the separate external-activity path, `bridge._native_external_activity` requires a fresh, unfrozen, in-game bridge with no app session/request/worker/training-pack/continuation and returns only `{session_id: bridge_session}` (`bridge.py:299-310`). No selected map identity is compared there.

## Session boundaries, failure, and Return

- **Online and unowned sessions:** The native request is rejected unless it is in the verified owned Steam offline frontend. Online, stale, replay, in-game, busy, wrong-build, wrong-nonce, and wrong-generation states fail closed before dispatch (`WorkshopLoadPlan.h:320-339`; `MyCareerTraining.cpp:841-914`). The path is not permission to start or use an online session. The external-activity bridge likewise does not represent a map-specific MCT training session.
- **Before dispatch:** A failed preparation or cancellation closes the temporary current pin; `failAttempt` reports refusal and returns to idle/settled unless callback outcome is unknown (`NativeWorkshopLauncher.h:371-388, 504-562, 611-658`). `cancelPending` is nonblocking and only cancels preparation that has not dispatched (`NativeWorkshopLauncher.h:70-79`).
- **At and after dispatch:** The pin is committed before executor invocation. A returned callback yields `callbackReturned`; a thrown callback is treated as unknown and remains pinned/blocks future requests (`NativeWorkshopLauncher.h:611-686`). Scope-loss cancellation does not unload a dispatched map or release its package handles. Pins remain through normal completion and Return until launcher release/shutdown, with a 32-group cap (`NativeWorkshopLauncher.h:11-14, 50-55, 371-405`; `MyCareerTraining.cpp:926-944`). Thus the current Return path is not a package-handle restoration boundary.
- **Return from an external offline activity:** The UI binding identifies the external activity with the current bridge-session ID, empty fixture ID, and `abandon=false` (`NativeMatchLayout.h:687-701`). `bridge._action(return_hub)` accepts that exact external receipt, publishes `native_return_ready` with the same ID and empty fixture, and sets the app page to hub without saving an app-owned match (`bridge.py:1102-1132`). The native gate additionally requires a durable idle/clean bridge response and a new frontend handshake with the actual `RootMenuMovie` stack before marking arrival (`NativeReturnGate.h:84-130, 247-277`; `NativeMovieHost.cpp:968-981`). This proves a stock frontend return, not which Workshop map was loaded or that a prior map/lesson state was restored. Native host also blocks Workshop actions while Return is pending (`NativeMovieHost.cpp:566-573`).

## Requirements before a lesson can use a Workshop map

The current RLBot lesson setup is a separate built-in-map path. `adapter.match_config` rejects custom maps, chooses only its supported built-in arenas, uses Soccar with one ball and Normal Boost, and makes training unlimited-length/unlimited-score/overtime (`adapter.py:40-43, 88-112`). It appends the Human player last and returns that exact index (`adapter.py:54-92, 109-112`). `desired_state` applies a whole ball/car layout keyed by the supplied Human and bot indices (`adapter.py:167-203`); `game_worker` forwards engine `set_state` events to that writer (`game_worker.py:1307-1318`; `engine.py:671-684`).

The Power Shots scenario source fixes a standard Soccar coordinate frame, goal/back wall dimensions, car starts, ball origins/lanes, and targets; the scenario definition also names Human/bot roles and teams (`scenarios.py:20-76, 330-350`). There is no map-profile transform or Workshop-arrival guard in this path. Before a future Workshop lesson can send any `set_state`, it needs all of the following as verified runtime facts:

- exact selected entry asset and package identity, plus dependency/asset-role resolution;
- active map identity tied to that request, not merely `IsInGame` or callback return;
- geometry/coordinate frame and goal orientation, floor, walls, backboard, bounds, and lesson anchors compatible with the scenario, or an explicit transform;
- actual game mode and mutators (including gravity, boost, ball count/rules and kickoff/state-setting support);
- observed player layout with the intended Human slot/team, bot slots/teams, and actor loadouts/hitboxes;
- a controlled readiness check that target positions and success detectors match the active map before the first state write.

Until those checks exist, an unsupported Workshop map must stay outside lesson state setup. The exact expected geometry and physics profile cannot be filled in from the current exports; they must be verified per supported map.

## Future acceptance cases

1. Select one exact installed package and record its Workshop ID, entry asset, package digest, dependencies, and expected in-game map identity. A catalog alias with multiple installed packages must require an explicit package choice.
2. Make the command callback return while the active map remains unchanged, transitions to the wrong map, or lacks a dependency. The UI/bridge must not mark arrival or enable a lesson in any case.
3. For each admitted map, compare observed map identity, Soccar coordinate frame, goal/wall/floor/backboard geometry, and lesson anchors against a versioned map descriptor; reject or transform incompatible coordinates.
4. Observe actual mode, boost/gravity/mutators, ball count, Human slot/team, bot slots/teams, and hitboxes after arrival. Refuse `set_state` if any part differs from the lesson profile.
5. Exercise online, unowned, stale bridge, replay, in-game-at-selection, busy, wrong-build, nonce-change, and generation-change cases. Prove none dispatches the loader and that any pre-dispatch pin is released.
6. Exercise package disappearance/change during preparation and executor refusal/exception. Do not retry an uncertain post-dispatch outcome automatically; retain the package handle while the loader may still depend on it.
7. From an arrived map, Return should require the exact external activity binding, preserve unrelated career data, reach a fresh authored `RootMenuMovie`, and clear map/lesson-ready UI state. Verify package handles are released only at a safe, explicit lifecycle boundary.

## Evidence boundary

This is static source evidence only: no game launch, input, capture, network action, test run, or install edit was performed. These declarations and routes do not establish actual Workshop loading, map geometry, dependency completeness, mutator behavior, or a successful lesson on any custom map. The relevant older native-map manual observation in `map-01` is not request-bound evidence for this candidate path.

## Source hashes

SHA-256 of each inspected candidate source file; line references above apply to these exact bytes.

| Source | SHA-256 |
|---|---|
| `plugin/include/NativeCareerLayout.h` | `17D2EC0A82C79FAD1949715AD62840BCACE4177CBBE137DA3AA675289109EB78` |
| `plugin/src/MyCareerTraining.cpp` | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/include/WorkshopLoadPlan.h` | `d7266e99106d468699607a1b792d5185311e9715f2341dad8fb3e8860e66f7bf` |
| `plugin/include/NativeWorkshopLauncher.h` | `a8ce39f52c4d9c1aabc30aa6a70d7331d3ca87f71e1772939ad941f7952f6a32` |
| `plugin/include/NativeWorkshopDispatch.h` | `0e1429ce1b53bcc1f5bf6cc93d00d41b61285aaa0f12970e3947324301d254c6` |
| `plugin/include/NativeMatchLayout.h` | `a986f0ed827f11ef2716c8fc6bb196d55f822cc22c6b5316b0fde0bb278a8d53` |
| `plugin/include/NativeReturnGate.h` | `960e4042e1092dc1ad791ccbb8f1ccf800584f1c931a85ef71012ba8a385219d` |
| `plugin/src/NativeMovieHost.cpp` | `d336dc9958403791e7ba14779f29c719e45e6642a0644092934746e189a0a282` |
| `src/my_career_training/bridge.py` | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/workshop.py` | `4dea4b359f612389d6186c6fed640c2ee207bf92b4ad1bd6b4e4d56bfb9eb945` |
| `src/my_career_training/map_guard.py` | `b2e79d11639b9c29908ea9e5053d23fbf5eFDDAFF58D5CD03A125BE5FA4746A6` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/scenarios.py` | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
