# Recorded ghost production wiring — 6 November 2026

Implementation base: `fc3195e`. Wiring commits: `d5f8337`, `d7288a3`.
Builder assignment: GPT-6.1 Sol high. This is source integration and synthetic
transport evidence, not a rendered or accepted flip-reset demonstration.

## Explicit dependency

The patch consumes `nativeGhostSampleFromState` in `NativeGhostRecording.h`
and its paired recorded-worker telemetry contract. That companion implementation
is `678f7d7` plus correction `ad85a88`, subject to its separate review. These
commits were not added to the implementation branch. Integrate its final reviewed
replacement before this patch. The adapter header used for compilation has SHA256
`f740ca93bc363265906a025d2f6d9db5f73cac6550e4983c3e295d191ac7df63`.

A separate verification checkout combined the base, both companion commits and
both wiring commits at `440b3d2fbc2521247f7b5a0ae67b6ba232e860ac`. That temporary
combination is preliminary evidence, not authorization to integrate the companion.

## Function contract

1. Preconditions: the actual owned offline worker lesson is running; the native
   movie host independently verifies the executable hash, BakkesMod core and live
   game build; the companion adapter admits an enabled, visible, compatible paired
   recording; a continuous active packet is less than 100 ms old.
2. Input: the existing ghost toggle and recorded playback telemetry. This patch
   installs no new input binding or recording-selection rule.
3. Outcome: the production game-thread tick submits the recorded car and ball to
   the reviewed Canvas renderer. Every draw rechecks ownership, active worker,
   build, toggle/recording admission, native event/car/ball/round and packet age.
   The active worker lesson is explicitly attested; an ordinary offline match is
   insufficient. No game actors, inputs, camera, scoring or scenario state are
   changed by the native ghost host.
4. Persistence: only the existing ephemeral worker telemetry and atomic bridge
   snapshot gain source metadata. No saves or recordings are rewritten.
5. Failure/recovery: missing metadata, pause/replay/online, build/scope loss,
   packet gaps, wrong session, out-of-order source or expiry clears rendering.
   A cleared cached packet cannot revive itself; a newer admissible callback is
   required. Retry/attempt and native actor/round changes advance the draw epoch.
   Unload stops the renderer before destroying its producer and native movie host;
   tick exceptions clear both producer and consumer snapshots.
6. Acceptance: the native build and tests below establish source contracts. An
   actual successful permitted recording, loaded exact DLL, visible synchronized
   demonstration, live cleanup and non-interference remain required separately.

## Source age and transport

`GameSession.receive_packet` samples Windows `GetTickCount64` at the actual RLBot
packet callback, before inbox coalescing and worker processing. Its frozen envelope
carries a per-worker increasing sequence. The worker emits that exact uptime in
`telemetry.native_ghost_source`, together with session, attempt, active phase and
the production cadence classifier's packet-gap result. Direct packet calls without
the callback envelope supply no native age authority.

Python binds the Win32 result as an unsigned 64-bit integer; the native host uses
the same Win32 function. Both clocks count milliseconds since the same system boot.
The host rejects future receipts and receipts aged 100 ms or more. It converts the
remaining lifetime once to the renderer's steady-clock domain. Re-reading the same
sequence preserves that exact frame and expiry. A fresh bridge `published_at` never
extends source age. No wall-clock timestamp grants rendering permission.

The existing normal bridge interval is 100 ms. While the same running worker has
a visible enabled ghost, `FileBridge.poll()` requests 33 ms and bootstrap applies
that interval. Off and scope loss restore 100 ms. Faster publication retains the
original source receipt, so it cannot keep stalled telemetry visible. This increases
state-file publication while active; actual scheduling, file latency, CPU cost and
visible jitter still require live measurement. The age limit was not increased.

## Validation and limits

The full Release DLL compiled with MSVC 19.44, native movie trial enabled, pinned
SDK `479e8f571cf554b25f4eeb64d611dec4133edcaf`, and the exact companion adapter header
above supplied as an external build dependency. Six relevant CTests passed:
playback, renderer lifecycle, paired projection, immutable frame, proxy geometry
and native draw observation. This is not a self-contained build of the dependency-free
implementation branch, a package build or a loaded DLL.

The implementation branch passed 73 focused Python checks with the companion
transport check skipped. The preliminary combined checkout passed all 74 of those
checks, including the actual worker callback, inbox, production packet dispatcher,
Backend, FileBridge, companion native parser and native lease consumer. The test
also runs the real Win32 clock in Python and a separate native process and checks
their shared range before using synthetic packet timings. It proves fresh display,
heartbeat-only expiry, recovery with a newer callback and rejection after delivery
delay. Synthetic recording fixtures are never claimed as successful gameplay.

Native unit checks cover missing/future/late receipts, repeated heartbeat snapshots,
sequence rollback, gaps, retry epochs, native identity and scope loss, toggle loss
and fresh recovery. Ruff passed for changed Python files. No game was launched,
controlled or modified, no DLL installed and nothing published.

The existing native movie build verifier remains unchanged and still pins its
earlier executable. An updated unmatched executable fails closed. This patch does
not declare compatibility with the new game update or bypass that verifier. The
renderer also retains its documented screen-overlay/occlusion limitations. Actual
provider time/token/cost totals were unavailable.
