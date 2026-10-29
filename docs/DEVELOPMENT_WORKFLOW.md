# Development and testing workflow

Updated 26 October 2026. Universal working agreement for implementation, review
and evidence. Product/release truth lives in [PROJECT_STATUS.md](PROJECT_STATUS.md);
the taskboard is [NEXT_TASKS.md](NEXT_TASKS.md); the product contract is
[BUILD_SPEC.md](BUILD_SPEC.md); the testing recipe is
[the game-state skill](../skills/my-career-training-testing/SKILL.md). Historical
status tables, timings and recovery detail live in the
[archived original](archive/2026-10-26/DEVELOPMENT_WORKFLOW.md); this file states
only current rules.

## Fresh main: read order and first questions

1. Read `AGENTS.md`, then the short `PROJECT_STATUS.md` and `NEXT_TASKS.md`, then
   only the relevant `BUILD_SPEC.md` section for the task at hand.
2. Ask the user for the intended player-visible outcome and any unresolved
   detail before starting a broad new build. Never re-ask what is already
   confirmed, and never block independent work while waiting for an answer.
   Resolve routine implementation details with engineering judgment; ask when a
   choice materially changes the player's experience, scope or permissions.

## Roles (owner-selected, exact)

| Role | Model / route | Boundary |
| --- | --- | --- |
| Main | Current main agent | Interviews, defines contracts, independently reviews, integrates, accountable for correctness |
| Preferred builder | DeepSeek V4.1 Flash 1017 via RunInfra, request ID `deepseek-v4-1-flash-1017`; multiple workers allowed | Scoped implementation patches, previews, behavior and bug fixes, including HTML/CSS/JavaScript and event handling |
| Fallback builders by depth | GPT-5.6 Sol high via Codex CLI; Grok 4.7 high via Cursor CLI; existing login sessions | Difficult implementation, integration or fixes when main judges escalation useful |
| Design only | Claude Opus 5.5 high | Mockups, layout/appearance specifications, design review. No HTML/CSS/JS, code, scripts, builds, input logic or behavior fixes |
| Reverse-engineering research | DeepSeek V4.1 Flash 1017 with bounded read-only REA/source tools | Separate from builders; exact artifact/source evidence, independent review, no unattended integration |
| Public research, exploration, testing | GPT-6 Luna max | Bounded research, test plans, independent verification, exact-candidate evidence |

Record the actual assignment and observed model/reasoning; never silently
substitute an unapproved model or designer. Main sends a rejected patch back with
specific defects and acceptance criteria.

## Credentials and private key policy

Only the DeepSeek builder uses an additional paid API key. Every other agent uses
its existing login session; do not request extra keys or change global
authentication, the main agent's provider, or Cursor/Codex sign-in settings. Keep
the key in a private OS-protected store outside the checkout and load it only into
the bounded builder process. Never place it in prompts, command-line arguments,
source, tracked config, previews, raw HTTP logs, GitHub, release files or public
evidence. Send only the source and task context the assignment needs.

## Parallel work and the review pipeline

- Parallel workers may share one goal through complementary scopes, or through
  bounded competing approaches in separate copies. Main selects one; never merge
  two alternatives blind. No concurrent writes to the same file.
- Builders self-check, then an independent targeted review/testing pass (Luna or
  the exact approved build reviewer) returns a compact acceptance receipt against
  an immutable patch. Main reviews shared interfaces, high-risk changes, actual
  evidence and integrated behavior. Never rubberstamp; there is no automatic
  merge, and integration stays gated on main.
- When the review queue grows, throttle new builder assignments; add independent
  reviewers only if real capacity exists. Never an arbitrary worker count.
- Respect actual concurrency slots and provider limits; bound each job's time,
  tokens and cost; cap speculative alternatives at 2 by default.
- Prove the hardest end-to-end integration first, then polish.
- After two failures of the same hypothesis, log expected vs actual, evidence,
  cause, confidence change and the next alternative (research or experiment).
  Stop repeating; do not abandon the goal. Failure log: concise public notes in
  the repo, private evidence kept separate.

## Task card (tiny, one deliverable)

Every assignment states: base commit, write paths, interfaces/payloads touched,
deliverable, executable acceptance check, failure cases, time/token budget and
dependencies. A deadline yields partial findings and limits, never an invented
pass. Main creates and maintains the taskboard in `NEXT_TASKS.md`; the testing
skill is the linked recipe for game routes.

## Player-facing function contract

Every unique player-facing function — downloads, buttons, thumbnails, settings,
startup, saves, garage, mods and the rest — is specified and accepted through the
same six steps, in this order:

1. **Preconditions** — required state, environment and ownership.
2. **Input** — the exact click, key, controller or automatic trigger.
3. **Actual visible/state outcome** — what the player sees and what state changes.
4. **Persist** — what is written, where, and atomically (if applicable).
5. **Failure/recovery** — the visible error and the safe recovery route.
6. **Acceptance proof** — the exact-candidate evidence that proves it.

Three illustrative examples, explicitly not exhaustive:

| Function | Preconditions / input | Visible or state outcome | Persist | Failure / recovery | Acceptance proof |
| --- | --- | --- | --- | --- | --- |
| Thumbnail resolve/cache/fallback | Content present; hover or select | Correct image, no placeholder flash | Cache only | Missing asset → fallback tile, no crash | Visual check on exact candidate |
| Lesson reset all actors | Lesson loaded; reset control | All actors return to start state | None unless lesson state is saved | Partial reset → visible error, retry | Reset, observe every actor |
| Mods download is not activation | Mods view; start download | Download progress and cached state, still inactive | Downloaded content + manifest | Network/disk error → safe retry or clean rollback | Download, verify digest, confirm not active; installation/enable require their own verified contracts |

## Game session and input ownership

Reuse a healthy owned game: one input owner, copied career, exact PID, creation
time and executable, verified foreground before each input/capture. Never replace
loaded assets. Return requires fresh READY, actual RootMenuMovie and visible hub.
Verify restoration after closure. A handoff names game identity, scenario, allowed actions and ending
condition; both agents acknowledge it. Main does not click while a tester owns
input; observers stay read-only; user control suspends automation.

## Testing and evidence rules

- Tests are boundary-focused; do not repeat a passing check without a change.
- A UI preview is not gameplay. Source checks do not authorize a player-ready claim.
- Binaries must trace to exact source provenance. Docs-only changes and helper
  provenance notes do not trigger a binary rebuild.
- Destructive fault tests use isolated copied test data only; there is no
  requirement to kill or restart the real game merely to test saves.
- Source scripts must select the correct project and a validated toolchain.
- Record times for build, launch, continuation, waiting, review and rework, plus
  actual tokens and cost from the provider-reported source. Unknown values stay
  unknown, never guessed.
- The 12-second click-to-Playing continuation target remains historical and not
  achieved; its evidence and recovery detail are in the
  [evidence-and-recovery reference](../skills/my-career-training-testing/references/evidence-and-recovery.md).

## State policy and publishing

An incomplete review is never approval. Publish only per proven capability. Every
claim carries one status — planned, implemented, unverified, verified or blocked —
with exact revision, mode and date. Public updates contain sanitized outcome,
revision, counts and release blockers only.
