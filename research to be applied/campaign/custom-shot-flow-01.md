# CUSTOM-SHOT-FLOW-01 — stock custom training shot selector

## Scope and evidence identity

This is a static read of 12 selected ActionScript exports from the stock `CustomTrainingSelectShotMenu` movie: the original four plus focused follow-up batches of two, five and one class. It does not establish what a running game displays or how input behaves at runtime.

The inspected movie is 871,352 bytes, SHA-256 `5c8507cf9b0543ce778d8c71854c9e88d6b96aceaa9f762e050138427e2280d7`; its package is SHA-256 `ce5407b03ed248171493575532c29dab47fbeed09e2adef842deb35b4409b567`. The four source exports and hashes are:

| Export | Bytes | SHA-256 |
| --- | ---: | --- |
| `menus/CustomTrainingSelectShotMenu.as` | 1,517 | `690abf24f75dea8115d0dc546d0648cf731733ee457d18c436b677fe9a5e4789` |
| `CustomTrainingSelectShotMenuScreen.as` | 2,582 | `cdf14698c470ff7f943d2c6a1530de217ef2a1226248ac61e2427558650ec068` |
| `tagame/api/Training.as` | 9,802 | `b7328796d817758bae712c556135c331b0cc86a37dd4a2b0bfab2de2482c2bea` |
| `tagame/constants/MenuName.as` | 7,666 | `1830f29e84c6700d6fe7ebcc2abc4e30fdecaa0e71a2374b283da0b3cb570120` |

The missing view was then exported directly with the pinned FFDec CLI using a `-dumpAS3` inventory followed by a separate `-selectclass ... -export script` command from the same verified movie. This was a read-only CLI export, not a modified helper run. Only these two selected exports were read:

| Follow-up export | Bytes | SHA-256 |
| --- | ---: | --- |
| `menus/CustomTrainingSelectShotView.as` | 2,015 | `5f7c99a1a86afc8fb4e53c679fc4b6451e3684226c5580549963261913c797a5` |
| `CustomTrainingSelectShotViewMovie.as` | 341 | `18b224a5af5a33acf3578a2f74607f4ce149356c90aa36d977c81793f5ae0c89` |

A second direct FFDec CLI selection (`-selectclass ... -export script`) added exactly five row/list classes after inventory confirmed their names. This was read-only; no other private exports were opened:

| Follow-up export | Bytes | SHA-256 |
| --- | ---: | --- |
| `tagame/api/TrainingProgressPerShot.as` | 2,152 | `39c776645771f570320d4b493a33a5d2358ffbcbc831e6c1982371ae9c34bbc6` |
| `tagame/api/TrainingProgressPerShotRow.as` | 1,727 | `86ff42cb2837e032462a7bf5fa5ad733a873f3d707726beba3c8869b7e2be654` |
| `tagame/controls/ModalScrollingList.as` | 1,234 | `f6d6cea2703be29a81956f2aed96037a457df3468877020c7462f2b8f6072107` |
| `controls/SelectShotButton.as` | 4,326 | `27e9678a82f7ce51b1faa0c042fa2b5efb64fb25b1c264e4d66b38ef1dbabdaf` |
| `SelectShotButtonMovie.as` | 296 | `8e92cff0140cc61a0c5a8554a8dde0dcdf1014196b75c31cc5a8f619d9f8fec8` |

A final direct FFDec CLI selection exported one enum-like class after a separate `-dumpAS3` inventory and separate `-selectclass ... -export script` command. Its constants are reported below as candidate values only because the selected status-row declarations do not reference this class:

| Follow-up export | Bytes | SHA-256 |
| --- | ---: | --- |
| `tagame/api/ETrainingRoundAttempt.as` | 468 | `3f9c89e78a7f7c4714b9ca209a9bcdfc9044b16850260fbb8c1d5e07892e8a8f` |

## What these exports establish

