# STOCK-TRAINING-SETTINGS-01 — settings checkbox evidence

## Result

The focused `SettingsMenu` export confirms a stock Training category and a separate `TrainingSettingsMenu` page with three settings groups. The follow-up exports now trace the complete authored checkbox path: a Boolean user-settings row supplies the displayed state, a `ButtonEvent.CLICK` requests the inverse through the native Settings API, and row callbacks refresh the visual state. The exports also show focus-hook plumbing and the shared description field. These are static UI/API findings, not proof of durable persistence or actual training-feature effect.

The existing My Career Training pause page already has its own Training-first settings panel. Its checkbox mark is drawn by the MCT movie while the interactive row remains an ordinary native menu button. This is evidence about the current MCT implementation, not a claim that its styling matches Rocket League's stock checkbox.

## Available stock training source

The existing `TrainingMenu` movie is 894,001 bytes, SHA-256 `a216ae0b061340bda02ccf713ddac556909f88e96213baf1c99d42bd5561fcc1`, from `GFX_TrainingMenu_SF.upk` (1,146,549 bytes, SHA-256 `BF9BAA4238D077F35F8041204EA4AEC8E9E7C9BB943D1E3DF2DA07DD07A57663`). Its package table has one `SwfMovie` export named `TrainingMenu`. The selected AS export binds `TrainingMenuScreen` and `TrainingMenu` to that movie; these identities and their focused-source limits are recorded in `native-training-flow-01.md`.

The focused class search found no `TrainingMenuSettings`, checkbox, or toggle class among the available `TrainingMenu/scripts` sources. In the selected code:

- `TrainingMenuScreen.as:21–39` opens `DifficultyMenu` or the standard training menu, while `TrainingMenu.as:131–192` routes tutorial, Goalie, Striker, Aerial, Free Play, and Custom Training. It contains no settings-checkbox path.
- `MenuName.as:178` declares the identifier `TrainingMenuSettingsMovie`. This is a menu-name string only; no corresponding implementation class was among the selected exports.
- `tagame.api.Settings.as:78–129` provides scalar, boolean, and list setters through `GFxData_Settings_TA.Settings`, plus index/load/callback helpers. `tagame.constants.SettingsGroupName.as:42–46` names Training General, Training Free Play, and Training Actor Modifiers groups. These APIs and group labels do not identify a checkbox or its screen caller.
- `tagame.controls.MenuOptionStepper.as:14,71–74,182–197,231–243` wraps a generic multi-value stepper. It enables focus only when its data provider has multiple entries and responds to previous/next changes. It is not a checkbox, and these sources do not show it being used by the training settings screen.

Selected file hashes: `TrainingMenu.as` `215CE7675FA7785AC68CA271482D6AAC82BB877C24E577783D4C675A4B59C273`; `TrainingMenuScreen.as` `C96CD5F7004418D6164DE307164C30063A17CBE0A5D5185219A0662AF8A356BF`; `Settings.as` `CB3D9A9A87963F804BF9D4FFEF24ED8623501FCA02760B691956B64F1E405969`; `SettingsGroupName.as` `C9FFE492910A7E08DD8BC76D3499F83D040379CCCBFF2B982A538D417BA4C347`; `MenuOptionStepper.as` `442BD8091AB3C38EC4F46BF2413F9C4A0329A8FC97910CF8D605383DAEF9CBAB`. `native-training-flow-01.md` records `MenuName.as` hash `BC19F3699382C3BCBE447CF28862419E93C649130BBF59DCA12D2524FB9ED218`.

## Settings movie metadata

Using the existing `inspect_menu_package` API and the already-staged in-memory decoder, I inspected metadata only for `GFX_SettingsMenu_SF.upk`. Its SHA-256 before and after was unchanged: `237BD62421434CB0E285EC88E42A93A9B8BB277AD5EC561059A3BC86178BBB95` (689,160 bytes). The reader reports UE version 868, licensee 34, flags `0x0288028D`, a 19,661-byte header, 59 names, 9 imports, 11 exports, and one compression chunk.

The exact movie is export 3, `SettingsMenu`, class `SwfMovie`, with a 1,745,584-byte **logical serial size**. This is export metadata, not a measured RawData movie length. A bounded class inventory found 567 entries. A focused FFDec 26.4.0 export of eight selected classes from the identified movie returned success; the movie identity is also recorded in `work/native-settings-inspection-01/receipt.json` (1,745,158-byte RawData, SHA-256 `25F346B66E93219E5E22BBD43129ACA801F43EA906CB4AD07E9ECA4799C9C24`). The following dependency passes expand this to seventeen selected classes; no inventory-wide source export was performed.

