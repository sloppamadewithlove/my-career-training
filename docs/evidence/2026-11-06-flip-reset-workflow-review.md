# Flip-reset workflow review — 6 November 2026

Active work began at 18:04:11 UTC. The requested 45-minute review was due at
18:49:11 UTC and began at 18:49:16 UTC, five seconds later. This was tracked
within the active chat, not by an installed timer; the current session exposed
no Codex scheduling control. No unattended continuation is claimed.

## Evidence and changes

- Owner priority is an actual-looking translucent, toggleable flip-reset ghost.
  The native-results source and gameplay checkpoints remain distinct from the
  reviewed source-only foundation at `76cc231268b93b18689858c5fc0c2edf0fe57d78`.
  Its focused checks were 79 Python tests and 3/3 CTests; no game or full
  plugin package was tested in this continuation.
- Two DeepSeek review requests yielded no visible answer after 3,000 and 7,000
  completion tokens. A GPT-5.6 fallback was unavailable. The owner selected
  GPT-6 Astra max for independent review and DeepSeek V4.1 Flash 1017 max or
  GPT-6.1 Sol high for code building. Record actual model and provider telemetry;
  do not count empty responses as review, or repeat unchanged calls.
- Astra found that a triangulated concave proxy could pass edge/volume checks
  while overlapping and facing inward. Sol reproduced and corrected it; Astra
  independently cleared the delta. Future mesh tests must check side winding,
  coverage and overlap in addition to topology. This is pure geometry evidence.
- Static SDK/PE findings suggest drawable removal is type-keyed, but callback
  thread safety and in-flight drain are unknown. A timed barrier alone does not
  bound an opaque unregister call. First establish a nonblocking documented
  route; do not assert safe unload based on the existing declarations.
- A same-user bridge nonce provides routing and attribution, not protection
  against another process running as the same user. The pending development-only
  reset observer independently checks native build and scope, and must not claim
  authenticated IPC or infer reset identity from freshness. Its source is still
  under builder verification; independent review is required before integration.
- After this review began, Astra found two diagnostic completion failures: the
  native test advanced monotonic time while leaving wall time unchanged, masking
  expiry being reported as failure; the backend withdrew its request before a
  normally delayed terminal heartbeat could arrive. The builder reproduced both
  and is correcting them. Future time-boundary tests must advance wall and
  monotonic clocks together and exercise realistic acknowledgement delay without
  renewing observation authority. Raw results remain in the existing private
  heartbeat; adding another export is unnecessary for this diagnostic.
  The corrected observer was subsequently reviewed by Astra with no new blocker
  and published on `experiment/native-flip-capture-2026-11-06`; it remains a
  default-off source/compiled candidate with no loaded or live-game acceptance.
- The game's updated executable matches the previously identified hash in a
  read-only check. That does not establish that the candidate loads or works.
  The user authorized the official `Without EAC` option for offline testing;
  separate game-session ownership and the requested testing handoff remain open.

## Next cycle

Freeze and independently review the bounded reset-observation candidate; resolve
any review findings before integration. Obtain a fresh game-testing handoff and
establish updated-game compatibility before a live observation. The actual
successful flip-reset trace, translucent native car, cleanup and non-interference
remain required. Next active review target: 19:34:16 UTC, only while this chat
is actively working; no persisted schedule is implied.
