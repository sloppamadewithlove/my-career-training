# HUD-FLOW-01: stock Training HUD behavior

## Artifact and scope

This report uses the 15 selected HUD AS classes and 13 exact dependency AS classes from the focused `GFX_Hud_SF` export. The package identity supplied for this export is 1,260,419 bytes, SHA-256 `1a6c92191333c5612711b84fa4570d4f088bc977feb7cad58f4ec4343d0e5a59`; the HUD movie is 1,145,308 bytes, SHA-256 `65535317cbc36b2added175b2ff3c817b9093a2ea83951e08d7349c15c1073ef`. FFDec completed successfully for both focused exports. The helper receipt is an inventory receipt; individual file hashes below pin the source files read here. These hashes identify this HUD movie's embedded copies; a same-named class in another movie can have different declarations. This is static decompiler evidence, not runtime proof.

## HUD fields and state flow

| Area | Confirmed in the selected source | Unknown from this export |
|---|---|---|
| Timer | `TrainingView` subscribes to changes in `GameEvent.TimeRemaining`, then reads the integer from the `GameEvent` DataAPI table (`TrainingView.as:154-184,571-615`; `GameEvent.as:43-46,379-382`). `TIME_SECONDS=0` and `TIME_MINUTES=1`; the HUD calls `getFormattedTime(value, 0, TIME_MINUTES, callback)`, which formats total minutes plus seconds, including leading zeroes (`DateTimeUtils.as:128-131,245-300`). The callback pads the minute component and joins the two fields with `:`; the display is `MM:SS`, with minutes allowed to exceed 59 (`TrainingView.as:605-615,654-674`). `DateTimeUtils` formats the magnitude and prefixes `-` for a negative value, so `-1` formats as `-00:01` (`DateTimeUtils.as:252-300`). If the formatted string ends in `1`, the HUD appends a nonbreaking space and applies letter spacing (`TrainingView.as:605-615`). | The HUD does not start, decrement, or poll this timer. The DataAPI writer, update cadence, and timeout cause are outside these classes. |
| Countdown and expiry display | For `TimeRemaining <= 3` while `GameState.ACTIVE` (`ACTIVE` is the literal string `ACTIVE`), the label animates; sounds play for values 3, 2, and 1 (`TrainingView.as:581-610`; `GameState.as:14`). Striker/aerial modes show the timer, goalie hides it; tutorial visibility follows `TimeRemaining >= 0` (`TrainingView.as:429-487,571-579`; `MatchType.as:20,24`). | There is no general expiry branch that resets the shot or hides a ball. Outside tutorial, the timer label remains enabled for striker/aerial even when a negative value is formatted. The host timeout behavior is outside these classes. |
| Shot and score | The stock `Training` DataAPI exposes `CurrentRound`, `CurrentScore`, and `TotalRounds` (`Training.as:27-45`). The HUD labels the count as Shot and appends `/TotalRounds`. The current numeric label displays score in the older path, but displays current round when V2 is available and progress rows exist (`TrainingView.as:210-221,511-527`). A round change animates the label/glow (`:529-552`). | Host rules that assign score or advance rounds are not present in the HUD consumer. |
| Progress | The older bars use score/total and round/total; the pip display receives the round and shows a percentage from `CurrentScore / TotalRounds` (`TrainingView.as:250-266,520-561`). V2 selection checks a host feature call plus whether per-shot rows exist (`:250-266,511-520`). The per-shot API exposes `RoundNumber` and a `Status` read as plain `int` (`TrainingProgressPerShot.as:25-57`; `TrainingProgressPerShotRow.as:17-34`). | `TrainingView` does not iterate per-shot rows or read their status; it checks row count. `ETrainingRoundAttempt` separately declares values named NotAttempted, Attempted, and Completed (`ETrainingRoundAttempt.as:3-12`), but no typed link in these files attaches that enum to the integer `Status` field. Those names are only a candidate interpretation, not confirmed status semantics. The writer and any status consumer remain unknown. |
| Training mode | The enum names None, Aerial, Goalie, and Striker (`ETrainingType.as:3-12`). While visible, the HUD registers callbacks for mode, totals, score, round, shuffle, randomize capability, and time (`TrainingView.as:154-206`). Mode changes select title/icon and timer visibility (`:429-487`). Match-type constants include Tutorial and Game Editor (`MatchType.as:20,24`); game state includes Active (`GameState.as:14`). | These branches describe stock training mode. They are not MCT Power Shots state. |

