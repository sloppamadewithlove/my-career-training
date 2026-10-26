# Training and Workshop direction

Owner decisions, 25 October 2026. This is a design/implementation direction,
not a claim of completed gameplay, downloadable lessons or Epic support.
Existing acceptance and release status remain in PROJECT_STATUS.md.

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
2. Opus produces HTML layout previews; main checks honesty, behavior and fit to
   the owner's request. Owner selects/refines before native UI implementation.
3. RunInfra's official documentation confirms the intended model and endpoint;
   configure private credentials and verify an actual bounded request before
   delegating paid building work. No supplied/configured API key at this point.
4. Build one complete speed-flip teaching path using a real validated reference;
   verify left D-pad input and ghost visibility in the actual game when available.
5. Expand Workshop discovery and on-demand acquisition, then test supported
   loading and Training-only mod lifecycle. Add Epic only after its own evidence.

The other session's demo recording must finish before this session acts inside
the game or alters installed runtime files. Observing a process does not convey
input ownership. Keep research, HTML previews and source documentation independent
of that session; arrange a handoff before live testing.
