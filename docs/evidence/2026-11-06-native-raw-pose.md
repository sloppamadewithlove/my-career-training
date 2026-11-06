# Native raw pose diagnostic — 6 November 2026

Base: `e98ae149a92bf71e1d91d3cdc43d666873d8d9ee`. Reviewed source:
`e0da8173f10d41676c709f27e9d649cf0aeef319`.

The existing default-off reset diagnostic additionally copies raw car and ball
rigid-body states and mapped player-controller inputs into the same bounded
private heartbeat. Quaternions are labeled in SDK X/Y/Z/W field order; no Euler
conversion, reset inference, teaching recording or renderer is enabled. The
existing one-shot five-second window, 150-sample limit and scope checks remain.

GPT-6.1 Sol high built Release plugin DLLs with the diagnostic off and on against
the pinned SDK and reported passing native tests, 17 Python checks and Ruff. A
fully populated extreme-value 150-sample payload was 192,631 bytes, below the
2 MiB bridge limit. Independent GPT-6 Astra max found no blocker, verified SDK
field declarations and build provenance, and reported 17 Python checks and the
existing native test passing. Reviewer usage/cost metadata was unavailable.

This samples sequential wrapper reads in a scheduled callback. It does not prove
one physics-frame synchrony, clock/reset semantics, successful flip-reset capture,
the current game's compatibility, a rendered ghost or live non-interference.
No DLL was installed or loaded for these checks.
