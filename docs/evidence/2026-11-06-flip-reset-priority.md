# Flip-reset ghost priority — 6 November 2026

The owner selected flip reset as the first skill to play, with a toggleable
ghost that looks like a translucent car. The requested demonstration approaches
the ball in the air and shows the reset, with a synchronized demonstration ball
and no effect on the real attempt. The owner authorized selecting the official
`Without EAC` option for offline testing if offered; Steam should remain online.
No actual EAC state or game-input ownership follows from that decision.

[Flip Reset Tutorial in 5 Seconds](https://www.youtube.com/watch?v=IMntbm1eDo0)
describes a wall setup, wheel contact with the ball and using the restored flip.
The available browser did not provide playable video or a transcript: this is
description-based research, not a visual examination or a motion capture. It
does not grant permission to copy or distribute a recording.

An isolated, unintegrated change adds optional ball-position interpolation to
the existing car playback clock. It does not enable ghost practice for
ball-dependent lessons or introduce a native renderer. Two runs of 50 focused
Python tests passed, including independent test execution; Ruff passed. Neither
run exercised an actual recording or the game.

The existing Python lesson detector requires an observed `has_dodged` transition
before it accepts reset acquisition, and the lesson text tells the player to use
the initial flip. A direct aerial approach without that observed dodge therefore
cannot pass that detector, even if the game grants a reset. This is a source-path
finding, not a live diagnosis. Before relaxing the guard, verify actual
flip-availability and reset transitions for the native scenario; do not treat an
already available flip as a newly acquired reset.

The existing private RLBot capture worker records a project-controlled bot,
not native Custom Training, and its 120 Hz assumptions are not established for
the current native path. The native diagnostic frame currently has no producer
recording a complete oriented car pose, ball, controls and reset epoch. The
shortest native proof is to establish those sampled signals and a shared game
clock, then validate an actual fixed-start successful reset before enabling
teaching playback. An RLBot trace is not interchangeable without proving its
setup and success match the native lesson.

The first sampler implementation attempt found the required capture authority
missing: `NativeDrawLease` and its reset epoch are supplied only in synthetic
tests, and bridge freshness is not explicit capture intent. Existing owned
session and build checks are not a replacement for that lease. The builder made
no code change and did not arm native reads. Next, define a trusted issuer and
an observed reset-generation boundary using the owned-session flow; do not infer
an attempt from stable wrapper pointers or a merely fresh bridge.

Two bounded DeepSeek reviewer requests
returned no visible answer after 3,000 and 7,000 completion tokens respectively;
neither is an approval. Reported costs were $0.002001 and $0.00423972. Stop
repeating that unchanged reviewer request. GPT-6 Astra max subsequently reviewed
the exact source, found no blockers and reported 98 passing checks; see the
[timeline branch receipt](https://github.com/sloppamadewithlove/my-career-training/blob/feat/ghost-ball-timeline-2026-11-06/docs/evidence/2026-11-06-ghost-ball-timeline.md).
The reviewed source and gameplay evidence remain separate.

The specified GPT-5.6 Codex fallback was also attempted; the existing ChatGPT
login reported that model unsupported, so no review occurred. The owner then
selected GPT-6 Astra max for independent review, with DeepSeek V4.1 Flash 1017
max and GPT-6.1 Sol high for building. A pinned SDK
header declares car spawn and collision-related methods, but declarations alone
do not establish safe translucent, non-contact car rendering or cleanup.

Read-only research of the pinned SDK and existing drawing receipt found no
native car renderer or drawable registration in the current diagnostic core.
Canvas declares projection, filled triangles and alpha color; runtime blending,
callback threading and unload behavior are unverified. The SDK exposes
unregister-all rather than a per-drawable token. The next bounded experiment is
an isolated, explicitly temporary, self-authored filled car-shaped diagnostic
proxy: test alpha, projection, toggle and cleanup in an owned offline session,
and compare real car, ball and score with the proxy off and on. Do not spawn a
game actor for this test. A successful proxy would not prove a final
translucent car model, a permitted successful trace or teaching readiness.

A later read-only inspection identified the installed BakkesMod core as a
4,638,208-byte x64 PE with SHA-256
`1b3226b447606f5552396907e34655de099202f371441bd4ce09bb6c74f20e3e`.
REA's complete export inventory found the drawable registration and removal
entry points. A bounded `dumpbin` fallback showed both paths pass a type key,
and removal reaches a keyed helper. That suggests type-scoped removal, but does
not establish the ownership mapping, synchronization or whether an in-flight
callback is drained. The Ghidra provider was unavailable due to its local temp
volume self-test; other REA disassemblers were unavailable. No runtime claim
follows from the fallback. A proposed two-plugin callback-barrier experiment was
subsequently held: the SDK does not establish the callback thread or make a
concurrent unregister call safe, and a timed callback does not bound an opaque
unregister call. First establish callback thread identity and a supported
registration/unregistration route with a nonblocking isolated observation;
do not use a barrier or access car or ball actors until that contract is known.

The first pure proxy mesh candidate passed edge-pairing and volume checks, but
independent Astra review found overlapping, inward-facing triangles in the
concave side polygon. The correction passed independent review. Improvement: mesh
tests must also check face orientation and coverage/area against the intended
silhouette; a closed edge topology alone does not establish a valid surface.

The older [Ghost Plugin](https://bakkesplugins.com/plugin/174) documents recorded
workshop racing ghosts. Its [map integration guide](https://rocketleaguemapmaking.com/guide/misc/ghostplugin)
describes a map-authored mover and Kismet position/rotation variables, optionally
with a holographic material. This is a custom-map technique, not evidence of a
noncontact car ghost in native Custom Training. The 2021 listing names one supported
map; current compatibility, source license and video playback were not verified.
The current Free Touch catalog mentions ghost races, but its rendering mechanism,
license and Custom Training behavior remain unverified. Neither plugin was
downloaded, installed or executed.
