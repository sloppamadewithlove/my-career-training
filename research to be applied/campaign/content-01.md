# CONTENT-01 — lesson geometry and Workshop map fit

## Scope

Read the current reviewed-training source, `MAP-01`, `ARTIFACT-01`, the local Steam Workshop manifest’s aggregate fields, and the catalogued creators’ public map pages. This pass did not launch or control the game, inspect package contents, download content, run tests, compile, or change product files. No locally installed item IDs, account data, raw package paths, or extracted content are included; the links use public map pages from the project catalog.

## Main finding

Current lesson coordinates assume the standard Soccar field frame. The shared lesson builder labels every lesson `DFHStadium` and exposes only generic RLBot capabilities; the launch request does not carry a map. `adapter.match_config` therefore selects its fallback `Stadium_P`, uses Soccar mode and Normal Boost, and does not set a gravity mutator (`training/catalog.py:53–69`; `bridge.py:1727–1792`; `adapter.py:103–117`). The `DFHStadium` field is also used in recording metadata; it is not the source of a dynamic Workshop geometry transform.

Power Shots has the strongest geometry dependence: its 12 hand-authored situations use Soccar-scale world coordinates, side-wall/back-wall constants, and a single goal plane. The engine detects goals only when the ball crosses positive Y=5120; the renderer draws the target at Y=5110 (`training/scenarios.py:24–26, 59–149, 218–228, 294–361`; `training/engine.py:1084–1168`; `game_worker.py:1492–1505`). `field_info` contributes boost-pad positions and active state to normalized packets (`adapter.py:133–163`); it does not supply goal, wall, ceiling, or obstacle anchors to the lesson engine. Boost-pad observations are available to bot tactics, but they do not retarget lesson geometry.

The current Python Workshop path keeps every custom map `can_launch=false`. The native Workshop launcher is a separate development path; a Workshop row is not currently bound to a lesson setup (`workshop.py:200–218, 258–282`; `MAP-01`). The maps below are discovery references and possible standalone practice concepts, not verified lesson-compatible arenas.

## Existing lesson geometry and fit

This matrix describes the eight legacy lesson definitions in `training/catalog.py`. It does not imply that the full product-required twelve situations are implemented for each lesson; the current 12-situation scenario module is Power Shots only.

| Lesson | Current target/setup dependency | Map fit from the source | Relationship to catalogued maps |
|---|---|---|---|
| Speed flip | Starts at a fixed negative-Y position and crosses a rectangular plane at Y=0; then checks landing (`catalog.py:79–93`). | Open straight floor lane in the standard coordinate frame; no goal required. The code does not scale/re-anchor the finish line to a course. | No named catalog map is a verified speed-flip lesson. A time-trial/obstacle course can be separate practice, but its checkpoints would need their own route definition. |
| Flip reset | Fixed car/ball poses around the center of the field; success uses a ball-reset threshold and a `central_space` value (`catalog.py:96–107`). | Requires a safe open aerial volume and a resettable ball. The current single setup is not the owner-required wall-roll progression, and it does not define a map surface/anchor. | None of the named maps is established as a flip-reset fit. Obstacle or ring categories are not enough to infer a usable wall start. |
| Ground dribble & flick | Ground carry box relative to the car plus a rectangular goal target (`catalog.py:110–121`). | Needs a controlled floor/carry area and the expected goal plane/mouth. Goal crossing is evaluated in the fixed Soccar frame. | Dribble 2 Overhaul and Noob Dribble are thematically close as independent ball-control courses. Their map-owned levels/checkpoints do not align with this lesson’s carry box or goal target. |
| Power shots | Twelve ball-launch situations, goal targets, and pressure actors are hard-coded in world coordinates (`scenarios.py:59–149, 294–361`). Side-wall and backboard launches use X=−4096, Y=5120, and a fixed goal-mouth bound (`:24–26, 218–228`). | Requires standard Soccar goal/wall geometry, orientation, and actor positions. No field-frame adaptation is present. | Aim Training is a thematically relevant independent shooting map, but its own random target modes are not the app’s goal/attempt criteria. It is not a drop-in scene for these situations. |
| Shot placement | Fixed car/ball setup and a goal zone centered at X=480 (`catalog.py:133–141`). | Requires standard Soccar goal plane, goal mouth and orientation. | Aim Training is conceptually relevant for aiming practice only; its target/survival scoring is map-owned. |
| Fast aerial | One gate at fixed world position `[0, -600, 850]`, with a radius (`catalog.py:143–154`). | Requires an unobstructed volume at the authored coordinates. It does not bind to a map-authored ring or checkpoint. | Rings/obstacle courses fit the skill concept, but a standalone course is not this lesson’s gate or recorded outcome. |
| Aerial & air-roll | Three ordered gates at fixed X/Y/Z coordinates (`catalog.py:157–171`). | Needs an open route in the standard field frame; route safety and gate reach are not transformed from map geometry. | Ring maps are the closest standalone practice category. To run this lesson there, its gates and safe route would need map-specific anchors. |
| Fast flight & recovery | Two fixed aerial gates followed by a fixed-Y recovery corridor (`catalog.py:175–190`). | Needs both open aerial volume and a traversable floor/recovery lane at the expected coordinates. | Fractal’s Funland and obstacle/recovery maps are conceptually related but have their own course progression; they cannot validate this gate/corridor result. |