- **Focus, Back and confirm boundary:** `menus.CustomTrainingSelectShotMenu.handleAddedToStage` gives focus to `selectShotView.scrollList` (lines 26–30). Its `handleInput` first lets `UIMenu` process the event; if still unprevented, `GAMEPAD_BACK` and `GAMEPAD_B` are marked handled on either event edge, while `Training.OnOpenShotSelectionMenu()` is called only on `KEY_UP` (lines 32–50). The view sets `captureAllInput` true on stage entry and false on removal (`CustomTrainingSelectShotView.handleAddedToStage/handleRemovedFromStage`, lines 48–58; SHA-256 `5f7c99a1a86afc8fb4e53c679fc4b6451e3684226c5580549963261913c797a5`). When the row is selected/hovered on non-PC input, its renderer reveals a `GAMEPAD_A` icon prompt; its action dispatch runs when the inherited state is `down`. The specific input-to-state mapping is inherited and not established by these exports (`controls.SelectShotButton.configUI/handleInputTypeChanged`, lines 39–44 and 93–109; SHA-256 `27e9678a82f7ce51b1faa0c042fa2b5efb64fb25b1c264e4d66b38ef1dbabdaf`). The Back callback's destination and binding are not shown.
- **Controller/game-input suppression:** `CustomTrainingSelectShotMenuScreen.handleAddedToStage` disables shuffle, mirror, next/previous shot, throttle forward/reverse, boost and jump, then registers a game-state callback (lines 21–33). Removal sets all eight actions enabled, unregisters, and dispatches the custom-training-close event (lines 35–48). The source sets them back to `true`; it does not show restoration of each action's prior value. If the game enters replay playback while this screen is open, the callback invokes the same `OnOpenShotSelectionMenu` hook (lines 50–60).
- **Available progress/selection data:** `tagame.api.Training` exposes `CurrentScore`, `CurrentRound`, `TotalRounds` and `CurrentPlaylistIndex` as DataAPI reads from the `Training` table, row 0 (lines 29–45 and 83–87). The view uses `CurrentPlaylistIndex` as its selected list index. The renderer separately reads per-shot `Status` for its checkmark; `CurrentRound`, `TotalRounds` and `CurrentScore` are not read by the view or renderer, so they do not establish the row progress display.
- **List count and displayed row label:** `menus.CustomTrainingSelectShotView.configUI` sets `N` to `TrainingProgressPerShot.getRowCount()`, builds the data provider from integers `0` through `N-1`, and assigns it to the scroll list (lines 25–43; SHA-256 `5f7c99a1a86afc8fb4e53c679fc4b6451e3684226c5580549963261913c797a5`). `TrainingProgressPerShot.getRowCount()` reads the `TrainingProgressPerShot` table row count (lines 20–38; SHA-256 `39c776645771f570320d4b493a33a5d2358ffbcbc831e6c1982371ae9c34bbc6`). Each renderer labels its integer data as localized, uppercased “Shot” plus `data + 1`, so list index `0` is presented as `SHOT 1`, index `N-1` as `SHOT N` (`controls.SelectShotButton.s_shot/setData`, lines 18 and 46–55; SHA-256 `27e9678a82f7ce51b1faa0c042fa2b5efb64fb25b1c264e4d66b38ef1dbabdaf`). No separate “current of total” text is formed in these classes; runtime `N` depends on the table.
- **Current highlight and per-shot progress mark:** The view sets `scrollList.selectedIndex` directly to `Training.CurrentPlaylistIndex` (lines 44–45; view hash above), with no offset. The renderer separately reads `TrainingProgressPerShot.GetStatus(rowIndex)` and chooses the checkmark's highlight color transform when that integer is `> 1` (`SelectShotButton.setData/setSelected`, lines 46–55 and 87–91; button hash above). This checkmark tint is separate from the list's current highlighted index. The API reads `Status` and `RoundNumber` from the same table (lines 40–48; API hash above); the row wrapper exposes both as integers (lines 17–25; SHA-256 `86ff42cb2837e032462a7bf5fa5ad733a873f3d707726beba3c8869b7e2be654`). The renderer does not use `RoundNumber`. The inspected classes establish the exact checkmark predicate but not the semantic mapping of the status integers.
- **Candidate status names, not a proven field enum:** `tagame.api.ETrainingRoundAttempt` declares `NOTATTEMPTED=0`, `ATTEMPTED=1`, `COMPLETED=2`, and `MAX=3` (lines 3–12; SHA-256 `3f9c89e78a7f7c4714b9ca209a9bcdfc9044b16850260fbb8c1d5e07892e8a8f`). However, `TrainingProgressPerShotRow.Status` is declared and returned as plain `int` (lines 22–24; row hash above); neither that row wrapper nor `TrainingProgressPerShot.GetStatus` refers to `ETrainingRoundAttempt`. So an association is not proven by the selected source. If the table uses the same numeric convention, `COMPLETED=2` passes the renderer's `>1` check; `MAX=3` also passes numerically, but its declaration alone does not establish it as a per-shot status.
- **Confirm and index translation:** The renderer receives provider data `i` in `[0,N-1]`; when its inherited list-item state becomes `down`, it calls `Training.StartAtPlaylistIndex(data as int)` and then `Training.OnOpenShotSelectionMenu()` in that order (`SelectShotButton.setState`, lines 57–75; button hash above). The wrapper forwards the integer unchanged to Unreal method `GFxData_Training_TA.Training.StartAtPlaylistIndex` (Training API lines 233–239; SHA-256 `b7328796d817758bae712c556135c331b0cc86a37dd4a2b0bfab2de2482c2bea`). Thus the view-to-host mapping is zero-based, while the visible row label adds one. The callback's result and the specific input that transitions the inherited renderer to `down` remain unknown.
- **List-control inheritance:** `tagame.controls.ModalScrollingList` only customizes padding, spacing, renderer-name default, scrollbar default and available-width calculation; it does not override input or activation behavior (lines 7–41; SHA-256 `f6d6cea2703be29a81956f2aed96037a457df3468877020c7462f2b8f6072107`). The view replaces its renderer with `SelectShotButtonMovie` (view line 28). `SelectShotButtonMovie` only embeds a symbol and subclasses `controls.SelectShotButton` (lines 1–15; SHA-256 `8e92cff0140cc61a0c5a8554a8dde0dcdf1014196b75c31cc5a8f619d9f8fec8`).
- **Menu identity:** `MenuName.SHOT_SELECTION` is the string `ShotSelectionMenuMovie` (line 138). Separately, the screen checks the screen-manager key `CustomTrainingSelectShotMenu` during replay handling (screen lines 50–59). Do not treat those two identifiers as interchangeable based on these declarations.

