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

Independent source review is pending. Two bounded DeepSeek reviewer requests
returned no visible answer after 3,000 and 7,000 completion tokens respectively;
neither is an approval. Reported costs were $0.002001 and $0.00423972. Stop
repeating that unchanged reviewer request; obtain an approved independent code
review through another available route before integration. The reviewed source
and gameplay evidence remain separate.

The specified GPT-5.6 Codex fallback was also attempted; the existing ChatGPT
login reported that model unsupported, so no review occurred. The owner then
selected GPT-6 Astra max for independent review, with DeepSeek V4.1 Flash 1017
max and GPT-6.1 Sol high for building. A pinned SDK
header declares car spawn and collision-related methods, but declarations alone
do not establish safe translucent, non-contact car rendering or cleanup.
