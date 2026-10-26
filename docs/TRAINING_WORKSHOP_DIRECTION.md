# Training and Workshop direction

Owner decisions, 25 October 2026. This is a design/implementation direction,
not a claim of completed gameplay, downloadable lessons or Epic support.
Existing acceptance and release status remain in PROJECT_STATUS.md.

## Owner playtest correction — 26 October 2026

This section supersedes the separate Training/Workshop navigation and preview
choices below. The owner tested the game and rejected the current experience:
Speed Flip and Power Shot behaved like empty Free Play, with no useful feedback,
automatic retry or teaching ghost. Catalog navigation checks did not establish
working training. Treat these as functional failures, not a visual polish pass.

- One **Training** home entry opens a large native blue bordered browser inspired
  by the supplied Training Browser reference. Four tabs: **Lessons**, **Workshop**,
  **Mods**, **Favorites**. Favorites combines entries across the first three.
- Use a scrollable row list with a selected-item detail panel, creator, updated
  date when available, description/preview, and a clear Play/Download action.
  Include search and useful filters. Do not replace rows with a vertical list
  of action buttons or require repeated More/Previous menu pages.
- Select a lesson and enter it directly. Put assistance and drill options inside
  the running session's Training options, enabled by default where implemented.
  No pre-flight list of toggles. Unavailable demonstrations must have an explicit
  explanation rather than an inert ghost button. Do not manufacture references.
- Speed Flip offers meaningful **Free practice** and **Kickoff practice** modes.
  Kickoff practice uses actual kickoff positions, including left/right starts;
  explain the scenario in the session instead of generic pre-entry Left/Right.
- Power Shot is a sequence of distinct scoring drills with intentional car/ball
  positions and ball movement, an actual goal target, success/failure feedback,
  and automatic retry after a miss/timeout. Goals must count. Left/Right moves
  between drills; keep lesson navigation separate from the ghost toggle. The
  older left-D-pad ghost binding needs remapping when shot navigation owns it.
- Latest Power Shot steering: use existing Psyonix training content or packs
  published/featured by Psyonix first, instead of building a large replay-scenario
  database. Group verified shot packs by their documented difficulty/rank;
  distinguish Psyonix-authored packs from featured community authors. Do not
  invent Gold/Diamond/Champion/Grand Champion/SSL labels or call a mixed mechanic
  rank pack a pure power-shot pack. Preserve actual creators and source links.
  Speed Flip is a mechanic lesson across ranks. Verify the supported in-game
  pack-loading route before offering Play; catalog metadata alone is not a lesson.
- Training Return is one action to the home page. No intermediate menu of
  additional actions may flash or become briefly selectable while leaving.
  Keep durable attempt saving and cleanup; immediate intent does not authorize
  dropping a result or claiming the hub was reached before it actually was.
- The controller display is an optional controller silhouette with animated
  inputs, no rectangular card or persistent technical labels. Use a simple
  **Show controller: On/Off** in Training options, no fade mode. Verify real USB
  DualShock 4 input. A stock Free Play Controls Display setting is not this HUD.
  Do not replace or relabel stock game settings as though they control our HUD.
- Keep normal game speed for lessons. Avoid exposing irrelevant development
  controls. Existing stock game settings are separate from our Training options.

The owner supplied four visual references: one Training Browser with tabs,
rows and a right detail panel; Garage references show cosmetic slot selection,
thumbnail inventory and a filtered item grid. Keep raw attachments private.
Opus 5.5 owns the Garage/controller visual specification and design review.
The owner permits DeepSeek to help with design **for this revision only**;
DeepSeek remains the implementation builder. This does not authorize Opus code.

### Garage design requirement for Opus