## Remaining display and confirm dependencies

The row labels, checkmark predicate, current highlight source and zero-based host index are established. Remaining gaps are the numeric value of `N` in a particular playlist; whether `Status` uses `ETrainingRoundAttempt`'s candidate values; what `OnOpenShotSelectionMenu` does; and which concrete key, button or click transitions the inherited renderer to `down`. Those input-state details belong to uninspected `projectx.controls.StateTweenListItemRenderer` / `scaleform.clik.controls.ScrollingList` ancestry, so no specific confirm-button mapping is claimed beyond the visible `GAMEPAD_A` glyph and the renderer's `down`-state dispatch. `CustomTrainingSelectShotViewMovie` only extends the view and embeds a movie symbol (lines 3–12; SHA-256 `18b224a5af5a33acf3578a2f74607f4ce149356c90aa36d977c81793f5ae0c89`). No further classes were opened.

## Fit with My Career Training

The MCT product contract specifies keeping the Training browser's four tabs—Lessons, Workshop, Mods and Favorites—and opening a separate rank menu after lesson selection. For Power Shots, that intended rank menu has eight ranks, Bronze through Supersonic Legend; Start begins at situation 1, while all twelve situations stay selectable in-game (`TRAINING_WORKSHOP_DIRECTION.md`, lines 19–24 and 175–181). This is a product requirement, not a claim that the current candidate implements it: the integration owner reports the candidate's full-page `LessonDifficulty` has no routed action and rank choices currently remain in the Lesson panel. Treat the stock selector as an **in-session situation picker** after the intended rank flow, not as a replacement for the four tabs or a combined lesson/rank/situation page. Preserve rank while navigating situations and derive MCT `situation N/12` from MCT's own scenario state. The stock view's table row index is zero-based and its row label is one-based, but do not reuse the stock host call or assume the stock table has MCT scenario IDs; keep scenario state and display owned by MCT.

## Limits

The conclusions above are static decompiler-source observations only. The initial four exports came from the recorded bounded export; the eight follow-up classes came from direct FFDec CLI selections after separate inventories. No game input, capture, launch, attachment, installation change, or runtime validation was performed. API declarations and static call order are not proof that the host accepted a call or that a selection started a shot.

## Receipt links

The [initial selected export receipt](../evidence/stock-menu-export-01.json) and [eight-file follow-up receipt](../evidence/stock-menu-followup-01.json) preserve the file hashes without publishing proprietary source. The latter receipt also includes the separate twelve-file navigation batch.
