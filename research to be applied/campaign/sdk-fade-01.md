# SDK-FADE-01 — installed ball fade wrappers are replay-gated

## Result and correction

The installed `pluginsdk.dll` does not support the earlier assumption that the named `BallWrapper::FadeOutBall()` / `FadeInBall()` pair is a suitable first candidate for ordinary MCT Power Shots. **Both inspected wrapper bodies return without their effect when a shared replay-type guard is false.** That guard obtains WorldInfo and checks the associated object's class ancestry against `TAGame.GameInfo_Replay_TA`. This is static evidence of a replay restriction, not an observed live call.

MCT's ordinary lesson is an RLBot Soccar session, with replay excluded by its ownership gates. Withdraw the proposed use of this pair from [BALL-VISIBILITY-01](ball-visibility-01.md) for that session. A declaration and apparent inverse name did not establish applicability. Do not work around this restriction by writing offsets or calling internal engine functions.

## Artifact and method

Read-only REA analysis, Ghidra 12.1.4, of installed x64 `pluginsdk.dll`, 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`. Six exact function dossiers were inspected. Each reported a complete contiguous body; indirect engine dispatch remains unresolved. The eight-record evidence bundle was retained privately and the binary session closed. No game process was attached, no wrapper called, and no installed file changed.

| Function | Address / body bytes | Evidence ID |
| --- | --- | --- |
| `BallWrapper::FadeOutBall` | `0x180092740`, 733 | `ev_de9663dc5b68f9a64177a6066a5134c5465cb36fa5c28c284d5735aa7f1783b5` |
| `BallWrapper::FadeInBall` | `0x180092a20`, 545 | `ev_7a62ad41410bb242e675eb9fea69f381b93d8745a4b30f507653356a1bed1a35` |
| `BallWrapper::GetbFadeOut` | `0x180092e10`, 20 | `ev_30d650eb14b7c0ac164286fd29c1d702a9f0fca5ad5ae420886c6518e4bbe941` |
| Material scalar helper | `0x180005710`, 309 | `ev_2bb6a70f93e5ce78d542bbe856651ac8b96c35692f156d4b628e49d5c69e3807` |
| Shared replay-type guard | `0x1800b6f10`, 101 | `ev_a5e5aebdad2774b668ecd68f2c53d69f318051002bd99087587978dcf868af6c` |
| WorldInfo query helper | `0x180003e80`, 306 | `ev_cfa478ae941f88477ae34fbb96787e1c0c3ec5dae479fc45672e58d3cbc1201d` |

Addresses identify this exact artifact for reproducibility; they are not integration offsets.

## What the bodies establish

1. Both fade wrappers call the same guard and test its low-byte Boolean result before doing their work. The guard returns true only after matching the replay class in an ancestry walk. Its context helper resolves `Engine.WorldInfo.GetWorldInfo` and dispatches that query through the engine. The meaning of the associated object is inferred from that type check; the returned live object was not observed.
2. Inside the allowed path, FadeOut enumerates material objects, filters for `Engine.MaterialInstanceConstant`, and sends the `Dissolve` scalar with zero through the inspected scalar helper. It then requires a compatible `TAGame.FXActor_Ball_TA`, sets the bit read by `GetbFadeOut`, and dispatches the named `TAGame.FXActor_Ball_TA.StartBallFadeOut` function. The latter engine function's implementation was not recovered here. Duration, collision effects, final pixels, and eventual cleanup remain unknown.
3. FadeIn resolves and dispatches `Engine.MeshComponent.GetDefaultMaterial` and `SetMaterial` for slot zero. Its inspected body has no direct clearing of the fade bit and no symmetric `StartBallFadeIn` call. Engine-side material effects are unknown. Calling it an exact state-restoring inverse would exceed the evidence; default-material replacement could also differ from restoring a previously customized material.
4. The getter reads the same bit that FadeOut sets. That links a flag to the wrapper's write, but does not turn the flag into proof of disappearance or restored physics. The getter itself has no validity guard in its twenty-byte body, so callers still need valid current wrappers.

## Consequence for implementation

Keep terminal-timeout signaling and ownership design from [ATTEMPT-END-01](attempt-end-01.md): the worker owns the attempt clock, and an eventual visual effect needs current session, attempt and actor identity plus explicit restoration. **The specific fade adapter is not ready to implement for Soccar.** First identify a supported public operation with the correct mode contract, or capture the stock built-in training lifecycle in a separately owned acceptance session. Do not substitute destruction, hidden-field offsets, material replacement, or moving the ball outside the arena as an equivalent effect.

This narrows an implementation choice; it does not prove that every SDK version behaves identically or that all possible ball-visibility interfaces are unavailable. The build's SDK header pin and installed runtime artifact remain separate provenance boundaries.
