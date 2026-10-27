# ACCESSIBILITY-01 — native menus and HUD usability

Static source review of `work/reviewed-training`, the pinned SDK declarations,
prior NATIVEUI-01 and CAMERA-01 reports, plus official Rocket League support
documentation. No game interaction, screenshots, builds, or tests were run.
Navigation mechanics are not repeated here; the focus is settings ownership,
layout, text, and visibility.

## Settings and actual consumers

| Setting / affordance | Source-confirmed consumer | Native menu/HUD effect |
| --- | --- | --- |
| `text_scale` | `Main.qml` maps the saved value to `root.textScale`; `Copy.qml` scales its font sizes and `ActionButton.qml` scales button text (`ui/Main.qml:24,594`; `Copy.qml:6-10`; `ActionButton.qml:9-20`). UI offers 100%, 115%, 130%; storage accepts 80–160% (`storage.py:65-67`). | No native consumer found. `CareerUI.cpp` uses fixed `textScale = 1.16f`; AS details use fixed font sizes and shrink-to-fit. The setting does not alter these authored surfaces. |
| `reduced_motion` | Persisted and exposed by a checkbox (`storage.py:26-27`; `ui/Main.qml:595`; `bridge.py:1322`). | No motion code reads this setting. It is not connected to the native menu transitions or `StateTweenButton`; the authored sources contain no reduced-motion branch. A saved checkbox state therefore does not establish reduced motion in-game. |
| `binding_profile` / “Input display” | Stored in Python settings and rendered in the native Settings panel as Game actions, Keyboard, PlayStation, or Xbox (`NativeCareerLayout.h:2469-2480`). | It changes labels/settings state, not Rocket League key binds. The native training HUD still spells out D-pad shortcuts (`CareerUI.cpp:735-750`), and the authored browser footer uses a fixed mixed prompt “ENTER / CROSS … ESC BACK” (`MctRootMenu.as:1760-1763`). These labels are not selected from the active controller or actual user remapping. |
| Color-blind/high-contrast choice | Rocket League itself documents Color Blind Mode in Settings → Interface; it forces car/team colors to default high-contrast orange and blue ([official support](https://www.epicgames.com/help/c-37599050/c-32343914/a21923567)). | No app/native color-blind setting or read of that game preference was found. `CareerUI.cpp` uses fixed orange/ice/muted values (`:21-23`); authored Scaleform rows use their own colors. Whether Rocket League’s option changes these plugin-drawn colors is unverified. Keep status and focus understandable from text, shape and border as well as hue. |
| Language/localization | The reviewed QML and native sources use literal English labels. A search found no localization/resource-bundle calls in authored UI paths. | No language selector or translated native strings. `MctRootMenu.displayText()` maps a short list of punctuation/star glyphs to ASCII because the Scaleform renderer has a small glyph set; it is not general script/font fallback (`MctRootMenu.as:970-999`). |

The pinned BakkesMod SDK exposes `GameWrapper::GetUIScale()` and
`GetSafeZoneRatio()` (`GameWrapper.h:143-145`; SDK archive pin in
`plugin/CMakeLists.txt:26-30`). Neither API is called in the reviewed plugin
source. This is interface availability at the pinned SDK declaration level,
not proof about current runtime values or safe calls.

## Sizing, fitting, and truncation

**Gameplay HUD.** The authored Power Shots card sizes itself from
`ImGui::GetIO().DisplaySize`. `TrainingHudLayout::forScreen()` chooses a
14/18-pixel edge margin, a 280–420-pixel left column, a height below 45% of the
screen, and a top offset based on screen height (`CareerUI.cpp:700-723`;
`TrainingLessonInput.h:471-489`). It does not consult `GetSafeZoneRatio()` or
`GetUIScale()`. Although the layout function accepts a text scale, the actual
caller supplies the fixed 1.16 constant. The card uses wrapped text and
`ImGuiWindowFlags_NoScrollbar`; height is estimated from row counts, not the
number of wrapped lines, so long instructions or translations need explicit
overflow checks. `TrainingHudModel::safeText()` caps strings at 80 UTF-8 bytes, backing up to a character boundary
without adding an ellipsis (`TrainingLessonInput.h:432-441`); the full source
text is not guaranteed to fit in the HUD.

**Authored menus.** The frontend browser, pause details and results details
respond to stage resize and use `UIScreen.ContentStageWidth/Height`
(`MctRootMenu.as:369-388,804-805,1488-1489`; `MctPauseMenu.as:212-224`;
`MctResultsMenu.as:148-180`). This is resize-aware geometry, but no explicit
safe-zone inset is applied. The root browser uses a virtual minimum stage of
960×640 and a 1600×900 panel cap. Pause and results details shrink text from
20px to 10px before Scaleform auto-shrink; root details shrink from 20px to
14px then auto-shrink (`MctPauseMenu.as:278-291`; `MctResultsMenu.as:217-231`;
`MctRootMenu.as:391-414`). These are fixed fitting rules, not a player text
scale. Results detail width is capped at 240px; verify readability at small
stage sizes and with long messages.

`NativeCareerLayout` limits the complete body to 2,000 bytes, individual
descriptions to field-specific limits, and uses UTF-8-safe truncation. Its
`plain()` helper replaces unsafe/control characters and appends ASCII `...`
when a bounded string is shortened (`NativeCareerLayout.h:296,444-448,1054-1085`).
This avoids malformed UTF-8, but does not give the player a way to expand a
truncated explanation.

### Error and notice visibility predicates

The C++ layout prepends feedback to `view.body` in priority order: `error`,
then a busy session message, then `notice`; it adds `Could not finish: ` only
for an error (`NativeCareerLayout.h:440-448`). The display path is conditional:

- On a normal frontend page, `generateControls()` calls `showBrowser(false)`
  and assigns `view.body` to the details field (`MctRootMenu.as:423-452`).
- When a browser view is active, `showBrowser(true)` hides both the stock
  details and control container (`:567-573`). `renderBrowser()` draws an
  additional message only when `view.body` starts with `Could not finish:`
  (`:1760-1762`). Therefore the source has a browser error path, but it does
  not establish that the generic busy message or ordinary notice is visible in
  browser mode. The browser error field is fixed at 12px and 24px high, with a
  360-character cap; full-text readability is unverified.
- For a panel route, `renderPanel()` presents row help/disabled reasons, but
  does not consume `view.body`; a global feedback notice is not guaranteed to
  appear there.
- If `validView()` fails, the frontend shows a waiting state rather than the
  stale view body (`MctRootMenu.as:425-432,2155-2172`).

The pause and results authored menus pass `view.body` into their visible
details fields when the current view is valid (`MctPauseMenu.as:262-263`;
`MctResultsMenu.as:213-214`). This is source evidence of a consumer, not a
runtime proof that every error fits or remains visible at every resolution.

## Player-facing gaps and evidence limits

- The desktop text-size control currently does not reach the in-game HUD or
  native pause/results/frontend movies. The app setting accepts values outside
  the three UI choices, while native text uses unrelated fixed/shrink rules.
- “Reduce motion” stores a value but has no consumer in the authored UI. Native
  menu buttons can use tween states; the setting is not wired to them.
- Safe-zone and game UI-scale getters exist in the pinned SDK, but no code uses
  them. Current HUD positioning is a fixed edge margin; authored menus use the
  content stage without a source-verified inset contract.
- Colors and symbols have partial text/border fallbacks, but no color-blind
  adaptation is tied to Rocket League’s documented setting. The browser footer
  is a fixed keyboard/controller mixture, and the in-game prompt remains D-pad
  text even when another label profile is selected.
- English-only authored text and fixed boxes leave translated/long strings
  unverified. Some fields are byte-capped; native browser body errors have a
  separate, narrow visibility path. Source-string presence alone is not proof
  that a notice is displayed.
- No screen-reader/accessibility-tree contract was found for the Scaleform
  native menu surfaces. This is an unverified capability, not a runtime test.

Official history: Rocket League support currently documents Color Blind Mode
under the Interface tab and describes its high-contrast orange/blue behavior.
The official [v1.11 patch notes](https://www.rocketleague.com/news/patch-notes-v1-11)
(2016-02-10) record that PC UI Scale was added under Video Settings; this is
historical documentation, not evidence that a particular current build exposes
the same controls or that plugin HUDs inherit them.

## Proposed acceptance dimensions

These are future verification targets, not claims that these viewports or
settings have already been tested:

1. **Stage geometry:** exercise a 16:9 baseline (1280×720), 1920×1080, an
   ultrawide viewport (2560×1080), and a 4:3 viewport (1024×768), plus the
   current game’s smallest and largest supported UI-scale/safe-zone values.
   Confirm no essential action, focused control, title, notice, or status card
   crosses the usable content boundary or collides with stock HUD/scoreboard.
2. **Text sizing:** cover app choices 100%, 115%, and 130%, and the storage
   validator’s 80%/160% bounds if imported values remain accepted. Confirm
   desktop text and native HUD/pause/results/frontend behavior are explicitly
   consistent with the chosen product contract; long wrapped HUD text must not
   disappear behind a no-scroll window.
3. **Color and motion:** compare Rocket League Color Blind Mode on/off, retain
   text and shape cues when color changes, and compare reduced-motion on/off
   across custom and inherited menu transitions. A setting counts as supported
   only if it changes the declared surface.
4. **Input labels:** inspect keyboard, Xbox, PlayStation and a remapped/custom
   binding context. Ensure labels/glyphs match the active context or fall back
   to generic action wording plus readable text; a profile choice must not
   imply that gameplay bindings were changed.
5. **Localization and feedback:** once supported languages are defined, test
   the longest strings in each language with missing punctuation/special
   glyphs. Trigger ordinary error, busy, notice, disabled reason, browser error,
   and stale-view states on normal/browser/panel routes. Confirm the message is
   visible in each route and offer a way to read its complete text when it is
   shortened.
