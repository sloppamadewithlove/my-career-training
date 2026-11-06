# Next work and acceptance board

Updated 5 November 2026. Current source/check evidence is in [PROJECT_STATUS](PROJECT_STATUS.md). Do not confuse the current PR head with the last loaded candidate.

Current owner direction: reuse the game's native training menus, maps, HUD and
behavior; add custom lesson content and a successful synchronized ghost where
needed. Do not rebuild stock training behavior before checking its native route.

Exact live candidate `a59c45f` includes independently reviewed `1c21770` + correction
`d98ba04`, rooted at `ef94b24`. Candidate packaging/frozen smoke passed. The separate
**Rocket League Training** row reached stock **Play**, then manual Training and
Custom Training Created. Back reached the authored hub and Down moved focus to
Garage. Local New Sequence was visible, but no pack was created/saved or lesson
played; controller acceptance remains open. Later docs commits are not this tested
candidate. A saved inactive Career is allowed through the shared `lessonReady`
guard; live workers, pending results and pending Return remain gated.
See the [entry receipt](evidence/2026-11-05-stock-training-entry.md).

The defender-attribution source fix is independently reviewed (`d733917`, receipt
correction `41d3730`), with 232 focused checks passing. Exact `2c08e74` subsequently
passed full source/native/package checks and reached the authored hub/GC lesson
in an owned offline probe. Full Human-shot attribution and whole-level retry
remain unaccepted.

The terminal-score repair `eb1be7d` is independently reviewed with 268 focused
source checks. It blocks a reproduced late-score-after-timeout source defect;
it does not establish the cause of the observed live 1/2 to 2/2 transition.
It is included in packaged `a59c45f`; that menu-only run did not exercise its
gameplay behavior.

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
| Independent reviewer | Source and correction approved | Live behavior remains a separate acceptance gate |
| Owned tester | Native menu handoff passed on `a59c45f`; session ended | Next scope is one native lesson/editor gameplay loop and return, with fresh ownership and separate game-profile protection |

## Next proof sequence

1. Retain the exact `a59c45f` package and source/ABC provenance for the accepted
   authored hub to stock Training UI and responsive Back route. Rebuild only for
   a changed candidate or an acceptance question that requires it.
2. Separately prove native Custom Training/editor use and gameplay return before
   adding a lesson to that flow. Creating a native sequence can write a game-owned
   file even before manual Save; a copied MCT profile is not game-save isolation.
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
| T04 | Ghost — blocked on valid trace | Capture successful actual skill; validate car/ball/action trace. For shots/flip resets render at fixed lesson start with faint non-contact demonstration ball/controller; prove no effect on real attempt/physics/scoring |
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
