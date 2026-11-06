# Assistance ghost Off/On roundtrip — 6 November 2026

Review base: `85df20a`. Corrected code:
`200f630d86b44fdcfad5f8c437cc55dca4c3f7c2`. Builder: GPT-6.1 Sol high.
Independent delta review remains required. This is source/synthetic transport
evidence; no game was opened, no DLL installed and nothing published.

The preceding Off fix cleared Backend's desired flag. A later assistance On only
sent worker preferences, so the worker enabled its ghost while Backend continued
to suppress every visible packet. Both existing assistance surfaces use that path.

Explicit assistance ghost preferences now request the existing exact-command
ghost acknowledgement. The worker emits it after applying actual practice state,
including the real enabled value. An unavailable or unsupported recording receives
a rejection, not an assumed success. Backend tracks desired state and pending
confirmation in both directions; an acknowledgement must match session, command
and requested enabled state. Each newer ghost control supersedes previous controls
for the same worker/lesson, preventing an older Off answer from undoing an already
confirmed newer On as well as preventing old On answers after Off.

Callback receipts also capture the last actually applied ghost-command ID. After
assistance On, Backend requires that exact ID on a fresh worker packet. Delayed old
On telemetry stays hidden before and after the new acknowledgement; only a matching
packet can make the paired recorded pose visible. The reset generation fence,
100 ms receipt limit, ownership/build checks and native rendering code are unchanged.

The saved assistance semantics remain independent of the toggle's display-setting
synchronization: the selected lesson preference persists, while global training
display preferences are unchanged by assistance acknowledgement, rejection or
timeout. Runtime rejection/timeout hides the ghost without rewriting that saved
assistance choice. Ordinary non-ghost preferences do not request this acknowledgement.

The implementation branch passed 107 focused Python checks with three companion
transport cases skipped. Preliminary combined checkout
`c59095d330ffe0266f5d3d7d4a763bec7c09e34d` passed 121 checks, with four other optional
companion parser/menu cases skipped. It contains the same companion producer
dependency recorded in the earlier receipts.

Actual Backend dispatch, worker command application, production packet processing,
FileBridge and the compiled native consumer prove On → assistance Off → assistance
On → Off for both speed flip and flip reset. Checks include delayed old On packets
before/after the new real acknowledgement, an older Off answer after newer On, an
old On answer after latest Off, matching post-command receipt recovery, persistence,
unavailable/unsupported recording rejection and timeout. Existing retry/automatic
reset and fence regressions also passed. Packet/game SDK fixtures remain synthetic;
they do not prove a successful real flip reset or live controller behavior.

Ruff, whitespace and evidence privacy checks passed. The unchanged native binary
and its preceding seven passing native contract checks were reused; no native
rebuild or new package claim is needed for this Python-only correction. Actual
provider token/time/cost totals were unavailable.
