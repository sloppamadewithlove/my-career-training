# STOCK-TRAINING-PROGRESSION-01 — stock drill and pack progression

## Scope and source boundary

This report reuses already-selected ActionScript exports and the four requested campaign reports: `pack-01.md`, `native-pack-browser-01.md`, `custom-shot-flow-01.md`, and `hud-flow-01.md`. I also read `native-training-flow-01.md` for the stock built-in difficulty route. No new class export, game input, capture, launch, attachment, install change, or test was performed. The conclusions about built-in score and pass semantics are bounded by the selected UI/API wrappers; their native writer is not included.

## Built-in Aerial, Goalie, and Striker drills

The stock Training menu routes Aerial, Goalie, and Striker through one `DifficultyMenu` when the training-difficulties feature is enabled. It maps the visible Rookie/Pro/All-Star choices to native difficulty strings Easy/Medium/Hard, then calls `Training.PlayTraining(mode, difficulty)`. In the legacy branch it launches Easy directly. Tutorial is separate: Basic/Advanced pass Boolean values to `PlayTutorial` (`TrainingMenu.as:131–181`; `DifficultyMenu.as:96–140,243–256`; `Training.as:304–311`). These are stock difficulty labels and API arguments; they are not MCT’s Bronze–Supersonic Legend practice ranks.

The difficulty menu asks the host’s `HasPerfectedTraining(mode, difficulty)` Boolean for each of the three standard difficulty rows and displays a “perfect” icon when it returns true (`DifficultyMenu.as:137–139`; `Training.as:221–229`). The selected menu code does not define what earns that Boolean. `Training.as` also declares `HasCompletedTraining(mode, difficulty)`, but no consumer of that call appears in the selected Training menu/HUD sources. The separate `ETrainingType` declaration names None, Aerial, Goalie, and Striker; it supplies no scoring or completion rules (`ETrainingType.as:3–14`).

The Training DataAPI wrapper exposes integer `CurrentScore`, `CurrentRound`, and `TotalRounds`, plus the current mode and difficulty strings (`Training.as:27–54`). `TrainingView` labels the count as “Shot” and appends `/TotalRounds`. On the legacy HUD path the numeric field displays `CurrentScore`; when the V2 UI is enabled and per-shot rows exist it displays `CurrentRound` instead. The older bars use score/total and round/total; the pip view formats `CurrentScore / TotalRounds` as a percentage (`TrainingView.as:210–265,500–563`). These are display calculations, not a pass threshold. The selected source does not expose a per-round attempt counter, number of retries, allowed score range, or an equation for `HasPerfectedTraining`.

The HUD’s time label reads `GameEvent.TimeRemaining`; it animates/sounds at the last three seconds while game state is Active. That consumer does not start the clock, end a round, award score, or decide success (`TrainingView.as:571–615`; `hud-flow-01.md`). No selected source ties time expiry to a failed attempt or progress reset.

### Per-shot state and limits

`TrainingProgressPerShot` exposes a row count and integer `RoundNumber`/`Status` values; the row wrapper declares those as plain integers (`TrainingProgressPerShot.as:25–57`; `TrainingProgressPerShotRow.as:17–34`). The shot-selection renderer reads `Status` and applies a checkmark tint when the value is greater than 1 (`SelectShotButton.as:46–55,87–91`; `custom-shot-flow-01.md`). That is the consumer’s exact display predicate. Separately, `ETrainingRoundAttempt` declares candidate values named NotAttempted=0, Attempted=1, Completed=2, and Max=3 (`ETrainingRoundAttempt.as:3–12`). The row field has no typed reference to this enum, so those names do not prove the field’s meaning or the host’s assignment rules. The HUD itself checks whether progress rows exist but does not read their statuses (`TrainingView.as:250–266,511–520`).

No per-shot score, attempt-count, best-score, or personal-best field is exposed by these selected row declarations. A boolean perfected result exists at mode/difficulty level, but the score threshold and how any best is calculated are native-side unknowns. This is absence from the inspected UI/schema surface, not proof that no native save data stores such information.

The HUD offers conditional prompts for Reset/Randomize, Next/Previous, shot selection, Shuffle, and Mirroring only when the host capability calls say they can be used. It reads `bShufflePlay` to switch the displayed on/off icon. The prompt consumer does not implement the input effect or explain progress changes (`TrainingView.as:227–255,618–623`; `Training.as:75–90,191–218`). The `Training` wrapper declares `StartAtPlaylistIndex`, `ResetTrainingProgress`, and capability queries through native GFx calls, but their wrapper bodies do not define single-shot retry, progress reset, or persistence semantics. A ResetTraining HUD prompt is also changed to “Randomize Shot” when the host says randomization is available (`TrainingView.as:229–231`).

