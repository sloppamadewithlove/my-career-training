# Session improvement receipt — 5 November 2026

Main recorded the requested 45-minute cycle as 20:34–21:19 UTC. This receipt
was written after the deadline. Documentation base:
`d9929d135fb4afcc287f587e2f6dccb19df2237a`. No scheduler configuration was changed.

## Completed improvements and evidence limits

The defender-attribution repair `d733917` includes all configured opponents in
the latest-touch comparison. Its eight new synthetic cases failed before the
repair, including four incorrectly credited goals; 232 focused source checks
then passed. Receipt correction `41d3730` clarifies that defender-touch evidence
is in attempt summaries, not the recording samples. This does not establish
defender usefulness or live shooting acceptance.

The private prerecorded-input experiment `54fad04` initially passed 275 checks
but independent review found a real integration defect. With consecutive game
frames 1200/1201/1202 and wall arrivals 100.000/100.008/100.0167 seconds, the
worker's wall-clock throttle skipped the middle frame. The controller then
treated the skipped dispatch as a gap and aborted. Controller-only tests had
bypassed that production gate.

Repair `cf1a0e4` dispatches prerecorded inputs on observed game packets after
cadence classification. Real `process_packet` regressions fail before that
repair and pass afterward: valid ticks retain every input row despite arrival
jitter, while a genuinely missing game frame immediately sends neutral and
aborts. Cancel/baseline profiles retain their prior throttle. Independent review
accepted the corrected provisional experiment with 281 focused checks passing.
These suites overlap; their counts must not be added. Input adaptation remains
lossy, operator data stays private, and the new profile cannot pass the existing
reference evaluator. No successful demonstration or teaching ghost is established.

## Protect provenance and the owner's work

The old dirty checkout was preserved. Builders used isolated exact-base
checkouts/worktrees; the interpreter import root was checked before testing.
Immutable commits, corrected deltas and explicit review decisions were handed
to main. Published work stayed on separate descriptive branches. The tester's
exact `2c08e74` build remains distinct from the later `d9929d1` source experiment.
Nothing here relabels a loaded binary or infers live proof from a branch head.

Current and future workers should report the base, changed files, exact test
scope and remaining acceptance; reviewers should run the real changed caller,
including its clock, acknowledgement and failure boundaries. Preserve dirty
work, personal data and loaded files rather than repairing them in place.

## Windows build failure resolved to a concrete build strategy

The exact `2c08e74` candidate build reported C1083 in the pinned SDK's
`AttachmentPickup.h`, although the referenced header existed. MSVC 19.44
preprocessing reproduced failure at a raw expanded include length of 267
characters; the normalized target was 232 characters. The redundant relative
include expansion, rather than absent SDK content, explained the failure.

All 184 SDK headers were copied into a separate private scratch directory and
their SHA-256 hashes compared; every copy matched. The same preprocessing probe
passed with a 241-character expanded include. A scan found 381 existing quoted
relative includes, with 11 paths above 259 characters in the original location
and a maximum of 267. No SDK bytes, pin or compiler settings were changed.

The tester moved the exact commit to a shorter isolated worktree. At this
receipt's checkpoint, `MyCareerTraining.dll` had compiled and the remaining
plugin test targets were still building. Full candidate checks, packaging and
live acceptance remained pending. This is not a full native-build pass.

The concrete workflow change is to inspect raw and normalized include lengths
when an existing header produces C1083, then use a shorter exact-commit checkout.
Shaving a few characters from FetchContent's directory would only move the
limit; patching upstream headers was unnecessary. Preserve the pinned archive
hash and normal candidate source/archive receipts in the shorter build.

## Bounded research instead of repeating a timeout

The REA investigator reported that Ghidra did not finish importing the installed
PE within its configured 330000 ms startup deadline. `search_strings` returned
`provider_timeout` with no usable strings; `close_binary` succeeded. The import
did not establish any absence or presence of the requested runtime fields.

The productive alternative used the project's package reader in memory for a
pinned EndGame SWF inventory. It found scoreboard class names, which is static
inventory evidence rather than proof that live player rows can be accessed.
The next decisive step is an owned offline display-tree observation. Do not
repeat the unchanged Ghidra import or turn a class-name inventory into a runtime
access claim. No machine path, game asset bytes or raw output is published here.

## Applied next actions

`DEVELOPMENT_WORKFLOW.md` now requires production packet-dispatch timing tests,
the Windows expanded-path diagnostic and a bounded alternative after an import
timeout. The candidate tester continues the exact-source native/package checks;
the acknowledged game operator separately owns any subsequent offline acceptance.
Ghost promotion still requires successful observed traces and independent review.

This documentation change uses privacy scanning, whitespace checks and manual
diff review. It does not trigger a binary rebuild or alter source, game state,
the scheduled task, credentials, saves or installed assets. Provider token/cost
totals were not supplied for this cycle and are not estimated.