The `Training` wrapper declares host-call methods such as `StartAtPlaylistIndex`, `PlayTraining`, and `ResetTrainingProgress` (`Training.as:181-264`). This HUD does not call them in its time callback. `GameEvent.ForceStartPlay` is also a wrapper to the host (`GameEvent.as:678-683`), but the HUD does not call it. These are interface names, not proof of which native action starts a timer or finishes a shot. `EControlsVisibilityType` assigns Visible=0, Hidden=1, and Fadeout=2, matching the control-panel comparisons (`EControlsVisibilityType.as:6-10`).

## Prompts, visibility, and placement

The HUD builds a control panel from named actions. It offers `ResetTraining`, changing the instruction between Randomize Shot and Reset Shot according to `Training.bCanRandomizeShot`. Optional prompts cover editor testing, previous/next shot, shot selection, shuffle, and mirroring (`TrainingView.as:210-365,627-640`). Each prompt resolves a key with `Shell.GetKeyForAction`; missing bindings hide that prompt, and valid bindings are formatted into localized instruction text (`:316-365`). The separate `TrainingUseActions` table API exposes action names and localized names (`TrainingUseActions.as:25-62`; `TrainingUseActionsRow.as:17-49`), but `TrainingView` does not import or read it; its prompt list is built from explicit action IDs.

The prompt binding route is: `TrainingView` calls `tagame.api.Shell.GetKeyForAction(action, isGamepad)` (`TrainingView.as:316-365,642-652`; `Shell.as:351-356`). The wrapper calls native `GFxShell_TA.Shell.GetKeyForAction`. Its boolean is derived from `ShellAPI.inputType != InputTypes.PC`; the input types identify PC, 360, PS3, PS4, XB1, NX, and NX single-controller modes (`TrainingView.as:316-329,642-648`; `ShellAPI.as:49-68`; `InputTypes.as:3-18`). `ControlBindingsManager` has a separate resolver that reads each binding row's `UIKey` or `UIAxisKey` (`ControlBindingsManager.as:51-70`), but `TrainingView` does not call it for the displayed prompt. `SystemIconManager` converts controller markup such as GP_A/GP_B into gamepad image resources and selects platform suffix sets from the current input type; it subscribes to `InteractionManager` input-type changes (`SystemIconManager.as:55-66,79-128,144-226,352-435`).

Input-type updates flow from the `UIShellHooks.SHELL_onInputTypeChanged` callback into `ShellAPI`, then to the handler installed by `InteractionManager`; the manager updates PC/controller interaction mode and dispatches `InteractionEvent.INPUT_TYPE_CHANGED`, which `TrainingView` and `SystemIconManager` consume (`ShellAPI.as:12-16,82-87`; `InteractionManager.as:132-170,360-372`; `TrainingView.as:154-184,642-652`). Single-controller mode uses a combined left/right-trigger glyph for ResetTraining (`TrainingView.as:642-648`).

Rebinding has a qualified path, not a fully established refresh guarantee. `TrainingView` listens for PC/gamepad binding-update events and refreshes prompt text when it receives them (`TrainingView.as:181-183,685-688`). `ControlBindingsManager` builds action-to-row maps from PC/gamepad binding tables and dispatches those events only when a table's row count changes (`ControlBindingsManager.as:28-39,51-89`). Its recording-complete callback dispatches `BINDING_COMPLETE`, not either update event (`:161-165`), and `TrainingView` does not listen for `BINDING_COMPLETE`. Therefore these sources do not prove that editing an existing binding with unchanged row count refreshes the prompt. Input-type changes and shot-menu close trigger full prompt refreshes; menu-stack change refreshes only if the ResetTraining binding string changed (`TrainingView.as:311-316,642-688`).

When the view becomes visible, it registers data/input listeners and refreshes the mode, round, time, and controls; hiding/removing it unregisters callbacks (`TrainingView.as:154-206,367-389`). A mode change fades the view in (`:429-488`). The controls panel is placed at local `(10,104)`; its background is adjusted for stage width, safe-zone percentage, and content scale (`:268-273,391-397`). `Training.ControlsVisibility` can hide the panel or start a five-second one-shot timer followed by a two-second fade. The midgame menu also hides the panel and restores its configured state on close (`:118,690-727`). That local timer controls only the prompt panel.

