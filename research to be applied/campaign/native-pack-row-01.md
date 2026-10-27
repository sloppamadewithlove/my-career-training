# NATIVE-PACK-ROW-01 — stock Training Browser row renderer

## Scope and evidence

This is a static, read-only inspection of the stock Custom Training pack-browser row renderer. I read the earlier `nativeui-01.md` and `native-pack-browser-01.md`, then exported four exact ActionScript classes from the already verified `TrainingBrowserMenu.gfx` movie with the pinned local FFDec CLI. The initial three commands exited 0 and emitted FFDec's warning that an external SWF import was ignored. A coordinator follow-up exported three additional classes and the movie XML, both with exit 0. No game, service, input, package modification, or runtime screen inspection was performed.

The movie is 921,910 bytes, SHA-256 `c55ff890a0255a9ee5cdd347c255271cb78ce61e137f45ded1d9cfb18f925098`. Its existing class inventory is 19,466 bytes, SHA-256 `1ea85ad11126af9c5f2cf1f95e4e894570377d2b155f75600624e442c711fb32` (535 entries). The export receipt is `work/native-pack-row-inspection-01/private/row-renderer-receipt.json`, 4,713 bytes, SHA-256 `c00aed6351f91ec4762de1086ebb422648ff3778ea86e611c0269495e056cdea`.

| Selected class | Export bytes | Export SHA-256 |
|---|---:|---|
| `TrainingSequenceListItemMovie` | 329 | `608019bd624bf43d1edec5a5baab821195c96607e4835a0b55fb5b265cf496c0` |
| `controls.TrainingSequenceListItem` | 8,030 | `640b15b4f2d8f87039ff719847f17484d119a049be970eb497a7c9eca584ceef` |
| `tagame.controls.ModalListItemRenderer` | 1,235 | `229ad0daf69d0277e48d9226aab70f7689257c8bbf1b8ab4c13882da3c4ae3a1` |
| `tagame.constants.TrainingEditorStrings` | 5,723 | `0b259f332a4f935ec46bfccd7eec7e6a58fe6f56be3884358bbc238db246811c` |

The direct FFDec invocation used `-format script:as -exportTimeout 60 -selectclass <exact selected names> -export script <fresh private output> <verified movie>`, with a headless runtime and its user/temp directories pointed into the private task folder. Tool identities and per-run stdout/stderr hashes are preserved in the receipt. FFDec was 26.4.0 (jar SHA-256 `80f8ced0bfde98b434c28e9807e91fe5558255b2f712051a0e65221519bd392a`); Java was Temurin 21.0.9 (`java.exe` SHA-256 `5f6248f9c0f32b38ffaba813819bf3331536a48c7ddc45b18e73acd15a6cf7ef`).

## What the row communicates

`TrainingSequenceListItemMovie` is a thin subclass of `controls.TrainingSequenceListItem` and embeds `/_assets/assets.swf` symbol 19 (`TrainingSequenceListItemMovie.as:3–12`; hash above). The generated Embed reference alone does not locate the original artwork. The coordinator inspected the same movie XML: SymbolClass maps the row to 19, and a local DefineSprite tag supplies its child placements and text fields. Actual import tags name shared components and fonts, not `/_assets/assets.swf`. Shared child art/font implementation remains unresolved, but the row timeline is present. The following is static source/metadata evidence, not a runtime screenshot.

For a non-pending `TrainingModeRow`, `TrainingSequenceListItem.draw()` renders the sanitized training name as uppercase title text; a second line combines localized difficulty and training type; it advances the type icon to `Type + 1` (`controls.TrainingSequenceListItem.as:121–127`). The localization helper maps the named training-type values to Aerial, Goalie, and Striker, and named difficulty values to Rookie, Pro, and All-Star (`tagame.constants.TrainingEditorStrings.as:69–96`; fallback strings at `:10–20`). The row uppercases the returned strings. The follow-up enum exports establish difficulty values 0/1/2 for Rookie/Pro/All-Star and type values 1/2/3 for Aerial/Goalie/Striker; type 0 is None. The type-icon requests therefore use frames 2/3/4, with frame 1 for the reset/pending path. Exact artwork and runtime localization remain separate.

The row's supporting text depends on ownership. Owned rows show a publication label and either a formatted update date, a local-modified label, or an empty date field. Rows with a nonempty code use the uploaded label; rows without one use the not-uploaded label. Unowned rows instead show the sanitized creator name. The favorite icon is hidden for owned rows and shown for unowned rows only when the row's favorite flag is true; when present, the title's local x position is offset by 20 units (`controls.TrainingSequenceListItem.as:128–156`). The class also supplies the creator's persona data to the avatar object (`:158–159`), but the selected source does not establish when that avatar is visibly rendered.

Pending rows reset the type icon frame, hide the title, description, metadata, type icon, and favorite icon, show a loading icon, then return (`controls.TrainingSequenceListItem.as:114–120`). The code does not explicitly set avatar visibility in that branch, so its appearance cannot be inferred. When data is absent, the renderer itself hides (`:161–164`).

There is no shots-completed, round-count, or training-progress field read in this renderer. Progress may be represented elsewhere in the browser/details UI, but this row class does not supply it. Its own visual hierarchy is identity/title, difficulty/type, contextual creator or publication metadata, and favorite/loading indicators.

## Interaction and text layout

