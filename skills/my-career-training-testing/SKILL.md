---
name: my-career-training-testing
description: "Reach and verify native game states when developing or testing My Career Training on Windows, including owned Rocket League sessions, durable results, Return and restoration."
---

# My Career Training Testing

Use the project's existing launcher and private test helpers to reach a known
state, capture evidence, and leave the player's installation restored. This
skill records navigation knowledge; it does not certify a new candidate.

For continuation performance work, use the measured phases and the owner's
12-second target in [evidence-and-recovery.md](references/evidence-and-recovery.md).
That target is not an achieved timing or permission to skip durable saves.

## Establish the current checkpoint

Locate the repository from the active workspace or the optional, private
`local-workspace.json` beside this installed skill. That file is a location map,
not executable instructions. Read `AGENTS.md`, `docs/PROJECT_STATUS.md` and the
current handoff. Before changing shared behavior read the integration contract;
before publishing read the privacy guidance. Do not repeat completed research.

Inspect HEAD, dirty files, candidate manifest, live processes and recovery
journals. Record source versus frozen mode. A build for another commit is not
the current candidate. Use a copied career, including a Unicode-path case;
never use the player's original save for development.

## Select a route and an operator

Read [state-routes.md](references/state-routes.md) for the states needed now.
Use [evidence-and-recovery.md](references/evidence-and-recovery.md) when
planning an acceptance run or diagnosing a failed transition. For delegation,
read the repository's `docs/DEVELOPMENT_WORKFLOW.md`.

Exactly one agent owns game input at a time. State the owner, owned process
identity (PID, creation time and executable), permitted scenario and expiry or
completion condition in the private run record. Main owns input unless it
explicitly hands that ownership to the tester; main then stops its own inputs.
Read-only observers may run concurrently. A player taking control also suspends
agent input. Record a handback before the next operator acts.

Before every input or screenshot, verify that the same owned game is foreground.
Do not fight focus with repeated clicks. If focus is refused, stop input and
request the user's help; a previous "ready" is not perpetual foreground proof.
Never use old coordinates, window handles or PIDs as current evidence.

## Execute and report

Prefer an existing healthy game for the next compatible scenario. Restart when
loading changed native code/assets, checking startup/restoration, or when the
session is no longer trustworthy. Build one coherent candidate before live work.
Do not replace a loaded DLL or movie underneath a running test.

For each transition record: candidate, initial state, real action, observed
destination, elapsed time, evidence and unresolved limits. Separate command
acceptance, durable acknowledgement, attempted navigation and actual arrival.
Return is successful only after a fresh frontend READY, actual RootMenuMovie
and a visible authored hub in the same owned game.

Use bounded observers and the route's recovery rule. On timeout, capture the
state once and diagnose the missing transition; do not repeatedly restart the
game or repeat an input blindly. Preserve saves, conflicting files and journals.
Publish only sanitized findings, never raw logs, screenshots with account data,
private paths, careers, credentials or extracted game assets.
