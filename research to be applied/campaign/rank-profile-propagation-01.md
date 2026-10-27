# Power Shots rank-profile propagation

The defender omission documented in this baseline audit has a later [isolated candidate and regression evidence](defender-attribution-candidate-01.md). That patch is not installed and does not change the profile values or grading-policy limits below.

## Scope and evidence

This is a source-only audit of the frozen `work/reviewed-training` checkout. I enumerated `scenario_definition` for the 12 implemented situations at all eight profile labels (96 definitions); this was an inline read-only calculation, not a test run or gameplay evaluation. The coordinator independently repeated the enumeration and retained the [96-definition calculation receipt](../evidence/rank-profile-propagation-01.json), including source hashes, projected windows and Silver-to-Gold deltas. These calculated values are not measured ball trajectories.

Primary anchors are `src/my_career_training/training/scenarios.py:19-47, 208-245, 247-292, 294-366, 404-416, 477-490`; `training/scenario_setup.py:10-29, 79-106`; `training/engine.py:100-150, 477-572, 817-829, 1268-1345`; `bots/__init__.py:14-30, 37-70`; and `bridge.py:1726-1736, 1790-1793`, `game_worker.py:501-511`, `adapter.py:45-53`.

SHA-256 values for the inspected frozen files:

- `training/scenarios.py`: `35714A224AA8765AE62BE6FDE3DF6DC87C088C32D297ADCDA3795D0BC682D979`
- `training/scenario_setup.py`: `D2421BF8F7AC2508E9F3A65DB21B2847A0E147B75CC62A6159A976999536A0FE`
- `training/engine.py`: `37028379A268D6F6E19D42B32A9E3C20778ED4F41D87BFBD3BC76955C61C602A`
- `bots/__init__.py`: `6B9E406B1532D1064499CE5918D6A4187A7D08300F769C8B6A9FB52E1687A12E`
- `bridge.py`: `AC502D1F19810BACA479A534AA766A6AFBEA7BA57A405452835CC9DCFF379AC2`
- `game_worker.py`: `2E3982DFC352E4FAFCD667898B3CB1F76538B61447C2B6E47ADC6D9F862E89C2`
- `adapter.py`: `98D1F4612967EDA756B21857DFD198A3A12E4A211684067A248B9A829B74285C`
- `training/coaching.py`: `3B8336A54F4997479F1CE56F787377EB748683A117C8BA24A82E6E3C03B25D3B`

## Profile values and propagation

The launch-speed factor multiplies each situation's authored base speed in `_launch`; it is the horizontal velocity magnitude. The timeout starts at “go.” The projected shot window is `timeout - (2D path length / speed)` and is returned as metadata. The last column is the min/max of that calculation over all 12 situations, not an observed in-game timing range.

| Label | Speed factor | Timeout (s) | Keeper `(level / skill / speed cap / reaction s / lane Y / depth Y)` | Defender `(level / skill / speed cap / delay s)` | Projected window range (s) |
|---|---:|---:|---|---|---:|
| Bronze | 1.00 | 15 | — | — | 10.97–13.52 |
| Silver | 1.06 | 14 | — | — | 10.20–12.61 |
| Gold | 1.11 | 14 | 2 / .20 / 850 / 1.40 / 4400 / 4860 | — | 10.37–12.67 |
| Platinum | 1.17 | 13 | 3 / .30 / 950 / 1.10 / 4380 / 4830 | — | 9.55–11.74 |
| Diamond | 1.22 | 12 | 4 / .42 / 1050 / .85 / 4350 / 4780 | 3 / .34 / 900 / 1.10 | 8.69–10.79 |
| Champion | 1.28 | 11 | 5 / .55 / 1150 / .65 / 4320 / 4720 | 4 / .48 / 1050 / .85 | 7.85–9.85 |
| Grand Champion | 1.33 | 10 | 6 / .68 / 1250 / .48 / 4290 / 4660 | 5 / .62 / 1200 / .62 | 6.97–8.89 |
| Supersonic Legend | 1.39 | 9 | 7 / .80 / 1350 / .34 / 4260 / 4600 | 6 / .76 / 1350 / .42 | 6.10–7.94 |