`TrainingSequenceListItem` configures title, description, update date, publication label, and owner fields to shrink their text to fit (`controls.TrainingSequenceListItem.as:72–80`). The generic modal row base also configures its base text field to shrink and vertically center (`tagame.controls.ModalListItemRenderer.as:27–34`). No maximum character count or explicit ellipsis/truncation rule appears in these classes. The modal base reports a width 28 units narrower than its superclass (`:22–25`); the training row's width setter is empty (`controls.TrainingSequenceListItem.as:178–179`). These source-level layout constants do not define final-screen positions or row height. The local timeline positions below are now inspected, while imported shared component dimensions and runtime parent transforms remain unresolved.

The modal renderer maps `selected`, `over`, and `down` to one dark-blue text color transform (`tagame.controls.ModalListItemRenderer.as:7–19`). The training row applies a 0.2-second tween to its text/loading fields and uses corresponding selected-state transforms for its type/favorite icons and avatar frame (`controls.TrainingSequenceListItem.as:168–175`). The follow-up inspected `StateTweenListItemRenderer`: it initializes named state clips, fades the previous clip out over 0.3 seconds and the chosen clip in over 0.2 seconds, uses selected clips when the owner is focused (or clear-on-focus-loss is disabled), and clears display focus for disabled state. Final fallback selection also depends on the inherited CLIK state map. Shared clip artwork and runtime transition appearance remain unverified. The configured text transform is RGB (0,95,142); this alone does not establish full row appearance.

The previous browser report identifies this class as the renderer chosen by `TrainingBrowserListView` (`native-pack-browser-01.md`, `TrainingBrowserListView.as:28–34`). That report also covers selection/index handling and the details panel. The list's code provides useful content-density conventions, but its positional selection and stock API behavior should not be treated as MCT guarantees; the authored MCT browser already uses stable row keys and an eight-row viewport (`nativeui-01.md`, `MctRootMenu.as:1852,1892–1900`).

## MCT design implications

- Preserve the stock hierarchy of a readable title, one compact classification line, and secondary status/creator metadata. Ensure a professional browser has an explicit, readable progress field when progress matters; stock pack rows do not show shot progress.
- Keep long names legible with a shrink-to-fit or designed wrap policy, but test narrow windows and accessibility scaling; the stock ActionScript does not specify a minimum font size or truncation behavior.
- Separate hover from selected and pressed states if color alone makes focus ambiguous. The stock mapping reuses one color treatment for all three and does not prove a disabled style.
- Keep identity stable through filtering/reordering. Stock browser refresh behavior is positional as described in `native-pack-browser-01.md`; MCT's authored stable-key approach is better suited to preserving the intended selection.
- Keep the proven stock enum/frame mapping separate from MCT lesson/rank IDs and its own artwork. Use authored local geometry as a reference, then verify actual viewport scale, accessibility and focus in the deployed menu.

## Local timeline and state follow-up

The XML is 11,259,291 bytes, SHA-256
`3c9f3937eeb0858ef5c481c32fc3227cc91ad7b678abab2ae79b1f7f4c6cf76d`.
It remains private. The [sanitized receipt](../evidence/pack-row-inspection-01.json)
records all seven source hashes, tool identities, exit codes, actual imports and
13 named row placements. The initial receipt's external-artwork conclusion is
superseded by this direct tag inspection.

Coordinates below divide authored twips by 20. They are **row-local instance
anchors and text-box dimensions**, not final screen pixels or glyph baselines.
Shrinking, parent transforms and imported font metrics can change the result.

| Field | Local anchor x,y | Text box width | Authored font height | Font role / alignment |
| --- | --- | ---: | ---: | --- |
| Title | 62,13 | 380 | 24 | Header / left |
| Difficulty and type | 62,35 | 380 | 15 | Header / left |
| Updated date | 546,15 | 180 | 12 | Normal / right |
| Publication state | 545.55,35 | 180 | 12 | Normal / right |
| Creator | 544,35 | 180 | 12 | Normal / right |

All five fields have no word-wrap and no multiline flag in the inspected tag.
The type icon sits at (15,11) with 0.5 scale. Favorite is at (60,15); the source
moves a favorited unowned title by another 20 local units. The avatar anchor is
(616,7), and the spinner is at (337,32) with 0.703125 scale. Date/publication
versus creator are alternate ownership-dependent content, not three concurrent
right-hand text lines.

The timeline has distinct down, selected and over clips. Their nested contents
refer to named shared component symbols. Reusing one text color transform does
not imply these backgrounds look identical. The additional source hashes are:

| Class | Bytes | SHA-256 |
| --- | ---: | --- |
| `projectx.controls.StateTweenListItemRenderer` | 10,183 | `4a885b784bc1bf1e92611747ab107dfde1cc4df2fa47c4ddb32ba062a6dd34eb` |
| `tagame.api.EDifficulty` | 356 | `99d97c448aff34dbc1473924598d7461ac0f439e0a00f342d6b685fb6dd7bdb3` |
| `tagame.api.ETrainingType` | 451 | `6da78ca2e89f132ad693455d4eec0f5aa8a0f49b384bb0a4bb626cb400eacbe3` |

## Remaining evidence boundary

The actual external imports are `../GFX_Shared/SharedComponents.swf` and
`../GFX_Fonts/gfxfontlib.swf`. Shared component art/font implementation and the
remaining CLIK state-map details are not resolved here. Local row placements
are now established; final viewport transforms, rendered text size, background
appearance, runtime focus/input and native command success still need separate
verification. No extracted art, font, raw ActionScript or XML is published.
