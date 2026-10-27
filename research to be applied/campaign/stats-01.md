# STATS-01 — telemetry and player progress surfaces

Read-only source and documentation research, accessed 2026-10-27. No game,
account, credential, build, or test activity. This report distinguishes
documented interfaces from implemented project behavior and from metrics that
would still need definitions and validation.

## Findings by scope

| Scope | Supported evidence found | Limits |
| --- | --- | --- |
| **Practice attempt** | The project’s RLBot v5 worker consumes live `GamePacket` state. Its adapter normalizes car/ball physics, player `last_input`, per-player `latest_touch`, wheel-contact/air state, dodge state, and elapsed game time (`src/my_career_training/adapter.py:133-153`; RLBot v5 `Game Data` docs say `GamePacket` carries live ball/player physics, boost-pad timers, scores and time at 120 Hz). | It is a local game/session feed, not a Psyonix account-stat API. `latest_touch` is attributed contact evidence; it does not measure quality or technique mastery. Packet gaps limit timing and ordering claims. |
| **Match** | Rocket League’s official Stats API emits local JSON over TCP and/or WebSocket. `UpdateState` documents per-player match Score, Goals, Shots, Assists, Saves, Touches, CarTouches and Demos, plus match/team/time metadata. `BallHit` reports the player(s), ball pre/post speed and impact location one frame after a hit. `GoalScored` reports scorer, optional assister, last touch, goal speed/time and impact location. | It is opt-in and disabled by default (`PacketSendRate=0`); the documentation requires an INI change before launch and a restart. It is not documented here as covering every custom training/freeplay/tutorial mode. Several instantaneous car fields are explicitly spectator-only. It provides match data, not persistent profile/MMR. |
| **Account / competitive profile** | Epic Support says Match History shows the 20 most recent matches from the past 30 days and Player Profiles include XP level and highest rank; viewing the Rocket League website profile requires signing in with an Epic Games account. | The reviewed official sources document a signed-in website experience, not a public programmatic account-stats endpoint. Do not scrape it or request credentials. In-game Career records are local and may mismatch the website. No app integration should imply it can read, update, grant, or synchronize account data. |

## Project state and plausible measures

The custom training engine saves a per-attempt UUID, lesson ID/title, outcome,
duration, metrics, observed events, feedback, and (where applicable) the
Power-Shots scenario identity and authored difficulty label. Current metric
fields include carry and boost time, gate count, packet-gap count, sampled ball
speed shortly after contact, crossing time/speed, target hit/location, and
landing orientation/alignment/speed/angular speed (`training/engine.py:222,
979-982,1027-1028,1114-1115,1146-1147,1268-1305`). It stores bounded sampled
recordings on game time with car pose/actions and ball state
(`training/recordings.py:12-23,204-260`). These are per-attempt observations;
the project does not currently compute a validated global mechanic rating.

The separate match-review path is intentionally narrower. For ordinary
non-training, non-workshop matches, the worker updates `MatchReview`, then
stores its bounded summary with the observed final team score
(`game_worker.py:1327-1338`). `review.py` retains at most 12 moments. It reports
observed score changes, recent human `latest_touch` contacts, and two explicitly
heuristic positioning suggestions (double-commit and empty-boost challenge).
The score text expressly says it establishes a scoreboard change, not its
cause (`review.py:78-212`). The QML presents review as optional and says it does
not affect progress (`ui/Main.qml:255-261`). This is not yet a player match-stat
ledger (goals/shots/saves/touches), and none of these review moments should be
turned into progression gates without separate validation.

Useful future learner records, grounded in fields already observed:

- **Repeatability / consistency:** for an exact lesson version, scenario/profile,
  variant and compatible setup, show `successful attempts / complete attempts`
  with the denominator, sample count and coverage/gap status. Keep time-to-event
  distributions separate from completion rate. Exclude incomplete/gap-invalid
  attempts or display them separately. This measures repeatability under that
  setup, not general skill or competitive rank.
