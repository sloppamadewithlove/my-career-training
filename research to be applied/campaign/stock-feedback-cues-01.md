# STOCK-FEEDBACK-CUES-01 — training feedback and audio boundary

## Scope

This is a static comparison of the already-selected stock Training HUD/menu exports and frozen MCT source. It adds no class exports and does not inspect or extract audio/art assets. It does not use game input, launch or attach to the game, alter installation/settings, or run tests. The conclusions distinguish a source-level call from a rendered frame or audible result.

The prior [HUD flow report](hud-flow-01.md) records the movie/package identity and HUD data boundary. The [stock progression report](stock-training-progression-01.md) already covers the built-in drill counters, perfect badge, and the difference between built-in drill progression and Custom Training pack progression. This report narrows its question to feedback cues and visible transitions.

## Stock Training HUD: calls and visible changes

Selected source: `tagame.hud.TrainingView`, especially `onCurrentRoundChanged`, `onTimeRemainingChanged`, `onShufflePlayChanged`, and `onShotRandomized`.

| Event path in selected source | Cue identifier passed to an API | Visible change in the same handler | What this establishes |
|---|---|---|---|
| Cached `Training.CurrentRound` differs in `onCurrentRoundChanged` (`TrainingView.as:529–568`) | `MainMenuSounds.BASIC_NEXTTAB` (`:550`) | Glow and number scale/color tween; round progress bar or pip/percent and displayed count update (`:533–568`). | The handler requests this named cue for a round-value mismatch. It is not labeled a success cue. `onTotalRoundsChanged` calls this handler too (`:500–509`), so the source does not limit the call to a scored completion transition. |
| Time-remaining callback while `GameState.ACTIVE` and remaining integer is 3, 2, or 1 (`:571–615`) | `TutorialSounds.COUNTDOWN` via `SoundAPI.playSound` (`:593–603`) | Timer label pulses in color/scale and updates its formatted text (`:581–615`). | The method calls the API for those observed values. It has no visible once-only latch and contains no zero-second call; callback frequency and audible playback are unverified. |
| `Training.bShufflePlay` change callback (`:618–625`) | `MainMenuSounds.BASIC_SELECT` (`:624`) | On/off shuffle clips tween their alpha (`:621–623`). | The callback has a named cue request tied to the state-update handler, not a claim about whether the state change was accepted by the native host. |
| Host callback `Training.OnShotRandomized` (`:727–730`) | `TutorialSounds.TRAINING_RANDOMIZE` (`:729`) | No additional visual transition is implemented in this callback. | The callback requests the named cue if the host invokes it; the selected code does not establish that randomization succeeded. |

`handleAddedToStage` loads `TutorialSounds` and `handleRemovedFromStage` unloads it (`TrainingView.as:367–378`). The selected exports do not include the `TutorialSounds`, `MainMenuSounds`, or `SoundAPI` implementations or their asset mapping. The cue names therefore identify call arguments, not decoded clips, playback duration, mix level, or proof of audible output.

The HUD also builds prompts for reset/randomize and capability-gated previous/next, shot selection, shuffle, and mirror controls (`TrainingView.as:227–255`). The selected leaf class shows no explicit focus, confirm, back, or reset sound call. A shared menu/input base class may handle some of those interactions; that base behavior is outside the selected export set. The stock difficulty menu conditionally shows a `perfect` icon from `Training.HasPerfectedTraining` (`DifficultyMenu.as:137–139`), but its selected source contains no corresponding attempt-result cue or threshold logic.

No distinct training-attempt success/failure dialog class appears among the selected HUD/menu exports. This is a boundary on the inspected exports, not proof that no other movie or native game layer presents one. `TrainingView` presents counters/progress and state animation; those surfaces do not by themselves establish the host's success/failure decision. See the stock progression report for the limits of `CurrentScore`, `CurrentRound`, `TotalRounds`, and the `HasPerfectedTraining` Boolean.

## Frozen MCT feedback path