`TrainingViewMovie` and `_v2` are thin embedded-symbol subclasses of the same `TrainingView`; the selected shot, total, time, and score label classes are thin `SimpleLabel` symbol wrappers (`TrainingViewMovie.as:6-12`; `TrainingViewMovie_v2.as:6-12`; label wrappers `:3-12`). The ActionScript sets control-panel/background geometry but does not set the main labels' screen coordinates. Their placement is timeline-defined; this source alone does not prove top-left anchoring.

The parent coordinate system is described by `UIView` and `UIScreen`. A root UIView sets stage alignment to top-left and scale mode to no-scale, initializes interaction/icon managers, and installs resize handling (`UIView.as:140-166`). `UIScreen` exposes safe-zone percent and computes `ContentScale = max(stageScaleFactor × UIScale × safeZonePercent × scaleModifier, 0.5)`; the safe-zone inset is half the unused width/height, with a separate ultra-wide centering branch. In an active game/GFx stage it adjusts stage offset/scale, while a non-game path adjusts the screen object (`UIScreen.as:67,123-136,202-254`). This bounds the coordinate transform but does not expose the active HUD movie's timeline layout or prove the runtime parent chain.

## Ball lifecycle and MCT separation

None of the 28 inspected classes imports a ball API or requests ball visibility, fade, spawn, teleport, or reset. The timer callback updates a label; timer expiry is not evidence of ball disappearance. The timeout/shot transition and ball-visibility writer must be traced on the native training host side.

The stock HUD reads Rocket League `Training` and `GameEvent` DataAPI fields. MCT Power Shots are started with an app-owned scenario ID/difficulty request and run through the app's game worker/TrainingEngine path (`src/my_career_training/bridge.py:1729-1792`; `src/my_career_training/game_worker.py:446-453,694-742`); worker telemetry is emitted from its own frame data (`game_worker.py:1345-1357`). These are separate state sources. This HUD export does not map `CurrentRound`, `CurrentScore`, `TimeRemaining`, or `TrainingProgressPerShot.Status` into MCT attempt or RLBot telemetry state.

**Integration contract.** In MCT practice, use fresh app-owned session/scenario identity and worker telemetry as the authority for MCT shot, attempt, and car/ball state. Treat native `Training`/`GameEvent` tables as stock-mode display inputs; do not translate their timer or integer per-shot status into MCT timeout/completion, and do not infer ball hide/fade from a native HUD label. Any native comparison needs a documented adapter that checks session/mode identity and an explicit mapping validated against the native writer and lifecycle. The optional `native_hud` capability flag is not evidence that stock training tables are populated by an MCT worker.

## Remaining dependencies and bounded follow-up

- For the native timer/state writer: `projectx.api.DataAPI`, `projectx.proxy.UIShellHooks`, and the native GFx writers named by the wrappers, `GFxData_Training_TA` and `GFxData_GameEvent_TA`, followed by the narrow training-mode timeout/shot transition and ball visibility/fade owner.
- For complete binding refresh semantics: `tagame.api.ControlsPCBindings`/`ControlsPCBindingsRow`, `ControlsGamepadBindings`/`ControlsGamepadBindingsRow`, `Controls`, `tagame.api.EAxisSign`, `GameUtils`, and the `GFxShell_TA.Shell` hook (imports/call targets of the inspected manager and Shell wrapper). Their write/callback behavior is not established here.
- For visual anchoring: timeline data for `TrainingViewMovie` and `_v2`, plus an owned runtime view if the question is actual on-screen position. `UIView`/`UIScreen` establish the transform, not the label coordinates.
- For per-shot status semantics: a focused consumer/writer of `TrainingProgressPerShot.Status`; no consumer is identified by these 28 classes, and the similarly named enum has no typed link to the field.
- For controller artwork: the `GamepadIcon_*` and PC icon resources named in `SystemIconManager`; mapping is source-supported, actual art/render is not checked here.

## Selected-file fingerprints

