# Development and testing workflow

Updated 25 October 2026. This is the working agreement for faster implementation
and useful evidence. Current product/release truth remains in
[PROJECT_STATUS.md](PROJECT_STATUS.md). The reusable
[game-state skill](../skills/my-career-training-testing/SKILL.md) records routes,
known failures and recovery. Install that folder in the local Codex skills
directory; keep machine-specific helper locations in an uncommitted local map.

The owner accepted this workflow. First priorities are state notifications,
healthy-session reuse and focused checks. Keep useful work as the measure of
model usage; quota exhaustion is a fallback trigger, not an objective. In the
first resumed cycle, actual Forfeit and the next native fixture shared one game,
and a private milestone notifier detected fresh results. The timer Options test
then exposed a real unhandled screen; the release stayed on hold.

## Roles and work ownership

| Role | Requested model / route | Concrete output and boundary |
| --- | --- | --- |
| Main interviewer, builder, reviewer and integrator | Current main agent | Clarify requirements, define contracts, implement as needed, independently review DeepSeek patches, return defects for correction, integrate and own acceptance |
| Research, exploration and testing | GPT-6 Luna, max reasoning, Codex CLI | Bounded source/web research, test plans and exact-candidate evidence; game input only after an explicit handoff from main |
| Builder and hard implementation problems | DeepSeek V4.1 Flash 1017 via RunInfra, paid using the owner's private API key | Scoped implementation patches against an immutable base, rationale and focused verification; no independent merge/publish authority; connection is not yet configured or verified |
| Designer only | Claude Opus 5.5 high, Cursor CLI or a verified existing Anthropic authenticated session | Visual mockups, layout/appearance specifications and design reviews for game and website; no implementation/code edits, input logic, bug fixes, scripts or builds; stop designer on quota exhaustion |
| Independent workflow reviewer | GPT-6 Astra, low reasoning | Check a bounded checkpoint's assignments, receipts, unresolved defects, privacy and claims; do not duplicate every code review |

These owner-selected roles supersede the earlier Grok-primary / Sol-fallback
building arrangement. DeepSeek is the preferred builder now; do not silently
replace an unavailable builder or designer with another paid model. The main
agent remains accountable for correctness and sends a rejected patch back with
specific defects and acceptance criteria. Luna verifies the corrected behavior;
main reviews the resulting diff and evidence before integration.

**Strict owner clarification:** a working HTML preview is implementation. Opus
provides the visual design; main or DeepSeek writes its HTML/CSS/JavaScript and
all event handling. Keyboard/controller behavior, state management, downloads,
runtime fixes, asset compilation and native integration belong to builders.
Afterward Opus may review screenshots and request visual adjustments; a builder
implements those adjustments. Do not send behavioral defects back to Opus merely
because it designed the screen. Main may build directly and remains responsible
for reviewing DeepSeek output. Luna owns research and test work. This clarification
overrides older assignments that called Opus a design engineer or asset builder.

The owner identified RunInfra's model page. Its [official model documentation](https://runinfra.ai/inference-api/deepseek-v4-1-flash-1017)
documents the request ID `deepseek-v4-1-flash-1017`, upstream name
`deepseek-ai/DeepSeek-V4.1-Flash-1017`, API base `https://api.runinfra.ai/v1`,
Chat Completions and Anthropic-compatible Messages, and tool calling. These are
provider-documented capabilities, not a successful authenticated integration.
No key has been supplied or configured at this checkpoint. Record requested and
returned provider/model identity without claiming more than the API exposes.
If using an agent harness through the Messages API, configure only that child
process; it remains a DeepSeek builder, not an Opus designer. Do not change the
main agent's provider or replace existing Cursor/Codex sign-in settings.

Only this builder uses an additional paid API key. Other agents use existing
subscription/login sessions; do not request additional API keys or change global
authentication. Keep builder credentials in a private OS-protected local store
outside the checkout. Load them only into the bounded builder process/request;
never place them in prompts, command-line arguments, source, tracked config,
HTML previews, raw HTTP logs, GitHub, release files or public evidence. A chat
paste is not repository content and must not be copied into the project. Send
only the source/task context necessary for the assignment, excluding private
game evidence, saves, unrelated files and credential stores. Track usage and
actual provider-reported costs; do not claim price or speed savings without
measurement. Set a per-job request/token bound rather than unlimited retries.

