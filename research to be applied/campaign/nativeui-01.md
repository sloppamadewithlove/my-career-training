# NATIVEUI-01: stock training browser and authored UI integration

## Scope and evidence level

Static reading only. I inspected the existing training-browser AS export, the existing main-menu AS export, and the authored `work/reviewed-training/native_ui` sources. No game, runtime input, compile, or full executable analysis was used. The report paraphrases source behavior and contains no copied source bodies or artwork.

Evidence labels: **direct** means the supplied AS body shows the behavior; **library only** means a generic Scaleform/CLIK class is present but the training browser's use of it is unproven; **unknown** means the referenced game widget or movie timeline is absent.

## Findings

### Stock training browser composition

**Direct:** `TrainingBrowserMenu` is a `UIMenu` composed around a title label, `ButtonLegend`, category buttons, `TrainingBrowserListView`, `TrainingSequenceDetailsPanel`, create/action buttons, loading state, and a logged-out message. Categories are Featured, Browse, Favorites, Created, plus History when `TrainingModeBrowser.CanShowHistoryTab()` allows it. The exported screen is a 1120×720 SWF and centers the menu on `UIScreen.ContentStageWidth/Height`; the menu itself reports dimensions through a timeline `size` display object. (Training-browser AS export: `TrainingBrowserMenu.as:59,92,128,130,210`; `TrainingBrowserMenuScreen.as:8,35`.)

Tabs use a `ButtonGroup`. Their horizontal reflow follows each button's size-updated event and uses 42 px overlap; the displayed L1/R1 icons are loaded through `SystemIconManager.getIconForNavEquivalent` when the active input type is not PC, and faded out for PC. Tab switching is handled on L1/R1 `KEY_UP`, with a sound and boundary checks. The menu's `handleInput` delegates other inputs to the sequence detail panel after its own base handling. (Training-browser AS export: `TrainingBrowserMenu.as:249,410,473,488`.)

The list index-change handler retrieves the selected `TrainingModeRow` from the list data provider and sets it as the detail panel's current item; an invalid selection clears the detail. A list data-change event calls the same handler. A list item click starts the selected training mode only when the interaction mode is `BOUND`. The Create button's focus event clears list selection; directional DOWN from Create moves focus to the list and selects index 0 when rows exist. Category changes set `currentFocus` to either Create or the list and choose the corresponding list height. (Training-browser AS export: `TrainingBrowserMenu.as:511,529,542,554,631,636,657`.)

**Initial export boundary, subsequently narrowed:** definitions for `TrainingBrowserListView`, `TrainingSequenceDetailsPanel`, and `TrainingModeRow` were absent from this initial export. Later same-movie exports in [native pack browser](native-pack-browser-01.md) establish list inheritance, actions and index-based selection retention. [Pack row composition](native-pack-row-01.md) adds the row class and local timeline. Those reports supersede the dependency-only boundary; final screen geometry and live input/rendering still need acceptance.

### Generic list behavior is available, but not proven as the training widget

The separate exported CLIK `CoreList` and `ScrollingList` provide a concrete reference implementation. `CoreList` dispatches index-change on selected-index changes; on PC it registers mouse-wheel and rollover listeners, and row click selects the clicked renderer. `ScrollingList.handleInput` accepts Up/Down and Page Up/Down on `KEY_DOWN` or `KEY_HOLD`; it also implements Home/End. Its refresh clamps the scroll position and selected index to the new data length, then repopulates visible renderers. This is index-based retention, not stable-key matching. (`CoreList.as:187,228,334,351,654,659,672,680`; `ScrollingList.as:20,224,537`; `ListItemRenderer.as:6,53`.)

This initial comparison was **library only**. The later [same-movie browser trace](native-pack-browser-01.md) establishes `TrainingBrowserListView` through `ModalScrollingList` to `ScrollingList`, including the selected input and refresh handlers; it does not certify every runtime default. The exported `FocusManager.as` has stubbed/no-op methods and explicitly directs callers toward `stage.focus`; it is not evidence of usable GFx focus-group behavior. (`FocusManager.as:26`.)

### Authored browser behavior already in the project

`MctRootMenu.as` implements its own browser surface rather than reusing the stock training list. It has four source tabs, search, toolbar actions, eight visible rows, a details panel, and a calculated scroll track. Rows are regular `Sprite`s with mouse click and hover handlers. Hover selects the row; wheel moves one row; keyboard arrows move among tabs, tools, rows, and actions; Tab cycles focus zones; Enter/Space activates. The `InputEvent` path translates controller navigation equivalents into the same browser movement actions. This gives explicit visible focus borders and text labels, while keeping row data and focus state in authored code. (`MctRootMenu.as:56-57,472,550,900,1474,1774,1807,1999`.)

Selection is keyed by the row's stable `key`. Normalization retains the selected key if it remains in the new rows, adjusts the visible window to keep it in view, and falls back to the first row if it vanished. When a page change is pending, the code applies one pending directional move after the new data arrives. (`MctRootMenu.as:1852,1892,1900,1943`.)

The browser renderer rebuilds display objects for structural refreshes. Same-generation media-only updates instead match image metadata by row key and update existing image slots, without rebuilding the browser controls or claiming focus. Async loads are keyed/token-checked; placeholder text covers loading, absent, and error images. These are direct authored-source facts, not runtime results. (`MctRootMenu.as:1420,1442,1474,2384`.)

The custom mouse wheel changes selection by one row; the drawn scroll thumb is not shown to be draggable. The keyboard stage handler processes key-down events, while controller routing uses the normalized UI input event. No authored repeat delay/acceleration policy is visible here; repeat cadence remains an input-system/runtime question. (`MctRootMenu.as:152,550,472,900`.)

