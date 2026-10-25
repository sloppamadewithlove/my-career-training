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
| Main integrator | Current main agent | Architecture, shared contracts, bounded assignments, integration, privacy review, GitHub checkpoints and release acceptance |
| Game tester | GPT-6 Luna, max reasoning, Codex CLI | Test plan and exact-candidate evidence; only operates the game after an explicit input handoff from main |
| Code reviewer | Grok 4.7 High, Cursor CLI; GPT-5.6 Sol high after actual quota exhaustion | Review an immutable commit/range, report actionable defects or no findings with scope; no production edits in a review job |
| Designer | Claude Opus 5.5 high, Cursor CLI | Scoped native button/layout/focus/copy changes, rebuilt assets where assigned, visual acceptance checklist; stop designer on quota exhaustion |
| Independent workflow reviewer | GPT-6 Astra, low reasoning | Check a bounded checkpoint's assignments, receipts, unresolved defects, privacy and claims; do not duplicate every code review |

The latest designer preference is **high**. Historical ExtraHigh work is not a
claim that the current model setting has been exercised. Verify requested model
and reasoning in CLI/session output before accepting a task receipt; a command
line request by itself is insufficient. Keep raw output private. If the exact
model is unavailable, report it and follow only the user's specified fallback.
On a Grok quota failure, record the failure without retrying it in a loop and
switch the next useful review to Sol high. On an Opus quota failure, disable
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
| 1. Short real development fixtures | Reach save/results without waiting through every normal match | Research only: RLBot OneGoal exists. Verify a private source-only launch hook, retain real goals, copied saves and explicit evidence. Normal timed frozen acceptance remains required |
| 2. Notify on state changes | Stop missing the short results window or waiting after work finished | Private bounded milestone observer now emits one scoped signal; main forwards actionable events. Playing, returned-hub and natural-results signals observed on d95f4cc. 32 synthetic checks cover identity, freshness and transient file reads. This is a test helper, not a shipped player feature |
| 3. Reuse a healthy game session | Avoid repeated startup, injection and focus setup | Source tests have started another activity in the same process. Group routes and use the skill; never reuse across loaded native-code changes |
| 4. Tests selected by changed boundary | Catch errors early without rerunning unrelated suites | Focused suites already used; maintain a simple change-to-check mapping below. Full coherent source checks remain separate |
| 5. Incremental builds with verified inputs | Avoid recompiling or repackaging unchanged components | Native build tooling is incremental; measure actual cache hits. Broader artifact reuse is planned and must preserve input hashes/provenance, never relabel binaries |
| 6. Agree feature contracts before parallel edits | Reduce UI/host/service integration rework | Existing integration contract plus explicit file ownership. Add each feature's command, acknowledgement, rejection and persistence rules before handoff |
| 7. Bounded reviews with required artifacts | Prevent open-ended review loops and vague completion claims | Adopt this workflow: immutable scope, time budget, actual model receipt, findings, test result and unresolved limits |
| 8. Measure waiting and rework | Spend effort on the actual bottleneck | Start private per-cycle timing now: build, test, game startup, fixture, focus recovery, review wait and rework. No benchmarked speedup claimed yet |

## Change-to-check guide

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