The latest designer preference is **high**. Historical ExtraHigh work is not a
claim that the current model setting has been exercised. Verify requested model
and reasoning in CLI/session output before accepting a task receipt; a command
line request by itself is insufficient. Keep raw output private. If the exact
model is unavailable, report it and follow only the user's specified fallback.
The prior Grok-to-Sol quota rule is historical. On an Opus quota failure, disable
that role and maintain [the design handoff](OPUS_DESIGN_BRIEF.md). Do not silently
substitute another designer. Spend available quota on useful work; do not create
busywork just to consume it.

These are roles, not five continuously running jobs. Respect the available
concurrency slots and rotate roles. Separate file scopes/worktrees for builders;
main alone integrates and pushes. A review should not block unrelated work.
Exactly one input owner may operate the game. A handoff names the game identity,
scenario, allowed actions and ending condition; both agents acknowledge it.
Main does not click while the tester owns input. Observers stay read-only. User
control suspends automation. Input ownership is currently a recorded procedure,
not an automatic lock enforced by the helpers.

## One useful work cycle

1. Choose one acceptance result and its smallest coherent change. Define shared
   payloads, save semantics and success/failure states before splitting files.
2. Assign each worker an exact base revision, owned paths, deliverable, validation,
   forbidden side effects and a time budget. Default to a narrow 5–10 minute
   first pass; extend only for a specific useful next result. A deadline produces
   partial findings and limits, never an invented pass.
   If the first pass only repeats research, retain its findings and narrow the
   next assignment to one concrete file or behavior. Transfer implementation
   ownership explicitly when a requested model has not produced a patch; record
   who actually wrote it and retain the requested model for a bounded review.
   Ask for a final conclusion from existing analysis before restarting research.
3. Run focused checks while builders work independently. Review an immutable
   result once; re-review the fix and affected boundary instead of restarting the
   entire investigation. Broaden tests when a failure or change justifies it.
4. Integrate a batch and build one coherent candidate. Record its hashes and
   evidence. Rebuild/stage changed movies together with their host. Keep all
   production artifacts attributable to the candidate.
5. Schedule compatible live routes in one owned game. Start the result observer
   before a fixture, check it while the match runs, and react when results arrive.
   Reuse the game for subsequent activities; restart for changed native code or
   startup/persistence/restoration checks.
6. Record passed, failed and untested behavior separately. Push reviewed source
   and sanitized status to the repair branch/PR. Full release still requires
   exact frozen inventory, installer lifecycle, real fixture/save/Return/restart,
   restoration and required input routes. Update the existing website only with
   the tested release; source checks do not authorize a player-ready claim.

## Eight improvements and their current status

| Improvement | Benefit | Status / next concrete step |
| --- | --- | --- |
| 1. Short real development fixtures | Reach save/results without waiting through every normal match | Private opt-in source harness has ten focused checks and a real 0–1 fixture/save/receipt acknowledgement on ff3ee52. Uses RLBot OneGoal, copied careers and explicit development-only receipts. Frozen/CI modes are refused. Normal timed frozen acceptance remains required |
| 2. Notify on state changes | Stop missing the short results window or waiting after work finished | Private bounded milestone observer now emits one scoped signal; main forwards actionable events. Playing, returned-hub and natural-results signals observed on d95f4cc. 32 synthetic checks cover identity, freshness and transient file reads. This is a test helper, not a shipped player feature |
| 3. Reuse a healthy game session | Avoid repeated startup, injection and focus setup | Source tests have started another activity in the same process. Group routes and use the skill; never reuse across loaded native-code changes |
| 4. Tests selected by changed boundary | Catch errors early without rerunning unrelated suites | Focused suites already used; maintain a simple change-to-check mapping below. Full coherent source checks remain separate |
| 5. Incremental builds with verified inputs | Avoid recompiling or repackaging unchanged components | Native build tooling is incremental; measure actual cache hits. Broader artifact reuse is planned and must preserve input hashes/provenance, never relabel binaries |
| 6. Agree feature contracts before parallel edits | Reduce UI/host/service integration rework | Existing integration contract plus explicit file ownership. Add each feature's command, acknowledgement, rejection and persistence rules before handoff |
| 7. Bounded reviews with required artifacts | Prevent open-ended review loops and vague completion claims | Adopt this workflow: immutable scope, time budget, actual model receipt, findings, test result and unresolved limits |
| 8. Measure waiting and rework | Spend effort on the actual bottleneck | Start private per-cycle timing now: build, test, game startup, fixture, focus recovery, review wait and rework. No benchmarked speedup claimed yet |

