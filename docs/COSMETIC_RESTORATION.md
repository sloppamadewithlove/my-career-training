# Local cosmetic restoration

The plugin uses two existing BakkesMod cvars: `cl_itemmod_code` and
`cl_itemmod_enabled`. It captures both before its first setter and retains that
baseline across subsequent My Career design changes. It does not change game
inventory, ownership, entitlement, or car physics.

`CosmeticOverrideState` is the tested transaction boundary. Successful apply
requires both values to read back as requested. A setter failure or mismatched
readback triggers restoration. Both restoration setters are attempted even if
one fails. The original enabled flag is restored only after the original code
reads back correctly; otherwise the helper attempts to disable the unresolved
temporary design and retains the baseline for another attempt. Restoration is
reported complete only after both original values read back correctly.

The host applies new designs only in its current owned offline session. It
restores on manual Restore, loss of that scope, a tick exception, and unload.
Scope-loss failures are retried on later ticks. An unload failure is logged;
unloading destroys the in-memory recovery state. This is not hard-crash recovery
or proof that BakkesMod never persists its cvars. Restore returns to the captured
session baseline, including when another plugin changed the same shared cvars
during the session. Concurrent cosmetic editing is not isolated.

Fixtures cover unavailable settings, failure between the two setters, repeated
design changes, ignored setters, partial restore, retry, and both original
enabled states. They use test-owned values. A game test must still confirm the
rendered appearance, unload behavior, and preservation of the normal profile.