- **Contact evidence:** record attributed touch time/location and the following
  ball response. The current adapter can preserve touch timing/location/normal;
  Stats API `BallHit` has pre/post speed and location. A speed delta is an
  observable contact result, not by itself a “clean hit” score: the official
  event does not define clean contact, and its example has no outgoing direction
  vector. Define any clean-contact rubric per drill before scoring it.
- **Recovery:** use the observed grounded/wheel-contact transitions, pose,
  orientation and velocity to measure time from a declared recovery start to a
  declared stable landing condition. Current engine already stores selected
  landing values, but not every named mechanic has a thresholded recovery rule.
  Publish this only for continuous samples and a versioned threshold; report
  missing coverage as unknown.
- **Placement:** for a fixed target profile, retain the actual marked-zone
  crossing/location and count in-zone crossings over eligible shots. Compare
  location error/spread only against the same target geometry and setup. Current
  `target_hit` and `shot_location` are setup-specific; neither implies
  competitive shooting accuracy. A match `GoalScored` impact is useful match
  evidence but is not a substitute for the custom drill’s marked target.

Stats API match counts can complement this with match-scoped totals and
event-derived goals/statfeed records. Keep match summaries separate from
training attempts and career simulation. If exact identity is unnecessary,
avoid retaining `PrimaryId`, player names, or other platform identifiers;
the Stats API docs identify `PrimaryId` as a platform identifier and
`MatchGuid` is only set for online/LAN matches.

## BakkesMod SDK declarations

The project CMake file fetches BakkesModSDK archive revision
`479e8f571cf554b25f4eeb64d611dec4133edcaf` with SHA-256
`e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`
(`plugin/CMakeLists.txt:26-30`). These are declaration facts from the SDK
headers consumed by that pin, not proof that a particular installed runtime
supports or successfully executes every call.

- `CareerStatsWrapper::GetStatValues()` returns rows containing `stat_name`,
  `private_`, `unranked`, and `ranked` integers
  (`CareerStatsWrapper.h:5-15`). The declaration does not establish when these
  values refresh, their full semantic mapping, or whether they are account
  authoritative.
- `GameWrapper::GetMMRWrapper()` returns `MMRWrapper`
  (`GameWrapper.h:73`). That wrapper declares `IsSyncing`, `IsSynced`,
  `IsRanked`, and player rating/rank/MMR getters that require a player ID and
  playlist ID; `SkillRating` is `{Mu, Sigma}` and `SkillRank` is
  `{Tier, Division, MatchesPlayed}` (`MMRWrapper.h:32-44`; `GameWrapper.h:73`;
  `wrapperstructs.h:857-867`).
  This is a BakkesMod plugin interface to runtime state, not evidence of a
  standalone/public account API, current network availability, a complete
  playlist history, or valid data for every player.
- `PriWrapper` declares match-only counters such as MatchScore, MatchGoals,
  MatchAssists, MatchSaves, MatchShots, MatchDemolishes, BallTouches and
  CarTouches (`GameObject/PriWrapper.h:20-31,116-120`). `ServerWrapper` also
  declares goal/touch-index and event functions. These indicate possible
  in-match plugin reads; they are declarations, not validated measurement
  contracts. The reviewed project source has no `CareerStatsWrapper` or
  `MMRWrapper` call sites (`rg` over `plugin/` and `src/`).

## Official sources and exact version context

