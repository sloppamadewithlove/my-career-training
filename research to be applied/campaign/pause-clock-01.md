# PAUSE-CLOCK-01: MCT settings surfaces, pause observation, and worker flow

## Finding

“MCT Settings” can refer to two different source paths. In the default CMake configuration, `MCT_ENABLE_NATIVE_MOVIE_TRIAL` is **OFF** (`plugin/CMakeLists.txt:44–50`). The default MCT settings page is part of a full-screen BakkesMod/ImGui overlay opened by the career shortcut. The MCT code gates its input/menu handling while that overlay is visible, but does not call a pause API or send a pause command to the training worker. Source therefore supports input capture/gating as MCT behavior; whether Rocket League physics pauses when that overlay is opened is not established by source.

The authored `MctPauseMenu.as` belongs to the separate opt-in native movie trial. It extends `MidGameMenu`, and its header comment says the document screen owns pause, unpause, and input release (`native_ui/menus/MctPauseMenu.as:33–35`). The host classifies this surface only when Rocket League reports `IsPaused()` and the top menu is `MidGameMenuMovie` (`plugin/src/NativeMovieHost.cpp:237–270`). Its training settings panel is therefore inside an already-open game pause menu; the panel does not itself initiate that pause. The checked-out source does not establish which option was used for a particular compiled binary.

## Default ImGui overlay: open, input gate, and settings messages

- `mct_menu` and `mct_training` only operate when the native movie trial is off; they toggle/open `menuOpen_` and issue `openmenu mycareertraining` (`MyCareerTraining.cpp:208–220`). A separate shortcut path does the same toggle (`:621–624`). The Settings page is page 7 of the overlay menu (`CareerUI.cpp:142–148, 180–189`); its controls modify career and training-display preferences (`:611–665`).
- The settings page is rendered in the fallback menu branch only when `!MCT_ENABLE_NATIVE_MOVIE_TRIAL && menuOpen_` (`MyCareerTraining.cpp:1759–1775`). The `ShouldBlockInput()` override delegates to `MenuLifecycle::blocksInput`; in the default branch this is true only for a ready session with the menu visible and host window open (`:1745–1749`; `MenuLifecycle.h:47–49`). The plugin README describes this as preventing clicks from reaching underlying controls (`plugin/README.md:68–72`). This is menu input capture/gating, not a source-level physics pause. No `SetPaused`/pause call appears in these inspected paths.
- The training shortcut owner is gated separately: `scope.nativeMenuActive` includes `menuOpen_`, `ShouldBlockInput()`, probe/dialog state, and a pause-menu name; `TrainingLessonInput::lessonScope()` rejects that scope (`MyCareerTraining.cpp:1217–1228`; `TrainingLessonInput.h:154–164`). Thus opening the overlay releases MCT’s temporary lesson D-pad bindings. This does not send a pause command to RLBot or to `TrainingEngine`.
- Opening Settings itself sends no worker command. Changing a display preference does: `CareerUI` calls `command("training_settings", ...)`; the plugin forwards it through `bridge_->send()` (`CareerUI.cpp:655–665`; `MyCareerTraining.cpp:1725–1728`). The bridge persists the preference and, when a lesson worker is active, sends a `coaching` update (`bridge.py:1246–1255`). The worker updates `GhostPlayback` mode/speed/loop from that command (`game_worker.py:998–1003`). Explicit Watch/Lead pause is a separate `ghost_control` operation (`CareerUI.cpp:437–446`; `bridge.py:1256–1269`; `game_worker.py:1004–1033`). Neither settings visibility nor `training_settings` sends that pause operation.

The host snapshot polls actual game state (`IsInGame`, `IsPaused`, and top menu) independently of whether the ImGui window is open (`MyCareerTraining.cpp:1268–1285`). `MenuLifecycle` uses a real pause edge to show the fallback menu (`MenuLifecycle.h:20–45`); `MyCareerTraining.cpp` then opens the MCT window on that transition (`:1334–1358`). Consequently, the same MCT Settings page can be visible after either a direct shortcut while gameplay is active or an actual game-pause transition. Overlay visibility alone is not a reliable pause indicator.

## Actual pause and Resume path

The native movie host’s Pause surface requires both `IsPaused()` and top menu `MidGameMenuMovie` (`NativeMovieHost.cpp:237–270`). The authored pause menu is added to that document; its own settings rows use native menu controls and retain stock menu focus/navigation (`MctPauseMenu.as:33–35, 65–75, 131–199`). It is not an ImGui menu that asks the game to pause.