| AS file | SHA-256 |
|---|---|
| `tagame/hud/TrainingView.as` | `95BB46F99E46B7BBE6E44D6FA641FD22058D4160A4F39180ADEE3C758FD60528` |
| `tagame/api/Training.as` | `EC806F97BCA48E655CC8E9500B5B8815DE50E3C8D0B4997504B7B0ECB9CD6AD2` |
| `tagame/api/GameEvent.as` | `E8224A8D8690BCFFC4E250C5233275E50C85F78B53FD8D5290031CF571E2DDDE` |
| `tagame/api/TrainingUseActions.as` | `98C07EA662D85159C5C4F2DF0B4F811840A03A16BCF0B473602E35615F733BEE` |
| `tagame/api/TrainingUseActionsRow.as` | `B9A9B44CB562B6708FF048377F99761C96191BB344AC4AE98ECEA1F1CC6AB411` |
| `tagame/api/ETrainingRoundAttempt.as` | `3F9C89E78A7F7C4714B9CA209A9BCDFC9044B16850260FBB8C1D5E07892E8A8F` |
| `tagame/api/ETrainingType.as` | `6DA78CA2E89F132AD693455D4EEC0F5AA8A0F49B384BB0A4BB626CB400EACBE3` |
| `tagame/api/TrainingProgressPerShot.as` | `39C776645771F570320D4B493A33A5D2358FFBCBC831E6C1982371AE9C34BBC6` |
| `tagame/api/TrainingProgressPerShotRow.as` | `86FF42CB2837E032462A7BF5FA5AD733A873F3D707726BEBA3C8869B7E2BE654` |
| `TrainingViewMovie.as` | `30D2104FCC8390E5A15FF144613DE2B2EB0A43B9ADD215B1217640DCDB221A29` |
| `TrainingViewMovie_v2.as` | `5D35F2C38037AC4AE3C0904E85E350ED670F1E4C6B00443C80AAECC19CF9EF5B` |
| `TrainingTimeLabel_v2.as` | `5126CD1EE46260F7EFF4869CE715DFA18DCD10F6DA91D18868A442D194F276F7` |
| `TrainingScoreLabel_v2.as` | `EE1E77C228698F85ECC0482E9A6FB2BF521DC2AA7CF27D1ECCCE8B11C093D842` |
| `TrainingShotLabel.as` | `AB90BCDAFEC2C019605A900F8A3EBDCFFF5D1D6B3FFE7AA1C6BBAAA8F1A050DA` |
| `TrainingShotTotalLabel.as` | `855D2BF5B6D96AC1334682E7D8DA7B94CAE7B7D3D8158843C78F8FD4A9AF3062` |

### Dependency classes

| Dependency AS file | SHA-256 |
|---|---|
| `projectx/utils/DateTimeUtils.as` | `0DFE33DAC2A4D7A3C438536E6848BC3839883E9B43EE67975D24E69E724A1028` |
| `tagame/constants/GameState.as` | `02416B25588042DEF2B9B7B7F8D66DC29CCEFAF03066416BB8D42FDBE6B22103` |
| `tagame/constants/MatchType.as` | `843B9F6E1F8FA2CF61458E40440A91DD8BB776E5F90C0ED65AFE77184B9C89E0` |
| `tagame/api/EControlsVisibilityType.as` | `8B5B7BEF8FCEBFC82A887250D535F270446DABEF1706CE14990C6909800E572A` |
| `tagame/api/Shell.as` | `B542AD5CC406290FF85CB2C556DA7A448BA50CDA11A70C34B77449AA4BF4EFF6` |
| `projectx/api/ShellAPI.as` | `7FAF82CDA315FFF00825CF3A63B8345E419AAE8EEF6D9AD2F4C086F3EB014C9A` |
| `projectx/api/InputTypes.as` | `0EE9C21E6C63688E2E388D80D96698E5E4FE01ED71CB780804C0A2903133B747` |
| `projectx/managers/SystemIconManager.as` | `384E8CDF3B6C309DFADAB4BE245C80BAE7D6EAFA8E1D148FC17BB7734EFBDE39` |
| `projectx/managers/InteractionManager.as` | `0353BF514D1AFCE294EF426F4DCD9F2DDEFB2FB1D7EB5DFE0CB644DCB9BCBBBD` |
| `tagame/managers/ControlBindingsManager.as` | `1D42C5179ABE61F00B3A08B60046F4E317361F780E56871D49CFB9D359782C63` |
| `tagame/events/ControlBindingEvent.as` | `D50DC4AA543E175457A0B23A91BAF173969BF4677410BA65B5B6DB70121D1BF1` |
| `projectx/core/UIView.as` | `A2FE593A1C68F0DD90DAF97146083E1AA1F7AE845908E8DC692E970AB18CED50` |
| `projectx/core/UIScreen.as` | `9E26E1599DB761F62C018AA16E73F8DC21195A85557CABFCBE01D4755CF556AB` |

Static evidence only; no game state, ball behavior, or runtime HUD placement was exercised.

The [sanitized HUD receipt](../evidence/hud-inventory-01.json) records the initial inventory and both focused source batches (fifteen plus thirteen files), including their individual hashes. Raw assets and decompiled source remain private.