- [Rocket League Stats API documentation](https://www.rocketleague.com/developer/stats-api): configuration, UpdateState/event fields and visibility. The page says the feature must be enabled before launching, configuration changes require restart, `PacketSendRate` defaults to 0/disabled and is capped at 120; TCP defaults to port 49123 and WebSocket to 49124. It also documents commands accepted over the socket. A data-only integration should be receive-only and must not send commands.
- [Rocket League patch notes v2.72](https://www.rocketleague.com/news/rocket-league-patch-notes-v2-72/) (2026-08-04): explicitly says Stats API added WebSocket support and commands. This establishes official announced availability of those capabilities in v2.72, not an inferred initial release date.
- [Rocket League Season 24 patch notes v2.76](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276) (2026-09-21): lists a fix for `GoalScored` not triggering in replays and a no-contest winner value of -1. Treat event presence and winner attribution defensively even with the documented fixes.
- [Epic Support: Match History and Player Profiles](https://www.epicgames.com/help/c-37599050/c-32343914/a15090520): says the feature started 2024-10-22, Match History covers 20 matches from the last 30 days, and the website profile requires sign-in and includes XP/highest-rank information.
- [Epic Support: incorrect in-game Career Stats](https://www.epicgames.com/help/c-37599050/c-32343914/why-are-my-rocket-league-career-stats-incorrect-in-game-a26668371): says in-game Career records are locally saved and can differ from the website; Support cannot sync/update those local records.
- [RLBot v5 Game Data](https://wiki.rlbot.org/v5/botmaking/game-data/) and its linked [flatbuffer schema](https://github.com/RLBot/flatbuffers-schema/blob/main/schema/gamedata.fbs): framework documentation for packet contents. The project adapter identifies its own consumed versions as RLBot core `v5.0.0-rc18` and Python SDK `2.0.0b56` (`adapter.py:1-8`); do not substitute the live docs' current branch for those pinned project versions.

## Integration boundary and next acceptance

1. Preserve three scopes in storage and UI: attempt, match, and account/profile.
   Attempt summaries keep lesson/profile/build identity, outcome, denominator,
   sample coverage and event provenance. Match records keep match identity,
   playlist/mode, per-match totals and the source API version. Account/profile
   is unavailable unless an official supported programmatic surface is
   established separately.
2. Before any Stats API reader exists, detect/document whether the installed
   client supports the documented feed and whether the user enabled it. Do not
   rewrite its INI or restart the game as a side effect. Gracefully report
   unavailable/disabled feed. Keep the socket client receive-only; the same
   documented endpoint also ingests commands.
3. Validate event parsing against official-shaped fixtures, including absent
   conditional fields, missing `MatchGuid` offline, duplicate/reordered events,
   replay `GoalScored`, no-contest winner `-1`, and socket disconnects. Never
   invent stats from a missing event or turn a team scoreboard delta into scorer
   attribution.
4. For attempt aggregation, require exact lesson/profile/version/setup
   compatibility and packet continuity for time-based measures. Show sample
   count, denominator and unknown/gap attempts. Require explicit per-mechanic
   measurement definitions for contact quality, recovery completion and target
   placement before labeling any output as a grade.
5. Keep authored practice challenge labels separate from MMR/competitive
   division. The existing Power Shots label explicitly says “Intended
   difficulty only; not a certified bot rank” (`training/engine.py:1302`);
   aggregation cannot certify mastery or establish rank equivalence.

## Unknowns left open

- Whether the current installed Rocket League build exposes the documented
  Stats API, whether it is configured/enabled, and which modes emit it; no
  runtime experiment or config change was performed.
- Whether the pinned BakkesMod runtime successfully supplies Career Stats/MMR
  getters, data freshness, playlist coverage, and current profile values; no
  call was made.
- Which drill-specific “clean contact,” stable recovery, and placement criteria
  correlate with learner improvement. Current source fields can support
  observation and aggregation, not validate pedagogy or competitive skill.

## Installed default configuration observation

The shipped `TAGame/Config/DefaultStatsAPI.ini` contains 396 bytes, SHA-256
`7d6c053c69a1e2375f40e6939043595d7c548c8d3763c153beb075052e193427`.
Its MatchStatsExporter section declares `Port=49123`, `WebPort=49124` and
`PacketSendRate=0`. No `TAStatsAPI.ini` was found in that same shipped config
folder. This identifies default file values only: it does not establish the
running process's effective configuration, whether another configuration layer
applies, or whether a socket is active. No config was changed, socket opened,
or game restarted. See [NATIVE-CONFIG-01](native-config-01.md).
