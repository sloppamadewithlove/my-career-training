# NATIVE-TRAINING-FLOW-01 — stock lesson difficulty route

## Scope and export provenance

Static paraphrase of only the selected ActionScript exports under the private `TrainingMenu/scripts` tree: `menus/TrainingMenu.as`, `menus/DifficultyMenu.as`, `TrainingMenuScreen.as`, `tagame/api/Training.as`, `TrainingIconButton*.as`, `DifficultyMenuMovie.as`, `TrainingMenuMovie*.as`, and `tagame/constants/MenuName.as`. No other export classes were read. No raw source body is reproduced here.

The owning movie is the `TrainingMenu` `SwfMovie` payload (894,001 bytes, SHA-256 `a216ae0b061340bda02ccf713ddac556909f88e96213baf1c99d42bd5561fcc1`) from current package `GFX_TrainingMenu_SF.upk` (SHA-256 `BF9BAA4238D077F35F8041204EA4AEC8E9E7C9BB943D1E3DF2DA07DD07A57663`). The supplied export record identifies FFDec 26.4.0 and Temurin Java 21.0.9; its FFDec command returned success and wrote the selected ActionScript files. The enclosing helper did **not** issue a passing receipt: its inventory found 508 classes against a 500-class cap. The selected-file review below does not repair that receipt failure. A later exact-class export receipt would strengthen provenance. No game/runtime observation was made.

## Selected source identities

| Export | Bytes / SHA-256 | Classes or relevant members |
|---|---:|---|
| `menus/TrainingMenu.as` | 8,078 / `215CE7675FA7785AC68CA271482D6AAC82BB877C24E577783D4C675A4B59C273` | `menus.TrainingMenu`; `configUI`, `handleButtonClick`, `trainingPrivilegeSuccess`, `closeAllMenus` |
| `menus/DifficultyMenu.as` | 12,367 / `FC01BE9F86540EE67679B58B98A585E73CE809537EB5F3CF2A28ABD723563A7A` | `menus.DifficultyMenu`; `setTrainingMode`, `generateControls`, `refreshMenu`, `updateTitleLabel`, `playTutorial`, `playTraining`, `cleanUpMenus` |
| `TrainingMenuScreen.as` | 1,897 / `C96CD5F7004418D6164DE307164C30063A17CBE0A5D5185219A0662AF8A356BF` | `TrainingMenuScreen`; `handleAddedToStage`, `handleMenuStackChange` |
| `tagame/api/Training.as` | 10,998 / `EC806F97BCA48E655CC8E9500B5B8815DE50E3C8D0B4997504B7B0ECB9CD6AD2` | `Training`; `HasPerfectedTraining`, `PlayTutorial`, `PlayTraining` and related state accessors |
| `tagame/constants/MenuName.as` | 7,930 / `BC19F3699382C3BCBE447CF28862419E93C649130BBF59DCA12D2524FB9ED218` | `DIFFICULTY`, `TRAINING`, `TRAINING_NO_CUSTOM` constants |
| `DifficultyMenuMovie.as` | 286 / `5A0D19156C20D5ACF9A9894691A949D24FCFED5682509851BE421D69D4DF44F2` | Binds `DifficultyMenu` to embedded symbol 26 |
| `TrainingMenuMovie.as` | 278 / `AD02109C6C9117063661576F56F825428A7F08954A69EC671C7B586C090BA357` | Binds `TrainingMenu` to embedded symbol 20 |
| `TrainingMenuMovie_NoCustom.as` | 296 / `8B539FFC33FE22D1D42617E4585E7576AD097FEA5498A958337492A13BE1EB21` | Binds `TrainingMenu` to embedded symbol 19 |
| `TrainingIconButton.as` | 294 / `BD026D5587FF37A89C5D4D64CC86CF1A836093981CF0F95ED6E76A4E057ED1F5` | `MenuIconButton` subclass; symbol 15 |
| `TrainingIconButtonLabel.as` | 300 / `243DF4A3B8841FCF55857E5F7D57567B09794BBC1F15C31F605F0A82D4D738AA` | `SimpleLabel` subclass; symbol 14 |
| `TrainingIconButtonLabelWide.as` | 308 / `BDECFFB9D3869479CCFB6D0E59118768A97128004E41C7412B02587C447364A1` | `SimpleLabel` subclass; symbol 17 |
| `TrainingIconButtonWide.as` | 302 / `8C3D2CEB7FA4F6657FBF7B8ACC463462DE466653610C939DA09D2DA589DB1AD0` | `MenuIconButton` subclass; symbol 18 |

## Evidence-backed route

