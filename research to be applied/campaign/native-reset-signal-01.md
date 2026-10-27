# NATIVE-RESET-SIGNAL-01 — reset acquisition signal surfaces

Read-only source/header review on 2026-10-27. No game process, runtime call,
or REA binary target was opened. This distinguishes a documented reset-held
state from a direct acquisition event, wheel-contact evidence, and scoreboard
count.

## Findings

| Surface | Evidence | What it establishes | What it does not establish |
|---|---|---|---|
| RLBot packet schema | Pinned [`gamedata.fbs`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs), `PlayerInfo` lines 179–263 (availability at 199–206 and 245–255); `ScoreInfo` lines 91–113; per-tick accolades at 230–242 | The packet includes `air_state`, `dodge_timeout`, jump/double-jump/dodge flags, latest ball touch, and ordinary score fields. The schema documents holding a flip reset as `InAir` with all three flags false. `dodge_timeout` describes remaining dodge availability and can remain available after falling off a surface. The documented per-tick accolade names also contain no reset event. | There is no explicit `reset_acquired` event, wheel count, or reset count in these packet fields. Availability alone does not identify how it was acquired or prove three wheel contacts. `ScoreInfo` lists score, goals, own goals, assists, saves, shots and demolitions, not resets. |
| Pinned BakkesMod SDK declarations | SDK CMake archive pin: commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`; cached headers are the CMake-fetched archive, not an independently verified Git checkout. | `CarWrapper::HasFlip()` returns an availability-like value (`CarWrapper.h:34`), but the header does not document its reset/timing semantics. `VehicleSimWrapper::GetWheels()` yields wheel wrappers (`VehicleSimWrapper.h:18`). Each `WheelWrapper` declares `GetContact()`, `GetbHadContact()` and `EventContactChanged(...)` (`WheelWrapper.h:46,50,66`). `WheelContactData` has contact/world-geometry flags, change time, actor/component pointers, location and normal (`WrapperStructs.h:978–988`). `CarWrapper` declares `GetLastWheelsHitBallTime()` and its setter (`CarWrapper.h:69–70`), plus `HandleWheelBallHit(WheelWrapper)` (`CarWrapper.h:123`). | This is a promising per-wheel contact inspection surface and a named wheel-ball-contact time field, but the headers provide declarations only. They do not document the actor pointer’s exact meaning/lifetime, whether the time field is updated for every relevant contact, or how to subscribe to `EventContactChanged`. `HandleWheelBallHit` and `EventContactChanged` are auto-generated function proxies, not proof of a registered callback or reset-acquired event. No inspected declaration supplies an explicit “three wheels acquired reset” boolean/event. |
| BakkesMod player stats declarations | `PriWrapper.h:20,118,120`; `PlayerReplicationInfoWrapper.h:20`; `StatEventWrapper.h:5–27` | Wrappers expose generic stat-event metadata and typed player match-score and ball/car-touch totals. | No reset-specific per-player counter or acquisition event was found among these targeted declarations. Generic stat-event metadata does not identify a reset stat without a documented event name and value path. |
| MCT source snapshot | `adapter.py:133–164`; `engine.py:47–50,1031–1077`; prior [`flip-reset-01`](flip-reset-01.md) | MCT maps RLBot `air_state`, `has_jumped`, `has_double_jumped`, `has_dodged`, and latest touch. Its detector emits `reset_acquired` on a new transition into the schema-defined reset-held state, combined with attributed fresh touch, post-spend ordering, geometry and packet checks. | The adapter does copy `dodge_timeout` (`adapter.py:141`), but the acquisition predicate uses the held-state flags rather than an explicit acquisition event. It does not map wheel records, `GetLastWheelsHitBallTime`, or a native reset cue/stat. The emitted lesson event is MCT’s inference; it is not evidence of which wheels contacted the ball. |
| Product documentation | [v2.66 notes](https://www.rocketleague.com/news/rocket-league-patch-notes-v2-66); [v2.76 notes](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276/); summarized in [`native-feature-delta-01`](native-feature-delta-01.md) | v2.66 documents a configurable acquisition cue associated with at least three wheel contacts; v2.76 documents selectable scoreboard statistics including reset counts. | Release notes do not name a callable API. The cue and scoreboard are product features, not evidence that RLBot packets or the pinned BakkesMod wrappers expose their event/count values. A scoreboard count is aggregate corroboration, not an event timestamp or attempt identity. |

## Local artifact and provenance boundary

The reviewed MCT working files have hashes `adapter.py` `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` and `engine.py` `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a`; both are modified relative to the checkout’s Git HEAD. Treat the line trace as the captured reviewed source snapshot, not a clean-HEAD assertion. `pyproject.toml` pins `rlbot==2.0.0b56` and `rlbot-flatbuffers==0.19.0` for Windows. The schema citation above is the separately pinned public RLBot source revision.

Earlier static inventory identified the installed MCT DLL as SHA-256
`18569d2b321f30f20c018e8ba14a596d1ebb89ab785addda9777662c73b9887e` and the
installed `pluginsdk.dll` as `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` ([SDK-02](sdk-02.md)). That import comparison was complete for the plugin but did not test the wheel-contact API family specifically, and the installed DLL is not established to match this reviewed source. No deployment/runtime capability is inferred from those identities.

## Conclusion and next evidence

There is no direct acquisition-event or reset-count field in the inspected
RLBot schema, and no reset-specific per-player stat in the targeted pinned SDK
player/stat declarations. The SDK does expose stronger *candidate contact
evidence* than MCT currently consumes: wheel wrappers/contact records and
`LastWheelsHitBallTime`. A future adapter could evaluate each wheel’s contact
actor against the active ball and correlate the result with reset availability,
but this remains an inference/design candidate until pointer identity,
sampling and timing semantics are validated in an authorized offline test.

Minimum proof sequence: establish four wheel identities and the active ball;
capture contact actor/time/flags for each wheel across ordinary ground contact,
car-body ball touch, one/two/three/four wheel ball contacts, and the native cue
enabled/disabled; compare against RLBot flags and any visible scoreboard count.
Only a validated source with actor, event time, attempt boundary and contact
count should upgrade the lesson from inferred to directly observed. Keep the
v2.76 scoreboard count as optional aggregate corroboration unless its precise
player-scoped read path and reset boundaries are separately proven.

## Fingerprint receipt

| Source | Bytes | SHA-256 |
|---|---:|---|
| `CarWrapper.h` | 5,566 | `42c0c29c7a2d42a1fc5d55929c5dd6d38f0676dfe894dfb63c4206db79bdcb54` |
| `VehicleSimWrapper.h` | 1,702 | `6d77b55e4057051887aeefc5f1a7d6db4f694f105b759c70d47f5a945d6c0cbc` |
| `WheelWrapper.h` | 2,652 | `74da6eaecf2c6c00d71e7105701b12fdc129f31bc1edf4d5990385b2b6a9b17e` |
| `WrapperStructs.h` | 31,163 | `18f95a9016843623211204d0332d835bf695e2a2d4c3776fb292b5647bd25d5a` |
| `PriWrapper.h` | 10,093 | `693920d69f061d11be6096bcf576b5747ac398713b3ef6f71d0132426fc57e91` |
| `PlayerReplicationInfoWrapper.h` | 3,729 | `bcbccb0a56ef18dd58890e13bcb766950da2dd3b7f1a95124fe0d84e3618016c` |
| `StatEventWrapper.h` | 1,009 | `aaaeba51820cfd8021155e037f8baf9a343b8f6d86b97844ed57fd9dfcf08e41` |
| `adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |

The RLBot schema is cited by immutable commit URL; the generated package in the
project environment is the pinned `rlbot-flatbuffers==0.19.0` dependency.
