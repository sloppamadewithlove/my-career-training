# Improvement heartbeat: execution contract

The desktop scheduled task runs every 45 minutes using GPT-6 Luna Max on this computer, retains its chat, and uses Important updates only. Windows Task Scheduler is not used. A scheduled audit ran on 29 October 2026; the owner rejected its audit-only output. This contract replaces that behavior.

## Required outcome

For an actionable run, finish one bounded improvement before reporting: corrected build/test failure, a meaningful regression test with executed evidence, a researched uncertainty resolved into an implementation decision, an applied workflow/handoff improvement, or a reviewed source patch on an isolated GitHub branch. Merely listing stale docs, recommending a test, reporting missing gh, or saying a builder was not dispatched is not completion. Research counts only when it resolves a named uncertainty with reusable evidence and a concrete next action.

1. Read live PR heads, issue #8, PROJECT_STATUS, NEXT_TASKS and DEVELOPMENT_WORKFLOW. Reuse the existing REA campaign and previous receipts. Detect what changed, not every historical issue.
2. Claim one disjoint lane in issue #8 with owner, exact base, files/interfaces, failure hypothesis, acceptance command and expiry. Consult the active builder assignments before edits. If main owns a changing source file, independently reproduce the failure, test an isolated alternative or improve a separate research/workflow artifact. Do not overwrite or move main's branch.
3. Execute. Luna researches/reviews/tests; use the configured DeepSeek builder for bounded code proposals, then independently inspect and run targeted checks. A timeout, token-exhausted response or null content is a failed task, not approval. Bound context/output; after two failed attempts use a different concrete approach instead of repeating the same request.
4. Publish source/records through GitHub. Temporary local checkouts are compilation/testing material only. Preserve private game/account data. Record exact candidate, test scope, operator/input ownership, actual result and limitations; do not add counts from overlapping suites or conflate PR head with loaded DLL.
5. Verify the write by reading it back. Reconcile the task board/status/PR description if the completed action changed them. Post one concise issue #8 receipt linking the commit/test evidence and next owned action. Close/release the claim.

## Working access, not assumed blockers

Prefer a working connector. This session's GitHub connector returned Unknown tool and gh is absent; **authenticated REST using the existing Git credential helper has repeatedly succeeded**. Missing gh or an environment token does not imply write access is absent. The scheduled prompt supplies the private local helper route. Use git credential fill for protocol=https/host=github.com with prompts disabled; consume stdout only in memory, send Authorization only to api.github.com, never print/log/persist the credential or put it in a URL/command line. Do not change global login settings. Verify one scoped repo read before a write. Public-safe source/evidence goes in this repo only.

The DeepSeek route is a private Python helper, not an ALL_TOOLS entry. Use the local location supplied in the scheduled prompt; inspect its public request interface/example, not its secret store. Record actual model, returned answer, usage/cost and limits. No invented agents or substituted models.

## Agent communication

Assignments carry an exact SHA, owned paths, output contract and acceptance check. Resume idle named subagents with followup_task; send_message alone does not start work. Give the reviewer the actual producer/consumer contract and changed delta. Keep GitHub ownership claims current so separate chats do not duplicate or overwrite work. A handoff names the defect, reproducer, immutable patch/evidence, reviewer result and remaining acceptance, not just a suggestion to investigate.

## Test/build quality

For a player-visible bug, first preserve the failing input/state, then verify its result through the real route. A passing helper test does not prove keyboard polling, game clock, rendering or native state changes. Inspect exact SDK method bodies when behavior is uncertain; this run found ServerWrapper goal-reset functions are no-op stubs despite their names. Use exact-source narrow checks; broaden when changes/failures justify it. Track full plugin/frozen/live results separately. Keep heavyweight builds out of live physics acceptance. A failed build yields its first actionable error and a fix attempt, not a CI status digest.

The heartbeat never independently takes game input, restarts a game, changes product choices, merges/releases a candidate or claims full-mod acceptance. It may prepare a concrete reviewed result and use existing authorization for ordinary fixes. User interaction remains with the acknowledged game operator.

## Notifications

Stay quiet while unchanged or non-actionable. Notify only for an actual improvement/completion, a newly reproduced failure, or a required user decision. State what changed, evidence and the next action in a few sentences. If truly blocked after trying available routes, record the exact failure and a concrete fallback; do not repeat unchanged blocker reports every run.
