# Feature evidence matrix — 0.1.0 testing prerelease

Evidence date: **22 October 2026**. This is a development snapshot, not a completed
V1 acceptance certificate. App version 0.1.0; Python 3.12.13; PySide6-Essentials
6.12.0; RLBot interface 2.0.0b56; FlatBuffers 0.19.0; core v5.0.0-rc18. The player's
installed Rocket League/Windows versions remain to be recorded.

GitHub is canonical and the Cursor Origin mirror is configured. See the attached
release receipt for the final source hash, mirror hash, test count, Windows job,
artifact checksums and packaging outcome. A source document cannot establish that
a later workflow or game session succeeded. Passing constructed-packet tests is
distinct from actual game observations.

Legend: **Source** = implementation exists; **Partial** = a required part remains
missing; **Local** = exercised without the game; **Pending CI** = Windows receipt
not yet available. **Not tested** means no real game receipt exists for this app.

| Feature / acceptance risk | Implemented | Locally tested | Game tested: Steam | Game tested: Epic | Remaining dependency |
|---|---|---|---|---|---|
| Desktop career UI, original artwork/icon, setup/settings | Source | QML/UI and bridge checks; Windows packaging pending | Not tested | Not tested | First installed Windows interaction; scaling and display checks |
| 1v1–4v4, one human, correct teammate/bench counts | Source | Domain/config and human-control boundary tests | Not tested | Not tested | Observe all four actual game configurations and player identities |
| Roster changes only between fixtures; recruit identity retention | Source | Domain and adversarial roster/format cases | Not tested | Not tested | Installed UI plus in-game starting lineup |
| Distinct specialist roles, driving/recovery and progression parameters | Source, experimental | Representative constructed scenarios and level differences | Not tested | Not tested | Evaluate whole-match behavior per mode; no ranked capability certification |
| Diamond–SSL challenge providers | Partial: capability boundary only | Manifest/availability checks | Not tested | Not tested | Compatible licensed stronger provider and measured evaluations; baseline is unranked |
| Six-round league, standings, deterministic rival simulations | Source | Season completion, seed stability, tie rules and historical fixture checks | Not tested | Not tested | Play human fixtures in game; verify table from observed results |
| Title playoffs and next-season continuity | Source | Two/three/four-way domain bracket and retained-career checks | Not tested | Not tested | Actual human playoff fixture and end-to-end continued career |
| Actual final score/overtime and disconnect handling | Source | Terminal-state/packet-order and no-result-on-loss cases | Not tested | Not tested | Full live match/overtime; disconnect/reconnect observations |
| Exactly-once score/XP/rewards and crash receipts | Source | Duplicate result, failed save, receipt replay and post-commit crash cases | Not tested | Not tested | Live worker/UI crash around observed final result |
| Atomic saves, malformed/corrupt imports, backup and single instance | Source | Storage validation, preserved bytes, failed replacement and lock cases | Not tested | Not tested | Windows locking and actual installation-upgrade receipts |
| Speed flip drill and timing observations | Source | Technique ordering, target crossing, gaps and alternate timing cases | Not tested | Not tested | Current-game reset, actual inputs and successful human attempts |
| Flip reset drill, shorter setup and acquisition observations | Source | False positives, touches, held/spent flips and packet gaps | Not tested | Not tested | Actual wheel/ball contact and reset-use observations |
| Dribble/flick, power shots and placement | Source | Carry gaps, target geometry, reset/variant/recording cases | Not tested | Not tested | Live ball setups, speeds, contact and targets |
| Fast aerial, air-roll control and fast flight/recovery | Source | Ordered gates, reset states and shared engine/metrics checks | Not tested | Not tested | Actual jump/boost sequences, route rendering and landing observations |
| Six independent lesson assistance settings across relaunch | Source | Preferences, bridge persistence and engine settings | Not tested | Not tested | Installed settings/relaunch plus live rendering behavior |
| Personal recordings and non-colliding wireframe ghost playback | Source | Bounds, provenance, interpolation and compatibility checks | Not tested | Not tested | Actual recording/synchronization/rendering; no effect on physics |
| Validated expert teaching references | **Missing** | Missing-reference labels/import validation only | Not tested | Not tested | Obtain permitted real successful recordings, verify technique/provenance per required lesson |
| Optional match review/coaching | Source | Observed score/touch, bounded sustained positioning heuristics, missing-evidence and save/relaunch checks | Not tested | Not tested | Validate timestamped observations and heuristic suggestions in actual matches |
| Bot garage and local cosmetic rewards | Source | Documented ID/palette validation and career records | Not tested | Not tested | Current-game item appearance/fallback; no human inventory grant API |
| Creator links and local map-file import | Source import/catalog boundary | Header/size/path/hash/permission-label cases | Not tested | Not tested; Epic import unavailable | Verified Steam loader launch/recovery; import alone is not loader or security approval |
| Play Online No/window-close has no transition side effects | Source | Lifecycle confirmation cases | Not tested | Not tested | Real app/game Yes/No/Escape test independently for each launcher |
| Play Online save/late result/stop/close/exit/relaunch | Source | Injected save failure, late events, timeout and launch failure paths | Not tested | Not tested | Actual owned process exit and normal EAC-enabled launch; platform remembered options |
| Pre-existing game refusal and owned process identity | Source | Preflight, identity/control boundary and platform checks | Not tested | Not tested | Actual launcher child processes, Epic startup behavior and safe close |
| Mouse/keyboard/controller and accessibility | Source | UI/bridge smoke paths; no physical controller receipt | Not tested | Not tested | Windows controller navigation/disconnect, focus and text-scale inspection |
| Installer, portable ZIP, worker and dependency notices | Source build workflow | Core checksum/license collection and script checks; **Pending CI** | Not tested | Not tested | Successful Windows artifact build, frozen smoke, clean install/upgrade/uninstall |
| Two-captain multiplayer | Research only; unavailable | Investigation/protocol document | Not tested | Not tested | Separate supported two-PC game/host verification and coordination implementation |

## Evidence still needed before calling full V1 complete

1. Successful exact-commit Windows CI plus real installer/portable artifacts and
   checksums. Perform a fresh-player Windows run without developer tools.
2. Separate Steam and Epic receipts with OS/game/app/core/provider versions,
   actual owned process identity, human/bot mapping, complete match/overtime,
   lessons/ghost/input/reset and the real Play Online transition.
3. Licensed real teaching recordings and technique review. Personal-best data or
   synthetic fixtures do not fill this requirement.
4. Resolve remaining product gaps honestly, including measured provider strength
   and game-validated community loading.

Keep observed outcomes, failures and exact remaining dependencies in the release
report. Do not turn documentation links, a successful SDK serialization, a launch
request or a green package workflow into game-tested evidence.
