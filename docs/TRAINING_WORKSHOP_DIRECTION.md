# Training and Workshop product contract

Current owner-agreed product contract for Training, Workshop, Mods, Favorites and
Garage. It states requirements, not implementation status. Status lives in
[PROJECT_STATUS.md](PROJECT_STATUS.md); the current gap list is in
[NEXT_TASKS.md](NEXT_TASKS.md); the product specification is
[BUILD_SPEC.md](BUILD_SPEC.md); roles and coordination are in
[DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md). Nothing here is evidence that
a feature works in the real game.

## Training content model

- Every lesson has **12 distinct scenarios**, each mechanically appropriate to
  that skill. Scenarios are not cosmetic repeats of one setup.
- All 12 are eventually required for every lesson; do not silently drop a
  scenario from the release catalog.
- Most skills also offer a **simple practice** mode: free repetition of the
  mechanic without scenario progression.
- Core match scenarios are **custom-authored** for this product. They are not
  replaced by downloaded community packs.
- The non-overlapping flip-reset bands below resolve the example's shared endpoints.
  Propose and review the remaining skill-specific scenario cards before building
  a broad catalog; do not present an unreviewed or partial set as the finished 12.

## Power Shots

- The teammate makes a **real pass**; the keeper protects part of the goal.
- The player must aim with a proper angle and speed, and the attempt ends in an
  **actual goal or explicit feedback** — not an inert drill.
- Easier settings give more space and slower bots using **normal game physics**;
  harder settings add pressure. No fake physics or scripted outcomes.
- Downloaded/featured shot packs are not the core scenario source. Any pack
  route must be verified before it is offered as playable training.

## Flip resets

- Levels 1–4: solo, four distinct wall/approach starting points; the ball rolls
  up the wall and the player touches it out to reset.
- Levels 5–8: the same progression with a keeper.
- Levels 9–12: two defenders.
- Each level is a real, repeatable setup; difficulty comes from the situation,
  not from relabeling the same drill.
- Validate that the reset is actually acquired and that the outcome succeeds
  under normal physics. Skill difficulty per lesson is approximate, never a rank
  certification.

## Speed flip

- 12 meaningful kickoff situations, including different starting positions.
- Free practice is available alongside the kickoff scenarios.
- Do not fake variety by duplicating setups, and do not claim rank expertise or
  a verified expert demonstration that does not exist.

## Selection, entry and progression

- Lessons are entered **directly** with useful defaults; assistance and drill
  options live in the running session's **Training options**, not a pre-flight
  list of toggles.
- All lessons are selectable; there is no career gating of training content.
- After a pass the default is to **remain on the current level** until the player
  moves on manually. No progression gating.
- Level selection uses D-pad **Left = previous, Right = next**. These defaults
  are adjustable, not hard-locked.
- Training bindings are configurable and suppress conflicting stock Free Play
  actions **only inside a lesson**; stock behavior is restored outside. The
  earlier Left-D-pad ghost binding is obsolete.
- Physical DualShock 4 input must be tested before it is claimed.

## Session controls

- **Up = ghost toggle, Down = retry**, alongside Left/Right navigation. Adjustable
  defaults, not hard-locked.
- **Show controller: On/Off** displays a transparent DS4 silhouette with animated
  inputs, no fade mode, and must not overlap the boost HUD.
- **One Return action** goes home, saving the attempt and cleaning up, with no
  intermediate action pages.

## Attempt lifecycle

- Every attempt resets all actors — car, ball, bots — plus scenario logic, so a
  retry starts from the defined state.
- Use a deterministic seed where a scenario needs randomness.
- Input remains human. No AI takeover of the player's car.

## Ghost demonstration

- A ghost is **required**: a non-contact visual demonstration built from a
  verified successful trace.
- On toggle it starts from the beginning and repeats at normal game speed until
  switched off; off hides the ghost and its ghost inputs.
- The player's own controller display is toggled independently and shown
  distinctly from the ghost's.
- It must not affect collision, goals or scoring. "Invincible" here means
  non-physical and immune to interference — not an immortal solid bot.
- "Live demonstration" means rendered during play, not an AI driving the car.
- For shots and flip resets, the owner selected a fixed lesson starting position
  with its own faint, non-contact demonstration ball. Replay verified car and ball
  poses together so the correct contact remains visible if the real ball diverges.
  The demonstration ball is visual only, cannot score, and is visibly distinct
  from the playable ball. On/Off never resets or alters the player's attempt.
- A slight ahead offset remains appropriate for ground-move demonstrations only
  where the validated route and targets still align. Do not attach wall moves to
  a constant moving offset from the player.
- Never fabricate a "perfect" recording, and never claim a universal ghost.

## Tutorial video

- An optional in-game toggle opens the lesson tutorial.
- Source, rights and access must be verified before it is offered.

## Thumbnails

- Thumbnails are required for Lessons, Workshop and Mods, and the same item shows
  the same thumbnail in Favorites.
- Use a real, appropriate preview — not a generic graph or placeholder.
- Source, rights, caching and fallback behavior must be explicit.
- No unbounded downloads.

## Native browser

- One Training entry opens a large native blue bordered browser with four tabs:
  **Lessons**, **Workshop**, **Mods**, **Favorites**.
- Rows with a selected-item detail panel, search, and favorites across all
  content. Favorites combines entries from the other three tabs.
- No repeated More/Previous pages and no vertical list of action buttons.

## Mods

- Training-only. Activation requires a compatible, verified integration.
- Career isolation is mandatory; gameplay-changing mods stay off in Career.
- Browsing a plugin is not installing it, and listing is not certification.

## Maps

- Optional, download-on-demand; keep the base mod small. Display actual map download
  sizes and local storage use rather than promising that every map is small.
- Source rights must be established; preserve creator metadata and dates when
  known.
- Epic support requires its own separate verification.

## Garage

- Pending. Target: the full installed cosmetic catalog with search, filters,
  thumbnails, live preview, apply and restore.
- No account unlock or ownership change.
- Validate item/body compatibility; do not promise every historical licensed item
  is present in the current installed catalog. Preserve the normal preset.

Implementation status is tracked only in [PROJECT_STATUS.md](PROJECT_STATUS.md).
