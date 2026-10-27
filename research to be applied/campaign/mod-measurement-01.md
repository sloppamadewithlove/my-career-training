# MOD-MEASUREMENT-01 — modifiers and comparable practice results

Source research by DeepSeek, reconciled against the native overlay/cosmetic
consumers and the import-selection trace. No game, new test or production edit
was performed. Configured effects and readback code are not observed runtime
effects.

## Effects that need different treatment

| Feature | Current source effect | What a stored result establishes |
| --- | --- | --- |
| Auto retry | Starts a new attempt/recorder after the existing result acknowledgement path. Strict reference capture disables it locally. | An attempt lifecycle preference, not a physics setting; acknowledgement and durable-save behavior are covered separately in PERSIST-01. |
| Controller overlay | Native `ControllerOverlaySession` writes and reads back its owned `xco_*` values, reconciles the lesson preference and handles restore/conflict paths. | The summary records a requested preference. Source readback code does not establish pixels drawn by plugin 707 or the value held during a particular historical attempt. |
| Ghost and coaching aids | Render a recorded path/actions and instructions; the current playback does not apply player input. Ghost playback speed advances its cursor, not the game's physics clock. | Assistance can change what guidance the learner sees despite not changing physics. Preserve its context when presenting aided versus unaided comparisons. |
| Ghost view preference | Saved/exposed, but the renderer does not apply it as a camera/view selection. | A stored choice is not an applied viewing mode; see CAMERA-01 and ACCESSIBILITY-01. |
| Game speed | The adapter reads game speed and the recorder stores it per sample. The scored-lesson path has no active speed-setting toggle in the inspected source. The separate community-plugin trial snapshots/restores `sv_soccar_gamespeed`. | Personal-best selection excludes explicit non-normal speed, but missing fields default to normal; imported data therefore needs separate treatment. |
| Boost | The session request specifies NormalBoost; recordings can retain observed car boost amounts. | Observed boost amount and requested boost policy are different facts. The ordinary recording's mutator metadata is not a complete observed policy acknowledgement. |
| Cosmetics/hitbox | Native application supports eleven non-body slots. Body slot 0 is excluded. The worker reads hitbox dimensions/offset and updates recording metadata from the packet. | Current MCT cosmetic application is not a demonstrated hitbox-changing path. An external mid-attempt body change remains an untested scenario. |

Source entry points: `training/engine.py:156-159,204-226,1288`;
`game_worker.py:976-981,1299-1302`;
`training/recordings.py:175-202,211-259`;
`ControllerOverlaySession.h:108-114,151-225`;
`MyCareerTraining.cpp:1443-1467,1572-1605`;
`CosmeticDesignCode.h:74-82`;
`NativeCommunityHost.h:319-330,656-679`.

## Current comparability limits

The ordinary recorder defaults `metadata.mutators` to an empty object. Two
empty objects compare equal in `compatible_recordings`; that is equality of
stored values, not proof that runtime mutators were observed unchanged.
The owned launch requests its mutators explicitly, so drift requires an
additional writer or another demonstrated transition. No such drift was
observed in this pass. Avoid presenting a hypothetical external modification
as an existing MCT toggle or a reproduced failure.

Hitbox metadata is updated as a single value, rather than retained for every
sample. If a body could change during an attempt, the final value could describe
samples from different setups. The current cosmetic adapter cannot supply that
trigger. Any future body-selection feature should establish its timing and
attempt boundary before comparing results across it.

Imported provenance and missing speed are a separate, source-reachable issue:
[IMPORT-IDENTITY-01](import-identity-01.md) traces an imported successful
`local_player` claim into automatic personal-best selection. That selector
defaults omitted speed fields to 1.0 and the bridge does not pass a compatibility
candidate. Later ghost loading may refuse the selected file. A notice about
unverified imports does not change this selection behavior.

Attempt summaries already include preferences. Recording metadata does not
retain a dedicated history of assistance changes; a final requested preference
snapshot does not establish what was active throughout a recording.

## Integration contract

Keep the player's requested toggles separate from applied/observed feature state.
Retain relevant assistance context for labels or filters without claiming that
unaided attempts certify skill. For a future physics-changing feature, record
the exact profile and an observed setup acknowledgement; define whether a change
starts a new attempt or makes the current attempt non-comparable. Preserve
normal result persistence and restoration even when a helper fails.

Distinguish three kinds of evidence in the UI and saved data: requested setup,
observed state, and imported claims. A successful checkbox write, a matching
metadata object, and a physically observed normal-speed attempt are different
levels of proof. These proposals require scoped implementation and acceptance;
this report does not claim that every modifier or downloaded plugin works.
