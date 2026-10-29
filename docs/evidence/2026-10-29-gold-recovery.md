# Gold playtest and SDK recovery receipt

Date: 29 October 2026. Mode: source/native candidate `dca381786a8adfd00e436295b2a5d9e623585bee`, isolated copied save and Unicode profile. Main performed menu navigation; the owner took gameplay input after Gold started at 05:54:08 UTC. Automated game inputs stopped during the owner test. Owner later explicitly finished testing and authorized the replacement; the recorded owned game exited after a normal close request. Raw account-bearing captures, logs, saves and private paths remain private.

Observed route: real hub → Training → Lessons/Workshop/Mods → Power Shots → rank buttons → Gold. Saved pending Career incorrectly disabled starts from the hub; main cleared only the copied fixture through the actual recovery UI for this test. That restriction is fixed in later source and covered by save-preservation checks.

Owner failures: keyboard Up did not restart; challenge switching rejected input; scored goals returned to standard spawn; countdown was a drawn HUD timer rather than native game clock; both feeds too easy/similar; only two challenges. Neither feed is approved. Owner now requests one combined 12-challenge Gold set using Poquito Ground Shots and Skogur Powershot Practice as references, with varied feeds and a ground keeper.

## Cadence evidence and limits

Passive worker telemetry from this candidate reported ordinary Gold packets with `dt=0.0250091552734375`, `steps=3`, `gap=true`, reason `step_count_exceeded`; preparation examples had 7–9 such gaps among 14–15 samples. A saved Gold attempt had 320 gaps and invalidated technique attribution. Earlier TELEMETRY-01 documented the then-source limit of two normal physics steps and one strict-capture step; that is not a measured universal runtime guarantee.

Commit `312e298` accepts up to three **clock-consistent** steps in ordinary human training. Explicit transport gaps, wrong clocks/counts, four-or-more steps and strict-reference multi-step samples remain gaps. Tests include exact 0.025 and observed quantized intervals; strict capture remains one step. This is a candidate calibration from one PC/session, not proof every packet loss is harmless or that scoring is now live-accepted.

One step rejection persisted across 43 snapshots at unchanged game time; those are not 43 separate presses. Later telemetry entered Error/Recovery and blocked retry while waiting for fresh packets. Passive snapshots alone do not establish which physical press caused a given attempt transition. The owner report is the failure oracle; no contrary acceptance is claimed.

## Native behavior research

Installed pluginsdk.dll SHA256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`, REA/Ghidra 12.1.4, SDK-only analysis; no game executable/process inspected. Luna investigator exported the private retained evidence bundle and closed the target.

- ServerWrapper DisableGoalReset/EnableGoalReset exports both resolve to the same `RET 0` stub. Export evidence `ev_9455583198693fcd3b1cc189b844e7275358412899b54ebb64631e68b09de488`; body `ev_a713c35bcaeb66d4d64427cce1390206adb7fdc411b8cfbd33b64df208ac89d2`. They cannot implement Soccar kickoff suppression in this SDK.
- TutorialWrapper similarly named methods do write fields, but Disable also changes an extra field that Enable does not restore. Bodies `ev_beaa48152f29912ccf99b0415a96fb5edc3f82971e45130e1407e85e3769027b` and `ev_b2db6b49f1cc977e611d926a93d81001fd38ad79ae93e1b7cfa0eb1e55a33214`. Do not cast a Soccar event to Tutorial to reuse them.
- SetGameTimeRemaining writes a real float field: `ev_46b58860046271f240b805b56698adb88efa08252b032a49761ca3bd16654e4c`. Unlimited-time/overtime/goal-delay are separate real flag accessors. HUD effects and timer-expiry behavior remain runtime-unverified.
- SetScoreAndTime dispatches the actual Soccar UFunction; SDK evidence `ev_cc607ef5b00b0f2d6bdb55e70ee5ee021d40d59a0f05f954c4524c86813ab8cf` does not establish the target function's behavior.

Decision: do not add another drawn timer or rely on no-op reset APIs. Prove native timer/round behavior with the defender present before accepting it. The source control queue advances only after save acknowledgement and Active phase; stock kickoff suppression is a separate unresolved requirement.

## Research agents

Three named GPT-6 Luna Max lanes handled controls/testing, native REA, and public pack research. DeepSeek `deepseek-v4-1-flash-1017` completed pack comparison (4,697 total tokens, reported $0.00230295) and scoped timer synthesis (1,208 prompt / 3,948 completion, reported $0.00255). Main independently checked source evidence; model suggestions are not runtime observations. Two other bounded transition/boundary builder responses ended at their output limit and are not approvals.

Psyonix lists Skogur Powershot Practice as Gold, code C9E4-0F05-B71A-C322: https://www.rocketleague.com/news/training-pack-refresh--shoot-your-shot- . Poquito Ground Shots code 6EB1-79B2-33B8-681C is confirmed by https://www.rocketleague.com/news/community-spotlight-april-2017 . Current actual shots/counts still require inspection; do not fabricate their geometry from titles.
