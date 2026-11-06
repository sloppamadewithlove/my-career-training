# Actual flip-reset capture route — source investigation

Base: `c284df6a692e6334731766befbce80c62e4fe7e8`. No game operations, policy or
game-asset downloads, private-save reads, capture publication or successful real
flip-reset execution occurred in this investigation.

## Existing routes and inventory

The project catalog bundles no reference recording. A bounded recording-directory
inventory checked the default application location, this session's work area and
the prior session work area, excluding repositories/dependencies/build trees and
without opening career/save documents. All 63 flip-reset recordings found were
identifiable test fixtures; none was a non-test actual execution. This is a scoped
inventory, not a claim about every user directory. Raw captures and paths were
not copied into evidence.

`reference_capture.py` explicitly allows only canonical speed-flip, with
`cancel`/`baseline` profiles. Worker setup instantiates `SpeedFlipTrialController`;
its controls, setup fingerprint and evaluator are speed-flip-specific. Removing
the lesson-id check would not create a working flip-reset capture route.

Ordinary Human lessons already capture actual packet car/ball poses and
`last_input` actions. The detector requires an observed spent dodge, later
airborne availability transition, fresh attributed ball contact, nearby ball,
underside alignment, central airspace, excluded arena surface and continuous
packets. Its confidence is strong telemetry evidence; the packet exposes no
direct per-wheel contact event. This investigation does not relax that detector.
The owner has chosen another route rather than performing the demonstration.

Both pinned Necto and Nexto models, their license and CPU runtime were already
present and passed the project's provider-catalog checks. Their manifests claim
general aerial play, not demonstrated flip-reset execution. They are candidates
for a bounded bot experiment; no result is promised. Their existing license is
CC-BY-NC-SA-4.0; capture distribution permission remains a separate decision.
No new third-party bytes were acquired.

The official [v5 botpack](https://github.com/RLBot/botpack/blob/master/README.md)
offers source-backed offline bots and identifies licensing expectations. Its
[source map](https://github.com/RLBot/botpack/blob/master/.gitmodules) includes a
[v5 Necto/Nexto port](https://github.com/VirxEC/NectoFamily), but its existence is
not evidence of this lesson's successful reset. A training reward named flip
reset and a bot's TODO do not establish a working policy or compatible trace.
No public permitted complete successful trace for this lesson was established
by the bounded source search.

Video alone lacks sampled logical inputs and physics. The official
[RLBot replay guidance](https://wiki.rlbot.org/v5/botmaking/machine-learning-faq/)
describes tools that approximate inputs from replays. Such reconstruction cannot
be relabeled as observed `last_input`, and a match replay normally does not match
this lesson's reset state/version/variant. Public accessibility also does not
by itself establish redistribution permission.

## Shortest bot experiment from the installed source

Reuse the existing gated private bot-reference capture boundary, not Human input
injection. Add one explicit flip-reset profile with one designated mapped bot,
the unchanged canonical lesson setup, copied profile, allow marker and bounded
attempt count. Bind an already-verified provider or an original feedback
controller; observe/reset only the designated bot, retain Human clearance,
scope-loss shutdown and playback exclusion. The currently installed learned
provider API is `step(frame, player_index)`, whereas speed-flip capture calls
`step(elapsed_seconds, frame)`; that caller must be adapted explicitly.

Capture actual resulting physics/actions and stop after the bound. The policy
must really spend its original dodge and then regain availability at the ball;
the existing guard must not be weakened merely to accept a policy attempt.
If Nexto does not perform that maneuver, the next alternative is an original
closed-loop reset candidate, calibrated against actual bot physics. Neither a
schedule nor a simulation output is a real teaching trace. Do not repeatedly run
an unchanged policy hoping its metadata becomes success.

Persist any actual candidate with the existing private UUID/hash receipt,
`gate:not-evaluated` and `permission.distribute:false`. Independently check
sampled dodge -> touch -> availability chronology, orientation, geometry,
cadence, no intervening arena contact and a matching lesson setup. Then verify
the exact captured ghost live for synchronization and non-interference. No
existing speed-flip evaluator should certify flip-reset data.

This requires a separately reviewed source capture extension and a main-owned
offline test assignment. This investigation neither installs that extension nor
performs the experiment.

## Narrow capture improvement

`Recorder` previously discarded the per-sample jump/dodge/air-state and touch
values used by the detector. It now preserves available observed flags,
`dodge_timeout`, attributed `car_latest_touch` geometry/time/ball index,
the source game clock and available frame number. Touch copying excludes names
and unrelated fields. Existing car/ball/actions remain synchronized; evidence
fields are optional for old recordings and absent facts are not invented.
Validation rejects malformed optional evidence. No success detector, provenance,
permission, recording eligibility, controller or playback behavior is changed.

158 training, bot-reference and ghost checks passed; four native-executable
integration tests were skipped because those optional executable paths were not
set for this isolated source checkout. Ruff passed. Tests include the production
TrainingEngine detector -> exported recording path, missing optional fields,
copied observed values and malformed evidence. All fixtures are synthetic and
are never installed as teaching content. Source tests prove retention only;
they do not prove a real reset, live capture or game compatibility.
