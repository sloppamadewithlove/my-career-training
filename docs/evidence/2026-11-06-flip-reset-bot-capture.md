# Bounded installed-policy flip-reset capture — source only

Base: `ef585ef4e2c55ba8ba54fd47de74668aecb60565`. This adds a real capture path
for an experiment with the installed pinned Nexto policy. It supplies no recorded
execution and makes no claim that Nexto can perform this lesson's reset. No game
operations, downloads, private-save inspection or publication were performed.

## Experiment contract

1. Preconditions: source checkout, verified installed Nexto model/license/CPU
   runtime, owned offline Steam session, process-bound copied private profile,
   existing operator allow marker and matching `MCT_REFERENCE_CAPTURE_PROFILE`.
   The current game/EAC compatibility and input ownership must be established by
   main before a real test. Packaged builds and ordinary lesson requests cannot
   enable this capture.
2. Input: the private worker start request selects `lesson_id:"flip-reset"` and
   `reference_capture:{profile:"flip-reset-nexto",trial_id:<canonical UUID>}`.
   Only canonical lesson variation is allowed. Controller parameters, arbitrary
   provider selection, ball-launch scenarios, Career, Workshop and calibration
   are refused. No public UI action was added.
3. Actual state behavior: one designated bot is index 0, team 0; the uncontrolled
   Human remains index 1 and is team 1 so Nexto receives its expected opposing
   player observation. Only bot 0 is mapped, reset or sent inputs. The existing
   Human-clearance, marker, mapping, observed bot and scope-loss gates remain.
   On Go, the adapter passes the actual complete observed frame to the existing
   `policy.step(frame,0)` API. No elapsed-time script or intended policy output
   is substituted for observed packet physics or `last_input` in the recording.
4. Persist: the existing private `reference-candidates` UUID file and exact hash
   receipt retain `gate:not-evaluated` and `permission.distribute:false`.
   Successful metadata must match the finished canonical engine attempt and
   its single `reset_acquired` event, strong telemetry confidence, all detector
   evidence booleans, summary event and exported success evidence. Missing or
   mismatched evidence refuses persistence as a success. Failures may be retained
   as private diagnostics. This consistency guard is not independent validation
   or proof of per-wheel contact; no reference is promoted or bundled.
5. Failure/recovery: normal observed game speed and continuous capture packets
   are required before sending flip-trial controls. Missing standard-arena boost
   telemetry or unavailable policy fails explicitly. There is one initial reset
   and one attempt, with no retries even before completion. The existing engine
   and controller stop at the canonical 12-second game bound. An independent
   120-second wall limit includes startup and stops capture even if game time or
   incoming packets stall. Attempt completion stops the owned worker/runtime;
   another experiment needs a new scoped request. Existing shutdown/restoration
   still requires exact-candidate live acceptance.
6. Proof: 289 focused Python checks passed; four optional native parser/menu
   executable checks were skipped because their paths were unset for this
   isolated source checkout. Ruff and diff checks passed. Tests cover source
   gates, real installed Nexto CPU inference on a synthetic full packet, exact
   provider call API, designated-bot control/Human exclusion, speed/gap refusal,
   initial-reset quota, wall deadline, event consistency, private persistence,
   completion cutoff, worker regressions and existing speed-flip behavior.
   Synthetic tests are not teaching recordings. No DLL/package or live capture
   is established by these checks.

The independent-review deadline correction uses the same absolute trial budget
through setup, model loading, core verification/creation, connection completion,
match acknowledgement and the active loop. Connector/wait slices are capped by
the remaining budget; a late configuration callback cannot mark acknowledgement.
Checks after synchronous startup work prevent progression when it returns after
the deadline. Such a synchronous call itself must return before Python can
perform cleanup; this is not an ability to preempt a blocked native library.
The regression delivers the actual matcher callback at simulated elapsed130
seconds after fifty seconds of prior startup: the flip trial refuses it despite the matcher's
fresh ninety-second timeout, while ordinary/speed-flip sessions retain their
existing timeout and user cancellation still takes precedence.

## Remaining acceptance

Main must independently review this exact source, coordinate one current owned
offline test and inspect the actual resulting candidate. A useful reset still
requires the existing prior-dodge, attributed touch, airborne availability,
underside/proximity, surface exclusion and continuous-packet evidence; those
guards are unchanged. If the installed policy does not perform the maneuver,
the result is a failed experiment. Change the hypothesis or implement an original
feedback candidate before repeating; do not turn the failure into a successful
recording label. Rights to distribute and exact ghost synchronization/non-contact
acceptance remain separate from obtaining a candidate.
