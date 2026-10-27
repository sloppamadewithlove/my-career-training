# HUD-TIMELINE-01: authored training label geometry

## Finding

The HUD movie timeline gives clip-local placements for the legacy training view and its `_v2` view. In `_v2`, all four dedicated shot, shot-total, score, and time label symbols are placed in the movie's upper band. Their placement coordinates and field bounds are recoverable from SWF metadata. This establishes where they are authored relative to the movie clip; it does **not** establish where the movie clip itself lands on screen.

## Evidence and method

- Input: private `HUD.gfx` from the existing HUD inspection, 1,145,308 bytes, SHA-256 `65535317CBC36B2ADDED175B2FF3C817B9093A2EA83951E08D7349C15C1073EF`.
- A bounded FFDec 26.4.0 `-swf2xml` export produced well-formed XML (14,642,001 bytes; below the 50 MiB guard) at `work/native-hud-inspection-01/private/timeline-01/HUD.timeline.xml`. FFDec's XML metadata identifies generator version 26.4.0. The export SHA-256 is `5C7A558DD88D4628B7EBC89E74780D88561D8411377CDAB7F60E23FBFD72A5D4`. The FFDec jar SHA-256 is `80F8CED0BFDE98B434C28E9807E91FE5558255B2F712051A0E65221519BD392A`; Java 21.0.9 executable SHA-256 is `5F6248F9C0F32B38FFABA813819BF3331536A48C7DDC45B18E73ACD15A6CF7EF`. Export stdout and stderr were empty. No game/SWF runtime was started. An exit code was not retained, so this report relies on the complete, parseable XML output rather than asserting a numeric exit status.
- The movie display rectangle is 22,400 × 14,400 twips, or 1,120 × 720 Flash pixels. Conversion is 20 twips per pixel. `SymbolClassTag` links sprite 73 to `TrainingViewMovie`, sprite 60 to `TrainingViewMovie_v2`, and v2 label sprites 52, 44, 55, and 50 respectively to `TrainingShotLabel`, `TrainingShotTotalLabel`, `TrainingScoreLabel_v2`, and `TrainingTimeLabel_v2`.
- The focused queries covered view sprites 73/60 and their named placements; v2 label sprites 44/50/52/55; legacy time/score sprites 66/70; and the linked text fields (including legacy progress field 67). The relevant root selectors are `item[@type='DefineSpriteTag' and (@spriteId='73' or @spriteId='60')]`. Coordinates below are translated from SWF `MATRIX`/`RECT` metadata; they are not runtime measurements.

## `_v2` placements

Each position is the label sprite's authored translation from the view clip's local origin. The inner text field has no additional translation matrix. Field bounds are in that field's own local coordinates; align is the SWF text alignment value.

| Instance / linked symbol | Sprite translation (twips; px) | Scale | Text field bounds (twips; px) | Align |
|---|---:|---:|---:|---|
| `shotLabel` / `TrainingShotLabel` (symbol 52) | (1746, 1706) twips = (87.3, 85.3) px | (0.6666565, 0.7142792) | Twips X −40..1560, Y −40..527; px X −2..78, Y −2..26.35 | left |
| `shotTotalLabel` / `TrainingShotTotalLabel` (symbol 44) | (3055, 1706) twips = (152.75, 85.3) px | (0.6251221, 0.7142792) | Twips X −40..1160, Y −40..527; px X −2..58, Y −2..26.35 | center |
| `currentScoreLabel` / `TrainingScoreLabel_v2` (symbol 55) | (2656, 1438) twips = (132.8, 71.9) px | identity | Twips X −40..1160, Y −40..771; px X −2..58, Y −2..38.55 | center |
| `timeRemainingLabel` / `TrainingTimeLabel_v2` (symbol 50) | (6182, 1408) twips = (309.1, 70.4) px | (1.0001068, 1.0004883) | Twips X −172..2201, Y −168..634; px X −8.6..110.05, Y −8.4..31.7 | center |

The small negative field bounds mean the placement translation is a registration point, not the text field's visual top-left. The timeline stores these labels as separate named instances, making their local positions unambiguous.

## Legacy view

Sprite 73 (`TrainingViewMovie`) has named timeline placements for `timeRemainingLabel` (character 66) at (5100, 1600) twips = (255, 80) px, and `currentScoreLabel` (character 70) at (1720, 1040) twips = (86, 52) px. Their inner text fields are identity-placed. The time field bounds are X −40..2160, Y −40..683 twips (−2..108, −2..34.15 px); the score field bounds are X −40..1360, Y −40..1576 twips (−2..68, −2..78.8 px).

The legacy view has no direct `shotLabel` or `shotTotalLabel` instance in its one-frame timeline. It does have a distinct `roundProgressTextField` instance (character 67) at (4680, 120) twips = (234, 6) px. Its name alone does not establish that it displays the current shot number, so it is not treated as equivalent to the two v2 shot labels.

## Screen anchoring and limits

The SWF frame rectangle begins at (0,0), and each view sprite's placement matrices are local to that sprite's own origin. The existing ActionScript finding in `hud-flow-01.md` says `TrainingView` positions/resizes its controls panel, but does not set these main label coordinates. `UIView`/`UIScreen` provide root alignment, scaling, and safe-zone transforms; their source does not identify the active parent movie's runtime placement. Therefore the upper-band layout relative to the training-view clip is proven, while the actual screen-space top-left, safe-zone inset, clipping, and visibility at runtime remain unknown.

The export cannot establish which label values are populated in a given mode, when they are hidden, or whether the view is the active HUD variant. Those are ActionScript/native-state and runtime questions. This report makes no inference about timer expiry or ball visibility.