1. **Screen entry.** `TrainingMenuScreen.handleAddedToStage` opens the difficulty menu directly when screen data contains the `DifficultyMenu` submenu and a `trainingMode`, then passes that mode to `setTrainingMode` (`TrainingMenuScreen.as:21-27`). Otherwise it opens Map Selection when requested, or chooses the standard Training menu versus its no-custom variant based on `Features.TrainingEditor` (`:28-39`). The menu-name constants identify `DifficultyMenuMovie`, `TrainingMenuMovie`, and `TrainingMenuMovie_NoCustom` (`MenuName.as:44,178-180`).
2. **Lesson choice.** `TrainingMenu.configUI` localizes the Tutorial, Free Play, Goalie, Striker, Aerial, and optional Custom Training labels, and chooses an initial focus if none exists (`TrainingMenu.as:52-90`). Clicking Free Play opens Map Selection. Clicking Custom Training requests UGC privilege and then opens the separate Custom Training browser (`:147-149,183-192`).
3. **Difficulty gate.** For Tutorial, Goalie, Striker, or Aerial, `handleButtonClick` opens `DifficultyMenu` and supplies that mode when `Features.TrainingDifficulties` is enabled. With the feature disabled, it starts the legacy defaults directly: Basic Tutorial or the `Easy` training value (`TrainingMenu.as:131-181`).
4. **Difficulty rows.** `DifficultyMenu.generateControls` uses the `XPLevelMenuButtonMovie` symbol and a 240-pixel button width. Tutorial produces Basic and Advanced choices, passing `false` or `true` to `playTutorial`. Other modes produce Rookie, Pro, and All-Star labels mapped respectively to `Easy`, `Medium`, and `Hard` (`DifficultyMenu.as:30-40,96-142`). The screen title changes among Tutorial, Striker, Goalie, and Aerial difficulty titles (`:222-240`). For standard modes, focus is explicitly placed on Rookie (`:137-140`); active first-time-experience checkpoints can override focus to the Basic or Rookie button (`:198-220`).
5. **Native API dispatch.** `playTraining` passes the current built-in mode and selected stock difficulty to `Training.PlayTraining`; Tutorial uses `Training.PlayTutorial` (`DifficultyMenu.as:243-256`). `Training.as` forwards those to the `GFxData_Training_TA` object's `Training` methods through `UIShellHooks.SHELL_CallUnrealFunction` (`Training.as:268-275,304-311`). The row perfection badges query `Training.HasPerfectedTraining(mode, stockDifficulty)` (`DifficultyMenu.as:137-139`; API wrapper `Training.as:221-229`). Those calls prove the declared dispatch route, not successful runtime launch or the game-side meaning of every parameter.

## Focus, legends, and return behavior

The inspected classes use `currentFocus`, generated menu controls, and CLIK button click events. They do not declare a `ButtonLegend`, controller glyph mapping, or explicit `KEY_*`/`GP_*` navigation handler. `captureAllInput` is set when the menu is added to stage (`TrainingMenu.as:93-106`; `DifficultyMenu.as:164-182`), but the actual directional/controller input behavior is inherited from `UIMenu`/`DynamicMenu` or movie symbols not included in the selected export. The close button is non-focusable and only shown for the PC platform (`TrainingMenu.as:44-49`; `DifficultyMenu.as:70-82`).

Opening DifficultyMenu leaves the containing `TrainingMenuScreen` present; its stack-change listener closes the screen only when that screen has no menus left (`TrainingMenuScreen.as:40-55`). The selected code does not save a per-mode last difficulty or explicitly restore a focused lesson button after returning. `TrainingMenu` sets Free Play as a fallback focus only when focus is null; it also sets the Custom Training button when returning from that browser (`TrainingMenu.as:56-61,87-90`). Exact focus restoration after popping a child menu depends on inherited menu behavior and has not been proven from these files.

The movie wrappers establish class-to-symbol bindings but not the art, on-screen position, controller prompt, or timeline focus behavior. No claim about live screen appearance or input was tested.

## Relevance to a separate Bronze-to-SSL lesson menu

Stock architecture offers a useful **shape**: keep the lesson screen beneath a child selection screen, pass the selected mode in screen data, create a vertical set of localized choices, choose an initial focus, and launch through a central action method. Its actual values are only the legacy three training tiers (`Easy`/`Medium`/`Hard`) plus Basic/Advanced tutorial booleans. They are not the requested eight course levels and carry no evidence of equivalence to competitive ranks.

For My Career Training, the corresponding child screen should carry a stable lesson identity and one of the app’s own Bronze-through-Supersonic-Legend difficulty IDs. Preserve those as practice tiers in the app’s scenario/catalog contract; keep competitive MMR/rank data separate. Do not pass those labels to stock `Training.PlayTraining` unless a future validated game-side route explicitly supports them. The rank choice should resolve to the authored lesson/scenario setup, not silently become Rookie/Pro/All-Star. This preserves the stock menu-stack/focus pattern while keeping the requested curriculum semantics distinct.

## Limits

This report covers only the named exported classes. It does not inspect inherited `DynamicMenu`, `UIMenu`, `XPLevelMenuButton`, or host/native code, so it cannot establish controller focus traversal, back-button restoration, tier locks, or timeline layout. It does not establish runtime invocation, input, lesson completion, or timer/ball behavior. The FFDec per-command export succeeded, but the enclosing 508-versus-500 inventory cap prevented a passing helper receipt; a later exact-class receipt is still needed for stronger provenance.
