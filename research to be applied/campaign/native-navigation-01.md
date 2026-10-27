# NATIVE-NAVIGATION-01: stock menu navigation and MCT rank flow

## Findings

### Stock menu stack, Back, and focus

The statically inspected stock `UIMenu` source has a menu stack. `addToStack` pushes and activates a menu; `removeFromStack` removes the active child, reactivates the previous menu, and emits the pop/change events (`UIMenu.as:318-413`). The active menu's `currentFocus` is retained. On reactivation, `validateFocus` restores that component when it remains on-stage, enabled, and focusable; otherwise it asks `FocusManager` for the first downward focus target (`UIMenu.as:534-603,625-634`). Thus the source supports Back returning to the parent and restoring its still-valid focus. The fallback manager implementation was not among the inspected files.

On key-up, `UIMenu.handleInput` routes Escape or `NavigationCode.GAMEPAD_B` to `handleBackEvent`; the event closes the active menu when `bCloseEnabled` permits it (`UIMenu.as:557-564,711-739`). The already-inspected `TrainingMenuScreen` caller opens `DifficultyMenu` as a submenu through `UIMenu.openMenu` (`TrainingMenuScreen.as:21-40`); the generic pop therefore targets the existing parent menu. This is a source path, not a runtime observation of focus.

`DynamicMenu.refreshMenu` tries to retain focus while recreating controls, but matches the saved callback object when choosing a new control (`DynamicMenu.as:74-90,138-178`). That is a weaker identity than a stable row ID when multiple options share one callback. A specific difficulty choice should have distinct focus identity if the menu must reliably restore that exact row.

### Controller legends and glyph selection

The generic `ButtonLegend` component can subscribe to menu-stack changes and adds a localized Back legend when the active menu is closable, subject to its explicit menu exclusions (`ButtonLegend.as:72-82,157-210`). On PC it subscribes to input-type changes and switches between PC labels and controller glyphs (`ButtonLegend.as:125-142,212-238`). `LegendElement` renders the PC button/text or gamepad markup (`LegendElement.as:74-135,137-187`); `SystemIconManager` maps navigation equivalents such as A/B and selects platform-specific glyph substitutions from the current input type (`SystemIconManager.as:79-128,144-245,352-435`). The inspected `InputTypes` enum names PC, 360, PS3, PS4, XB1, NX, and NX single-controller types (`InputTypes.as:3-18`).

These are reusable generic components and mappings. The inspected Training/Difficulty menu classes do not directly reference `ButtonLegend` or `SystemIconManager`, and no runtime capture established that those symbols are instantiated for those screens. The authored MCT root also does not reference those components; it draws its own controls and handles navigation. A controller Back legend or device-switching glyph on MCT therefore cannot be inferred from the stock component's existence.

### Current MCT route and rank selection

The exact reviewed candidate inspected here is `work/reviewed-training` (not the older publication baseline). `native_ui/menus/MctRootMenu.as` is 125,301 bytes, SHA-256 `D0CEB137836A8154E30304D7BC2193841EEBD138DCD9A2548624781BE9C18025`. The current `plugin/include/NativeCareerLayout.h` is 167,035 bytes, SHA-256 `17D2EC0A82C79FAD1949715AD62840BCACE4177CBBE137DA3AA675289109EB78`.

The reachable lesson route is the Lessons browser row `lesson:power-shots`. `buildTraining` labels it “Choose rank” and binds it to `select_lesson` (`NativeCareerLayout.h:1600-1616`). Selecting that row passes through `NativeMovieProtocol::select` to `NativeCareerLayout::chooseBrowser`; the Power Shots case sets `lessonId_` and `page_ = Lesson` (`NativeMovieProtocol.h:130-181`; `NativeCareerLayout.h:677-690`). The native movie host receives the callback at `NativeMovieHost.cpp:686`, then validates and sends accepted dispatch effects through the bridge at `:557-623`. The bridge allowlist includes `select_lesson` and `lesson_scenario` (`LocalBridge.cpp:221-236`); Python stores the selected lesson and scenario/difficulty (`bridge.py:1361-1379`). `buildLesson` renders eight rank rows in the Lesson page's `view.panel`, marks the stored difficulty as `SELECTED`, and binds each rank row to `lesson_scenario`; starting practice uses that stored difficulty (`NativeCareerLayout.h:1793-1893`). The labels explicitly describe intended challenge, not certified bot rank.

There are two other rank-related source paths, and they are not the active lesson path:

- `CareerLayoutPage::LessonDifficulty` has a full-page eight-rank builder with Back targeting `Lesson` (`NativeCareerLayout.h:27,420,1896-1912`). A bounded search across the current candidate's `plugin/src`, `plugin/include`, and `native_ui` found no generated choice or other assignment targeting this page. In the current route, the enum, view switch, and builder exist, but the selection handler enters `Lesson`; no reachable navigation into `LessonDifficulty` was found.
- `MctRootMenu.as` also supports a generic browser-detail rank popup driven by `selected.ranks` (`MctRootMenu.as:1667-1754,1958-1997`). Current C++ Lessons rows set “Choose rank” and `select_lesson`, but do not populate `ranks`, `rankEnabled`, `rankValue`, or `rankLabel`; those fields default empty/false and the wire emits an empty ranks array (`NativeCareerLayout.h:52-61,1600-1616`; `NativeMovieProtocol.h:286-301,324-337`). That generic popup is therefore not the current Power Shots rank route.

