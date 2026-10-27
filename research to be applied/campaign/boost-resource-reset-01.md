# BOOST-RESOURCE-RESET-01 — boost and pad state across authored practice attempts

## Scope

Static trace of boost resources, boost pads, and demolition/respawn signals in the frozen MCT candidate. This follows the existing reset/readiness and map-geometry reports rather than repeating their pose, map, or contact analysis. No game, network session, test, build, install change, or code edit was performed. RLBot and BakkesMod declarations identify available fields and calls; they do not prove the live match accepted a requested mutator or state write.

## Finding

The authored lessons request Normal Boost and write the human car’s meter to 100 at reset. Power Shots also writes each configured keeper/defender to 100. The ready gate checks observed car meters near the authored values. Retries and situation changes reset actor physics/meters and local controller state, but do not restart the match or write boost-pad state.

The pinned RLBot v5 packet schema exposes each pad’s `is_active` and remaining `timer`, plus static pad positions/full-pad flags. MCT normalizes pad location, active, and full status but drops `timer`; authored lesson scoring does not consume pad state, while the Power Shots bot controllers do use active-pad observations for their tactical decisions. The pinned v5 `DesiredGameState` schema has car boost amounts but no boost-pad state array. Thus source supports a reset to 100 car boost, not a reset to the same pad cooldown layout.

The request for Normal Boost is not an observation of the active mutator. The ordinary training recording path does not add the request or an acknowledgement to `metadata.mutators`; recordings default that field to `{}`. A 100 meter at reset therefore verifies the observed meter within tolerance, but by itself does not distinguish Normal Boost from Unlimited Boost or establish identical pad history. This can affect repeatability and ghost/personal-best comparison even though pads are not a Power Shots success criterion.

## What the frozen MCT path requests and resets

| Area | Source behavior | Evidence boundary |
|---|---|---|
| Match configuration | `adapter.match_config` requests Soccar, one ball, training-time Unlimited length/max score/overtime, and `BoostAmountMutator.NormalBoost` (`adapter.py:107–119`). It does not request Unlimited Boost. Demolition and respawn-time mutators are not explicitly assigned in this construction. | This is the match-configuration request. The ordinary path does not verify a separate live mutator acknowledgement. Unassigned mutator/default semantics and actual host application are not inferred. |
| Authored start boost | Legacy built-in lesson `_state` sets the Human car’s authored boost to 100 (`training/catalog.py:34–50`). Power Shots sets `_HUMAN` boost to 100; keeper boost is 100 and defender is copied from `_HUMAN` (`training/scenarios.py:45–51, 257–288`). | These are authored desired values, not measured runtime outcomes. |
| Reset writes | `GameWorker.reset` sends the engine’s `settle_state` to `adapter.desired_state`; Power Shots passes every known bot alongside the human. The worker then resets each scenario controller (`game_worker.py:615–653`). The post-settling `set_state` event writes the moving start state the same way (`:1303–1317`). Situation changes construct a replacement engine, reset it, and send that state before committing the new scenario (`:729–782`). | `adapter.desired_state` builds one write containing ball 0 and each car’s physics plus `boost_amount` (`adapter.py:167–203`). No pad state is included. These are requests, not proof of applied state. |
| Start gate | `TrainingEngine` defaults `reset_boost` tolerance to 2; it checks Human boost against the authored start value and checks each configured bot against its own value (`training/engine.py:162–177, 427–431, 703–720`). | The gate confirms meter proximity, not boost consumption rate, mutator identity, pad layout, or resource history. Existing [reset-ready research](reset-ready-01.md) documents the broader readiness gate. |
| Between attempts | `TrainingEngine.reset` clears attempt metrics and returns to settling; the worker writes actors/ball without recreating the match. Scenario controller state is reset separately. | The new attempt starts with requested actor meters/poses; no source path in this reset writes or restarts pad cooldowns. A host-side event such as a goal reset is not verified here. |

## Pad telemetry, controller use, and absent pad reset

The pinned schema says static `FieldInfo.BoostPad` entries contain location and whether the pad is full (`gamedata.fbs:430–462`). Dynamic `GamePacket.BoostPadState` entries report `is_active` and `timer`, the seconds remaining until reactivation (`:293–303`); it documents 10 seconds for a large pad and 4 seconds for a small pad. `PlayerInfo.boost` is an observed 0–100 meter and `demolished_timeout` is a separate player-state field (`:179–224`). The game packet’s static and dynamic pad arrays are paired by order in this schema.

