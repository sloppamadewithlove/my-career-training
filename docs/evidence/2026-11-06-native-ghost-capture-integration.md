# Native ghost and bounded capture integration — 6 November 2026

Integration base: `35f4d83`. Final code:
`0a765088b4132b7cb7a08ed7ea8e3a0343178cad`. Builder: GPT-6.1 Sol high.
Independent review of this exact integration is pending; main alone publishes.

The reviewed production wiring chain `d5f8337`, `d7288a3`, `19891da`, `09ab19b`,
`85df20a`, `200f630`, `fcd04da` is integrated with the already-published recording
producer, malformed-index repairs, observed acquisition evidence and bounded bot
capture/deadline corrections. The only textual conflict was the Backend constructor:
both the validated-recording cache and native retry state are retained.

The actual packet callback still captures source uptime, sequence, reset generation
and applied ghost-command identity before inbox coalescing. The game-thread native
consumer retains ownership/build/actor checks, strict source expiry, the reset fence
and acknowledged assistance Off/On ordering. Both speed flip and flip reset retain
paired car/ball playback; no new game models or recordings are supplied.

One integration adjustment keeps the ghost-only reset fence outside development
capture. Capture prohibits playback and supplies no render generation. It therefore
does not perform ghost bridge I/O before its initial bot reset. The existing capture
mapping, Human exclusion, single-attempt rule, absolute startup/handshake deadline
and post-policy-call deadline checks remain intact. The new regression runs capture
reset with and without the native frontend, fails if it enters ghost bridge reads,
checks the initial write targets the bot, verifies no render generation and rejects
the second flip-reset attempt.

## Exact integration checks

- 214 focused Python checks passed, with all three native transport/parser/menu
  probe environment variables enabled and no skips. This includes actual Backend →
  worker → packet → FileBridge → compiled consumer retry/automatic-reset/assistance
  roundtrips, both lessons, source age, delayed/reordered acknowledgements and
  telemetry, complete reference-capture tests, real installed-policy inference,
  startup/handshake deadlines and late policy return rejection.
- Full Release native SDK build passed with MSVC 19.44, native movie trial enabled,
  pinned SDK `479e8f571cf554b25f4eeb64d611dec4133edcaf` and the pinned JSON cache.
  All source/header inputs came from this integrated checkout; no external companion
  header substitution was used.
- All 46 CTests passed. The first full run passed 44 and exposed two unchanged
  Workshop fixture guards: their executables require a literal `build` directory
  component. Setting the CMake runtime output to the checkout's private
  `build/native-sdk-check` directory and relinking resolved the location constraint.
  No test or fixture safety guard was weakened.
- The three complete worker/native transport cases were repeated against the final
  relocated native probe and passed. Ruff, whitespace and evidence privacy checks
  passed.

Final Release DLL SHA256:
`2516339f8640858628e298c37134f047487b171da2f168010e7ae72335f783b2`.
This hash identifies a compiled source candidate, not a packaged or loaded plugin.

No game was launched, controlled or changed, no DLL installed, no package built and
nothing published. No actual successful teaching recording or live non-interference
acceptance is claimed. Existing unmatched-game-build refusal, Canvas overlay/depth
limitations and live performance/controller checks remain open. Provider-reported
time/token/cost totals were unavailable.
