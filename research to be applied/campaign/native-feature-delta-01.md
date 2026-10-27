# NATIVE-FEATURE-DELTA-01 — current native feedback and regression leads

## Evidence scope

Official documentation checked on 27 October 2026. This report adds native
feedback and regression leads to the earlier stock-training settings research.
Published release notes describe the product; they do not identify the loaded
local executable, prove an API exists in the pinned SDK, or establish behavior
in an MCT-created match. No game, account, settings or plugin action occurred.

The pinned MCT source remains the frozen research snapshot described by
[source provenance](../source-provenance.json). Existing findings below are
linked to their source audits, rather than re-described as new measurements.

## Native features worth evaluating

| Documented feature | Official evidence | MCT benefit and evidence boundary |
| --- | --- | --- |
| Reset acquisition cue | March 10 v2.66 documents a configurable audio/visual reset cue and describes acquisition through contact by at least three wheels. Visibility differs between the acting player, spectators and replays. [Release note](https://www.rocketleague.com/news/rocket-league-patch-notes-v2-66) | Compare the cue with the [inferred detector](flip-reset-01.md) during a future owned test. Search for an exposed acquisition event or state separately. Do not infer a callable event name or wheel-contact API from the release note. |
| Car/ball velocity graphs | June 9 v2.70 documents a settings-controlled velocity overlay for matches and training. [Release note](https://www.rocketleague.com/news/rocket-league-patch-notes-v270-season-23-live) | Could provide native visual context alongside measured shot feedback. The note does not specify axes, units, filtering, sample cadence or event timing. It cannot replace MCT's attributed touch/target/score chain. |
| Vehicle hitbox display | The same v2.70 note limits its hitbox overlay to offline Freeplay. [Release note](https://www.rocketleague.com/news/rocket-league-patch-notes-v270-season-23-live) | Useful for contact-geometry teaching if available in the actual training context. Ordinary MCT requests Soccar with Freeplay false; do not assume availability. Current ghost wireframes are generic outlines, not this native active-hitbox visualization. |
| Configurable scoreboard events | September 21 v2.76, scheduled for September 22, adds per-mode scoreboard stat choices including reset counts. [Release note](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276/) | A possible corroborating aggregate for practice sessions. A count change does not identify the exact touch, event time, actor instance or attempt; establish the source and reset boundaries before comparing it with lesson results. |
| New camera/control defaults | v2.76 documents revised keyboard/mouse defaults and a free-look mode also available to controllers. [Release note](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276/) | Test prompts and camera-relative teaching against actual chosen bindings. A logical action sample does not identify a physical button, control preset or camera mode. Avoid silently resetting user controls. |
| Boost-pad recharge mutator | v2.76 adds a recharge-rate mutator. [Release note](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276/) | Add the effective value to the setup/compatibility audit if a lesson uses boost-pad timing. A normal game-speed value alone does not establish the pad policy. No enum value or current local setting is inferred here. |

Earlier research already covers the 2026 pack randomization, grounded-spawn,
round-start delay, car-velocity/pitch and boost-setting additions. See
[stock mode distinctions](../initial%20findings/stock-training-modes-research.txt)
and [native settings route](stock-training-settings-01.md). These features
should not be rediscovered as BakkesMod-only capabilities.

## Regressions that change the acceptance plan

The official issue page fetched without a language query reports an October 20,
2026 update. It lists a previous reset-indicator display failure despite a
successful reset, resolved in v2.67; mirrored pack cars spawning into the ground,
resolved in v2.76; and lingering private-match settings after exit, resolved in
v2.78. These are documented historical fixes, not reproduced local failures.
[Issue history](https://www.rocketleague.com/known-issues)

Consequences for MCT are proposed acceptance checks, not claims about game
implementation:

- Observe acquisition flags, attributed contact and the cue together. Test the
  cue disabled as well as enabled. Absence of a visual cue must not alone fail
  the lesson, and its presence must not override stale or ambiguous telemetry.
- Confirm both ordinary and mirrored starts after the state write. Check the
  actual grounded pose, ball spin, roster and launch state rather than accepting
  a successful dispatch as a valid start. Include elevated starts separately.
- Record selected/effective mutators before and after Return and after another
  activity. Match setting persistence belongs in session restoration acceptance.
  Do not diagnose a current MCT leak solely from a historical game bug.
- Keep rendered garage appearance separate from catalog/code acceptance. The
  current garage research has no visual proof; inspect the requested item in
  its intended scene before marking an appearance test passed.

The language-query variant of the issue page returned a September 25 update
while the unqualified page returned October 20. Preserve access date and exact
URL in future receipts; a cached page variant can describe an earlier state.
Neither page proves the local client has the corresponding patch installed.

## Research and integration sequence

1. Identify the native setting/event surface in current local artifacts or
   pinned primary SDK declarations. Retain binary/source hashes and label
   wrappers, engine implementation and UI declarations separately.
2. Build a small observation-only experiment if an appropriate public surface
   exists. Separate its builder and reviewer, and avoid broad hook attachment
   or live calls during another chat's game session.
3. In a later owned test, bind observations to the exact executable, active
   match, Human actor, map, mutators and attempt. Compare timestamps and record
   missing or contradictory evidence explicitly.
4. Add settings only after their supported context and observed state are
   established. Native rendering can improve presentation while MCT retains
   its lesson/rank identity and measured result contract.

These are candidates for further research, not implementation-ready API
contracts. No native cue, graph, hitbox or scoreboard adapter was built or
game-tested in this pass.
