# MAP-GEOMETRY-01 — Workshop arena geometry contract

Date: 2026-10-27
Scope: static read of the frozen `work/reviewed-training` candidate, its pinned RLBot package declarations, and official RLBot schema/documentation. This covers geometry and physics facts needed by a future map-specific lesson. It does not repeat the Workshop launch/arrival protocol. No map package was opened or extracted; no game operation, build, package download or test was run. Public documentation was read over the network.

## Finding

The current Power Shots definitions and outcome checks use a standard Soccar coordinate model and several fixed world-space planes. The frozen Python worker rejects Workshop/custom-map requests and its RLBot adapter only constructs matches for a small built-in arena allowlist (`adapter.py:40-43, 99-120`; `map_guard.py:76-81`). There is no per-map geometry profile or transform in the lesson data. Treating the existing constants as custom-map dimensions would be unsupported.

RLBot's public packet schema provides useful partial geometry: goal center/orientation/width/height, static boost-pad positions/types, car hitboxes/offsets, ball collision shape, the list of current balls, match gravity and game speed, team/score, match phase, and player state. It does not expose the arena's collision surfaces, wall curvature, floor/ceiling/bounds, backboard/post/crossbar mesh, or a map identity in `FieldInfo` or `GamePacket`. The adapter also drops several of the available fields before they reach the lesson engine. Therefore, a future map lesson needs an independently validated, versioned arena profile plus an observed session contract; packet telemetry alone cannot certify arbitrary map geometry.

## Current coordinate and geometry assumptions

The RLBot documentation inspected on 2026-10-27 defines Unreal-unit coordinates with Z up, Blue's goal toward negative Y, standard side walls at X ±4096, back walls at Y ±5120, ceiling at Z 2048, a goal 1785 units wide and 642.775 high, and a goal depth of 880. It describes the wall corners and floor ramp as curved rather than a single rectangular enclosure. The documented values are standard-field references, not guarantees for every built-in map or Workshop arena. ([RLBot useful game values](https://wiki.rlbot.org/v5/botmaking/useful-game-values/#basic-dimensions))

The scenario source hardcodes `_SIDE_WALL_X = -4096`, `_BACK_WALL_Y = 5120`, `_GOAL_MOUTH_HALF_WIDTH = 893`, and `_BALL_RADIUS = 93.15` (`scenarios.py:24-27`). The standard-field reference lists goal center-to-post as 892.755, resting ball-center height as 93.15, and ball collision radius as 91.25. Thus `93.15` is a local scenario value, not the documented collision radius. In `_launch`, the side-wall case reflects the receiving lane about X=-4096; the backboard case reflects about Y=5120 and applies an `impact_x` exclusion check using 893+93.15 (`scenarios.py:217-229`). These are authored launch calculations, not geometry queries against the active arena.

Other fixed assumptions in this candidate:

- Scenario starts, receiving lanes, opponent poses, and target rectangles are authored directly in the standard field coordinate frame (`scenarios.py:52-147, 247-357`). There is no map-origin/basis transform or map-keyed geometry lookup.
- Mirroring is an X=0 reflection: position/velocity X changes sign; angular velocity is reflected as an axial vector; yaw becomes `π-yaw` and roll changes sign; target center X and receiving-lane X also change sign (`scenarios.py:169-205`). This is valid only when the map, collision surfaces, goal assignments, and lesson objective have the corresponding lateral symmetry. It is not a generic team-side or arbitrary map transform.
- The engine sets `ball_out` when the ball center has `abs(x)>4096`, `abs(y)>5120`, or `z>2044` (`engine.py:531-532`). This is an axis-aligned center-point cutoff: it does not inspect ball shape/radius, wall curves, the goal cavity, or a floor crossing. `ball_out` only selects failure feedback after an attempt ends (`engine.py:1233-1250`); it is not the success predicate.
- The `goal` target detector only recognizes a positive-Y ball-center crossing of Y=5120, then checks that crossing point against a lesson-authored X/Z rectangle (`engine.py:1137-1162`). Its own event text defines this as a marked-zone crossing, separate from authoritative score. For a Power Shots scenario, credit additionally requires the observed contact/score chain; the rectangle is not a physical ball-versus-post/crossbar test (`engine.py:477-579`).
- The shared lesson target can be offset from goal center and can use up to a 900-unit half-width (`scenarios.py:52-147, 152, 355-357`). Do not interpret a target rectangle as the actual goal aperture. The Power Shots scenario path additionally requires a team-score edge. Legacy Shot Placement instead completes from contact and target-plane evidence, so the current lesson family does not universally use game score as its completion authority. See [Shot Placement](shot-placement-01.md).