`_opponents` builds no bots for Bronze/Silver, a keeper for Gold/Platinum, then a keeper plus defender from Diamond onward. Each profile field reaches an authored consumer: speed changes launch velocity; timeout limits the active attempt and drives remaining-time HUD fields; keeper and defender level/skill feed `SpecialistController`; explicit speed caps, reaction intervals/delays and keeper lane/depth affect their controllers or starting poses. Defender coordinates come from each situation's `pressure` point only when a defender exists. Thus the per-situation pressure points are present but unused below Diamond.

For late situations (the final six in the implementation tuple), setup applies the same contextual offsets at each rank: keeper depth and lane limit each move 220/180 units, and reaction delays increase by 0.4 s; a defender closer than 1400 units to the receiving lane is moved to exactly that distance and its delay also increases by 0.4 s. This changes scenario geometry/context but does not reverse the rank ordering of the profile's bot levels, speed caps or base reaction values.

Four authored situations change the `execution` category between Bronze/Silver and Gold+: the two bounce/drop deliveries, wall rebound and backboard rebound. Only the bounce/drop cases also change the launch's vertical start state at that threshold (from a shallow settling bounce to a higher/slower-dropping ball). The wall/backboard cases keep their reflected launch construction and receive a different execution label. The other eight situations remain `grounded-receive` across ranks.

## Monotonicity, defaults and grading

- The speed factors strictly increase; arrival estimates strictly decrease. Timeout is non-increasing, but Silver and Gold share 14 seconds. Consequently the projected window rises from Silver to Gold in **all 12** situations by 0.063–0.171 s, despite Gold adding a keeper. From Gold through SSL the projected window decreases. This is the only cross-rank inversion found in the computed timing values. Because `shot_window_seconds` is constructed only in `scenarios.py` and has no other source consumer, it is descriptive metadata, not a separate enforced pass window; the engine enforces the full selected timeout.
- Keeper and defender level, skill, speed cap, and base reaction delay are monotonic in the pressure direction (higher capability/speed, shorter delay). The keeper's lane limit and depth move in the authored pressure direction as numeric values decrease. The keeper start X is an exception to fixed geometry: absent a situation-specific `keeper_x`, it is `-620 + 95 * rank_index`, moving from −430 at Gold to +45 at SSL across ten situations. `keeper-commitment` and `crowded-box` override this with fixed X=650 and X=450 for every rank.
- The menu/persisted setup defaults to Bronze (`DEFAULT_DIFFICULTY = RANKS[0]`); `start_setup` preserves a valid saved rank or strictly validates an explicit rank. The normal bridge route copies that resolved rank into the worker request, and the worker passes it to both match descriptors and `TrainingEngine`. Separate lower-level defaults are Gold (`scenario_definition`, `scenario_descriptors`, `TrainingEngine`, and worker request fallback). They do not override the normal menu route, but direct/internal callers omitting difficulty get Gold while an empty UI preference gets Bronze.
- Rank labels affect setup pressure and attempt length, not the grading threshold. All profiles return the same target and nominal success-event list. The engine clears generic lesson completion events and uses the same scenario chain: observed setup launch, fresh Human touch, target crossing, and a team-0 score increase. No rank-specific accuracy, shot quality, speed, or pass threshold is applied. The returned `success_events` list is not consulted by that grading path. One rank-specific attribution caveat: bots are required to remain present, but the engine's post-shot actor list tracks Human and keeper, not the Diamond+ defender; a defender contact therefore is not part of the “latest attributed touch” check in the current source path.
- The code itself qualifies the names as intended exercise difficulty, not a certified rank. The specialist provider manifest also identifies the bot as experimental, with no rank certification, no evaluated formats, unavailable rank targets and no recorded Windows match evaluation (`bots/__init__.py:14-30`). These tiers should not be presented as calibrated competitive ranks or measured player-level equivalents.

No `_PRESSURE` tuple field was found to be dead: speed/timeout and bot tuple values reach setup or control logic. The meaningful unused outputs are `shot_window_seconds` and the `success_events` list described above. This report establishes static source propagation only; it does not establish that the profile difficulty is fair, that each bot creates the intended gameplay pressure, or that labels predict competitive rank.
