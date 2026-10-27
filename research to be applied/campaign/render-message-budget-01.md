# RENDER-MESSAGE-BUDGET-01 — RLBot render transport and MCT composition

## Finding

There is a hard, source-confirmed **65,535-byte limit for one serialized RLBot InterfacePacket payload**. The MCT renderer currently puts its whole render group in one such packet. Separately, RLBot documents a game-tick byte-budget warning and skipped messages, but the numeric threshold and its per-agent versus shared-server accounting are not exposed in the inspected public source: those details live in `Bridge.dll`, which RLBot Core identifies as closed source. Therefore no render size can yet be called proven safe from disappearing game-side draws.

For initial measurement, use **48 KiB (49,152 bytes) as a proposed soft ceiling per serialized RenderGroup packet**, leaving 16,383 bytes below the 65,535-byte protocol ceiling. This is an engineering margin for the client protocol only; it is not an RLBot server limit or a measured no-drop threshold. Do not treat it as runtime acceptance.

## Exact transport and replacement behavior

Artifact follow-up: [Bridge build-input inspection](bridge-waiter-artifact-01.md) identifies a separate per-messenger allowance of 65,535 payload bytes between explicit counter resets, excluding length prefixes. Its flush can clear a local batch after a normal-return size/budget rejection. This qualifies the earlier unknown-Bridge-boundary finding: the constant is now established in the pinned managed dependency, while its equivalence to the staged NativeAOT server and actual game-tick delivery remain unverified. Do not compare this controller-packet accounting directly with Python InterfacePacket bytes as though they were the same encoding.

Follow-up: the [reviewed serialization diagnostic](render-packet-probe-01.md) measured ten synthetic fixtures at 3,038–8,266 payload bytes. Its largest fixture has 124 messages; 127 remains a conservative independent-branch bound. The run confirms client rejection of a 70,113-byte payload, not game-side delivery or persistence.

The installed package metadata reports `rlbot==2.0.0b56` and `rlbot-flatbuffers==0.19.0`, matching `work/reviewed-training/pyproject.toml:15-16`. The pinned renderer and interface files are:

| Artifact | Bytes | SHA-256 | Relevant lines |
|---|---:|---|---|
| Installed `rlbot/managers/rendering.py` | 11,891 | `7da1cafc8a3d5b57b1677f54de2a6337b8f8c13e07cd210fc7c7cf3a91a5c7a0` | context/send 129-182; clear 184-200; draw 208-253 |
| Installed `rlbot/interface.py` | 13,386 | `abc030a97cda257a988abdb7b3915e5fbfdd981e95373624609200e79eb81822` | cap 14; `send_bytes` 103-113; `send_msg` 115-133 |
| Installed `rlbot_flatbuffers/__init__.pyi` | 162,320 | `5a89d86c709198b9b5748d67cf9fd6045c9c5bc445f13cd7222719fa35e3ca1e` | Render types and group, as listed in [GHOST-VISUAL-01](ghost-visual-01.md) |

`Renderer.context()` collects all draw calls, then `end_rendering()` serializes one `RenderGroup` message and calls `SocketRelay.send_msg`. `send_msg` wraps it in one `InterfacePacket`. `send_bytes` checks the already serialized payload length against `2**16-1`; if larger, it logs an error and returns without sending or notifying the caller. If accepted, it prefixes the payload with the two-byte big-endian length and calls `socket.sendall`. Thus the packet payload can be at most 65,535 bytes; the complete stream frame is up to 65,537 bytes including the prefix.

