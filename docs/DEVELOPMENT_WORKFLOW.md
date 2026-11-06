# Development and testing workflow

Updated 6 November 2026. Universal working agreement for implementation, review
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
| Code builders | DeepSeek V4.1 Flash 1017 max via RunInfra, request ID `deepseek-v4-1-flash-1017`; GPT-6.1 Sol high | Scoped implementation patches, previews, behavior and bug fixes, including HTML/CSS/JavaScript and event handling |
| Independent code reviewer | GPT-6 Astra max | Review immutable code changes and actual producer/consumer contracts; no automatic integration |
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
- Builders self-check, then GPT-6 Astra max independently reviews and returns a
  compact acceptance receipt against
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

If foreground is lost or the helper refuses an input, stop: refusal means no
input was dispatched. Do not automatically retry a refused click. Resume only
after the owner restores the intended game foreground and fresh same-process and
foreground checks pass; never reuse stale focus state.

Keep launch modes distinct: an RLBot `-rlbot` launch, a standard Steam launch
without that flag, Rocket League's EAC choice and Steam Offline Mode are separate
conditions. Steam Offline Mode disconnects the Steam client; it is not the game's
EAC setting. A normal Steam launch, an offered launcher choice or Bakkes version
metadata does not prove the active EAC state or a plugin's load state. If module
access is unavailable or no fresh log is retained, record loaded-plugin status as
unknown without inferring absence or cause. If a launcher choice requires the
user, wait for their explicit selection; a pending question is not consent.
Record the actual choice and follow the authorized gameplay mode. After upstream
updates, verify the exact
installed executable identity and supported launcher/plugin capability for that
binary before testing the candidate.

Native Custom Training's Created editor can write a `.Tem` and rotate the actual
Rocket League game profile before an explicit Save. A copied MCT Career does not
isolate those game saves. Keep private preflight copies and record a baseline
inventory before Create; after the owned game exits, compare changed names/hashes.
Test config override and restore helpers first against disposable config data;
restore an original only conditionally. Preserve newly written active saves and
other changed/new files. Restore only missing originals with create-new semantics;
never overwrite changed files or claim byte-identical restoration unless hashes
prove it. Keep cleanup scoped to verified test-owned artifacts; if review blocks
an exact cleanup, record the limit and do not broaden or repeat it blindly.

## Testing and evidence rules

- Tests are boundary-focused; do not repeat a passing check without a change.
- A UI preview is not gameplay. Source checks do not authorize a player-ready claim.
- Binaries must trace to exact source provenance. Docs-only changes and helper
  provenance notes do not trigger a binary rebuild.
- For a native candidate, retain its manifest, smoke receipt and staged/frozen
  authored-ABC hash comparison. Reuse them while source, dependencies and staged
  assets are unchanged; do not rebuild or repeat stable preflight to compensate
  for a focus failure. When a new compiled ABC changes, stage it once and build
  one coherent candidate; retain receipts for unchanged inputs and rerun only
  checks invalidated by the change. Preserve the manifest, license collection,
  exact source provenance and frozen asset/hash checks.
- After a platform update, verify the exact installed executable identity and
  launcher/plugin capability for that binary before launch. An unchanged file
  version, platform build ID or matching menu-package hashes alone do not prove
  compatibility; do not bypass or repin around the guard based on version alone.
- Monitor a quiet package build through its current process and logs at bounded
  intervals; set completion/failure/stop conditions before waiting or retrying.
  Gather stable launch prerequisites once per candidate and repeat them only
  when inputs change. Mutable game ownership/foreground checks remain fresh.
- Rank-specific live evidence must identify the settled rank/scenario. Retry
  acceptance separately observes actors, score and progression; a car/ball reset
  alone is not whole-level proof. Preserve unexplained transitions for diagnosis.
  For Quit, distinguish request enqueue/dispatch acknowledgement, actual owned-process exit and restored
  installation/journals; an accepted request does not establish cleanup.
- Destructive fault tests use isolated copied test data only; there is no
  requirement to kill or restart the real game merely to test saves.