Selected AS hashes:

| Class | SHA-256 |
|---|---|
| `menus.SettingsMenu` | `FD2DBBBAB4ACACB8BF291518AA98A52556574DCADCA12997AF3BA2B54F8B31B5` |
| `menus.TrainingSettingsMenu` | `4FA036E32B5B82AA6F602D149A872520F6A62043325B8AF93F61A3D72693808F` |
| `menus.GroupedSettingsMenuBase` | `E97EA558C0B252227A4548D41815FEC0309AC425501F1A8DC4F995BD9042E4D0` |
| `tagame.controls.OptionsCheckBox` | `7930DDEE20FE3F91A9652C5D1AC6A9B6BA356A2D2D3B553953D63D9299DD31E3` |
| `tagame.controls.UserSettingsGroup` | `D1869F0E582E8ADF714D45F8D47B007E7380AD9C3398D52359442F31D9D0D4FA` |
| `SettingsMenuScreen` | `C4AD79CEE7228D8873E5EFC391771A25A7661FD58F5D4CA7991897A27BD90BE4` |
| `TrainingMenuSettingsMovie` | `E89099C35824AD4C7B252A546318AA6C7E7823760952E8C88E52E35830A00DB9` |
| `tagame.constants.SettingsGroupName` | `BDA98B89E18F165A7DCCCC463B8501A36FD5F1A9DCDECBC238D470B3E0DD273D` |

## Stock Training category and checkbox surface

`SettingsMenuScreen.handleAddedToStage` passes a string route to `SettingsMenu.requestOpenCategory` (`SettingsMenuScreen.as:44–51`). `SettingsMenu` loads the user settings table in its constructor (`SettingsMenu.as:168–176`). Its category list begins with Training and associates that tab with `TRAININGGENERAL`, `TRAININGFREEPLAY`, and `TRAININGACTORMODIFIERS`, using `MenuName.TRAINING_SETTINGS` (`SettingsMenu.as:310–318`). Categories with no matching user settings are filtered; the first surviving category is selected (`:179–204,389–402`). Thus Training is the authored first category when at least one Training group has data; this source does not assert runtime row counts.

The Training category's content is a single page with three section headings, localized as **General Settings**, **Free Play**, and **Ball and Vehicle Settings**, rather than three additional tabs (`TrainingSettingsMenu.as:48–56`). The sections bind respectively to the three training groups. The Free Play and Ball and Vehicle headings are hidden when their groups contain no rows; the page repositions later groups when a section is empty (`:72–87`). `TrainingMenuSettingsMovie` links the page to embedded symbol 29 (`TrainingMenuSettingsMovie.as:3–10`).

`UserSettingsGroup.SetGroup` clears prior children, queries the `UserSettings` row table, creates one configured `UserSettingMovie` per matching row, calls its `Init(rowNum)`, and places the controls vertically (`UserSettingsGroup.as:42–80`). Each group can pass a focus callback to descendant `UserSetting.checkBox`, dropdown, or button controls (`:120–130`). `TrainingSettingsMenu` registers a user-settings value-change listener when added to stage, synchronizes each of the three groups initially and after changes, then unregisters the listener when removed (`TrainingSettingsMenu.as:59–70,89–94`; `UserSettingsGroup.as:82–89`).

The named `OptionsCheckBox` class extends `StateTweenButton` and defaults its `toggle` flag to true. It renders unchecked state with the check icon hidden; selection scales and fades the icon into place, and a selected disabled state dims the icon (`OptionsCheckBox.as:8–74`). The `UserSetting` row factory types its checkbox as `OptionsCheckBox` and turns automatic toggling off for Boolean rows; the row value and native callback own the displayed state instead.

Stock tab input is partly visible. The Settings menu switches categories on controller L1/R1, shows their system glyphs when the active input is non-PC, and uses a legend for B/Back and X/Defaults (`SettingsMenu.as:247–272,417–486,736–790`). Back from a later group in a tab returns to that tab's first group; Back at the first group closes the Settings menu (`:500–517`). Since the Training tab supplies `TRAININGGENERAL` as its first/current group, this path closes the Settings menu rather than stepping among the three sections (`:314–318,725–733`). A Defaults confirmation popup offers Yes and No; accepting a Training reset calls `Settings.SetDefaults` for all three Training groups (`:545–555,682–709`). `SettingsMenu.close` cleans up its modal and shared-UI state; `SettingsMenuScreen` closes when the menu stack empties and notifies the taskbar when removed (`SettingsMenu.as:905–918`; `SettingsMenuScreen.as:54–58,101–106`).

