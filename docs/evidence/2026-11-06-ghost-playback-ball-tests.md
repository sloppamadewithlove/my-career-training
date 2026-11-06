# Ghost playback ball transport — 6 November 2026

Base: `71cd776084262df0e0512bb66f465096a6d67e05`.
Test change: `2ba83e998baf17f176ff85aa36031069a47bf784`.

Tests exercise the existing `GhostPlayback.update()` and `snapshot()` path for
watch and lead clocks, synchronized car and ball positions, sample-held actions,
packet-gap hiding and recovery, and old recordings without ball data. The
change does not enable a practice ghost or modify production behavior.

The GPT-6.1 Sol high builder reported 29 passing tests and Ruff. Independent
GPT-6 Astra max review found no blocker, reported 102 passing focused tests and
rejected ten in-memory mutations affecting ball values, timing, actions, gaps
and legacy recordings. Synthetic source evidence only: no native render, actual
recording, successful reset or live game was verified.