## Refinements after the direct-continuation session

Observed on e41: native CI took about 15 minutes; the normal packaged fixture
took about 13.5 minutes from Play to saved result, including deliberate pause
checks. One results click reached the next Playing state in about 26 seconds.
The owner accepted these refinements and set a **12-second continuation target**.
It is not achieved yet. These are individual observations, not a benchmark or
guaranteed timings. Keep the same click-to-Playing definition and record visible
kickoff separately; never shorten the measurement by dropping save/arrival checks.
Manual screenshots/round trips, an artifact-transfer cancellation race, and an
independent probe's incorrect schema assumptions also caused avoidable rework.
The skill reduced repeated research; it is not yet an automated test driver.

| Refinement | Concrete next step / current status |
| --- | --- |
| 1. Verified menu-route driver | Build short routes that verify current process, foreground, surface and control identity before acting; stop on mismatch. Retain one input owner. Planned |
| 2. Checkpoint screenshots | Capture initial state, meaningful arrival and failures; use fresh scoped status for routine intermediate observations. Existing observer supports this; reduce manual over-inspection |
| 3. Immutable package reuse | Private frozen launcher now accepts an explicit full source pin while preserving manifest and complete same-run inventory checks. Documentation commits need not cause another binary build |
| 4. Resumable artifact transfer | Add byte-progress, total deadlines and digest-verified resume/reuse. This run recovered completed archives; a general robust transfer helper remains planned |
| 5. Exact reviewer input contract | Supply validated paths, current schemas and sample synthetic records with every assignment. Require a standard receipt separating observed evidence, inference and probe errors |
| 6. One bounded review per changed boundary | Review once, then only changed/failing portions; an incomplete review is not approval. Keep unrelated work moving and retain partial findings |
| 7. Two test speeds | Use the existing opt-in OneGoal source harness during iteration; run normal timed gameplay on the final coherent frozen candidate. Never label shortened development fixtures as normal acceptance |
| 8. Per-phase measurements | Record build, first launch, continuation, game waiting, manual actions and reviewer rework separately. Profile the observed continuation delay before changing startup or cleanup safeguards |

## Change-to-check mapping

| Change | First check | Broader evidence when ready |
| --- | --- | --- |
| Career/domain/service | Relevant Python domain/bridge tests and Ruff | Full source integration; actual persisted gameplay for changed save semantics |
| Native host/protocol | Affected native regression targets plus matching bridge tests | Coherent native build and real menu transitions |
| ActionScript/layout | Compile changed authored movies, verify pins and composition/assets | Coherent host/movie candidate, visual focus/mouse/keyboard/controller routes |
| Worker/packaging/startup | Actual redirected windowless-worker regression and build smoke | Exact frozen startup, inventory and real fixture |
| Installer/recovery | Lifecycle and preservation checks | Owned local install/restart/restoration plus normal Steam route |
| Documentation/skill | Links, privacy, skill validator and a realistic forward test | No automatic full product-suite rerun for wording alone |

## Small handoff and timing record

Private jobs record: task, base commit, requested and observed model/reasoning,
owned files, input owner (or no input), artifact/commit, commands and results,
elapsed time, findings, remaining limits and next action. Public GitHub updates
contain only sanitized outcome, revision, counts and release blockers.

For timings, record start/end and category for each significant wait; separate
active work from unattended match time. After several cycles, compare the
slowest categories and failed retries. Optimize the largest repeated cost first.
Do not promise a percentage improvement before measuring it.
