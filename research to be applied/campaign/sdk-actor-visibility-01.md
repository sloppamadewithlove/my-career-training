# SDK-ACTOR-VISIBILITY-01 — public hidden-state wrapper boundaries

## Result

After [SDK-FADE-01](sdk-fade-01.md) established that the inspected ball fade pair is replay-gated, this pass inspected the narrower alternative declared on `ActorWrapper`. In the installed DLL, **`SetHidden2` forwards to `Engine.Actor.SetHidden` without a replay-type check in the inspected wrapper and dispatch helper**. This is an engine request, not a direct proof that a Soccar ball disappears, stops colliding, or can be restored safely.

`SetbHiddenSelf` is different: it changes a single backing field bit directly, without an engine notification in its complete body. `GetbHidden` and `GetbHiddenSelf` read distinct bits. Do not use those names interchangeably or treat the self-hidden setter as the implementation of the general hidden operation.

## Artifact and evidence

REA static analysis with Ghidra 12.1.4; installed x64 `pluginsdk.dll`, 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`. Each of the following five dossiers reported a complete contiguous function body. Evidence was exported privately; the binary session was closed. No game process, SDK call, installed-file mutation or visibility change occurred.

| Function | Address / bytes | Evidence ID |
| --- | --- | --- |
| `ActorWrapper::SetHidden2` | `0x18007e4d0`, 12 | `ev_f39d200f4424b31ee2583aa1b38830d801af4926b8998bce6d2595e81572da3d` |
| Engine SetHidden dispatch helper | `0x180003150`, 283 | `ev_766e4aba7d24d1de2549bf208d4565154e9c2f9fe4630dfdb8367f5f77653812` |
| `ActorWrapper::SetbHiddenSelf` | `0x18007cb90`, 36 | `ev_2769bff75d60a70c8b9dbae6c930767058c127c21eec0688a1c4c2c1602e665c` |
| `ActorWrapper::GetbHidden` | `0x18007cb50`, 19 | `ev_411927e0efa3bdbf71af70891cd3bf5a08018f3a12431844b32c47842ffd6aff` |
| `ActorWrapper::GetbHiddenSelf` | `0x18007cb70`, 20 | `ev_ed87059e6e67dc7937796b6b439239fbd4bf724d36c974ca477f72db2fa774da` |

Addresses identify this exact artifact for analysis; they are not integration offsets. The existing public declarations were recorded in [BALL-VISIBILITY-01](ball-visibility-01.md).

## What is established

- The twelve-byte SetHidden2 wrapper obtains its wrapped actor pointer and forwards the supplied unsigned value to one helper. That helper resolves the named `Function Engine.Actor.SetHidden`, copies the argument into the request structure and dispatches through the actor's engine interface. The helper has no explicit game-mode gate in the inspected body. The unresolved indirect engine call prevents concluding that the native implementation has no additional gate or side effect.
- Neither the wrapper nor the helper establishes a return-value acknowledgement or null-safe actor access. The visible path dereferences its actor and engine function interface. A caller must obtain and validate a current actor through the supported wrapper path; stale wrapper reuse is not justified by this API shape.
- SetbHiddenSelf directly updates the bit read by GetbHiddenSelf. It contains no call to the engine SetHidden helper. GetbHidden reads a different bit. These complete small bodies establish distinct storage access, but not rendering propagation, component behavior, collision, or replication semantics.
- No inspected function reads an attempt clock, runs a timeout, changes ball velocity, or explicitly destroys the actor. That is a boundary of these bodies, not proof that the engine-side SetHidden operation has no physics or lifecycle effect.

## Useful next boundary

Keep the requested behavior explicit: on a timed-out owned training attempt, the ball should become visually absent, the completed attempt should stop accepting outcome evidence, and retry/Return should restore the appropriate current session state. Hiding, fading, stopping physics and destroying an actor are separate behaviors.

The public SetHidden2 route merits a separately owned offline experiment before any production adapter is chosen. Record prior general-hidden and self-hidden values, call only against the current session's ball, and observe the corresponding general-hidden readback, rendered ball/components/shadow, collision and goal/touch behavior. Then verify restoration on manual retry, auto-retry, Return and actor replacement. Also exercise a ball that was already hidden and a user/native visibility change after the request; do not overwrite those states as though MCT owned them.

Passing a prior general-hidden value back to SetHidden2 is a possible restore request, **not a proven inverse**. Readback alone is not visual or physics proof. No offset writes, replay-guard bypass, material replacement, ball destruction or out-of-arena parking is proposed by this report. Until the engine/runtime contract is established, keep the earlier replay fade pair withdrawn and mark ball disappearance as unimplemented/unverified.
