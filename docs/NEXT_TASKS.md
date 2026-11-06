# Next work and acceptance board

Updated 5 November 2026. Current source/check evidence is in [PROJECT_STATUS](PROJECT_STATUS.md). Do not confuse the current PR head with the last loaded candidate.

Current owner direction: reuse the game's native training menus, maps, HUD and
behavior; add custom lesson content and a successful synchronized ghost where
needed. Do not rebuild stock training behavior before checking its native route.

Exact live candidate `a59c45f` includes independently reviewed `1c21770` + correction
`d98ba04`, rooted at `ef94b24`. Candidate packaging/frozen smoke passed. The separate
**Rocket League Training** row reached stock **Play**, then manual Training and
Custom Training Created. Back reached the authored hub and Down moved focus to
Garage. In that menu-only run, local New Sequence was visible without creating
or saving a pack. Physical controller acceptance remains open. Later commits are
not this tested candidate. A saved inactive Career is allowed through `lessonReady`;
live workers, pending results and pending Return remain gated.
See the [entry receipt](evidence/2026-11-05-stock-training-entry.md).

A separate `a59c45f` probe played an existing local native Striker sequence:
W moved car/ball and showed 0:07, then a later initial scene at 0:10 suggested
timeout reset. Backspace at the initial state had no visible effect, so manual
reset is unaccepted. Escape exposed MCT pause with disabled Return and no native
exit. Reviewed repair `3b9ef72` delegates native Custom Training/editor pause to
the stock classes; it is source-tested only and needs a fresh exact-candidate
build. The local sequence file was unchanged and the owned run exited/restored.
See the [pause repair receipt](evidence/2026-11-05-native-custom-training-stock-pause.md).

Experimental `a983c61` supplies a reviewed pure drawing-diagnostic frame core;
synthetic checks and CMake/CTest 1/1 passed. It has no live renderer, registration,
arm route, replay or teaching availability. Before any live adapter, prove callback
ownership/thread/unload semantics. Teaching playback additionally needs native
reset/clock identity and a permitted validated successful car/ball/input trace
at the fixed scenario start. See the [core receipt](evidence/2026-11-05-native-draw-diagnostic-core.md).

The defender-attribution source fix is independently reviewed (`d733917`, receipt
correction `41d3730`), with 232 focused checks passing. Exact `2c08e74` subsequently
passed full source/native/package checks and reached the authored hub/GC lesson
in an owned offline probe. Full Human-shot attribution and whole-level retry
remain unaccepted.

The terminal-score repair `eb1be7d` is independently reviewed with 268 focused
source checks. It blocks a reproduced late-score-after-timeout source defect;
it does not establish the cause of the observed live 1/2 to 2/2 transition.
It is included in packaged `a59c45f`; the native UI/sequence probes did not
exercise that MCT gameplay behavior.

For retained custom-lesson diagnosis, retain settled rank/scenario, attempt identity, score
packets and automatic/manual command acknowledgements around timeout and retry.
The GC probe observed defender contact with no input, native clock stuck at
0:01, car/ball retry with 0–1 retained, then an unexplained automatic challenge
change. Do not infer a cause or require scoreboard zeroing without a product
decision. Verify the whole actor/scenario reset and native zero behavior.

Return reached the authored hub. Authored Quit needed the documented owned
WM_CLOSE fallback; final process exit and original-save/plugin/config/game-file
restoration checks passed. Normal authored Quit completion still needs acceptance.
See the [source repair receipt](evidence/2026-11-05-terminal-goal-progression.md).
Re-establish current process and input ownership before any game action; this
board does not grant ownership of a previous session.

## Active assignments

| Owner | Bounded work | Acceptance / next action |
| --- | --- | --- |
| Coordinator | Hand off one exact reviewed candidate | Name source, compiled movie and packaged revision separately; assign one input owner for a bounded live session |
| Native-entry builder | Source handoff and saved inactive Career correction complete | `1c21770` + `d98ba04` reviewed; no game control or package build performed |
| Native pause builder | Stock Custom Training/editor delegation reviewed | `3b9ef72` source/owned movie checked; stage its new pause ABC before packaging |
| Independent reviewer | Native entry and stock-pause source approved | Live behavior remains a separate acceptance gate |
| Owned tester | `a59c45f` local sequence probe ended/restored | Next: exact stock-pause candidate, native resume/exit, displaced-state reset and Career pause regression; fresh ownership and game-profile protection required |

