# Native drawing diagnostic core

Base: `bd9336d869363c51375bb9c35f0ae351aea74bb0`.
Status: `a983c6183c7b7f9a1cefbad05d0da39d01791912` independently reviewed;
pure source-only diagnostic preparation, synthetic checks only.
No drawable is registered or armed; no visible feature is enabled.

The native Custom Training path has no RLBot worker. Existing recorded ghost
rendering lives in that worker; its translated car-only placement explicitly
rejects ball-dependent drills. Recorded samples already hold car, ball and
logical actions together, but the current pose interpolator omits the ball.
There is no accepted native teaching demonstration supplied by this work.

`NativeTrainingDrawProbe.h` prepares an immutable frame from one caller-supplied
observation and an exact short-lived identity lease. It copies six fixed world
position-marker lines and logical actions. The markers are diagnostic crosses,
not an oriented teaching car or trajectory. Missing ownership/freshness/build
proof, non-native mode, pause/online/replay, unobserved data, nonfinite values,
identity mismatch, stale/future samples and lease expiry produce no frame.
Cached consumers can recheck freshness and the complete lease identity.

The identity includes process creation, nonce, event/car/ball identities, round
and an explicitly supplied epoch. This does not discover a native reset or grant
ownership: a future trusted producer must establish those fields. A future
adapter must replace its cached frame with null whenever preparation fails.
The source neither registers callbacks nor reads wrappers, files, sockets or
input devices. It cannot spawn/reset actors, send controls or certify success.

Pinned SDK declarations provide `RegisterDrawable`, `ProjectF`, `DrawLine` and
car/ball/input getters. Registration ownership, callback thread, unload cleanup,
camera clipping and runtime wrapper behavior are not proved here. No renderer
adapter is added before those questions are independently checked. Existing
native polling is 30 Hz; this work makes no 120 Hz capture claim.

Future teaching playback separately requires an immutable permitted actual
successful execution, independently validated for its exact lesson/setup, with
car, ball and logical inputs sampled on one timeline. Flip-reset/shot playback
must retain a fixed scenario start. Native clock, round and reset-epoch semantics
need observation; no initial-state reset or inferred timeout is sufficient.
Imported success metadata alone must not enable a validated teaching feature.

The dedicated C++ test compiled with MSVC 19.44 in C++17 mode with `/W4` and
passed immutable-copy, mode/scope/identity, frame age, lease and invalid-data
cases. Independent review built the dedicated CMake target and its CTest passed
1/1. Full plugin/package builds were not run for this diagnostic core.
Privacy and diff checks passed. No game action, installation change, private
recording or native asset is included.