The 2044 center cutoff sits below the documented standard ceiling coordinate 2048, and the source does not document why. It must remain labeled as the candidate's feedback threshold, not a ceiling measurement. The X/Y checks likewise simplify a standard arena with rounded corners, ramps, and a goal cavity into a box. No physical meaning is established for those cutoffs on a nonstandard arena.

## What the pinned RLBot data can supply

The project pins `rlbot==2.0.0b56` and `rlbot-flatbuffers==0.19.0` (`pyproject.toml:10-16`; `uv.lock:306-324`). The lock records the Windows wheel SHA-256 values `d5ca879e4fc0fdeef591413d56d24797a005a8c7af03e734ce2795dde2ffa2df` and `e9ae909cdcaf259719992eeeb77f96b813f0c20a2a5a9241423376d5f754ee70` respectively.

The public RLBot schema at commit `e27de77b4ae2cd9fef5bfea53994be7e24454b47` declares the following. This pins the cited public schema; it is not a claim that the installed wheel was built from that commit:

- `FieldInfo`: boost pads, goals, and Dropshot tiles only. `GoalInfo` provides owning team, center location, outward direction, width, and height; `BoostPad` provides location and full-boost flag. ([schema: `FieldInfo`/`GoalInfo`/`BoostPad`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L415-L463))
- `GamePacket`: arrays of players, dynamic boost-pad state, balls, match information, team scores, and Dropshot tile damage. `BallInfo` includes a collision-shape union with box, sphere, and cylinder variants; `MatchInfo` includes world gravity Z and game speed. ([schema: `BallInfo`/`MatchInfo`/`GamePacket`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L276-L409))
- `PlayerInfo`: car hitbox and local hitbox offset, team, boost, latest touch, air/jump/dodge information, and last controller input. ([schema: `PlayerInfo`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L179-L274))
- `MatchConfiguration`: requested `game_map_upk`, mode, players, mutators, state-setting, and freeplay flag. Its mutator declaration includes ball count/type/weight/size/bounciness, gravity, boost and other rules. This is configuration data, not a field in every live `GamePacket`; the schema does not establish that a request was applied. ([schema: `MutatorSettings`/`MatchConfiguration`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/matchconfig.fbs#L454-L604), [map and configuration fields](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/matchconfig.fbs#L629-L686))

RLBot's Game Data documentation says `FieldInfo` is sent at match start and `GamePacket` provides live state at 120 Hz; the useful-values page warns that boost-pad locations can vary by map and recommends using `FieldInfo`. ([Game Data](https://wiki.rlbot.org/v5/botmaking/game-data/), [boost-pad variation](https://wiki.rlbot.org/v5/botmaking/useful-game-values/#boost-pads))

### Fields currently dropped or not used by the lesson path

`adapter.normalized_packet` copies player kinematics, teams, boost, jump state, touches, actions, boost-pad locations/active/full flags, match time/frame/game speed, and only `packet.balls[0].physics` (`adapter.py:133-164`). It does not retain `FieldInfo.goals`, ball `shape`, additional balls, `match_info.world_gravity_z`, or the submitted map/mutator configuration in the normal lesson frame. `desired_state` always writes ball index 0 and car poses/boost; it does not choose a ball shape or validate collision against arena surfaces (`adapter.py:167-203`).

`game_worker` does observe each player's hitbox and offset through `observed_hitbox`, but the cited use is capture metadata; this geometry is not part of normal lesson frame normalization (`game_worker.py:206-210, 1157-1189`). It stores `FieldInfo` and passes it to the adapter, whose current copy loop consumes only pads (`game_worker.py:560, 1563-1566`; `adapter.py:151-156`). `capture_arena` records a requested/configured map name for a distinct capture metadata path, not a live map identity in normal lesson telemetry (`game_worker.py:471, 1157-1189`).

## Required map and session contract before authoring a lesson

Use two linked records rather than treating an installed package name or a few packet fields as complete geometry:

### Versioned per-map arena profile

1. **Identity and asset role:** an exact entry map asset identity and digest, plus the resolved dependency set/version needed by that map. Bind the profile to the entry asset selected for the match; a dependency package or Workshop row alias is not itself evidence of the map's geometry. The RLBot config field is named `game_map_upk`; the existing package research separately establishes that the Workshop catalog cannot infer entry-map versus dependency role (`map-arrival-01.md`, “Package selection”; official schema link above).
2. **Coordinate frame:** origin, X/Y/Z basis, units, handedness, yaw convention, team-to-goal mapping, and any explicit transform from the map profile into RLBot world coordinates. Reject unknown or non-rigid transforms.
3. **Collision/support geometry:** profiled playable floor and grounded regions; side/back walls including curves/ramps; ceiling; goal mouth plane and cavity, posts/crossbar/backboard; out-of-play boundaries; and areas excluded from spawn placement. A rectangular bounds tuple is insufficient for arenas with curved walls or non-Soccar topology.
4. **Goals and symmetry:** record each goal's team, center, outward direction, opening dimensions and validated crossing plane. State which symmetries have been proven. Permit X mirroring only if the actual goal, wall, floor, ramp, and spawn geometry is invariant under that reflection and team roles are remapped intentionally.
5. **Pads and launch anchors:** include static boost-pad positions/types only when lesson logic uses them, plus author-validated ball/car start poses and receiving/target volumes. Pad state remains dynamic per packet. A valid pose must account for ball collision shape and each car's observed body hitbox/offset, not just actor centers.

### Observed session contract linked to that profile

- Correlate the selected entry asset/profile with the active owned offline session and the exact `MatchConfiguration` request. `GamePacket` and `FieldInfo` lack map identity; matching coordinates alone does not establish that the requested map is active.
- Require the supported game mode and exact known mutators; verify their available observed effects before state-setting. At minimum record ball count and shape, gravity Z, game speed, game phase, ball physics, team/score, player teams/roster, and each active car hitbox/offset. Since all requested mutators are not echoed in `GamePacket`, reject a mode whose applied physics/rules cannot be established.
- Require the session's player/body roster to match the authored pose profile. A center point can be inside an arena while the car hitbox intersects a wall, goal frame, ceiling, or another actor.
- Use a goal crossing plane derived from the active goal center and direction, with a goal/aperture model compatible with the observed ball shape. Keep geometric target evidence separate from the authoritative score edge. Do not use `Y=5120` or an axis-aligned ball-out box as the per-map detector.
- Version/validate the profile independently for each entry map and supported session/mutator combination. Geometry can be shared across maps only after measured equality, not by similar map names or dependency membership.

### Fail-closed unsupported cases

Do not send lesson `set_state` when the entry-map identity is unknown/unmatched, the dependency closure is unresolved, the coordinate transform or collision profile is incomplete, goal/team orientation is ambiguous, required goal/wall geometry is absent, ball count/shape or physics is unsupported, player hitbox/body is unknown for pose-clearance needs, or requested mutators cannot be verified. Do not use current side-wall/backboard reflection variants or X-mirrored scenarios on an arena until those specific surfaces and symmetry have been validated. This is a targeted data-completeness rule: the missing field(s) above each rejection make the lesson's authored positions or success detector ungrounded.

## Geometry-focused future acceptance cases

1. For one candidate map, bind a profile to its exact entry asset digest and dependency set; show that a dependency file alone cannot select the profile. Confirm the actual active map identity through a trusted session source, not `FieldInfo` coordinates.
2. Compare RLBot world basis with the profile's goal centers/directions and wall/floor/backboard references. Validate positive and negative team direction, goal plane orientation, and each allowed transform.
3. For every authored launch pose, test the observed ball shape/radius and observed car hitbox/offset against collision clearance at the target position. Reject an overlap or unsupported body/ball variant before the first state write.
4. Perturb ball count, shape, size/gravity/bounciness mutators, map identity, game speed, and player body. Verify each unsupported configuration prevents setup or produces a specific unsupported-state reason.
5. Validate goal detector against center crossings inside/outside the goal frame, posts/crossbar, opposite-direction crossings, team-swapped goals, and scoreboard edge. For a proposed authoritative-goal lesson, confirm a target-zone metric alone cannot grant success. Preserve and label intentionally different target-only lesson outcomes rather than silently changing their meaning.
6. Enable mirroring only for profiles proven symmetric: compare mirrored floor/wall/ramp/goal geometry and team mapping. Include a deliberately asymmetric map/profile to verify mirror-based variants are refused.
7. Compare any ball-out/failure feedback with actual playable bounds, goal cavity, and ball shape. Verify out-of-world wording is not emitted from the standard 4096/5120/2044 constants on an unknown map.

## Evidence boundary

This is static candidate/source/schema research only. Standard-field dimensions are public reference values; they do not certify any installed arena, custom Workshop package, collision mesh, runtime mutator, or accepted state write. `GoalInfo` gives goal summary data, not complete goal-frame collision geometry. The public RLBot schema supports the listed packet fields, but the current app adapter omits several from the lesson engine, and neither `FieldInfo` nor `GamePacket` names the loaded map. The future contract above is an implementation requirement, not a claim that current MCT supports or has validated Workshop lessons.

## Local source hashes

SHA-256 of the frozen candidate files used for line references:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `src/my_career_training/training/scenarios.py` | 23706 | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/engine.py` | 63844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | 12018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | 90814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/map_guard.py` | 4986 | `b2e79d11639b9c29908ea9e5053d23fbf5efddaff58d5cd03a125be5fa4746a6` |
| `pyproject.toml` | 1221 | `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b` |
| `uv.lock` | 39490 | `8a255b76c2c7175647df67578381001074752319186ba298acf67c711b48ed22` |

**Status:** `research_only`.
