# Training browser visual spec (reviewed)

Status: **design preview only**. This document and
[`previews/training-browser.html`](previews/training-browser.html) describe and
demonstrate layout and interaction. They are not evidence of game capability,
downloads, installs, controller capture, video playback or native menu support.
Native integration is owned separately by main.

Source of direction: [TRAINING_WORKSHOP_DIRECTION.md](TRAINING_WORKSHOP_DIRECTION.md)
and the 26 October owner correction in [AGENTS.md](../../AGENTS.md) (Opus designs,
builders implement). Where the earlier Opus visual spec conflicts with the owner
review requirements, the review requirements win; the differences are listed at
the end.

## Scope

Two files only:

- `docs/previews/training-browser.html` — self-contained preview, no network
  requests, no fonts fetched, no CDN, no external images. All artwork is original
  inline SVG.
- `docs/TRAINING_BROWSER_VISUAL_SPEC.md` — this brief.

No runtime, plugin, QML or native source is touched.

## Honesty rules applied in the preview

- A persistent banner reads **Design preview — simulated, not a game feature**.
- Sample rows are labelled "sample data"; the item count line says so.
- Primary actions never claim a real effect. Pressing one replaces the note with
  "Design preview: this action is simulated and does nothing."
- Mods use **READ DETAILS** only. No **ENABLE** label appears anywhere, because no
  reviewed enable/disable integration exists.
- Workshop rows use **DOWNLOAD** or **PLAY** as *labels under review*; the preview
  states that no download or launch occurs. No percentage, progress bar or
  "installed" transition is fabricated.
- No raw HID events, no model assets, no screenshots, no success toasts.
- Garage lists installed-but-unsupported products explicitly under
  **Installed but unavailable**, with a per-item reason. They are not hidden.

## Shared tokens

| Token | Value |
|---|---|
| Backdrop | `#050B18` radial to `#0d1c33` |
| Panel fill | `#0B1A33` at 95% |
| Panel border | 3px `#2E8BFF`, 6px radius |
| Row fill / alternate | `#10264A` / `#0D2140` |
| Focus fill | `#1A4A8C` + 3px `#FFFFFF` outline |
| Primary | `#2E8BFF`; focused `#5CA8FF` + white outline |
| Accent (favorite) | `#FF8A1F` |
| Text / secondary / disabled | `#FFFFFF` / `#9FB4D4` / `#5A6E8F` |
| Error | `#FF5A5A` |

Type: system UI stack only (no fetched fonts). Titles 28, tab 15, row title 16,
body 13–14, hint 11–12. The earlier 40/24/22/18 scale is retained as intent for
native 1080p; the preview scales down so the whole frame fits a laptop viewport.

## Frame

Single panel, header band with title **TRAINING** and a one-line honesty note,
then the four tabs, then a toolbar, then a two-column body, then a hint strip.
No MORE/PREVIOUS controls, no version or status text.

## Tabs

`LESSONS`, `WORKSHOP`, `MODS`, `FAVORITES`. Selected tab: `#12305C` fill and a 4px
blue underline. Keyboard: `Tab`/`Shift+Tab` reach the tab buttons; clicking a tab
resets search and the favorites-only filter and keeps per-tab selection.

## Toolbar

- Search field, placeholder **Search**, filters title, creator, category and goal.
- **Favorites only** toggle chip (`aria-pressed`).
- Right-aligned count: `N items · sample data`.

## List (left ~70%)

Rows are 64px with a 4px gap, scrollable with the mouse wheel and a 6px
`#2E8BFF` thumb on a `#13284A` track. Each row: 80×44 inline-SVG thumbnail, title,
`creator · category`, updated date, and a `★` when favorited.

- Selected row: focus fill plus white outline; the detail pane follows selection
  immediately.
- `↑`/`↓` move selection and scroll the active row into view (`block: nearest`).
- Clicking a row selects it.
- Empty states: no results → `No results for "…"`; empty favorites → `No favorites
  yet. Press F on any item.`

## Detail (right ~30%)

Inline-SVG preview, title, `by creator · category`, updated date, goal text, tag
chips, an honesty note, one primary button, and a favorite toggle. Primary labels
by tab: LESSONS `START`, WORKSHOP `DOWNLOAD`/`PLAY`, MODS `READ DETAILS`,
FAVORITES the item's own action.

## Favorites

Shared across all four tabs, keyed by item id, persisted in `localStorage` under
`mct.preview.favorites.v1`. Loading is defensive: missing key, unparsable JSON,
non-array payloads and non-string entries are all discarded without throwing, and
a storage failure (private mode, quota) degrades to in-memory favorites. The
FAVORITES tab is a live filter over lessons, maps and mods.

## Garage (second view)

Reached from the header. Full installed-catalog concept with sample data:
category chips for Body, Decal, Paint, Wheels, Boost, Topper, Antenna, Explosion,
Trail, Audio; search; tile grid; selected detail with a simulated **EQUIP**.
Installed-but-unsupported items are listed with reasons. No live car preview is
claimed; the preview art is a placeholder.

## Training options (third view)

In-session mock screen. Every option starts **on** (ghost, controller, inputs,
labels). No pre-launch options. Includes a **Show controller** switch: when off the
controller silhouette is removed entirely (`hidden`), not dimmed. The silhouette is
an original DualShock-style drawing as inline SVG with a transparent background,
plus demonstrative button highlights labelled preview only. No controller is read;
no raw input is displayed.

## Differences from the earlier Opus spec (owner review wins)

| Earlier spec | Implemented |
|---|---|
| Hide unsupported Garage items | List them under "Installed but unavailable" with reasons |
| Mods primary action `ENABLE`/`DISABLE` | `READ DETAILS` only |
| Downloading row with `42%` progress | No fabricated percentages or progress |
| Live car preview, right-stick orbit | Placeholder art; no live preview claim |
| Rajdhani/Inter webfonts | System stack; nothing fetched |
| Controller HUD only during a session | Options mock screen with show/hide toggle |
| 8 skeleton loading rows, error/retry states | Not simulated; no fake async states |

## Testing instructions

1. Open `docs/previews/training-browser.html` directly from disk; confirm no
   network requests in devtools.
2. Check all four tabs, search, favorites-only, `↑`/`↓`, mouse wheel, `Enter`
   (focuses the detail primary action), and that the detail pane follows selection.
3. Favorite items in LESSONS, confirm they appear in FAVORITES, reload and confirm
   persistence. Then set `mct.preview.favorites.v1` to `not json`, reload, and
   confirm the page still renders with empty favorites.
4. Open GARAGE and TRAINING OPTIONS; confirm the unavailable list and the
   controller toggle/highlight behave, and that no action claims a real effect.
5. Confirm no `ENABLE`, percentage, or success copy exists in the file.
