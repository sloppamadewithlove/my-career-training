# Native ghost Canvas consumer — 6 November 2026

Base: `936adc2`; initial consumer: `c5493bd`; the correction below is based on
that immutable reviewed consumer. Builder assignment: GPT-6.1 Sol high. This isolated source
adds the actual pinned-SDK Canvas consumer for immutable recorded car/ball
frames. It does not yet connect the plugin's recording or native observation
producer, register itself on startup, enable ghost availability, or contain a
successful flip-reset recording. Main owns integration and independent review.

`NativeGhostRenderer(gameWrapper, currentLease)` is inert until a fresh `submit`.
Its current-lease callback must freshly verify ownership, supported executable,
active training identity, ghost toggle, recording and reset epoch on the game
thread. The consumer independently rechecks actual game/training presence, online,
replay and pause flags and server/car/ball addresses on every draw. Missing or
changed scope clears the cached frame; scope recovery cannot revive it without
submission. Car triangles and the non-contact demonstration ball share one
projection batch. No actors, inputs, camera, score or game state are written.

The producer must use `NativeGhostRenderer::now()` for lease/frame timestamps,
refresh faster than the existing 100 ms frame validity, and prepare a new frame
with the exact renewed lease issuance/expiry. Clear before toggle-off or reset;
each fixed-start retry changes the epoch. Invalid, near-plane or offscreen
geometry hides the whole pair. The renderer restores Canvas color on success or
exception and fails closed after a draw failure.

The SDK exposes filled alpha triangles and screen projection, but no world
depth-test control. The car therefore uses sorted translucent Canvas triangles;
it is a screen overlay and can appear through field geometry. It is self-authored
proxy geometry, not a game model. Actual opacity, appearance, camera conventions
and field occlusion remain live acceptance questions.

Independent review found that the initial normalized colors would be invisible
with the installed SDK. Independent bounded static inspection of installed
`pluginsdk.dll`, SHA256
`421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`,
confirmed direct float-to-integer truncation and byte conversion without scaling
in `SetColor(LinearColor)` at RVA `0x77CB0` and
`FillTriangle(Vector2F,Vector2F,Vector2F,LinearColor)` at RVA `0x78000`.
The correction supplies byte-scale RGBA: car `(38,191,255,31)`, demonstration ball
`(128,230,255,89)`. The SDK test double now reproduces this conversion and asserts
the effective RGB and nonzero translucent alpha values, plus color restoration.
This replaces the initial reliance on normalized-color documentation. It is
static binary evidence, not a live display claim. REA's native provider could not
start with its inherited unavailable temporary directory; the existing MSVC
`dumpbin` supplied the independent bounded export/disassembly evidence.

Production `adapter.match_config` starts lesson workers in offline Soccar with
unlimited time and instant start; native Custom Training is a separate route.
Accordingly, `NativeDrawObservation.workerTraining` is an explicit independent
attestation of the owned active worker lesson. Frame preparation accepts either
that attestation or native Custom Training, while retaining ownership, fresh
observation, verified build, actor, online, replay and pause gates. The consumer
requires actual `IsInGame()` or `IsInCustomTraining()` and the fresh lease callback;
an offline game alone cannot authorize drawing. The producer must independently
attest the current active lesson, recording and toggle, not infer these from
`IsInGame()`. No production scope/pose producer is added here.

The 100 ms frame age does not establish the source telemetry's age if a producer
rewraps a cached packet with a new timestamp. Production wiring must preserve an
actual new telemetry receipt/sample identity, bound its age and reset epoch,
and stop publishing on packet gaps. Generic bridge freshness alone is not this
guarantee. Recording playback age, scope delivery, production tick cadence and
the observation-to-render timing path remain unverified.

The callback holds a weak state reference; `stop()` revokes state before removing
drawables, and retained callbacks then do nothing. The pinned SDK can only remove
all drawables belonging to the plugin's GameWrapper. At this base there are no
other Canvas registrations in the plugin. Keep this as the sole Canvas owner, or
centralize dispatch before adding another Canvas feature. All consumer lifecycle
and scope callbacks run on the game thread; `stop()` must precede producer teardown.

Validation: MSVC 19.44 built the full Release plugin with native movie trial
enabled against pinned SDK `479e8f571cf554b25f4eeb64d611dec4133edcaf`. Five Release
CTests passed: renderer lifecycle against an SDK test double, paired projection,
immutable recorded frame, proxy geometry and draw-observation scope. Both native
Custom Training and explicitly attested worker Soccar are covered. The lifecycle test covers repeated
submission, revocation, native scope/actor identity loss, epoch and lease changes,
stale frames, clear/stop, retained callbacks, draw failures and Canvas color
restoration. The projection test covers painter ordering, finite camera/geometry,
viewport, invalid indices, near-plane and whole-pair failure. The test double
verifies our adapter behavior, not BakkesMod's implementation.

The initial configure failed because inherited TEMP referred to an unavailable
drive; a process-local workspace TEMP/TMP allowed the same toolchain to configure.
No game was opened or controlled, no DLL installed, and no package or loaded-DLL
claim is made. Real recording admission, production scope/pose wiring, fixed-start
synchronization, visible toggle, renderer cleanup in game and non-interference
remain unverified. Provider-reported time/tokens/cost were unavailable.