Replace repeated action-button pages with a searchable, filterable thumbnail
grid, category/slot tabs, selected-item details and a live car preview. Browse
the full product catalog available in the installed game, not only the player's
owned inventory. Include bodies, decals, wheels, boost, trails, toppers, antennas,
paint finishes/colors, engine audio and goal explosions, with compatible variants.
Apply supported offline visual overrides without changing account ownership.
Do not claim every historical/licensed product is present or compatible until
the installed catalog and actual equip path establish it. Show unsupported
items clearly; preserve the player's original preset and normal controls.

### Acceptance before the next player handoff

Verify a real Speed Flip attempt at the player's normal frame rate, a real
Power Shot goal and failed-shot retry, shot switching, visible feedback,
controller Show/Hide, and single-action Return. Separately verify the unified
browser, cross-category favorites and search. Tests alone are insufficient.
The owner subsequently handed the game back to main for restart and testing.
Use one recorded input owner and suspend automation if the player takes over.

Ranked community packs remain the requested Power Shot direction. The owner
declined substituting built-in Rookie/Pro/All-Star drills after the offline
download-service failure. Keep that unresolved capability visible; do not
present disabled or unverified pack loading as completed training.

## Training experience

- Players choose the skill they want to learn. Speed flip is the first complete
  lesson; aerials, dribbles, flicks, saves, half flips and other mechanics follow
  when each has a valid demonstration and lesson. A comprehensive library is
  the long-term goal, not current availability.
- A ghost demonstrates slightly in front of the player's car so its movement
  is visible. It is non-colliding teaching visualization and must not push the
  player's car or affect the ball. Its motion comes from an actual successful,
  validated recording; a personal attempt or synthetic path is not an expert
  demonstration.
- Left D-pad on a PS4 controller is the first toggle to try. On starts the
  demonstration from the beginning; Off immediately removes the ghost and its
  input display. The player can toggle it again whenever needed. Include an
  equivalent visible/settings control, synchronized with the same state. Check
  real input and existing bindings before claiming physical-controller support.
- Show the ghost's controller inputs synchronized with the demonstrated movement,
  including stick direction and analog triggers where recorded. Label ghost and
  player inputs distinctly if both are displayed. Never invent missing raw
  controller values from logical game actions. Adapt teaching labels to supported
  player bindings rather than silently assuming a universal button layout.
- No pause, speed or slow-motion controls are requested for ghost practice.
  The owner confirmed that the demonstration repeats until toggled off. Each
  repeat starts the recorded movement again with its inputs synchronized.
- Watch tutorial opens an optional in-game lesson video, with the move and
  controller inputs visible. Source and permission for recordings must be known.
  A schematic HTML preview is neither a tutorial recording nor proof of video
  playback in the game. Verify the actual native playback route before promising
  embedded video.
- A separate Match situation action is the desired practice progression:
  controlled starting states and bot positions let the player use the mechanic
  in a repeatable gameplay situation. Start with one concrete speed-flip scenario
  after isolated practice and correct teaching evidence work.

An engineering choice still needs evaluation: anchor a translated/rotated copy
of the recorded path slightly ahead at the start, then preserve its relative
motion. Do not continually drag the ghost to the player's car or alter timing to
stay ahead. For lessons involving ball/wall contact, preserve the demonstration's
spatial relationships; a separate ghost ball or fixed scenario may be required.
This is a feasibility proposal, not an owner-approved detailed motion contract.

## Menu previews

Use native-game-inspired dark blue panels with a clear blue border, legible text,
visible controller focus and scrollable items. Provide Rows and Grid in HTML
previews so the owner can choose before native menus are changed. Training should
show lesson selection and Watch tutorial / Practice with ghost / Match situation.
Workshop has exactly Training Maps and Mods as its two content tabs. Use original
artwork; do not redistribute game UI assets. Preview controls and sample content
must not suggest that real downloads, training or installation took place.

## Source baseline and research

At source checkpoint ce949226, `training/catalog.py` already defines speed flip
but has empty reference-recording lists. `training/coach.py` has watch/lead,
looping and recorded controller snapshots; its lead is a time offset, not the
requested spatial placement. `training/recordings.py` interpolates recorded
poses and sample-held actions and draws an oriented outline with a nose marker,
not a demonstrated translucent car mesh. Retain these building blocks while
validating the new visual representation, spatial placement and physical toggle.
None of this source inspection establishes live training acceptance.

