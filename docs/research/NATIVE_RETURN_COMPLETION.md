# Native return completion

Stopping the RLBot worker does not establish that Rocket League has returned
to the frontend. The native host therefore keeps a separate return intent.
Only a successfully sent native `return_hub` action arms it, using the current
bridge nonce and the exact expected activity and fixture identities. Opening
the unfinished-match confirmation does not arm navigation.

The service publishes `native_return_ready` with exactly `session_id` and
`fixture_id` after worker shutdown, result draining and a successful save or
confirmed abandonment. The host requires that receipt to match its retained
intent, plus `Idle`, `kind:hub`, an explicit null or empty-string activity id,
`fixture_id:null`, `worker_running:false` and
`busy:false`, no pending career fixture and an empty error. Receipt JSON never
supplies an engine command. A different activity, bridge nonce or lost owned
offline scope clears the intent.
A stale bridge suspends navigation while retaining the same scope's intent and
issued flag; fresh data must satisfy the full gate again.

The host checks this completion before its movie-surface gate, after the
existing executable hash, build, process ownership and fresh-bridge checks.
Resuming play or unloading the pause movie therefore does not lose the intent.
The one fixed SDK call is `GameWrapper::ExecuteUnrealCommand("disconnect")`.
It is marked issued before calling the SDK, and is not repeated. The retained
intent is completed only when the owned game is observed outside gameplay,
outside replay and outside online play. A void SDK return is not a completion
receipt.

The pinned BakkesMod SDK declares `ExecuteUnrealCommand`; the stock movie also
has a typed shell exit route, inspected privately. These source observations
do not prove the fixed command works in the supported game build. Pure tests
cover the ownership, persistence, identity, duplicate and surface-independent
gates. Live acceptance must separately demonstrate return from both paused
and resumed offline activity, and a saved results screen. No game assets or
private inspection output belong in this repository.
