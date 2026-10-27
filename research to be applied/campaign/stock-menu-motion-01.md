# STOCK-MENU-MOTION01 — Training Browser focus and motion

## Scope and evidence level

Static review of the existing FFDec exports for the verified Custom Training browser movie and same-build menu helpers, plus previously selected list and row classes. I reused cached exports under the REA skill’s bounded-artifact workflow; no new export, game input/capture, or runtime session was used. The browser movie is the previously verified 921,910-byte artifact; its package identity is recorded in [NATIVE-PACK-BROWSER-01](native-pack-browser-01.md). These are source-derived motion settings, not observed animation or viewport timing.

## Findings

**Menu transitions.** `menus.TrainingBrowserMenu` extends `UIMenu` and its constructor does not set a custom transition (`TrainingBrowserMenu.as:59,168–177`). The companion `UIMenu` export uses `UITransitionFade` as its default (`UIMenu.as:37,71–82`). The fade helper inherits 0.2 s in / 0.3 s out durations and targets `autoAlpha` 1 / 0 (`UITransitionTween.as:9–11,26–54`; `UITransitionFade.as:5–13`). No easing property is specified. Treat this as the default helper path only: the static class can be changed and runtime selection was not observed.

The browser screen is a separate close boundary. `TrainingBrowserMenuScreen` calls `close()` when its menu count reaches zero (`TrainingBrowserMenuScreen.as:19–44`). `UIMenu.removeFromStack` starts the last menu’s transition-out, then dispatches the stack-change event in the same call (`UIMenu.as:383–413`). `ScreenManager` defaults screen fades to `UIScreen.DefaultFadeTime`, whose exported value is 0; a zero duration removes the screen immediately (`UIScreen.as:43,160–168`; `ScreenManager.as:111–119,155–169`). **Inference:** this order may cut short the 0.3 s last-menu fade on Back. A caller-supplied screen duration or runtime override could change it; visible behavior remains unverified.

**Tabs, rows, and focus.** `CategoryButton` tabs are toggle buttons, non-focusable, and cannot deselect. Hover, press, and selected state share a text-color transform; disabled text is dimmed. Its selected arrow fades over 0.2 s (`CategoryButton.as:13–48`). The browser handles L1/R1 tab changes only on `KEY_UP` (`TrainingBrowserMenu.as:410–445`), so tabs are changed by a menu-level action rather than ordinary focus traversal. The selected list row and detail panel are synchronized by the browser’s index-change handler (see [browser trace](native-pack-browser-01.md)). Row hover/press/selected color and clip transitions are covered in [row evidence](native-pack-row-01.md); those shared states do not prove the final artwork’s contrast. The MCT browser’s own focus and stable-key behavior remains distinct ([native UI](nativeui-01.md)).

**Loading.** The browser hides its top loader at construction; category changes set it visible for local tabs and logged-in online tabs, while an online logged-out tab shows a not-logged-in message. The native-ready callback hides the loader (`TrainingBrowserMenu.as:168–177,244–247,547–565`). Pending rows hide their text/type/favorite fields and show a loading-icon clip (`TrainingSequenceListItem.as:114–120`). These methods set visibility; they specify no spin rate or loading duration. The clip’s rendered motion was not established.

**Input repeat.** The list accepts Up/Down on `KEY_DOWN` or `KEY_HOLD`, with page movement based on visible row count (`ScrollingList.as:224–325`). These handlers define no repeat interval, acceleration, or debounce. Tab changes are gated on `KEY_UP`; whether repeated controller actions arrive is an input-runtime question. The existing MCT browser report likewise finds no authored repeat-delay policy ([native UI](nativeui-01.md)).

## MCT reuse and acceptance boundary

Use the stock code as a starting behavioral reference: keep hover, active selection, and keyboard/controller focus legible as distinct concepts; animate small state changes briefly; show a textual loading/error state alongside any clip; and define MCT’s own repeat policy. The stock’s shared color treatment and exact durations are not product requirements. Test MCT’s actual viewport and scaling, Back/last-screen closure, mouse hover, keyboard navigation, controller hold at list bounds, input-type changes, loading/empty/error states, and focus after refresh. No such runtime checks were performed here.

## Source fingerprints

| Export | Bytes | SHA-256 |
| --- | ---: | --- |
| `TrainingBrowserMenu.gfx` | 921,910 | `c55ff890a0255a9ee5cdd347c255271cb78ce61e137f45ded1d9cfb18f925098` |
| `menus.TrainingBrowserMenu.as` | 30,434 | `b5e1890c1f891be6887508e27a13acf3d1c40c26554b72463a53e6c96a49c5eb` |
| `TrainingBrowserMenuScreen.as` | 1,468 | `00e557ca0eb544c3aec99b9ccbe1988b5113dc9a36743f0becdaef54bdc885fa` |
| `TrainingMenu.gfx` helper export | 894,001 | `a216ae0b061340bda02ccf713ddac556909f88e96213baf1c99d42bd5561fcc1` |
| `projectx.core.UIMenu.as` | 24,746 | `2145e5ab8f27b73e3a51792008dbeae4f9255c5fa9f4cff10c5ed0d03995122a` |
| `projectx.core.UIScreen.as` | 11,700 | `9e26e1599db761f62c018aa16e73f8dc21195a85557cabfcbe01d4755cf556ab` |
| `projectx.managers.ScreenManager.as` | 11,565 | `fdad3affff25d76976bd4fea1dc96ffb51ee8a3e350deaec32bdcfee0e313119` |
| `UITransitionTween.as` | 1,983 | `69582deb87765d9ef8dedd0fe952c9bd59d01236669b6e5c03ed281a90142015` |
| `UITransitionFade.as` | 403 | `efa5692cf5e7c487b8c30287bd2abd78aee1c8addb3b29a6c3b67349846a4886` |
| `CategoryButton.as` | 2,401 | `9f0d1ea1f13e17a838ab6c68c24390ad23d3c8afe20e84a15d02d0a5654eddf7` |
| `StateTweenButton.as` | 13,401 | `f6bc50573643d3ff08b1481f643d4d643e0a07f00aa2179695152519c6512798` |

All hashes above are from the selected local files; claims include exact class lines. Existing row/list export hashes and target package identity are recorded in [NATIVE-PACK-ROW-01](native-pack-row-01.md) and [NATIVE-PACK-BROWSER-01](native-pack-browser-01.md). No proprietary ActionScript or private absolute path is reproduced here.