- Source scripts must select the correct project and a validated toolchain.
- If packaging imports a module from an old environment or another checkout, stop
  before building. Select the pinned project interpreter, set an absolute
  `PYTHONPATH` for the intended checkout, and verify `sys.executable` plus each
  critical module's `__file__` before retrying from the initial staging build.
  For the native candidate, stage source/license evidence, collect licenses, then
  freeze and smoke in the order recorded by `docs/BUILDING.md`.
- For Windows identity observers, exercise a real directory-junction swap between
  validation and open; keep validated handles through use and test write/delete
  sharing. Canonicalizing a path string alone does not close that race. A source/test review
  of a default-OFF observer remains distinct from loading it live.
- Timing-sensitive controls need a regression through the production packet
  dispatcher, including valid game ticks with uneven wall-clock arrivals and
  a real missing tick. A passing controller-only test cannot prove dispatch.
- Check whether the loaded candidate already contains a proposed repair before
  repeating an old hypothesis. Match runtime fields and the visible HUD within
  the same attempt; historical readbacks cannot explain a later display failure.
- A timer returning to its initial display only suggests expiry. Verify the exact
  zero transition with same-attempt native timer/state evidence. A reset input at
  the initial state proves nothing; first change the attempt, then verify every
  relevant actor and state returns.
- Screen actual packet cadence before expanding a strict capture entry. Retained
  per-packet timestamps/gap flags can reject coarse delivery; positive strict
  acceptance also needs frame-number continuity. Throttled telemetry spacing is
  not the raw delivery rate. Keep failed feasibility separate from a code defect.
- On Windows C1083 with a present SDK header, compare the compiler's expanded
  relative include path with its normalized path before changing dependencies.
  If path depth is the cause, build the exact commit in a shorter isolated
  worktree and retain the pinned SDK and normal candidate provenance checks.
- A timed-out reverse-engineering import yields no evidence. Close its target;
  do not repeat the unchanged request. Reuse retained results or choose a bounded
  alternative, and distinguish static inventory from observed runtime access.
- Record times for build, launch, continuation, waiting, review and rework, plus
  actual tokens and cost from the provider-reported source. Unknown values stay
  unknown, never guessed.
- For requested active-session reviews, record actual due times and completion.
  If one or more targets elapse while the chat remains active, record all elapsed
  targets and perform one catch-up at the next natural boundary; set the next due
  time from that catch-up's actual start. Bound waits on builders and background
  processes so an open-ended wait does not defer a due review; make independent
  progress while a dependency runs. A scheduled prompt is not evidence that a
  review ran. Do not backfill progress or imply continuous monitoring while the
  chat is idle. When work resumes after an idle chat, record the actual restart,
  do not count elapsed idle targets as actively missed checks, and perform
  read-only process/foreground verification before any game input.
- The 12-second click-to-Playing continuation target remains historical and not
  achieved; its evidence and recovery detail are in the
  [evidence-and-recovery reference](../skills/my-career-training-testing/references/evidence-and-recovery.md).

## State policy and publishing

An incomplete review is never approval. Publish only per proven capability. Every
claim carries one status — planned, implemented, unverified, verified or blocked —
with exact revision, mode and date. Public updates contain sanitized outcome,
revision, counts and release blockers only.

The [5 November improvement receipt](evidence/2026-11-05-session-improvement.md)
records the observed failures behind these dispatch, path and research rules.
The [second cycle receipt](evidence/2026-11-05-session-improvement-cycle-2.md)
records package progress and the first bounded live retry/progression observations.
The [third cycle receipt](evidence/2026-11-05-session-improvement-cycle-3.md)
records matched clock evidence requirements and passive capture-cadence screening.
The [fourth cycle receipt](evidence/2026-11-06-session-improvement-cycle-4.md)
records the Custom Training route and save side effect, unresolved clock lead and
missed-review catch-up.
The [native-training catch-up receipt](evidence/2026-11-06-native-training-catch-up.md)
records native local-save behavior, timer/reset limits and packaging provenance.
The [native-pause focus checkpoint](evidence/2026-11-06-native-pause-focus-checkpoint.md)
records exact-candidate checks and the required stop on focus loss.