Community entry points checked on 25 October:

- [Rocket League Steam Workshop](https://steamcommunity.com/app/252950/workshop/)
  for discovery and the user's Steam subscription/library path.
- [BakkesPlugins catalog](https://bakkesplugins.com/plugins) for optional mods.
- [Workshop Map Loader & Downloader](https://bakkesplugins.com/plugin/223)
  documents Epic compatibility, loading from a folder and downloading through
  [the community map catalog](https://bakkesplugins.com/maps). This is a candidate
  integration, not proof of My Career compatibility, permission to redistribute,
  installed-file preservation or arbitrary map availability.
- [Lethamyr's FAQ](https://lethamyr.com/faq) describes direct creator map downloads
  and an Epic loader, but its Underpass-replacement approach conflicts with this
  project's installed-map preservation rule. Do not adopt that loading method.

## Community content and storage

- Discover new community maps, especially Steam Workshop, rather than limiting
  browsing to the small installed collection. Include creator attribution,
  useful categories/search, favorites and installed/download state.
- Keep installer size down with a lightweight catalog. Download chosen maps and
  lesson videos when requested, show required/downloaded size and allow deletion
  and later re-download. Reuse existing installed Steam map files rather than
  copying the same package into the app. Shared textures/dependencies should be
  stored once where the supported loader permits. Compression is supplementary;
  it does not eliminate on-disk map size or justify bundling the whole catalog.
- Steam subscription/download and native launch need separate observed success.
  Current native Workshop launch remains an unverified development path.
- Epic access is a requested research question. Use legitimate creator-supplied
  packages or a verified loader/download route with appropriate permissions;
  do not assume Steam Workshop authorization or current My Career Epic support.
  Third-party loader support for Epic does not certify the full app on Epic.
- Browse BakkesMod community plugins in Mods, with download and Training enable/
  disable controls for integrations that have actually been reviewed and tested.
  Listing a plugin does not certify compatibility, redistribution or safe unload.
- Gameplay-changing community mods must not operate during Career. Keep optional
  downloaded mods off by default; enable only chosen compatible Training items.
  Leaving Training requires actual cleanup, or a controlled restart when a
  plugin cannot safely unload. An unchecked switch is not proof the code stopped.
  Do not unload or change unrelated user plugins silently.
- Ball-path prediction is off/excluded for now. A controller display may remain
  useful in Career; this exception is not finalized, so Career community mods
  stay disabled in the first design. Do not change the running game's mod state
  while another session owns it.

## Delivery order and open dependencies

1. Record these decisions and the agent roles in DEVELOPMENT_WORKFLOW.md.
2. Opus supplies visual mockups and layout specifications only. A builder
   implements the HTML/CSS/JavaScript preview and fixes its behavior. Main reviews
   the result; Luna tests it. Opus can review rendered visuals. Owner selects/
   refines before native UI implementation. Calling code a preview does not make
   it an Opus design-only assignment.
3. RunInfra's official documentation confirms the intended model and endpoint.
   A bounded authenticated request and subsequent builder runs returned the exact
   requested model. The credential is protected outside the repository; no other
   provider credentials or global login configuration were changed.
4. Build one complete speed-flip teaching path using a real validated reference;
   verify left D-pad input and ghost visibility in the actual game when available.
5. Expand Workshop discovery and on-demand acquisition, then test supported
   loading and Training-only mod lifecycle. Add Epic only after its own evidence.

The owner confirmed that the other demo session finished. Observing a process
does not convey input ownership: establish fresh ownership and follow the testing
skill before live testing or installed runtime changes. The source implementation
and its unverified parts are tracked in TRAINING_WORKSHOP_IMPLEMENTATION.md.