MCT uses stable identities for its own focus state. `refreshMenu` captures and restores the enabled control name (`MctRootMenu.as:221-255`); browser selection is keyed by row key (`:1852-1904`); panel focus is keyed by row ID and normalized to the first row if the old ID is absent (`:596-644`). The panel separately shows which difficulty is selected from bridge state. Focus and selected difficulty are distinct state: the displayed rank is authoritative, while initial panel focus defaults to its first row unless a valid `panelFocusId` is already retained. The browser's generic rank popup similarly seeds its internal focus index from the selected rank when opened (`:1701-1705,1961-1972`).

Coordinator correction: `view.panel` is already a separate rank surface for Power Shots, not a panel beside the Lessons browser. `buildLesson` activates the panel without activating a browser. `NativeMovieProtocol.h:108-109` emits only active surfaces; `MctRootMenu.as:434-442` chooses `generatePanel()` when no browser is present, `:585-590` initializes it, and `:798-814` clears the layer and draws a centered full-screen-backed panel. The separate Power Shots rank route therefore exists through `Lesson`. The unused `LessonDifficulty` builder does not establish a missing user-facing route. Other seven lessons still lack the requested eight rank profiles and corresponding selection flow. MCT page transitions and focus IDs are handled by its own layout and authored movie.

For route provenance, the inspected candidate hashes are `NativeMovieProtocol.h` `596422F6D2E07946678188257BA7E75CC21C8A7FA40B98A49D1736868E97600B`, `NativeMovieHost.cpp` `D336DC9958403791E7BA14779F29C719E45E6642A0644092934746E189A0A282`, `LocalBridge.cpp` `284CEBDBBB18D1D2571BA28B35003061187BE85753D0C2AD5DDAEB7B59335C66`, and `src/my_career_training/bridge.py` `AC502D1F19810BACA479A534AA766A6AFBEA7BA57A405452835CC9DCFF379AC2`.

## Evidence identity and limits

The 12 private exported classes used for inherited navigation/input/legend mapping were read from the existing output02 TrainingMenu export. Their file SHA-256 values are:

| Exported class | SHA-256 |
|---|---|
| `projectx/core/UIMenu.as` | `2145E5AB8F27B73E3A51792008DBEAE4F9255C5FA9F4CFF10C5ED0D03995122A` |
| `projectx/menus/DynamicMenu.as` | `DD5BB00C9521EAB931C3F44375A2C144A79857ECF23F9BBB59320A04C069CD9A` |
| `projectx/core/UIScreen.as` | `9E26E1599DB761F62C018AA16E73F8DC21195A85557CABFCBE01D4755CF556AB` |
| `tagame/controls/ButtonLegend.as` | `BA4E6303F4E1A6F22B04C4B33C4BAA1416694D188523A292E35CD48B330570B4` |
| `tagame/controls/LegendElement.as` | `D151A773B14733987BEF28039536337248D7FB969EBC5FAB2EBEBB5540E53521` |
| `projectx/events/ButtonLegendEvent.as` | `29465AC2DF50ABE7736078837E5205EB73F37A3098313158A2EDCD22364C2ECA` |
| `tagame/controls/MenuButton.as` | `E2CB9B46826D325E6ECFAD3FB40B31B41E28C975E057E347B71874CBA91E94C1` |
| `controls/XPLevelMenuButton.as` | `1E12C7909B7DFC76C82B6EC20C308DFA2ACD1ABDF04205C2E1F0742BE3777A1F` |
| `projectx/api/InputTypes.as` | `0EE9C21E6C63688E2E388D80D96698E5E4FE01ED71CB780804C0A2903133B747` |
| `scaleform/clik/events/InputEvent.as` | `8B5D540345C2F7D6BB6D3160CA2633F56602BEDB54159A7A44EAA546E0624346` |
| `projectx/managers/SystemIconManager.as` | `384E8CDF3B6C309DFADAB4BE245C80BAE7D6EAFA8E1D148FC17BB7734EFBDE39` |
| `tagame/data/ButtonLegendData.as` | `5129FAF4678336396AFCACBF2F66812BE2745501D284636E3B625C5AFECF0907` |

The output02 decompiler invocation returned successfully, but its aggregate helper receipt failed its 500-class inventory limit after finding 508 classes. A later focused output03 receipt passed for selected menu classes; it did not include the inherited navigation/legend classes listed above. Treat the findings here as bounded static decompiler observations, not a complete package inventory or runtime proof. No game input, package modification, compilation, or code change was performed.

## Focused provenance follow-up

The coordinator subsequently exported the exact twelve navigation classes with the same pinned FFDec toolchain, using direct CLI class selection into a fresh private directory. That command exited 0; all twelve files match the previously inspected bytes. The [sanitized follow-up receipt](../evidence/stock-menu-followup-01.json) records their sizes and hashes and resolves the earlier aggregate-inventory limitation for these classes. This was a source export, not a runtime menu test.