All eight definitions inherit `map: DFHStadium`; the current match request has no `fixture` or map field, so the adapter’s `Stadium_P` fallback is what the source asks RLBot to start. This makes “DFHStadium geometry” an authored assumption, not proof that `field_info` or the running map was calibrated.

The lesson catalog’s required capabilities are only `state_setting`, `human_actions`, and `telemetry` (`catalog.py:60–61`). There are no current per-lesson requirements such as `goal_plane`, `wall_rebound`, `air_volume`, or `course_checkpoint`, and no map descriptor records coordinate transforms or dynamic map controls.

## Named map references and local package metadata

`content.py:61–82, 90–112` lists ten Steam Workshop references. The catalog marks compatibility unverified and `game_tested=false`; the dependency field is generic (“some maps also need creator-listed textures or plugins”), not an exact package-role manifest.

Text extraction from the ten Steam pages included removal/incompatibility notice text. A coordinator check of the actual public HTML on 27 October 2026 found both notice elements marked `style="display: none"` on all ten pages. Hidden template text does not establish a removed item or current incompatibility; that initial inference is withdrawn. Post-JavaScript rendered visibility was not observed. Catalog descriptions still do not establish runtime compatibility. See the [notice visibility evidence](../evidence/steam-notice-visibility.json).

| Map | Public creator description / intended activity | Local metadata observed | Fit boundary |
|---|---|---|---|
| Dribble 2 Overhaul | Creator describes an overhaul of Dribbling Challenge #2 with an in-map reset/toggle interaction ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1694288506)). | Present: one `.udk` candidate, about 81.3 MB. | Closest named map to dribble practice; it remains a separate map-owned course, not a mapped carry box or goal target. |
| Noob Dribble | Creator labels it a beginner-friendly dribbling course and also lists its difficulty as Intermediate ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1843822064)). | No matching local item directory. | Conceptual ground-control practice only; runtime course geometry unknown. |
| Aim Training | Creator describes Easy, Normal and Survival target-shooting modes with varying target size, wall distance and ball delivery ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1906378036)). | Present: one `.udk` candidate, about 80.2 MB. | Shooting practice is a close theme match, but the map’s target modes and success rules are separate from Power Shots/Shot Placement. |
| Speed Jump: Rings 3 | Creator describes an intermediate-to-hard obstacle course ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1671658424)). | No matching local item directory. | Aerial steering practice as a standalone route; no lesson gate coordinates are known. |
| Giant Rings | Rings-course reference; creator page says Workshop Textures can fix the water texture ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=2025564083)). | Present: one `.udk` candidate, about 328.3 MB. | Aerial practice concept; texture note is a possible visual dependency, not a confirmed gameplay dependency. The local scan does not prove the texture package is installed. |
| Neon Heights Rings | Steam page identifies it as a Lethamyr map rehosted for Steam users but gives no route geometry in its description ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=2468375059)). | No matching local item directory. | Aerial fit is a title/catalog inference; exact mechanics and anchors remain unknown. |
| Hornets Nest | Creator describes an intermediate obstacle arena ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1827631206)). | No matching local item directory. | Broad obstacle/recovery practice only; it does not establish the authored recovery corridor. |
| Fractal’s Funland | Creator says it practices momentum, recoveries and handling; it has its own level reset and D-pad level navigation ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=3109906046)). | No matching local item directory. | Closest named concept to flight/recovery, but its checkpoints and controls are map-owned and not compatible with current lesson coordinates by declaration. |
| Speed Jump: Boost | Creator describes an extreme obstacle course ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1421195368)). | No matching local item directory. | Boost/movement practice as a standalone route; no current lesson defines boost-pad or route targets for it. |
| Speed Jump 2 | Creator describes an intermediate-to-hard obstacle course ([page](https://steamcommunity.com/sharedfiles/filedetails/?id=1429288182)). | No matching local item directory. | Aerial/obstacle practice only; no authored route mapping exists. |
| The Immortals Progressive Tower | Creator page describes 20 levels covering timing, shooting accuracy, aerial control and boost. Persistent times use Map Expansion Plugin 294; some materials need Workshop Textures ([creator page](https://lethamyr.com/maps/173)). | It is not one of the ten Steam-ID references; local presence was not established in this pass. | Mixed standalone course, with explicit external plugin/texture expectations. No My Career scenario is mapped to its levels. |

The local Workshop ACF records seven distinct item entries and includes installed-item/detail sections with `timeupdated`, `manifest`, and `size` fields. A bounded path-only scan found seven numeric item folders and nine `.upk`/`.udk` candidates. The three catalogued maps found locally above each have one candidate file; four other item folders do not match this ten-map catalog. The remaining candidates’ entry/dependency roles were not inspected.

The current per-folder query found six one-file folders and one three-file folder. This differs from `MAP-01`’s earlier aggregate statement that three package-bearing directories contained multiple files; both observations agree on seven item folders and nine candidates. The coordinator independently reproduced the per-folder counts `[1,1,1,1,1,1,3]`; MAP-01 has now been corrected and its earlier aggregate claim withdrawn. Neither manifest keys, extension, nor a single candidate file proves that it is the entry map or that external dependencies are present.

## Entry package and dependency contract

The browser currently identifies discovered package rows by Workshop item plus relative filename. For a catalog item with one candidate it can bind that row; with multiple candidates it requires exact package selection. The source explicitly cannot tell whether a package is the entry map or a texture/dependency (`workshop.py:94–143, 171–199`; `docs/WORKSHOP_LIBRARY.md`). The local ACF’s size/manifest/update fields are download metadata, not an entry-map schema. Creator-declared dependencies stay separate: the Giant Rings page has a texture note; the Progressive Tower page names both textures and plugin 294. No code confirms those dependencies locally or installs them.

Keep map browsing and lesson compatibility separate. A safe future descriptor should include:

- **Identity:** source page/item, exact installed package path-relative name, SHA-256, package version/build, and explicit `entry`, `asset`, or `plugin` role for every required file.
- **Provenance/dependencies:** creator, source date, compatibility notice, license/permission state, required texture/plugin names and versions, and local presence checks.
- **Geometry:** coordinate frame/origin/orientation, playable bounds, floor/ceiling, side/back walls, goal plane and mouth, and explicit anchors/transforms for lesson spawns, gates and recovery corridors.
- **Physics/setup:** game mode, gravity and boost expectations, spawn/reset support for car/ball/bots, and map-owned checkpoint/control semantics.
- **Validation:** exact map-package hashes and game build for arrival, geometry, and lesson pass evidence. Do not infer this from category, title, or a recognized package header.

Lessons should declare geometry needs directly: `soccar_goal`, `soccar_side_wall`, `soccar_backboard`, `open_air_volume`, `route_gates`, `dribble_surface`, `recovery_lane`, or `map_owned_course`. A lesson is compatible only when the resolved map profile satisfies those needs and its world anchors align. Ring/dribble/obstacle maps can remain separate creator-authored practice until a real profile exists; they should not inherit DFH coordinate targets.

## Future lesson-fit acceptance

For each map/lesson pair, require all of the following before calling it supported:

1. Resolve the exact map item and entry package; record package hashes and every declared external dependency without installing content automatically.
2. Verify request-bound arrival of that exact map rather than a generic offline arena.
3. Capture the active world frame and physical anchors needed by the lesson. `field_info` boost pads alone are not geometry proof.
4. Confirm game mode, gravity, boost, actor spawn/reset and map-owned controls match the lesson assumptions.
5. Compare rendered target anchors with the physical goal/wall/course and confirm the success detector measures the same event (including the correct goal direction/plane).
6. Perform the lesson’s actual mechanic and retry/reset on that map; preserve the package bytes and return to the owned hub normally. Only then mark the specific map/lesson pair verified.

## Source references

- `work/campaign/map-01.md` and `work/campaign/artifact-01.md` — Workshop lifecycle and native package boundaries.
- `work/reviewed-training/src/my_career_training/training/catalog.py`, `training/scenarios.py`, `training/engine.py`, `training/scenario_setup.py` — lesson definitions and geometry checks.
- `work/reviewed-training/src/my_career_training/bridge.py`, `adapter.py`, `game_worker.py`, `workshop.py`, `content.py`; `docs/WORKSHOP_LIBRARY.md`; `docs/BUILD_SPEC.md`.
- Public Steam Workshop pages linked by each map row above. Only creator descriptions and page-level status were used; account pages, comments, and subscriber metrics were not used.