### Text anchoring, scaling, icons, and fallback

The exports include a concrete **local top-left alignment primitive**, but not a proven screen/HUD anchor. `UIAlignPosition.TOP_LEFT` is a defined mode; `CurrencyAmountLabel.setAlignPosition` and its `realignControls` place the label and optional background at the label display object's own origin, then center the text inside the backing rectangle when present. It reflows after text/icon replacement and dispatches resize; reported width/height use the current display scale, but this helper does not choose that scale or set a screen inset. The exported `CurrencyAmountView` subclass defaults to TOP_RIGHT, not TOP_LEFT. No inspected use places this component at an in-game HUD top-left origin or defines its safe inset. The stock training screen centers on `UIScreen.ContentStageWidth/Height`, which does not establish safe-area semantics; `RootMenuMovie.as` is a dynamic class bound to a movie symbol and supplies no layout metric by itself. (Main-menu AS export: `UIAlignPosition.as:16`; `CurrencyAmountLabel.as:36,61,131`; `CurrencyAmountView.as:14`.)

The nearest authored precedent is an **end-game menu side column**, not a HUD: `MctResultsMenu` aligns a text field to the left control container, starts at y=36 when space permits, caps its width at 240 px, and fits height against the content-stage bottom margin; it recomputes on stage resize/control refresh and shrinks text from 20 px down to 10 px before Scaleform auto-shrink. `MctPauseMenu` similarly derives its details field from its button column and recenters the panel after resizing. These are layout patterns, not stock HUD contracts. (`work/reviewed-training/native_ui/menus/MctResultsMenu.as:184`; `MctPauseMenu.as:227`; `MctRootMenu.as:375,391`.)

Concrete glyph mechanisms are visible: stock `ButtonLegend` resolves a named button class from the movie's `ApplicationDomain` and logs if the symbol is missing; it reacts to controller-vs-other input changes. The training browser requests the `GenericModalSquareMenuButton` symbol for its legend. The tab shoulder glyphs come from `SystemIconManager`, then `ImageLoader.setBitmap`. Thus symbol names and APIs are concrete, but availability depends on the loaded movie/runtime domain; the export does not prove that arbitrary glyph classes exist. (`ButtonLegend.as:98,212`; `ImageLoader.as:71,97`; training-browser AS export: `TrainingBrowserMenu.as:206,473`.)

For text-first fallback, the stock legend supplies localized action labels such as Close and Enter Code; browser tabs and actions are also labeled text. The authored browser uses visible focus strokes and disabled colors/text. This provides a keyboard/controller-readable path when a glyph is unavailable, but no screen-reader API or accessibility-tree contract was found. Generic `GenericMenuButton` and `CategoryButton` classes include disabled dimming; whether every training row uses those states is unknown. (`TrainingBrowserMenu.as:569`; `GenericMenuButton.as:16`; `CategoryButton.as:20`.)

## Six-part integration contracts (proposed from evidence)

| Contract | Gate | Input | Data | Focus/selection state | Visible response | Failure and accessible fallback |
|---|---|---|---|---|---|---|
| Switch source | Browser is frontmost and not busy | Tab click, arrows, or controller L1/R1 | Selected source and returned rows | Preserve source-specific selection key where valid; choose a documented fallback if absent | Selected tab styling plus textual label | Missing glyph falls back to text; empty/error source keeps focus on source controls and states why |
| Select / activate row | Row data is ready; action enabled | Mouse hover/click, arrows, Enter/A | Stable row key and action metadata | One canonical selected key drives both highlight and detail | Highlight, title/details, enabled action label | Disabled action remains focusable only if its reason is announced; otherwise skip it and expose reason as text |
| Scroll/window | More than one viewport or another page exists | Wheel, arrows, Page keys/controller hold, optional scrollbar | Offset, total count, has-more | Preserve selected key while moving viewport; defer one pending edge move until rows arrive | Count and position indicator stay synchronized | Clamp at list bounds, report loading/error, avoid silently dropping selection |
| Refresh media | Row key still exists and only media changed | Async completion or metadata refresh | Image status/file/credit keyed to row | Do not move focus or rebuild action controls | Keep fixed image slots; show loading/missing/error text and credit | Stale load is ignored; text placeholder remains when glyph/thumbnail art is absent |
| Text/glyph action | Active input mode known | Keyboard/controller/mouse | Localized action label and optional glyph mapping | Focus order remains independent of image loading | Native legend glyph plus readable action text | Missing symbol or unknown mapping uses text-only label; never make icon the only action cue |

## Integration guidance and acceptance checks

- Reuse the content-stage resize hooks and the results-menu left-column fit pattern for menu text. Do not call this a HUD safe-area implementation until an actual gameplay HUD parent/inset source is identified.
- Keep list selection and detail content driven by one stable key. On refresh, preserve that key if present; if removed, select the first valid row or an explicit empty state. Separate media-only refresh from structural refresh so image arrival does not reset focus.
- Use the game's input mode and icon APIs where available, but keep localized action text visible. The later same-movie browser trace supplies the `KEY_HOLD` inheritance/dispatch evidence; actual repeat behavior still needs device acceptance.
- Future acceptance should cover controller hold/repeat at list bounds, mouse hover/click and wheel, empty/loading/error states, resize/aspect-ratio fitting, missing glyphs/thumbnails, disabled actions with readable reasons, and row reorder/removal while selected. None of these have been runtime-tested in this research.
