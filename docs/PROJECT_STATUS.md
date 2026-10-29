# Current project status

Updated 29 October 2026. GitHub is canonical. PR #10 remains draft; no new release
or owner-accepted Gold playlist is available.

| Evidence | Exact revision and scope |
| --- | --- |
| Current source | `7ba05345cb2451d95dbbde64301d7c0ee4024d13`; Windows native CI passed |
| Last loaded candidate | `af8871d1c8703b7d6880648578bfaab0a1cf6974`; replacement rejected by owner and normally closed |
| Current game | Ordinary Steam reference session, not the mod; owner handed PC back; root is the sole game operator |
| Source checks | `af0845596f3dd764a1b90646b6e577cb644a7422`: 5 saved-result guard and 41 continuation tests passed |
| Full native candidate check | `af8871d`: 37 plugin and 13 launcher checks passed; not gameplay acceptance |
| Privacy improvement | Draft PR #11 aligned at `d2e7beb74ee5aea1a06c2cd4c35832dd83f5c8db`; 25 privacy tests, scanner, Ruff and native Windows CI passed |

Implemented source includes the three-tab/rank route, saved-schedule Training
access, live-match exit requirement, explicit saved-result choice including the
Calibration guard, keyboard-arrow polling, queued retry/step acknowledgement and
observed-goal advancement. Live behavior remains subject to the owner's failed
playtest. The SDK ServerWrapper goal-reset methods are no-op stubs; the separate
RLBot DisableGoalReset mutator is configured but its live effect is unverified.

Only two unapproved Gold feeds exist. Native scoreboard countdown/zero-time ball
lifecycle, physical Up, scored-goal advancement without kickoff, twelve distinct
Gold challenges, thumbnails and Garage/Mods/Options/quit regression are incomplete
or unverified. Mods is currently download-only in production; Workshop launch is
a development handoff without verified arrival/return.

Poquito Ground Shots and Skogur Powershot Practice are approved references for a
combined twelve-challenge Gold tier. Poquito has now been downloaded through the native browser and its 50-shot
training screen observed. Skogur download and exact shot decoding are in progress. The three cached packs were identified with valid CRCs and unchanged
original file hashes; none matches either target. Native download will resume
under the current root-owned input lease.

The bounded background research queue completed nine training and eight lifecycle
topics, with independent Luna corrections. Main has resumed normal-game pack
inspection and integrated two independently tested changes: hidden-ball cleanup
survives unavailable wrappers, and RLBot native clock fields are exposed for
verification. [Patch/test receipt](evidence/2026-10-29-training-cleanup-clock.md).
Neither change is loaded in the standard reference game; no new Gold acceptance
is claimed. Current build checks belong to their recorded revisions.
The original eight-hour research is on `research/rocket-league-2026-10-27` in
`research to be applied/`.

The saved desktop task **Improve My Career Training** runs every 45 minutes;
Windows scheduling was not used. It produced draft PR #11's privacy check. Main's
CI concurrency changes preserve an active candidate and retain newest pending
work; they do not certify another revision or replace gameplay testing.
