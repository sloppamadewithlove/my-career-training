# Evidence and recovery

## Minimal private run record

Record the source revision, clean/dirty state, source/frozen mode, candidate
manifest and runtime hashes; copied-save identifier; app/game/worker/helper
identities; input owner and handoff; start/end state and times; checks attempted,
passed, failed or not run; private evidence locations; and restoration outcome.
Keep a digest suitable for a public status update separate from raw evidence.

Resolve existing private helpers through the optional installed skill's
`local-workspace.json`. The canonical repository deliberately has no personal
paths. If the mapping is missing, locate helpers in the current session handoff
or private work directory. If neither exists, report that limitation and adapt
the project's supported launcher; do not download or reconstruct private saves.

## Separate the evidence layers

| Layer | What it can establish | What it cannot establish |
| --- | --- | --- |
| Domain/source tests | Forfeit outcome, score mapping, idempotency, cleanup and protocol behavior under tested inputs | Actual loaded movie, controller or real match |
| Native compilation and authored-asset checks | Compilable host, matching assets, protocol regression checks | Actual Shell navigation or visible arrival |
| Source live session | Actual native controls, game states and saved results for that source candidate | Frozen worker or installer behavior |
| Frozen startup and inventory | Exact executable entrypoints, dependency inventory and candidate provenance | A full fixture/save/Return/restart cycle |
| Installer lifecycle | Setup, reinstall/uninstall and preservation under tested conditions | Gameplay |
| Exact frozen live session | Observed complete player path for that artifact and environment | Arbitrary plugins, Epic, ranked bot ratings or every controller |

Do focused checks after a scoped change. Run the broader integration suite after
the batch is coherent or when cross-layer risk warrants it. Reuse a prior result
only if its inputs and scope are unchanged; record the tested revision. Do not
rerun every test for wording-only changes. Do not relabel an older binary with a
new revision. Follow `docs/BUILDING.md` and the candidate manifest machinery.

## Bounded failures

Set an expected transition and a scenario-appropriate deadline before action.
Use short bounded waits (normally at most 55 seconds per tool call); a complete
fixture may have a longer asynchronous observer. On expiry collect one current
snapshot and identify which acknowledgement/state is missing. Keep the old
intent and evidence; do not issue repeated destructive commands to force progress.

If the game is healthy but the authored pause unloaded, observe its state and
try the known ordinary Escape recovery once when appropriate. If the wrong
title screen or team-selection screen appears, record a failed route. Neither
screen is the authored career hub. Do not bypass the real button and call that
button verified.

On owned-process loss, changed creation time, stale bridge identity, failed
foreground checks or player input takeover, stop automated inputs. On worker
hold failure, resume that exact owned worker in cleanup. If safe restoration is
uncertain, preserve journals/conflicts and report the concrete remaining step.

Close only the owned or explicitly user-authorized game normally. Wait for its
helpers and file holds to end before restoration or another launch. Compare the
original My Career files and checked configuration/plugin files against the
baseline. Preserve ordinary Rocket League save changes; never blindly restore
them. Confirm the normal Steam path separately with no test injector/offline
arguments. Do not claim an original-menu observation proves online anti-cheat.