## Custom Training pack progression is a separate contract

The stock Custom Training browser and its shot selector are distinct from the built-in Rookie/Pro/All-Star drill menu. The stock browser launches a row through `TrainingModeRow.Play(MapName, bool)` and has separate favorite/history actions (`native-pack-browser-01.md`). The selector uses the current playlist index for highlight/selection and reads `TrainingProgressPerShot.Status` only for the checkmark tint (`custom-shot-flow-01.md`). Neither UI wrapper defines a score grade or a per-shot best score.

Psyonix’s official Season 7 article documents Custom Training pack progress saved in game save data, out-of-order completion, reset of started or completed pack progress from Pause, Next/Previous and Select Shot navigation, Shuffle Shots, and shot mirroring. It warns that mirroring may not work in future arenas whose shape or size prevents it. [Season 7 Custom Training changes](https://www.rocketleague.com/news/season-7-changes-coming-to-custom-training/). The article also says End Training shows pack progress. It does not establish whether shuffle includes already-completed shots, how long shuffle remains active, Select Shot status details, or the exact contents of that progress summary.

Those official progression details explicitly describe Custom Training packs. They do not specify how the built-in Aerial/Goalie/Striker drills count attempts or set their perfected thresholds. The 2016 official Custom Training introduction also describes Striker/Goalie and Rookie/Pro/All-Star as metadata for authored community sequences; it does not define built-in score rules. [Customize Your Training Soon](https://www.rocketleague.com/news/customize-your-training-soon).

| Question | Built-in Aerial / Goalie / Striker | Custom Training packs | MCT implication |
| --- | --- | --- | --- |
| Difficulty | Rookie/Pro/All-Star map to Easy/Medium/Hard; one Boolean perfect badge per mode/tier. | Pack authoring metadata includes Striker/Goalie and difficulty labels. | Keep MCT’s eight intended-practice ranks separate; no direct tier equivalence. |
| Counter | HUD receives CurrentScore, CurrentRound, TotalRounds. The displayed field varies by HUD capability. No attempt counter is exposed here. | Per-shot row has RoundNumber and Status integers; selector marks Status > 1. | Do not import stock score or the untyped status value as MCT completion. |
| Completion | HasPerfectedTraining/HasCompletedTraining are native wrapper calls; threshold and saved-state semantics are unknown. | Official docs say shots may be completed in any order and progress is saved per pack. | Keep MCT completion tied to its own existing scenario criteria. |
| Retry/reset | HUD prompt name and `ResetTrainingProgress` wrapper exist; exact single-shot retry and reset effects are not shown. | Official Pause reset clears progress for a started or completed pack; no official per-shot-best rule is stated. | Distinguish retrying an attempt from clearing accumulated situation completion. |
| Navigation | HUD exposes capability-gated controls; host effects are outside selected sources. | Season 7 documents Next/Previous/Select navigation, Shuffle Shots, and arena-dependent mirroring; exact shuffle inclusion/retention behavior is not established by the reviewed official source. | MCT order/mirror state can affect navigation, never the stable situation identity or its success criteria. |
| Best / perfect | A mode/difficulty perfect Boolean is displayed; no score threshold or per-shot best field is exposed. | Official progress material describes completion status and pack progress, not per-shot best scores. | If MCT adds a best, define its metric and key independently from completion. |

## MCT progression contract and current gap

The campaign direction requires 12 distinct situations for each lesson; all 12 are eventually required, remain selectable, and are adjusted by rank rather than replaced or locked. It states that rank names describe intended challenge, not a certified competitive rank. It also defines a free-practice path for repeating the mechanic without scenario progression (`TRAINING_WORKSHOP_DIRECTION.md:19–24,34–52`). Power Shots currently declares eight ranks and twelve stable scenario IDs (`scenarios.py:11–22`). Situation stepping retains the selected rank while moving through the current order, and shuffle validates a permutation containing every scenario (`scenario_setup.py:53–91`).

The persisted `lesson_scenarios` preference is currently only one `{scenario_id, difficulty}` selection per lesson; validation does not model per-rank/per-situation completion (`scenario_setup.py:13–39`; `storage.py:24–39`). Shuffle order, shuffle enablement, and mirrored state are runtime fields in the bridge, not saved progress. The save also has separate attempt and recording collections; those are not a completion matrix. A separate recording personal-best helper filters successful normal-speed local recordings and picks the shortest compatible duration (`recordings.py:145–201`); it is a whole-recording comparison, not a stock per-shot score or a 12-situation completion flag.

To meet the campaign’s progression contract without changing any lesson’s success rule, completion identity should be keyed by stable `lesson_id + rank_id + scenario_id` (and by a criteria/version identifier when those rules change), not current list position or shuffle order. Track selected/current situation separately from completed situations. A rank’s overall completion can be derived only from the twelve situation outcomes under that same rank; selecting or completing one rank must not imply completion at another. Keep practice repetitions out of progression. A personal-best metric, if wanted, is an additional value keyed to that same stable identity and does not replace the existing scenario result.

This report does not change or restate the shot success criteria. The native stock thresholds are not a basis for changing MCT’s authored lesson criteria, target/contact checks, or attempt lifecycle. The unresolved contract is persistence and presentation of MCT’s per-rank, 12-situation completion set; source reviewed here shows selection persistence, not that completion matrix.

## Remaining native dependency and acceptance boundary

The exact missing dependency for stock built-in thresholds, attempt counting, `HasCompletedTraining`/`HasPerfectedTraining` semantics, the `TrainingProgressPerShot.Status` writer, per-shot best storage, reset effects, and the native action effects for retry/next/shuffle/mirror is the game-side `GFxData_Training_TA.Training` implementation and its training-session/save-data writer. The selected ActionScript wrappers only dispatch calls to that host. Static exports and official pack documentation do not prove the current installed game’s runtime behavior. No claim that a built-in drill awards a particular score, fails after a particular attempt count, remembers a per-shot best, or persists shuffle/mirror across re-entry is made here.

## Selected-source fingerprints

| Selected source | Bytes | SHA-256 |
|---|---:|---|
| Training menu `menus/TrainingMenu.as` | 8,078 | `215ce7675fa7785ac68ca271482d6aac82bb877c24e577783d4c675a4b59c273` |
| Training menu `menus/DifficultyMenu.as` | 12,367 | `fc01be9f86540ee67679b58b98a585e73ce809537eb5f3cf2a28abd723563a7a` |
| Built-in/HUD `tagame/api/Training.as` | 10,998 | `ec806f97bca48e655cc8e9500b5b8815de50e3c8d0b4997504b7b0ecb9cd6ad2` |
| HUD `tagame/hud/TrainingView.as` | 30,691 | `95bb46f99e46b7bbe6e44d6fa641fd22058d4160a4f39180adee3c758fd60528` |
| HUD `tagame/api/ETrainingType.as` | 451 | `6da78ca2e89f132ad693455d4eec0f5aa8a0f49b384bb0a4bb626cb400eacbe3` |
| HUD `tagame/api/ETrainingRoundAttempt.as` | 468 | `3f9c89e78a7f7c4714b9ca209a9bcdfc9044b16850260fbb8c1d5e07892e8a8f` |
| HUD `tagame/api/TrainingProgressPerShot.as` | 2,152 | `39c776645771f570320d4b493a33a5d2358ffbcbc831e6c1982371ae9c34bbc6` |
| HUD `tagame/api/TrainingProgressPerShotRow.as` | 1,727 | `86ff42cb2837e032462a7bf5fa5ad733a873f3d707726beba3c8869b7e2be654` |
| Custom shot selector `menus/CustomTrainingSelectShotView.as` | 2,015 | `5f7c99a1a86afc8fb4e53c679fc4b6451e3684226c5580549963261913c797a5` |
| Custom shot selector `controls/SelectShotButton.as` | 4,326 | `27e9678a82f7ce51b1faa0c042fa2b5efb64fb25b1c264e4d66b38ef1dbabdaf` |
| Custom selector’s `tagame/api/Training.as` copy | 9,802 | `b7328796d817758bae712c556135c331b0cc86a37dd4a2b0bfab2de2482c2bea` |
| Direction doc | 11,875 | `555404a0141516b3e23b8d5be1d982006b1ff875d81cb8177a70193f6a3530cb` |
| MCT `training/scenarios.py` | 23,706 | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| MCT `training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| MCT `storage.py` | 8,410 | `3a291463f8ffdbab63adc4197a5b957413452aa011d4491895c722c151dd10de` |
| MCT `training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| Previously reviewed `custom-shot-flow-01.md` | 12,420 | `064e7c261c8e383833e694964c77716dbecc0b9b2bca3f84d4f4186d2e8da703` |
| Previously reviewed `hud-flow-01.md` | 16,328 | `7ef01c9fbbdddd582b643e181f4561a437fc2a38010d233501fea580ceb004fa` |
| Previously reviewed `native-training-flow-01.md` | 9,830 | `0cf2d18803bc721ed78507bd02f99379bd2010a51b3355c0320bddb31f557d79` |
| Previously reviewed `pack-01.md` | 11,001 | `d958e01c77b8de0733c7e58c9abad87ca93d40f11f389a83dc44751c8abac292` |
| Previously reviewed `native-pack-browser-01.md` | 14,307 | `b63f582bdfa06620c90a5dbe11d27c334ad4dc5d46c9c773a8c41ee1c11522a1` |
