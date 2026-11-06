# Flip-reset source foundation — 6 November 2026

Integration base: `9ee0c3333686be74afdd5de0e24cde2932b1af61`.
Reviewed source integration: `057fea9f996b35907aee910e460aae4adc3a9886`.
The owner requested a toggleable translucent-looking ghost car that approaches
the ball and demonstrates an actual flip reset. This integration is a foundation,
not that player-visible feature.

It combines reviewed recorded-ball interpolation, production playback transport
tests, the unregistered native position diagnostic, corrected self-authored
car-shaped proxy geometry, and the existing clock-lease regression registered
with CTest. No ghost renderer, SDK pose adapter, actor or ghost availability is
enabled. The older draw-core receipt's statement that the pose interpolator omits
the ball applied to its historical base; this integrated source now includes it.

On this integrated source, 79 focused Python checks passed. With MSVC 19.44,
`MCT_BUILD_PLUGIN=OFF`, the three relevant Release CTest targets passed 3/3.
Independent GPT-6 Astra max reviewed the exact integration and found no blocker;
it did not repeat those tests. The earlier independent component reviews and
corrected mesh overlap are recorded on their separate source branches.

This is not a full plugin build, package, loaded DLL, rendered car or live-game
acceptance. A real permitted successful flip-reset recording, native renderer and
callback cleanup, fixed-start synchronization and no-interference proof remain
open. The existing Python lesson detector requires a prior observed dodge; verify
actual native reset signals before changing that guard. The owner allows the
official `Without EAC` option for offline testing, while Steam stays online.
The requested ten- and 45-minute Codex schedules are not installed: the current
session did not expose the scheduling control.
