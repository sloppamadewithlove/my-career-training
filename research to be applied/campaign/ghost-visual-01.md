# GHOST-VISUAL-01 — feasibility of a richer non-colliding ghost

## Conclusion

An immediately available visual improvement in the current project is to improve the existing RLBot render-only car outline with more deliberate 3D wireframe geometry and a synchronized ball marker/path. The pinned RLBot renderer sends visual messages—lines, polylines, text, and billboard rectangles—not car meshes, materials, or actors. That supports a teaching visualization, but it cannot produce a textured Rocket League car model through the inspected API. If an authentic textured ghost is required, that remains an unresolved renderer integration task; a wireframe improvement does not close it.

BakkesMod’s pinned `CanvasWrapper` is another overlay route: its drawable callback can draw 2D lines, filled triangles, textures, and project world points to screen space. A projected, custom-drawn silhouette is feasible, but it is a screen-space overlay; depth ordering, clipping, and behind-camera behavior still need runtime validation. It is not a native in-world mesh renderer.

Do not use `ServerWrapper::SpawnCar` as a visual shortcut. It creates a game car, and the inspected API does not establish a reliable physics-free clone, safe collision-off behavior, or a render-only ownership lifecycle. Replay wrappers control the match’s replay mode and time; they do not expose a separate replay car that can be composited over a live practice session.

## Existing implementation and ball synchronization

The current `ghost_lines()` builds a generic fixed-dimension car from transformed line segments (recording source `recordings.py:407-457`, SHA-256 `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1`). `game_worker.render()` submits those lines with RLBot `draw_line_3d`; the ghost path does not create a game actor or send recorded actions as player input (`game_worker.py:1406-1472`, SHA-256 `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2`). These are source facts, not a live collision/render acceptance test.

Recordings already store car and ball samples, but `interpolate_pose()` returns only car position, orientation and actions. `relative_placement()` transforms only the car. `GhostPractice.snapshot()` therefore has no ball pose to render (`recordings.py:204-260,307-324,379-405`; `coach.py:507-535`, SHA-256 `0807fda8daf33ae67a9d1f31ccf93ecb10acccd21bb7efa3d9fb8a7fec905325`). For a ball-dependent demonstration, the next render snapshot must calculate car, ball, and displayed logical actions from one playback cursor and the same valid bracketing samples. If the view is offset from the recorded world, apply one identical rigid transform to both positions; the current car-only forward offset changes the car-to-ball relationship. On a gap, hide the paired visualization and inputs together.

## API options

| Route | Supported shape | Ghost-specific limits |
|---|---|---|
| **Pinned RLBot renderer** | `Renderer.draw()` accepts `String2D`, `String3D`, `Line3D`, `PolyLine3D`, `Rect2D`, and `Rect3D`. `draw_line_3d()` accepts world points or anchors; `draw_polyline_3d()` takes world-space points. The flatbuffer anchors attach to an existing car or ball. | No mesh, model, triangle-fill-in-3D, or material draw primitive in the pinned Python renderer. A recorded arbitrary pose is not an in-game car anchor, so submit world-space points as the cursor advances. Use polylines for connected body/roof/wheel loops to reduce render messages; disconnected edges need separate paths. RLBot documents fixed line width and render-message byte limits. |
| **Pinned Bakkes Canvas** | `GameWrapper::RegisterDrawable()` supplies a `CanvasWrapper`; it supports 2D `DrawLine`, `FillTriangle`, `DrawTexture`, and `DrawRotatedTile`, plus `Project`/`ProjectF` from world coordinates to screen points. | Can make a custom 2D sprite or projected/triangulated silhouette. This does not expose an in-world mesh or material, and the inspected declarations do not specify projection clipping, depth testing, or draw order. Treat those as runtime unknowns. The header exposes `UnregisterDrawables()` without an individual registration handle; the installed wrapper delegates to a host interface whose cross-plugin cleanup scope remains unresolved (see [SDK-DRAWABLE-01](sdk-drawable-01.md)). |
| **Spawned game car** | `ServerWrapper` declares `SpawnCar`; `CarWrapper` has `Destroy`; actor wrappers expose transform and collision-related setters. | This is a gameplay actor path, not a render-message path. The API declarations do not prove that disabling collision leaves a harmless, non-interacting visual proxy. Car identity, mesh/loadout cloning, actor ownership, reset/retry behavior and cleanup must all be established before any controlled experiment. Not a supported implementation choice from this evidence. |
| **Replay playback** | `GameWrapper` exposes replay state, replay-server access, and `PlayReplay`/`PlayReplayFromTime`; `ReplayServerWrapper` exposes current time/frame and seek/playback operations. | The public route controls game replay playback. No separate replay-actor or compositing interface appears in these inspected headers, so it is not a way to render an authentic second car over live practice. This is an interface-based inference, not a claim about private APIs. |

### Visual quality and appearance sourcing

The current outline already includes a body box, nose arrow, raised roof cage, underside cross and four wheel loops. Further work would refine those shapes, scale and color/alpha styling and add a synchronized ball marker/path; adding wheels or a roof is not a newly missing feature. A sphere can be approximated by a few world-space rings. Keep the geometry bounded and batch continuous paths as polylines; RLBot notes that too many messages in one tick can be dropped. The current dimensions `(118, 84, 36)` are generic, so tying outline proportions to a recorded hitbox would improve scale but still would not reproduce body styling.