In the fallback ImGui path, `Resume Play` queues a local Resume request (`CareerUI.cpp:153–160`). If the runtime snapshot says the game is not paused, `advanceResume()` clears the request and closes the MCT menu without sending input. If a real native pause is still present, it verifies that the owned game process is foreground, sends one Escape down/up pair, then rechecks pause/menu state and reports an error if the pause did not close (`MyCareerTraining.cpp:1647–1677`). This is the only pause-related synthetic input found in the inspected MCT menu path, and it is tied to the explicit Resume action; it is not gameplay input or an automatic pause/resume loop.

## Worker and clock connection

The overlay does not tell `GameWorker` to suspend. For each RLBot packet that reaches it, the worker processes it and feeds the same packet `frame["time"]` to the engine, Watch/Lead playback, and Practice (`game_worker.py:1227–1269, 1340–1345`). Thus if the underlying game remains Active and `seconds_elapsed` advances, the attempt and ghost clocks continue; if the game actually pauses, the phase and clock behavior follow the telemetry rules in [TELEMETRY-01](telemetry-01.md). That report already covers cadence gaps, Active/non-Active handling, scenario interruption, game-clock timeouts, wall-clock recovery/ack deadlines, and the unresolved question of whether `seconds_elapsed` freezes in Paused/Replay. [GHOST-PLAYBACK-01](ghost-playback-01.md) covers game-time playback and clock rewind behavior. This report adds the menu-to-worker distinction and does not duplicate those clock algorithms.

One player-visible consequence is source-supported: an actual pause-menu edge is not equivalent to opening the ImGui Settings overlay. For Power Shots, a Paused phase interrupts the active scenario attempt; Ended has its own terminal path, as TELEMETRY-01 details. Overlay-open alone does not send either phase transition. The renderer’s settings/ghost controls can still send their explicit preference messages while shown. Whether packets continue at all during either screen and whether physics advances behind the fallback overlay must be observed in the exact owned game build.

## Remaining runtime questions and acceptance

- Is the deployed plugin built with `MCT_ENABLE_NATIVE_MOVIE_TRIAL`? The source default is OFF, but no compile artifact/configuration was identified for this inspection.
- With the default ImGui overlay opened during an active owned lesson, does Rocket League continue physics and `seconds_elapsed`, or does the BakkesMod host pause/suspend the match as a side effect of `openmenu`? Does `ShouldBlockInput()` block all relevant controller input or only UI clicks in the actual host?
- With the real pause menu open, does the worker continue receiving packets while `match_phase` is Paused, and does `seconds_elapsed` freeze? TELEMETRY-01 records the source behavior and this runtime question.
- Does the player expect “open settings” to suspend the current attempt? Current source does not make the fallback overlay a pause command. Acceptance should record both active-match shortcut opening and native Pause → Settings separately, including `IsPaused`, top menu, match phase, `seconds_elapsed`, input actions, active attempt state, visible timer, and ghost cursor before/during/after. Confirm Resume sends Escape only after explicit Resume, then verify one observed resume edge and no unintended retry or second ghost action.

No tests, builds, game interactions, or input actions were performed.

## Source state and fingerprints

The inspected candidate is based on `work/reviewed-training` commit `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`, but the working tree is not clean. Some relevant paths were modified or untracked at inspection, as marked below; hashes identify the exact bytes used for the line references.

| Source | SHA-256 |
|---|---|
| `plugin/CMakeLists.txt` (modified) | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| `plugin/README.md` | `2b7f06fd1e95b03cd0931634c8ea559d3b3deb1bcccb42042428c35a83c07cf3` |
| `plugin/include/MenuLifecycle.h` (modified) | `dfdf3bba4a91442e186818a69c6d1f03f8f61b203636949b6d105f678487af40` |
| `plugin/include/TrainingLessonInput.h` (untracked) | `6cfa4f039ce965d5c9df7d64938ef70b0926b9055951388c2f83395d376d45d5` |
| `plugin/src/MyCareerTraining.cpp` (modified) | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/src/CareerUI.cpp` (modified) | `35b9c68b6eaeea0c3a81ca12563508271a390ee407b85b2ec08199dc3603e29c` |
| `plugin/src/NativeMovieHost.cpp` (modified) | `d336dc9958403791e7ba14779f29c719e45e6642a0644092934746e189a0a282` |
| `native_ui/menus/MctPauseMenu.as` (modified) | `ac74a0e3020b3c40356bb75739bb03fbc70385ce277522441a48b8feee86edc2` |
| `src/my_career_training/bridge.py` (modified) | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/game_worker.py` (modified) | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/coach.py` | `0807fda8daf33ae67a9d1f31ccf93ecb10acccd21bb7efa3d9fb8a7fec905325` |

Cross-references: `work/campaign/telemetry-01.md`, `work/campaign/ghost-playback-01.md`, `work/campaign/hud-flow-01.md`, and `work/campaign/input-collisions-01.md`.