The Settings menu has a shared context-description field: it subscribes to context changes and displays `desc` for the current InteractionManager context when that object is inside the menu, otherwise it uses `m_disabledDesc` (`SettingsMenu.as:264–272,945–962`). In Cabined Mode that fallback is a general parental-controls message (`:821–829`). The row-to-checkbox description route is traced below. The fallback does not expose the reason a particular `bEnabled` value is false.

## Direct row, focus, and input path

The bounded follow-up exported the seven named dependencies, then `scaleform.clik.controls.Button` as the base class needed to resolve activation. Their hashes are recorded below. Together they establish this static path:

1. `SettingsSubMenu.configUI` gives its `UserSettingsGroup` the `focusChange` callback before building the group (`SettingsSubMenu.as:60–69`). The callback returns the current stage focus for LEFT/RIGHT navigation and returns null for other directions (`:77–89`). The same base sets up a clipped scroll region and, for non-PC input, scrolls the focused control into view (`:187–240`).
2. `UserSettingsGroup.SetGroup` gets each row from the `UserSettings` DataAPI table, creates the configured `UserSettingMovie`, and calls `Init(rowNum)` (`UserSettingsGroup.as:42–80`). It walks descendants to assign the focus callback to a row's checkbox and dropdown (`:120–131`). `UserSettingMovie` extends `UserSetting`; the latter's `checkBox` field is typed `OptionsCheckBox` (`UserSettingMovie.as:27–36`; `UserSetting.as:26–55`). This confirms the concrete checkbox type used by this row factory.
3. `UserSetting.Init` stores the row ID/type and subscribes to changes in row value, values, and enabled state (`UserSetting.as:91–104`). Boolean `syncValue` sets the checkbox's selected flag from the row's current string value (`:192–214`). The enabled-state callback gates child interaction and assigns the checkbox's `enabled` flag from `UserSettingsRow.bEnabled` (`:132–162`). This proves the UI's source of truth and disable gate, not the native condition that sets `bEnabled`.
4. The Boolean setup attaches the row description to the checkbox as `desc`, disables the component's own optimistic `toggle`, and listens for `ButtonEvent.CLICK` (`UserSetting.as:246–251`). The handler calls `Settings.SetBooleanValue` with the uppercased row ID and the inverse of the checkbox's current selected value (`:274–277`). The settings table's value callback then drives `syncValue`; the sources do not guarantee callback timing or error behavior.
5. `OptionsCheckBox` supplies selected/disabled check-icon animation (`OptionsCheckBox.as:8–74`); it inherits `StateTweenButton`, which inherits CLIK `Button` (`StateTweenButton.as:8–16`). The exported `Button.handleInput` handles `NavigationCode.ENTER` on key-down and completes activation on key-up (`Button.as:353–378`). The shared button implementation also dispatches a click on mouse release and keyboard/controller activation (`:742–772,813–864`). This supports the stock activation route at source level; no live device switching or focus traversal was tested.

`SettingsMenu` subscribes to `InteractionEvent.CONTEXT_CHANGE` and renders the current context's `desc` when that context is within the Settings menu (`SettingsMenu.as:264–272,945–962`). Combined with `UserSetting` assigning `row.Description` to `checkBox.desc`, this is a direct authored route for row help to appear as the selected context changes. The exact timing and presentation for a particular Training row remain runtime questions; the fallback is the generic disabled-settings description, not a per-row disabled reason. The table provides `Description` and `bEnabled` values (`UserSettingsRow.as:42–45,67–70`), but these selected classes do not establish the reason for a disabled row.

The native setter invocation establishes a request to change the user setting. It does not establish that disk persistence has completed, that closing/back commits anything, or that a Rocket League training feature responds as intended. No explicit save call appears in the selected checkbox path. Those require runtime observation of the value after close/reopen and the associated feature effect.

Selected direct-dependency source hashes:

| Class | SHA-256 |
|---|---|
| `menus.SettingsSubMenu` | `4E4A856F741EC5896164F8A8052388695A233B7665BF404C1537F6A2DC380ADD` |
| `tagame.controls.UserSetting` | `0997702A9C62FF798D66815F40DDADD98CB4791D5511392CF9544D03481D34BA` |
| `tagame.api.UserSettings` | `25269EE95D9C460A1FA6A951EA2CC6D7488455A577EB09C79C49EC4D85A77C99` |
| `tagame.api.UserSettingsRow` | `042CC0B89AA8A58AD1A07A61B071A719A0F911B46B5D3681ACF7E21AA1F6EDC2` |
| `tagame.api.EUserSettingType` | `D713AC525E75FF5F4B6D63FE0AAA96C48BAF347D296F884D94098BD517E0C5C9` |
| `UserSettingMovie` | `0DB513C4E40150B9ADEF9CBDD3BC3961B69FE4F84D073BA01D8F9A497B1B6E71` |
| `projectx.controls.StateTweenButton` | `2978AB5A6F8F5E278FEB5235B9C7366CF0AF72C1592D7A41273C118CB4992A12` |
| `scaleform.clik.controls.Button` | `CC232A2C35D0F3DD7BB84B67D0A506963A79F1A00195C6FE65EB95E448575C02` |

The remaining gap is behavioral validation: the enabled training-row toggle, help display, close/reopen persistence, and actual feature effect have not been observed in a live game. The selected `GroupedSettingsMenuBase` writer is not used as evidence here; the Training path is established directly through `UserSetting.handleCheckBoxClick` (`GroupedSettingsMenuBase.as:82–102`; `TrainingSettingsMenu.as:10–17`; `UserSetting.as:274–277`).

## Comparison with the current MCT Training tab

In `work/reviewed-training/plugin/include/NativeMatchLayout.h:95–120,520–548`, the live lesson's pause route opens a Training options page and binds it to the same session and lesson. The first tab is Training; Game options preserves the stock Options route. Rows use `lesson_preferences` with declared defaults, display On/Off, and dispatch a signed control action. `settings-01.md:71–80` records the persistence, application, and limitations of those values.

`work/reviewed-training/native_ui/menus/MctPauseMenu.as:174–190,382–498,501–526,575–596` renders tabs and rows as ordinary menu buttons. Keyboard, controller, and mouse use the existing focus/choose path; left/right switch tabs on a key-down edge. A checkbox's square and tick are a non-interactive child derived from the backend value. Focus goes to the first enabled row or Back. Back dispatches the local signed navigation control that closes the page; it does not invoke a stock checkbox handler. A missing or disabled matching control makes the row disabled, and the button cannot dispatch it. `NativeMatchLayout` carries reasons in disabled control data, but the visible row builder uses label/value and does not render `row.help`; this source set therefore does not prove that a disabled-row explanation appears on screen.

The page is authored as a pause-menu settings surface. This evidence gives no reason to add a new context menu or rename/reorder the browser tabs: Lessons, Workshop, Mods, and Favorites remain the browser labels.

## Unknowns and next evidence

From the bounded static source set, the Training settings route, group headings, row-to-checkbox binding, current-value display, native boolean setter call, enabled gate, focus callback wiring, activation event path, description field route, and reset-defaults path are established. The native predicate/reason that disables a particular row, exact focus restoration/traversal at runtime, setter acknowledgement and durable persistence, and observable training effect remain unknown. No stock runtime behavior was observed.

The next useful evidence is runtime-only: choose one enabled training Boolean row, observe the initial value, activate it through a controlled input, verify the DataAPI update and visible checkbox/help, close and reopen Settings to check the value, then exercise the setting's actual training effect. This should remain a separately owned in-game test; source export alone cannot establish any of those outcomes.

MCT source identities used for comparison: `NativeMatchLayout.h` SHA-256 `A986F0ED827F11EF2716C8FC6BB196D55F822CC22C6B5316B0FDE0BB278A8D53`; `MctPauseMenu.as` SHA-256 `AC74A0E3020B3C40356BB75739BB03FBC70385CE277522441A48B8FEEE86EDC2`.

## Coordinator API-boundary cross-check

A fourth focused export selected only `tagame.api.Settings` from the same SettingsMenu movie (FFDec exit 0). Its SHA-256 is `85a3ce3ca8dbcecc967b17ed5984ae4c41423b503a321cade55dde1ea58d129a`, distinct from the earlier TrainingMenu copy. `Settings.as:86-93` checks for the shell hook, then requests `GFxData_Settings_TA.Settings.SetBooleanValue` with the ID and Boolean. It returns no success result. This closes the same-movie static request route without claiming native acceptance, persistence or gameplay effect. The complete sanitized export identity is in [settings evidence](../evidence/settings-inventory-01.json).