## Next proof sequence

1. Stage the reviewed stock-pause ABC and build its exact new revision; do not
   reuse the old `a59c45f` package. Keep the earlier accepted menu handoff distinct.
2. Prove native pause/resume, the applicable stock exit confirmation and actual
   destination, plus a normal Career pause/Return regression. Preserve native
   save/discard/cancel choices where applicable. Observe native reset
   from a displaced state separately. A copied MCT profile is not game-save
   isolation; preserve game-owned profile rotation and native save prompts.
3. Keep custom lesson and ghost work bounded to additions the native flow needs.
   Preserve unresolved custom countdown/reset/goal and physical-controller checks
   as explicit limitations; a successful stock screen does not close them.
4. Expand only after the representative native lesson loop works. Update the
   website for verified major releases, not this source candidate.

## Product backlog

| ID | Outcome / state | First proof / next action |
| --- | --- | --- |
| T01 | Power Shot situation — planned | Rework the rejected provisional feeds and prove useful pass geometry; Bronze/Silver solo, Gold/Platinum ground keeper, Diamond/Champion one advancing defender, GC/SSL two; verify human shot, feedback, whole-level retry and Return |
| T02 | Scenario lifecycle — planned | Stable IDs, actor roles, reset/settle, seeds, success/failure; prove switching removes old bots/timers |
| T03 | DS4 controls — planned | Adjustable Left previous/Right next/Up retry/Down supported ghost only in lessons; physical USB DS4, stock-conflict suppression, boundaries 1/12 and 12/12, restore outside |
| T04 | Ghost — blocked on valid trace and native lifecycle | `a983c61` is pure diagnostic preparation only, with no renderer or teaching feature; prove native callback/reset lifecycle, then capture/validate successful synchronized car/ball/actions at fixed lesson start; verify no effect on real physics/scoring |
| T05 | Twelve situations per skill — planned | Review distinct scenario cards after first full loop; flip reset 1–4 solo/5–8 keeper/9–12 two defenders; no cosmetic duplicates |
| T06 | Thumbnails — planned | Parallel builder after item/image contract; real gameplay lesson thumbnails and correct map/mod images, bounded cache, honest fallback |
| T07 | Browser — partial | Three tabs compiled and native-tested; verify search/scroll/details/primary/Back via mouse/keyboard/DS4; fix redraw flicker |
| T08 | Workshop use — browsing only | One legitimately obtained compatible map loads/plays/returns/restores without replacing stock assets; then download/cache; Epic separately |
| T09 | Mods — browsing only | One compatible helper download/enable/disable, training-only scope and cleanup; no arbitrary auto-execution/career gameplay changes |
| T10 | Garage — planned | Opus design, builders implement installed catalog/search/filter/images/preview/apply/restore; one full equip path before expansion |
| T11 | Controller/tutorial — partial/planned | Opus reviews DS4 silhouette avoiding boost HUD; builder fixes; distinguish human/ghost inputs; permitted in-game tutorial |
| T12 | Career/release regression — partial | Changed-boundary checks; exact frozen match/result/save/next/Return/install/recovery before release; 12-second continuation target unachieved |
| T13 | Build/startup efficiency — partial | Both CI concurrency layers preserve the active candidate and retain newest pending work; validate completion under subsequent updates. Further runtime-input equivalence/cache work must preserve exact provenance |
| T14 | Privacy/security — unresolved | Privately classify historical path/email and source literals; propose cleanup without automatic history rewrite; separately audit dependencies/workflows/releases |


Ghosts remain lesson-specific and require valid recordings. Browser tabs are Lessons / Workshop / Mods; Favorites is removed. Up retries, Down toggles a supported ghost, Left/Right selects challenges. A live Career match must be left/ended before Training; a saved schedule does not restrict it. Results await explicit Next or Return. Major verified releases update the Vercel website; draft source changes are not public release claims.