The inspected Bakkes wrappers expose `CarWrapper::GetLoadoutBody()` and a nameplate mesh-component getter, while `MeshComponentWrapper` itself has no mesh/material methods in the pinned header. Those declarations do not provide a source model to clone. A user-provided or newly authored, licensed 2D image can be used in the Canvas overlay, but it will remain a projected sprite. No Rocket League model or texture was extracted or copied for this research.

## Ownership, clearing, and acceptance

RLBot’s `Renderer.context("my-career-training")` begins and submits a named render group; sending a new group replaces that group’s earlier renders, and `clear_render_group()` removes the caller’s group. Current `game_worker.render()` uses that group during each render call, but it returns early when rendering is disabled or shutdown has begun. Worker teardown has no explicit group clear. The later [Core cleanup trace](render-cleanup-01.md) adds per-client removal and handler-wide clear requests, with a conditional queue-progress concern. Verify/reuse group replacement and those cleanup paths for Off/Stop/Next/Return; whether an additional explicit clear is needed depends on that acceptance. Static source does not establish the final visible result after relay shutdown.

For a future Bakkes drawable, follow the plugin unload lifecycle and verify cleanup ownership before invoking unregister-all. The prior wrapper investigation did not establish whether its scope is per-plugin. The pinned [BakkesModSDK README](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/README.md#L16) states that registered drawables are removed on plugin unload. No Bakkes ghost drawable is currently implemented in the audited Python ghost path.

Minimum future proof should demonstrate: (1) the ghost and ball align with one captured timeline and preserve their spatial relation; (2) gaps hide both depictions and controller hints; (3) Off, Stop, retry, lesson change and Return clear stale render groups; (4) render-disabled and worker-shutdown paths leave no stale overlay; (5) observation shows no change to the human car, ball, collision, input, score or completion state; and (6) the geometry remains readable within the renderer’s per-tick budget at varied camera distances and car orientations. No such game acceptance was performed here.

## Artifact identities and source references

The project pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, source archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` (`plugin/CMakeLists.txt:26-32`). Relevant extracted header identities:

| Header | Bytes | SHA-256 | Relevant lines |
|---|---:|---|---|
| `wrappers/GameWrapper.h` | 9,648 | `cae959eb403b56e907132b52d2e3cf3f4ce5bef04446c99e4f8c7f8b4b5446a9` | `GetGameEventAsReplay` 71; drawable registration 94-95; replay calls 159-160 |
| `wrappers/canvaswrapper.h` | 2,280 | `21ac16e4f0dc7e86d7056b751deed3194484e83ddf7064764e57306d5aa945a5` | 19-51 |
| `wrappers/GameEvent/ServerWrapper.h` | 10,846 | `1a0cb037cd8075ac02d910956c4f5367444604431f2f55fb9464eb5fe576d353` | spawn APIs 22-24, 213 |
| `wrappers/ReplayServerWrapper.h` | 800 | `b3258526af13024f5ec7b2d692e3241bef5e76a6aac79e381ab13906571de38b` | 4-22 |
| `wrappers/Engine/ActorWrapper.h` | 8,547 | `28a79a7b922c38be5656ba29ac2613cd920bcb8efde04bdb4dce1380dfd510a3` | collision setters 49-52 |
| `wrappers/GameObject/CarWrapper.h` | 5,566 | `42c0c29c7a2d42a1fc5d55929c5dd6d38f0676dfe894dfb63c4206db79bdcb54` | destroy/body/nameplate getters 32, 35-37 |
| `wrappers/GameObject/CarComponent/PrimitiveComponentWrapper.h` | 7,032 | `47fa8ee1cae328bd0299f86dde3efe31b4ad4a8b84fb4f33a90824d78a555c43` | visibility/collision and transform fields 18-134 |
| `wrappers/GameObject/MeshComponents/MeshComponentWrapper.h` | 288 | `fa07b55837766428117e0631de93ad6dd798b461ec2b69e5ed7772a446a63244` | class body 1-12 |
| `wrappers/ImageWrapper.h` | 1,254 | `2c25a3ab8dc49575881343c5c939574491bc96b057bedfd0016530b2e529af33` | image wrapper declaration |

Installed `pluginsdk.dll` inventory: 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`; REA Evidence `ev_89b826d50e766a634996a29158cb079e259a97baf6804decb9a0f3068b6c4051` reports the complete PE export table (8,801/8,801 entries, no parse issues). This summary does not establish which DLL is loaded or implementations of the wrapper methods.

The project pins `rlbot==2.0.0b56` and `rlbot-flatbuffers==0.19.0` (`pyproject.toml:13-16`). In the inspected installed package, `rlbot/managers/rendering.py` is 11,891 bytes, SHA-256 `7da1cafc8a3d5b57b1677f54de2a6337b8f8c13e07cd210fc7c7cf3a91a5c7a0`; relevant methods are `context` 130-151, group send/clear 153-205, draw type set 208-226, `draw_line_3d` 228-241, and `draw_polyline_3d` 243-253. `rlbot_flatbuffers/__init__.pyi` is 162,320 bytes, SHA-256 `5a89d86c709198b9b5748d67cf9fd6045c9c5bc445f13cd7222719fa35e3ca1e`; `RenderAnchor` 2615-2657, `Line3D` 4903-4947, and `PolyLine3D` 4949 onward.

Primary interface docs: [RLBot v5 Rendering](https://wiki.rlbot.org/v5/botmaking/rendering/); pinned [GameWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h), [canvaswrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/canvaswrapper.h), [ServerWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameEvent/ServerWrapper.h), and [ReplayServerWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/ReplayServerWrapper.h).