MCT’s `adapter.normalized_packet` pairs static and dynamic entries by index and exports `{position, active, is_full}` only (`adapter.py:133–164`). It omits the timer, and appends only entries for which a dynamic state exists. `bots.physics.perceive` passes this normalized list into each bot’s perception (`bots/physics.py:95–112`). The Power Shots keeper and defender use `SpecialistController`; its tactical selection may choose an active pad when the bot is low on boost, the situation is not dangerous, and the pad is on a suitable route (`training/scenarios.py:393–401`; `bots/tactics.py:128–139`). Driving may request boost while accelerating and with positive observed meter (`bots/driving.py:55–56`). The keeper’s boundary-return override explicitly forces boost off (`training/scenarios.py:452–463`).

This means pad availability is an input to the scripted bots during an active attempt, but pad cooldown timing is unavailable to them and the lesson engine. On a retry, the controller’s internal state is reset and its fixed seed is restored (`bots/__init__.py:58–91`; `training/scenarios.py:424–428, 491–495`), while match-owned pad state is not written by MCT’s RLBot state-setter. Equal bot start meters and equal AI seeds therefore do not establish equal bot trajectories across attempts if pad availability changed.

The pinned v5 `gamestatemanip.fbs` declares `DesiredCarState.boost_amount` and `DesiredGameState` car/ball/match-info fields, but no boost-pad state field (`gamestatemanip.fbs:45–82`). It confirms the limit of this reset path: actor boost can be requested; pad timers cannot be requested through this schema. The BakkesMod SDK pinned by MCT exposes additional declarations: `CarWrapper::GetBoostComponent`; `BoostWrapper` current/start/max meter accessors, setters, and no/unlimited-boost methods; and pickup wrappers with `bPickedUp`, `RespawnDelay`, and `Respawn2` (`VehicleWrapper.h:65`; `BoostWrapper.h:15–66`; `VehiclePickupWrapper.h:15–47`; `BoostPickupWrapper.h:13–22`). These declarations are not used by this MCT reset path, do not expose a `BoostPadState.timer` equivalent among these selected wrapper fields, and do not prove that calling the proxies is a safe or complete reset of every map pad.

## Demolition and respawn boundary

The RLBot schema reports `demolished_timeout` for each player; MCT normalizes a positive value to `is_demolished` (`gamedata.fbs:207–224`; `adapter.py:136–143`). The human lesson engine does not read that flag in its readiness, scoring, or retry source. The scenario bot’s `SpecialistController.step` does read it and returns neutral controls while that bot is demolished (`bots/__init__.py:93–101`). No MCT path requests an explicit car respawn.

`DesiredCarState` in the pinned RLBot schema contains physics and boost amount but no demolished/respawn field (`gamestatemanip.fbs:45–50`). The match schema defines separate demolition and respawn-time mutators (`matchconfig.fbs:296–315`), but MCT does not assign them in `adapter.match_config`. Therefore the active demolition and respawn policy remains host/mode behavior in this trace. An attempt reset writes the car’s desired pose and boost but does not explicitly clear a demolition timer. The readiness gate checks observed pose, ground/jump state, boost, and other reset fields; it has no direct `is_demolished == false` condition. A demo may make those other conditions fail, but the exact result and any game-side respawn timing are unverified.

## Recording and comparison effect

The training engine resets its `boost_seconds` metric and increments it from observed human boost-button duration, not from measured fuel consumption (`training/engine.py:224, 805–811`). `Recorder.append` retains the observed human boost meter as an optional sample alongside the action and car/ball trace (`training/recordings.py:227–260`). It does not retain boost-pad active/timer samples.

For ordinary sessions, `GameWorker` initializes engine metadata with the framework version; the later ordinary metadata update includes game version and car hitbox, while the capture-only metadata path is the one that packages requested and acknowledged match configuration (`game_worker.py:495–502, 1157–1188, 1299–1302`). `Recorder` defaults `metadata.mutators` to `{}` (`training/recordings.py:205–225`), and `compatible_recordings` compares stored mutator objects for equality (`:145–172`). Thus two ordinary records can compare equal with empty mutator metadata without proving their active boost policy matched; neither can prove equal pad cooldown history. Observed meter samples are useful evidence of actual resource level, but not a complete resource-policy acknowledgement.

The current ghost path displays recorded movement/coaching data and does not drive the player; it is not a deterministic replay of the pad or bot-resource simulation. For comparable trials, the product should either define pad use as irrelevant to the authored lesson and verify it is not part of the coaching/result claim, or record/validate the relevant pad and mutator context. Bot-pressure lessons additionally need a stated policy for whether bots may collect pads; otherwise start meter plus reset random seed is insufficient context for a repeatability claim.

## Implementation-useful acceptance cases

