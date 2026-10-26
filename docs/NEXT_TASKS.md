# Next work and acceptance board

Updated 26 October 2026. Main owns this board. Read current status before assigning work.
Ask unresolved product questions before broad implementation; never repeat confirmed
ones. EVERY unique function uses the six-part contract in DEVELOPMENT_WORKFLOW.md.

## Priority

This update consolidates instructions, blueprint and future-original licensing; it does
not implement runtime scenarios. Next recommended outcome: one real Power Shot pass/keeper
situation, then a validated ghost, before scaling to 12 scenarios. No game-input owner or
runtime worker is assigned by this document.

| ID | Outcome / state | First proof / next action |
| --- | --- | --- |
| T01 | Power Shot situation — planned | Agree first geometry/target; real teammate pass, keeper, human shot at normal physics; verify goal/miss feedback, whole-situation retry and Return |
| T02 | Scenario lifecycle — planned | Stable IDs, actor roles, reset/settle, seeds, success/failure; prove switching removes old bots/timers |
| T03 | DS4 controls — planned | Adjustable Left previous/Right next/Up ghost/Down retry only in lessons; physical USB DS4, stock-conflict suppression, boundaries 1/12 and 12/12, restore outside |
| T04 | Ghost — blocked on valid trace | Capture successful actual skill; validate car/ball/action trace. For shots/flip resets render at fixed lesson start with faint non-contact demonstration ball/controller; prove no effect on real attempt/physics/scoring |
| T05 | Twelve situations per skill — planned | Review distinct scenario cards after first full loop; flip reset 1–4 solo/5–8 keeper/9–12 two defenders; no cosmetic duplicates |
| T06 | Thumbnails — planned | Parallel builder after item/image contract; correct lesson/map/mod images and Favorites consistency, bounded cache, honest fallback |
| T07 | Browser — partial | Actual tabs/search/scroll/favorites/details/primary/Back via mouse/keyboard/DS4; fix redraw flicker |
| T08 | Workshop use — browsing only | One legitimately obtained compatible map loads/plays/returns/restores without replacing stock assets; then download/cache; Epic separately |
| T09 | Mods — browsing only | One compatible helper download/enable/disable, training-only scope and cleanup; no arbitrary auto-execution/career gameplay changes |
| T10 | Garage — planned | Opus design, builders implement installed catalog/search/filter/images/preview/apply/restore; one full equip path before expansion |
| T11 | Controller/tutorial — partial/planned | Opus reviews DS4 silhouette avoiding boost HUD; builder fixes; distinguish human/ghost inputs; permitted in-game tutorial |
| T12 | Career/release regression — partial | Changed-boundary checks; exact frozen match/result/save/next/Return/install/recovery before release; 12-second continuation target unachieved |
| T13 | Build/startup efficiency — planned | Helpers validate interpreter/import root/toolchain before work; measure build/launch/review waits and optimize measured bottleneck |
| T14 | Privacy/security — unresolved | Privately classify historical path/email and source literals; propose cleanup without automatic history rewrite; separately audit dependencies/workflows/releases |

## Material details still open

- Exact first Power Shot geometry and remaining 12-level cards. Teammate pass+keeper,
  mechanically different setups and increasing pressure are approved.
- Ghost placement is resolved: shots/flip resets use fixed lesson start and a faint
  non-contact demonstration ball. Do not ask the owner to choose this again.
- Tutorial/thumbnail sources and rights; unavailable media must be described honestly.
- Visibility and attribution are resolved in LICENSE/status; do not reopen by default.

## Known failures to reuse

| Failed approach | Evidence / confidence | Next distinct experiment |
| --- | --- | --- |
| Static Free Play as Power Shot | Owner observed no meaningful shot/feedback; rejected | T01 real pass/keeper; no relabeling |
| Offline exact-code pack load | 5b293d2 FeatureDisabled, stayed frontend; high confidence for that route | Custom scenarios; revisit packs only with different supported route and real launch proof |
| Strict capture never settled | Actual packet gaps; ordinary-preparation fix is not trace validation | Measure acquisition/timing; prove successful reference without weakening truth checks |
| Search dropped focus/edits | Fixed through 099fad1 with live slow typing/Escape | Reinvestigate only if current candidate reproduces |
| Build imported another checkout | Mismatched allowlists; explicit project path resolved | T13 import-root guard before expensive build |

After two failures of the same hypothesis, record expected/actual, evidence, cause
confidence and a different next experiment. Keep raw logs private; don't create another
general history file or abandon the goal merely because two tries failed.

## Assignment / receipt

Task ID, outcome, base revision, owned files, interface, dependencies, actual worker/model,
time/token/cost bound, acceptance and failure cases. Return immutable patch, actual checks,
evidence, risks and next action. Independent review precedes integration; main releases
file ownership and updates this board/status at handoff. Planned, implemented, unverified,
verified and blocked are distinct. A preview is never gameplay proof.
