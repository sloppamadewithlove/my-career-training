# Current project status

## Current recovery work

See [issue #8](https://github.com/sloppamadewithlove/my-career-training/issues/8) and branch `fix/training-browser-career-stability`. The eight-hour REA campaign is on `research/rocket-league-2026-10-27`, under `research to be applied/`; it is research evidence, not game acceptance. Existing unpublished scenario/menu work is under selective salvage assessment.

The first patch stops Career team mutations after the SDK reports match end and corrects a CI test that wrongly expected a valid boolean preference to fail. Separate DeepSeek source review found no blockers for those two deltas. GitHub CI and exact-candidate gameplay are pending. This does not yet prove the reported automatic-lobby failure fixed: stale bridge intervals can revoke the results timer hold. No new release or local game pass is claimed.

Current requirements: three Training tabs (Lessons/Workshop/Mods), no Favorites UI, lesson then rank then 12 challenges per rank; Up retries, Down toggles a supported lesson-specific ghost; clean Power Shots HUD; results wait for an explicit choice. Historical checkpoint details below retain their original evidence scope.


Updated 26 October 2026. Current entry point, not a release claim.
Next: [task board](NEXT_TASKS.md). Product: [blueprint](BUILD_SPEC.md) and
[Training/browser contract](TRAINING_WORKSHOP_DIRECTION.md). Process:
[workflow](DEVELOPMENT_WORKFLOW.md).

## Checkpoint

- Source before this documentation/license update: `4a62ad5`, branch
  `fix/windows-startup-and-download`.
- Last live source/native candidate: `099fad1`. Test game closed. Fresh sessions must
  establish current ownership; this note grants none.
- Final menu checks: 87 passed, one skipped; native checks: 48 passed. These do not
  prove working scenarios, ghost, physical DS4 input, installer or complete release.
- The 24 October Windows ZIP failed player testing. Do not promote it as fixed.

The subsequent workflow/blueprint update used two isolated DeepSeek builders and
independent Luna reviews. Official skill validation, relative links and Hatch
license metadata passed. Historical status/workflow/direction/design notes were
archived; no game or binary change was tested or claimed in that update.

## Capabilities and limits

| Area | Evidence / state | Remaining acceptance |
| --- | --- | --- |
| Browser | Native blue Lessons/Workshop/Mods/Favorites; rows/details/search and persisted cross-content favorites observed. 099fad1 slow search and immediate Escape passed | Real thumbnails; redraw flicker; physical-controller navigation |
| Speed Flip | a7de7b4 actual Start reached prepared drill with target/instructions; no-dodge timeout and auto-retry observed | Successful skill, timing despite packet gaps, 12 scenarios, teaching ghost |
| Power Shots | Six real Psyonix-featured pack metadata entries; 5b293d2 actual load returned Training/GetTrainingData FeatureDisabled offline | No accepted Power Shot gameplay. Custom pass/keeper scenario is now core; blocked packs supplement it |
| Scenarios | Owner requires 12 distinct situations per skill, usually plus simple practice; flip reset 1–4 solo, 5–8 keeper, 9–12 two defenders | Not implemented/tested. Rank labels do not replace scenario design |
| Ghost/tutorial | Non-contact repeating successful demonstration and synchronized controller required | No validated reference or accepted ghost/tutorial; personal timeout recording is not an expert demonstration |
| Options/Return | a7de7b4 Controller Off visibly removed silhouette; one Return reached fresh frontend READY, actual RootMenuMovie and visible hub | Physical DS4, full settings; silhouette overlaps boost gauge |
| Workshop/Mods | 5e3ba56 browsing: 30 Steam maps, 16 Bakkes maps, 16 plugins; a7de7b4 unified Mods loaded 16 entries | Browsing is not map launch/plugin activation; prove each route, training-only scope and restoration |
| Garage | Full installed catalog/search/filter/thumbnails/preview/apply/restore required | Owned-inventory/button flow rejected; replacement not accepted |
| Career | Historical source/frozen match/result/save/Return evidence in archive and dated receipts | Exact-release regression still required; no certified bot ranks |
| Distribution | Source Windows/Steam development route tested | Epic, latest frozen bundle and installer need separate acceptance |

## Owner decisions

Custom scenarios teach useful match moments: real passes, keepers/defenders, mechanically
appropriate setups, whole-situation resets. Community packs supplement them. No built-in
Rookie/Pro/All-Star substitution requested. Configurable training-only defaults:
Left previous, Right next, Up ghost, Down retry. Stay on current level after success
unless the player selects next. These are documented defaults, not implemented DS4 proof.
Real thumbnails required in Lessons/Workshop/Mods and reused in Favorites.
For shots and flip resets, the owner selected fixed-start ghost car and faint
non-contact demonstration ball, independent of the real attempt. This is a requirement,
not a working implementation.

Repository stays public by explicit choice. Future original changes are not offered
under MIT; approved public attribution is Slava Porollo. Prior grants and third-party
notices remain intact. See LICENSE.

## Preservation / privacy

After last test cleanup, checked career/settings/BakkesMod files and installed
executable/menu hashes matched baseline. Game saves had one changed save and one replaced
filename with a same-size save present; game-written files retained, private baseline kept.
No byte-identical game-save restoration claim.

Previous reachable-history scan found no supplied-key/private-key matches. A historical
personal home path and unclassified author email remain published; focused check found
the email in 29 commits on both remote and HEAD. No history rewrite. Two source email
literals remain unclassified. Issues, CI logs, releases and a full malware/dependency
audit were outside that scan. Do not call the repository/history completely clean.

## Historical evidence

[Previous status](archive/2026-10-26/PROJECT_STATUS.md) retains exact revisions/outcomes.
[Previous workflow](archive/2026-10-26/DEVELOPMENT_WORKFLOW.md) retains timings and earlier
improvements. Read only for a specific diagnosis; current task cards own next experiments.
