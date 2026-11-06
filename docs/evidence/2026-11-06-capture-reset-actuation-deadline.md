# Capture reset actuation deadline — 6 November 2026

Review base: `59504d6`. Corrected code:
`94b8b7b26ac6018c7efc21249b8da3af5b799c14`. Builder: GPT-6.1 Sol high.
Independent corrected-delta review is pending; main alone publishes.

The integrated review reproduced an actual gap: reset entered marker verification
at elapsed 119 seconds, verification returned at elapsed 130, and the worker still
sent the bot state reset. The earlier outer-loop deadline check did not cover that
synchronous verification interval.

Capture reset now rechecks user cancellation, stopping state and the absolute
flip-capture deadline immediately after marker verification, before calling the
engine reset. It checks again immediately before sending actor state, covering
synchronous state preparation. An expired flip trial aborts and stops without an
actor write; cancellation also prevents the write. Ordinary lesson/native ghost
reset paths and the legacy speed-flip wall-clock policy are unchanged.

Eight new regression cases use validated capture requests and marker files with
the real TrainingEngine reset method. Only the game SDK message boundary is fake.
They exercise slow marker verification and slow desired-state preparation for
actual flip and speed-flip profiles, with deadline expiry or user cancellation.
A late marker prevents even engine reset; late preparation prevents actor send;
the existing speed-flip profile remains permitted when only the flip-specific
wall bound has elapsed. All actor writes in permitted cases still target bot 0.

All 91 reference-capture checks passed. The complete focused integration run passed
222 Python checks with all native transport/parser/menu probes enabled and no
skips. Ruff, whitespace and evidence privacy checks passed. Native C++ inputs are
unchanged, so the preceding full SDK build and 46 passing CTests were retained;
no native rebuild or new package claim is made.

No game was launched or controlled, no DLL installed and nothing published. Tests
remain synthetic execution evidence, not a successful actual flip-reset recording
or live acceptance. Provider-reported time/token/cost totals were unavailable.

The subsequent packet-driven READY-launch correction is recorded in the
[packet actuation deadline receipt](2026-11-06-capture-packet-actuation-deadline.md).