1. In a fresh owned offline training match and on every retry/situation change, record the requested boost mutator, observed Human/bot meters at the ready boundary, and all pad active/timer values. Keep the request and observation distinct.
2. Deplete a player/bot meter, let it encounter a pad, then retry the same authored situation. Verify the actor meter is restored to the authored value. Verify pads either match a declared baseline reset policy or the attempt is marked as having different/unknown pad context; do not assume actor reset also resets pads.
3. With bot pressure enabled, vary an eligible pad’s active state while holding scenario, bot seed, ball, and actor start states constant. Confirm the controller’s pad decision and resulting bot behavior follow the observed pad field, or mark this bot-resource path unsupported for deterministic comparisons.
4. Exercise a demolished Human and a demolished scenario bot through settling and active phases. Require an explicit policy for holding/retrying/interruption until a fresh, non-demolished actor is observed; confirm that a `DesiredCarState` request alone is not recorded as a successful respawn.
5. Compare two recordings with identical start poses/meters but distinct requested boost policy or pad timers. Require compatibility to distinguish these contexts whenever they can change the lesson or bot pressure; keep ordinary blank-mutator metadata from implying an acknowledgement.

These are future acceptance cases, not tests performed for this report.

## Sources and fingerprints

The RLBot schema was read at commit `e27de77b4ae2cd9fef5bfea53994be7e24454b47`, the same declaration pin cited in [map-geometry-01](map-geometry-01.md). The MCT BakkesMod SDK pin is commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` (`plugin/CMakeLists.txt:26–29`). These pins identify inspected declarations; neither proves a matching installed runtime or session effect.

| Selected source | Bytes | SHA-256 |
|---|---:|---|
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/scenarios.py` | 23,706 | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/bots/__init__.py` | 5,925 | `6b9e406b1532d1064499ce5918d6a4187a7d08300f769c8b6a9fb52e1687a12e` |
| `src/my_career_training/bots/physics.py` | 4,481 | `d2aad719b6fea7b32883b8bd45c9af882e1eb01b63bf5df2de31fc1784981928` |
| `src/my_career_training/bots/tactics.py` | 7,907 | `f3a0ef1dd7d2714773e2e43448572fe9914eee8727798b25fee904159734af2f` |
| `src/my_career_training/bots/driving.py` | 3,582 | `e6d97e77535d6cf954b4bed3b100585843d006315af148175e43cd83f60e2b56` |
| `plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| Pinned SDK `GameObject/VehicleWrapper.h` | 3,578 | `19feb5afafcce50b4ccfee169655a95a06131ae7a554ec64803ccfb5e94c9a72` |
| Pinned SDK `GameObject/CarComponent/BoostWrapper.h` | 2,719 | `0d659ccbde09aadf04b1720110aaa2615768fb4712f44c1796921c9b81f075bd` |
| Pinned SDK `GameObject/VehiclePickupWrapper.h` | 1,674 | `cc70cc78d07aa61e20a683aa219a9971ae23fe94acd3fd21bb42696a24377e73` |
| Pinned SDK `GameObject/BoostPickupWrapper.h` | 665 | `d88938e847f35c8068f07560f35f780868a3e519d1f8f90bc37657cf9d88fbd4` |
| Pinned SDK `GameObject/CarWrapper.h` | 5,566 | `42c0c29c7a2d42a1fc5d55929c5dd6d38f0676dfe894dfb63c4206db79bdcb54` |
| Prior `physics-01.md` | 14,906 | `f7260a611521ade1f7c127930fabee751d72d535b1d212170d3a4a5abc07b8ac` |
| Prior `map-geometry-01.md` | 16,867 | `18243062f24efbba82901782e69a3ae93555386277f025b920de8288040793cc` |
| Prior `reset-ready-01.md` | 14,227 | `42716dae5b988655f7f8d64256c6bf50275f7c118d5894166787835dbebf1bb2` |
| Prior `mod-measurement-01.md` | 5,364 | `7291d2652bf237791cc292c7bb2ae7eb8eb3dbd82bf5189a5617fe0f5d159547` |
| Prior `settings-01.md` | 13,930 | `f57eb6d5ce171d9bfef0484450a6147d9e2c759ee012c324c42f57d82d88032f` |

Primary declarations: [RLBot `gamedata.fbs`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L179-L224), [dynamic/static boost pad fields](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L293-L303), [field pad locations](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs#L430-L462), [RLBot game-state mutation schema](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamestatemanip.fbs#L45-L82), [boost/demolition/respawn mutator declarations](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/matchconfig.fbs#L252-L315). Pinned SDK declarations: [VehicleWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/VehicleWrapper.h#L65), [BoostWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/CarComponent/BoostWrapper.h#L15-L66), [VehiclePickupWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/VehiclePickupWrapper.h#L15-L47), and [BoostPickupWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/BoostPickupWrapper.h#L13-L22).
