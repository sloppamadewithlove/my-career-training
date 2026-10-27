# RENDER-PACKET-PROBE-01 — measured client serialization

## Result and scope

Ten synthetic visual fixtures passed 257 diagnostic assertions using the unchanged frozen `GameSession.render`, `draw_target`, `draw_ghost_actions`, catalog, controller model and ghost-line helper, followed by the installed RLBot renderer and serializer. These are client-pipeline observations, not 257 independent tests or game acceptance. The fixture supplies a small fake engine and explicitly seeded session; it does not run a complete lesson engine, server, game or physics simulation.

The successful run began at 2026-10-27 13:08:25.5666346 UTC and exited 0 after 1.0902515 seconds. That elapsed time is an execution receipt, not a performance benchmark. The installed versions were `rlbot==2.0.0b56` and `rlbot-flatbuffers==0.19.0`.

## Measurements

All eight catalog fixtures enable the default explanation/action/timing/ghost preferences and include a visible 41-line recorded ghost with logical input text and synthetic coaching. Actual catalog text and targets are retained. The final two rows change the named condition; all exact inputs are in the [observation](../evidence/render-packet-observed-02.json).

| Fixture | Line3D | String2D | Total messages | InterfacePacket payload bytes |
| --- | ---: | ---: | ---: | ---: |
| Speed Flip | 45 | 11 | 56 | 3,971 |
| Flip Reset | 41 | 11 | 52 | 3,675 |
| Dribble/Flick | 45 | 11 | 56 | 3,867 |
| Power Shots | 45 | 11 | 56 | 3,860 |
| Shot Placement | 45 | 11 | 56 | 3,871 |
| Fast Aerial | 65 | 11 | 76 | 5,168 |
| Aerial/Air Roll | 113 | 11 | 124 | 8,266 |
| Flight Recovery | 89 | 11 | 100 | 6,723 |
| Power Shots, native HUD requested | 45 | 1 | 46 | 3,038 |
| Aerial/Air Roll, interrupted with coach ghost | 113 | 9 | 122 | 8,038 |

The wire frame adds a two-byte length prefix. The native-HUD request suppresses ten duplicate text messages in this Power Shots fixture while retaining its 45 world-space lines. It does not prove the native HUD actually appeared. The largest measured fixture is 124 messages, not the earlier conservative sum of 127 independent branch maxima. Neither figure establishes a maximum for future content or a game-side rendering budget.

Three direct calls to the unchanged render method produced the same group ID: identical inputs gave identical 3,860-byte payloads; changed logical actions produced a different 3,872-byte payload. The usual worker cadence gate is outside the called render method. Group IDs are process-derived; these observations do not promise a fixed numeric ID across launches.

## Oversized-message behavior

A separate real-renderer sequence sent a short valid group, attempted a 70,113-byte oversized group, sent a fitting 134-byte group using the oversized attempt's name, then explicitly cleared that name. The fake socket recorded three frames, with payloads of 130, 134 and 38 bytes. The oversized attempt logged an error and sent no frame, including no implicit clear. The first short group has a different name; this sequence does not simulate the server retaining an earlier same-name group.

For this sequence only, a recording wrapper serializes the same message object before delegating to the unchanged `SocketRelay.send_msg`; accepted bytes are checked against the actual fake-socket frames. The rejected payload size comes from that same-object capture. No server or socket peer exists. Whether earlier graphics remain visible after rejection or shutdown still needs game-side observation; see [render budget](render-message-budget-01.md) and [cleanup analysis](render-cleanup-01.md).

## Reproduction and provenance

A DeepSeek builder authored the [diagnostic](../experiments/research_render_packet_probe.py.txt), and a separate DeepSeek reviewer checked it. Review corrections covered the FlatBuffers field names and union, session setup, non-vacuous assertions and source identity. The first execution exited 1 before any fixture because a package re-export bound `catalog` as a function. Explicit module imports fixed that diagnostic defect and received independent review before the successful run. The failed run is retained in the [execution receipt](../evidence/render-packet-run-02.json); it is not a product failure or a passed measurement.

Run the diagnostic from an isolated copy of the frozen candidate using the project interpreter with `-B -X utf8`. It emits JSON and writes no result file itself; the parent captures stdout. Installed RLBot logging may issue the Windows console-color shell command during import. No game/server process is launched, no socket is connected/read, and no installed game/plugin file is replaced.

The successful script SHA-256 is `7429d38e50edcbcdb1fd8148b71fc4aba447f89889d17c298f2d4dc904800f49`. Raw successful stdout was 78,760 bytes, SHA-256 `be69872d882b15643dbde1a3301e4fbaf100ef478dfbd3ae63cf5ec502d2ab5f`. Publication may normalize line endings; these identify the private execution bytes. All 55 copied Python source files matched the frozen candidate before the run and remained unchanged afterward. The [source manifest](../evidence/render-packet-source-manifest.json) and [postcheck](../evidence/render-packet-postcheck-02.json) include the imported source and installed renderer/interface fingerprints.

## Application to MCT

Measure serialized bytes when changing ghost detail, labels, target geometry or HUD composition. Keep a rejected update observable to the caller and define its replacement/clear behavior. The proposed 48 KiB engineering margin remains provisional; staying below it is not proof of game-side delivery. Use these fixtures as a reproducible client baseline, then verify appearance, cadence and cleanup on the exact staged artifact in an owned offline session.
