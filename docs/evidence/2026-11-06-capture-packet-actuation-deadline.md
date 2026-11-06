# Capture packet actuation deadline — 6 November 2026

Review base: `d5d3d1e`. Corrected code:
`44228d76b083fb954fa15fd83d1947301ecebe2d`. Builder: GPT-6.1 Sol high.
Independent corrected-delta review is pending; main alone publishes.

The reviewed direct-reset correction passed, but packet-driven settling could
still reach READY, begin synchronous desired-state preparation at elapsed 119
seconds and send the launch after that preparation returned at elapsed 130.
Cancellation during the same preparation also failed to prevent that launch.

All three worker actor-state send paths now use one small sending method. It
checks capture cancellation, stopping state and the absolute flip-capture wall
deadline immediately before the SDK send. The paths are direct reset, scenario
setup and packet-driven launch. The existing post-marker/pre-engine-reset check
remains. Ordinary lesson/native ghost behavior and the speed-flip profile's
existing wall-clock policy are unchanged.

The send-site audit found no other runtime actor-state sends. Remaining relay
messages initialize relays or send player inputs; capture policy inputs already
have a deadline/cancellation check after policy preparation. The command-line
desired-state self-check only packs a message and does not send it.

Five new regression cases use validated flip and speed-flip capture profiles,
real TrainingEngine reset/settling and the actual receive-packet/inbox/process
route. The SDK converter is the controlled delay/cancellation boundary, with the
SDK send recorded by a fake transport. Flip expiry and capture cancellation
produce no launch send. Speed-flip expiry of only the flip-specific bound, and
the ordinary lesson path, retain their prior behavior. Allowed writes target
actor 0. These complement the eight direct-reset boundary cases.

All 96 reference-capture tests passed. The combined capture, worker, source
freshness, ghost practice, bridge and compiled native transport run passed 227
Python tests, with all native probes enabled and no skips. Ruff, whitespace and
evidence privacy checks passed. Native C++ inputs are unchanged, so the preceding
full SDK build and 46 passing CTests remain the native evidence; no rebuild or
new package claim is made.

No game was launched or controlled, no DLL installed and nothing published. These
tests do not establish a successful actual flip-reset recording or live acceptance.
Provider-reported time/token/cost totals were unavailable.
