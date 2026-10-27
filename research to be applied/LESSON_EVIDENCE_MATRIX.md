# Lesson evidence before adding eight practice tiers

This matrix describes the frozen research source, not the installed game or current active checkout. Use [source provenance](source-provenance.json) and each report's hashes before applying changes. Passing a lesson is the implemented event rule below; it does not establish mastery of every instruction shown to the player.

| Lesson | Implemented completion | Main boundary to resolve |
| --- | --- | --- |
| [Power Shots](campaign/outcomes-01.md) | Authored scenario launch, fresh Human touch, target crossing and team-score increase with attribution gates. | [Diagnostic](campaign/outcome-probe-01.md) shows a later defender touch is omitted from latest-touch attribution. Only this lesson currently has twelve situations and eight authored pressure profiles. |
| [Speed Flip](campaign/speed-flip-01.md) | Ordered jump, diagonal-dodge and opposing-pitch evidence before crossing and landing. | Crossing and landing have no order relative to each other; effective cancellation, minimum speed and upright recovery are not graded. |
| [Flip Reset](campaign/flip-reset-01.md) | Newly regained flip-state inference after a spent flip and qualifying attributed touch/geometry. | No per-wheel contact signal; using the regained flip is not required. Fixed bounds and packet gaps affect the inference. |
| [Dribble & Flick](campaign/dribble-flick-01.md) | Carry-zone dwell, later qualifying touch with jump/dodge state, and goal-plane target event. | Carry is a geometric proxy; target crossing need not follow the flick. It is not an authoritative goal-score test. |
| [Shot Placement](campaign/shot-placement-01.md) | Player-attributed contact plus ball-center crossing of the chosen goal rectangle. | An uncertain gap contact can satisfy the name-based completion rule; the Contact stage uses stricter confidence. No authoritative score requirement. |
| [Fast Aerial](campaign/aerial-lesson-01.md) | One valid car-position sample inside the aerial gate sphere before timeout. | The instructed jump sequence, pitch, boost use and avoided backward dodge are not completion requirements. |
| [Aerial & Air-roll](campaign/air-roll-lesson-01.md) | Three gate spheres in order plus a valid landing event. | Air roll and orientation are not required; landing need not occur after the final gate. |
| [Fast Flight & Recovery](campaign/flight-recovery-01.md) | Two ordered gate spheres, a valid landing and grounded position in the recovery rectangle. | No speed/alignment threshold or continued-drive requirement; recovery can be emitted on a gap sample after earlier valid prerequisites. |

The seven non-Power-Shots lessons currently have fixed setups or variants rather than eight rank profiles. Keep the requested separate Bronze-through-Supersonic-Legend selection flow, then author and version each supported challenge profile. Include profile identity in selection, attempts, recordings and ghost compatibility. These are intended practice difficulties; no competitive-rank calibration was established by this campaign.

Builders should align instructional claims, progress stages and final success rules, explicitly define event order/confidence/deadline behavior, and add targeted near-miss coverage before calibrating challenge values. Preserve the user's lesson choices and direct tier selection; this research introduces no prerequisite locks.

[Forty selected lesson/worker checks](campaign/lesson-acceptance-tests-01.md) and [130 scenario/readiness cases](campaign/scenario-acceptance-tests-01.md) passed offline. The latter includes 96 profile-construction cases. Neither result proves all eight lessons or all tiers work in Rocket League; each report identifies its actual coverage and missing game acceptance.