The frozen MCT Power Shots model translates existing coaching/session fields into text-facing HUD fields: scenario index/total, title/rank, phase, timer, pre-active `SETTLE`/`READY`, instruction/interruption, shuffle/mirror and optional timing (`TrainingLessonInput.h:320–420`). The native card renders those values and a reset-binding prompt as an ImGui overlay with `ImGuiWindowFlags_NoInputs` (`CareerUI.cpp:700–756`). Separately, the detail panel displays a textual `LATEST ATTEMPT` feedback/outcome value when present (`CareerUI.cpp:399–400`).

A targeted search of the frozen plugin/native UI sources found no sound-playback API invocation. The current feedback path is textual/visual. In particular, MCT's `finished` phase label is phase text; it should not be treated as a success cue, and an interruption message is not a failure result. No MCT success/fail audio event or user audio-setting route is established by these source files.

## Public SDK boundary and safe integration implication

The frozen build pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` and archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` (`plugin/CMakeLists.txt:26–29`). A bounded search of that pinned header tree for `sound`/`audio` finds vehicle audio-parameter initialization, world audio time, camera audio-fade controls, and an engine-audio cosmetic slot. It finds no general menu/game sound-play function in this public declaration set. These lower-level audio declarations do not provide a demonstrated cue adapter. This is a public-header boundary, not proof that no private or newer host API exists.

For MCT, the minimum safe next step is to keep the existing visible/text status path and require a verified, supported playback interface before adding any audible cue. If such an interface is later identified, map semantic state transitions (focus, confirm, back, reset, ready/countdown, success, fail, interruption) to cues once per genuine transition, retain textual state for silence/accessibility, and do not change game sound-volume or mute settings. Do not attach success/fail meaning to the stock `BASIC_NEXTTAB`, `BASIC_SELECT`, `COUNTDOWN`, or `TRAINING_RANDOMIZE` identifiers. Runtime verification would still be needed before claiming audible output or compatibility with player sound settings.

Useful future acceptance checks are: focus/confirm/back/reset do not fire twice for one action; countdown dispatch matches the chosen ready-state policy and does not retrigger on repeated state polls; success, failure, interruption, and retry each retain distinct visible text; cue playback respects existing mute/volume settings without writing them; and all essential state remains understandable when cues are silent. These are proposed checks, not tests run here.

## Selected source fingerprints

| Source | Bytes | SHA-256 |
|---|---:|---|
| Prior HUD flow report | 16,328 | `7ef01c9fbbdddd582b643e181f4561a437fc2a38010d233501fea580ceb004fa` |
| Prior stock progression report | 14,719 | `4579d0e234907dfa74a3a64917be111a75a6c8252e0e1913a5be1e4ebdf6cb35` |
| Stock HUD `TrainingView.as` | 30,691 | `95bb46f99e46b7bbe6e44d6fa641fd22058d4160a4f39180adee3c758fd60528` |
| Stock menu `DifficultyMenu.as` | 12,367 | `fc01be9f86540ee67679b58b98a585e73ce809537eb5f3cf2a28abd723563a7a` |
| Frozen MCT `plugin/include/TrainingLessonInput.h` | 20,415 | `6cfa4f039ce965d5c9df7d64938ef70b0926b9055951388c2f83395d376d45d5` |
| Frozen MCT `plugin/src/CareerUI.cpp` | 46,493 | `35b9c68b6eaeea0c3a81ca12563508271a390ee407b85b2ec08199dc3603e29c` |
| Frozen MCT `plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| Pinned SDK `GameObject/BaseCameraWrapper.h` | 3,923 | `f2be0e1354758b45d96dfd0966e4fa60aa0ad9a05745e563175b51e71049449a` |
| Pinned SDK `GameObject/VehicleWrapper.h` | 3,578 | `19feb5afafcce50b4ccfee169655a95a06131ae7a554ec64803ccfb5e94c9a72` |
| Pinned SDK `Engine/WorldInfoWrapper.h` | 750 | `942a0a4936c727f6a1268f7ee1881942e1e36580de15ce71f9663d85b08fcd46` |
