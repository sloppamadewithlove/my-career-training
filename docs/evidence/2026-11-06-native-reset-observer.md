# Native reset observation candidate — 6 November 2026

Base: `76cc231268b93b18689858c5fc0c2edf0fe57d78`. Source initially
`7fdceab915f2270aebbeb4ef8f3021fe3accae9d`; reviewed correction
`c840848e87d20f73f2c157f6f58f400234033dca`.

The candidate adds an explicitly requested developer diagnostic with backend and
native build opt-ins, both off by default. It observes raw native round, shot
attempt and clock values only under the existing owned offline/build/mode gates.
Each request has a nonrenewable maximum five-second observation window and a
150-sample limit. It issues no capture lease, reset generation, ghost recording,
actor mutation or renderer. The existing same-user bridge provides request
attribution, not authentication against another process under that user.

GPT-6.1 Sol high built both Release DLL configurations against the pinned SDK,
with the movie trial enabled and reset observation respectively OFF and ON.
Native CTest passed 1/1 in each configuration; 47 focused Python checks and Ruff
passed. Independent GPT-6 Astra max found two deadline/acknowledgement defects in
the initial source. Sol reproduced and corrected them; Astra cleared the corrected
delta after 17 Python tests and 1/1 native CTest using the builder's binary.
The correction keeps the original observation deadline, then accepts an attributed
terminal heartbeat for at most one additional second. Existing private heartbeat
data remains the diagnostic result; no new durable export is provided.

These DLLs have not been installed or loaded. The existing build gate targets
an earlier game runtime. Current-game compatibility, native clock and reset
semantics, wrapper behavior, live ownership and no-interference remain unverified.
This diagnostic is not a successful flip-reset trace or a visible ghost.

For a future owned offline test, first prove updated executable compatibility and
the exact loaded candidate, then arm one request before a single deliberate
native retry within the five-second window. Compare the raw before/after round,
shot-attempt and clock observations with the visible input and resulting state.
Missing samples, unchanged values or a timeout are inconclusive; repeat only
after diagnosing the observed failure and establishing a fresh authorized session.
Preserve and reconcile the real game profile separately from the copied Career.