The server implementation matching the staged runtime is RLBot Core `v5.0.0-rc18`, commit `11d5d863ec2f8b2647741cff22a2c59c6b6ad08e`. The staged `RLBotServer.exe` is 5,594,624 bytes, SHA-256 `454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1`, with ProductVersion `1.0.0+11d5d863ec2f8b2647741cff22a2c59c6b6ad08e`. The release tag is [pinned here](https://github.com/RLBot/core/releases/tag/v5.0.0-rc18). Core's `SpecStreamReader.cs:11-18,21-32` allocates a 65,535-byte payload buffer and reads the two-byte length before that payload, independently confirming the protocol ceiling.

The server routes a RenderGroup together with its `_clientId` into the bridge channel (`FlatBuffersSession.cs:287-303`). The public `Rendering` manager tracks groups by client and render ID. A new group with the same pair clears the previous items before adding and sending the new set (`ManagerTools/Rendering.cs:160-198`); explicit removal is also keyed by client and render ID. The schema says a group persists until overridden or cleared and that clients can clear only their own groups ([pinned `rendering.fbs`](https://github.com/RLBot/flatbuffers-schema/blob/f90c844f2f5118e28647d39b71cbde5a2cd6accf/schema/rendering.fbs#L163-L192)).

This yields one important failure mode: when the Python size check rejects a new full-group packet, there is no replacement or explicit remove, so the server may keep showing the previous same-ID group. A later fitting packet with that ID replaces it. The public sources do not establish whether a game-side skipped draw is retried or whether it leaves a partial group; do not claim either behavior.

## Game-side byte budget and queues

RLBot's v5 [rendering guide](https://wiki.rlbot.org/v5/botmaking/rendering/#rendering-a-large-amount) warns that rendering too much can produce `Too many bytes sent this tick, skipping message`. It recommends reducing rendered data, using `PolyLine3D` for continuous paths, and avoiding redraw every frame. It does not state a numeric limit or whether the skipped unit is one primitive, a bridge message, or a complete group.

Core source shows the boundary. `BridgeContext.cs:13-18,37-43` keeps one `TcpMessenger` and one `Rendering` manager in the handler context. `BridgeHandler.cs:64-82` resets the messenger's byte counter during normal incoming game-message clump processing; its comment says this only approximates a rendered frame because the server does not know exactly when Rocket League renders. This shared wiring suggests a shared interval counter, but the counter and drop policy are implemented in `Bridge.dll`, imported from `Bridge.TCP`. Core's pinned [README](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/README.md#L39-L44) says that DLL is closed source. Therefore:

- The 65,535-byte InterfacePacket cap is confirmed per client message.
- RLBot has a documented game-tick “too many bytes” skip, but its numeric threshold is unknown.
- Public code shows a shared Core messenger/renderer path and an approximate per-clump counter reset; the exact byte-accounting scope (per agent, per game clump, or another aggregation) is **not confirmed**.
- The visible `MaxClearsPerTick = 1024` in `ManagerTools/Rendering.cs:14,226-255` limits **clear operations only**. Overflow is queued FIFO and drained on later game-message clumps. It is not a draw-count or byte limit. This cap counts retired render-item IDs, not incoming RenderMessages; multiple updates/clients may contribute to it.

## Current MCT render-message count

In the audited source, `game_worker.py` checks a 1/30-second render interval at lines 1324-1326 and submits one `Renderer.context("my-career-training")` at lines 1406-1418. The interval configures a nominal 30 Hz update opportunity; it is not a measured tick rate or packet-latency guarantee. Every `draw_line_3d` and `draw_string_2d` contributes one FlatBuffer `RenderMessage`; `draw_polyline_3d` also contributes one message, regardless of how many points it contains.

| Current visual | Source-derived count per visible render group |
|---|---:|
| Car outline from `ghost_lines()` | 41 `Line3D` messages (`recordings.py:407-457`; render loop `game_worker.py:1458-1471`) |
| One gate target | 24 `Line3D` messages (25 points around circle, then adjacent pairs; `game_worker.py:1492-1501`) |
| One goal or supported plane target | 4 `Line3D` messages (`game_worker.py:1502-1515`) |
| Bundled lesson maximum | 72 target line messages: the three-gate Aerial & air-roll lesson (`catalog.py:156-172`) |
| MCT text with all optional conditions and visible practice ghost | Up to 14 `String2D` messages: title + six steps, actions, timing, coaching/interruption text, stage, ghost label and up to two ghost-action lines (`game_worker.py:1419-1490`) |

The current bundled lesson/scenario definitions have at most three gate targets in one lesson; Power Shots draws one goal target. Other catalog target kinds such as carry, recovery, and ball-reset do not match a geometry branch in `draw_target`, so they currently add no target lines. With the three-gate lesson, a visible 41-line ghost, and all text cases present, a conservative structural upper bound is **41 + 72 + 14 = 127 RenderMessages in one RenderGroup**. This is a count of primitives/messages only: it says nothing about serialized byte size because FlatBuffer offsets, point arrays and text lengths contribute variable payload. The three-gate lesson has three instruction steps, so the six-step text bound combines independent branch maxima and is not an attainable bundled maximum established by this audit. No render packet was serialized or measured in this research pass.

Source identities: `game_worker.py` is 90,814 bytes, SHA-256 `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2`; `training/recordings.py` is 22,459 bytes, SHA-256 `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1`; `training/catalog.py` is 9,097 bytes, SHA-256 `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73`.

## Measurable starting budget and acceptance

For a future implementation, instrument the exact packed `InterfacePacket(RenderGroup)` payload, not just primitive count. Track per update: payload bytes, each RenderMessage type count, total PolyLine points, UTF-8 text bytes, render-group ID/client, render call interval, serialization duration, `can_render`, and client-side oversized rejection. Log any RLBot “too many bytes” warning and whether a moving marker/group is still being updated; a client-side byte count cannot expose Bridge's hidden budget by itself.

Use 49,152 bytes as an initial soft ceiling **per serialized InterfacePacket**. Keep the hard client/protocol test at 65,535 bytes. If content approaches the soft ceiling, replace an overlarge candidate with a smaller valid same-ID group (downsample path points while retaining endpoints and splitting at data gaps); do not silently let the Python sender reject it while an old ghost remains. Consider separate event-driven static geometry/text and dynamic playback/HUD groups so static targets are not re-serialized at the 30 Hz render cadence. This reduces repeated client payload but does not establish a game-side aggregate budget.

Use `PolyLine3D` for connected geometry. As a design estimate, the 41 current car edges can be represented by about 18 polylines without joining disconnected edges: two body loops, four body uprights, one nose-arrow path, one roof loop, four roof struts, two underside strokes, and four wheel loops. A 24-segment gate can be one 25-point polyline; a four-edge rectangle can be one closed five-point polyline. This reduces RenderMessage/FlatBuffer table overhead; the point data remains in the packet and still counts toward bytes. The RLBot rendering guide specifically recommends this for continuous geometry.

Minimum future acceptance should record serialized packet sizes for the current maximum composition and proposed car+ball marker+path+HUD composition; assert all generated RenderGroup packets remain under the chosen soft ceiling and hard protocol limit; then run the owned offline v5 rc18 acceptance with rendering enabled and a representative second RLBot client. Confirm no budget warning or missing updates, that the same-ID group visibly replaces prior frames, and that Off/Stop/Return clears it. To determine the hidden game-side threshold and aggregation, the future runtime observation must correlate each sent group and measured bytes with the server warning/rendered sentinel; source alone cannot prove the result. No server/game run, rendering benchmark, or tests were performed for this report.

## Source references

- [RLBot v5 rendering guide](https://wiki.rlbot.org/v5/botmaking/rendering/), especially large-render advice and warning.
- [RLBot v5 packet specification](https://wiki.rlbot.org/v5/framework/sockets-specification/#packet-format), 16-bit big-endian length prefix.
- Pinned [Core `SpecStreamReader.cs`](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/SpecStreamReader.cs#L11-L43), [FlatBuffersSession.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/FlatBuffersSession.cs#L287-L303), [Rendering.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/ManagerTools/Rendering.cs#L160-L255), [BridgeHandler.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/BridgeHandler.cs#L64-L82), and [BridgeContext.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/BridgeContext.cs#L13-L43).
- Pinned [render schema](https://github.com/RLBot/flatbuffers-schema/blob/f90c844f2f5118e28647d39b71cbde5a2cd6accf/schema/rendering.fbs#L56-L192) and [InterfacePacket schema](https://github.com/RLBot/flatbuffers-schema/blob/f90c844f2f5118e28647d39b71cbde5a2cd6accf/schema/interfacepacket.fbs).
- [RLBot Core v5.0.0-rc18 release](https://github.com/RLBot/core/releases/tag/v5.0.0-rc18), matching the staged server ProductVersion commit above.

## Coordinator source checks

The four installed/staged artifact hashes above were independently matched. Core line references were reconciled against original downloaded source bytes, because the web reader removes some blank lines. The source-derived primitive bound has not been serialized or benchmarked.

| Pinned Core file | Bytes | SHA-256 |
|---|---:|---|
| BridgeContext.cs | 3568 | eda0c403a5552b4fbc4cc7c68871c40c742fb54c6eda6501b1c7cbcf67786a60 |
| BridgeHandler.cs | 10064 | d98ee7eaabb86c39a8a7c9ba7658fcc635cab9319be4d6d926c9bbec4b756785 |
| FlatBuffersSession.cs | 20755 | badb09b4b26a3dbcd1915a82056ae08f8989c652adbc743c81ba45cf9131e469 |
| Rendering.cs | 8432 | dd8470506d8ca9ae976adc5f8bd6885d2fee6998a9be424314c3da2fb5bc63df |
| SpecStreamReader.cs | 1249 | 5f33c723f32108b07407ed676f3200a705a61d1302d6df7b714f691fbc9d5e41 |
