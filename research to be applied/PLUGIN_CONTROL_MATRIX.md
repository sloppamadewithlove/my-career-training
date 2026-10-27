# Training controls and plugin ownership

This is a builder map, not a list of supported installed plugins. The audited
default-plugin source is pinned at
[`f412cd66`](https://github.com/bakkesmodorg/BakkesMod2-Plugins/tree/f412cd66ce0735be4aeb21ca41325337eb959aa0).
Each linked report identifies exact inspected bytes. Source availability does
not prove installed DLL identity, successful activation, or permission to copy
the implementation; no tracked license file was found at this pin.

## Match the control to its actual behavior

| Feature | Source behavior | Suitable MCT control | Integration requirement |
| --- | --- | --- | --- |
| [Dribble](campaign/dribble-plugin-01.md) | `ballontop` places the current ball; `shootatme` changes its velocity. No persistent mode. | Explicit setup/launch buttons. | Bind to a fresh attempt and confirm resulting state. A saved checkbox cannot acknowledge a one-shot action. |
| [Redirect](campaign/redirect-plugin-01.md) | `redirect_shoot` writes ball velocity toward the current car plus offsets/prediction. | Explicit feed action or an authored feed profile. | One launch owner; resolve effective parameters; establish the observed launch baseline after the write. |
| [Rebound](campaign/rebound-plugin-01.md) | `rebound_shoot` chooses a goal, generates velocity and changes ball spin. | Explicit rebound setup or authored scenario. | Use selected map geometry and deterministic recorded parameters. Existing MCT bounce/backboard profiles already own whole-state setup. |
| [Recovery](campaign/recovery-plugin-01.md) | Start/stop commands control repeated car-velocity disturbances. No active-state cvar. | Checkbox only after an adapter supplies observed activation state. | Idempotent start, stop before resets, pending-callback lifecycle proof, and assisted-attempt identity. Stopping cannot undo an applied impulse. |
| [Defender](campaign/defender-plugin-01.md) | Repeated ball shots for save practice, goal-triggered relocation, and a goal-scoring cvar change. No bot-car controller. | A named goalkeeper-feed mode with an enabled checkbox. | Preserve goal-scoring settings, confirm active state/context, own launch and reset, and define save evidence. Keep it separate from MCT's defender bot. |
| [Mechanical](campaign/mechanical-plugin-01.md) | Changes intercepted control inputs; clamps axes, blocks buttons, holds boost or maps yaw to roll. | Named assistance profiles with enabled state and explicit effective values. | Human-only actor binding, context/handler acknowledgement, deterministic option precedence, cleanup and recording compatibility. |
| [Ball Prediction](campaign/ball-prediction-01.md) | Maintains a prediction cache and draws an overlay. | Overlay checkbox after cache/context/cleanup validation. | Refresh on MCT state resets and establish drawable ownership. No scored-outcome claim from a prediction. |
| [Legacy shot JSON](campaign/shot-data-01.md) | Partial ball/car shot parameters with parser limitations and an executable script option. | Validated data import into a separate authored draft. | No script execution; explicit units and versioned targets/outcomes. A shot file is not a complete MCT lesson. |

Steam Workshop loading has a separate [arrival contract](campaign/map-arrival-01.md).
The audited [legacy WorkshopPlugin](campaign/workshop-plugin-01.md) exchanges
shot JSON/playlists through an external peer; it is unrelated to Steam map
loading. Its delegated reset schedules later ball writes without a bound
shot/session identity. Keep those systems separate, and reject executable
script fields in any future data-only shot importer.

## Common implementation contract

Keep Training first in the owned-match settings menu. Preserve Lessons,
Workshop, Mods and Favorites in the browser and the separate lesson-to-rank
menu. Group controls by their player effect: display aids, authored setup
actions, and assistance modes. Show the reason when a feature is unavailable;
stock settings already have a description/help path.

Before an adapter reports Active, establish exact plugin/build availability,
supported session context, session/attempt identity, Human actor where relevant,
effective parameters, and acknowledgement from the component owning the effect.
An installed file, saved preference, issued console command or returned callback
does not supply all of that evidence.

The audited default commands commonly require BakkesMod Freeplay and some also
require the pause menu closed. Ordinary MCT lessons request an offline Soccar
match with `freeplay=False`. The exact runtime relation between those APIs has
not been measured. Keep unsupported controls unavailable until that context is
verified; a click inside an open pause menu is not proof a pause-closed command
ran.

Whole-state setup must have one owner. Stop repeated mutation before MCT resets
actors, then confirm the selected ball/car/roster state before starting the
attempt clock. Treat direct state writes and control transforms during a scored
attempt as recorded assistance or a distinct authored variant. Include the
effective profile in personal-best and ghost compatibility instead of silently
mixing assisted and unassisted runs.

Capture prior settings before changing them and track ownership of each written
field. Restore only values still owned by this adapter, report conflicts, and
test disable, failed activation, retry, Return, scope loss and unload. The
[cosmetic reproducer](campaign/cosmetic-restore-probe-01.md) demonstrates why a
single saved baseline can overwrite a later user edit.

## Evidence still required

The six newly audited mutation plugins were not loaded or exercised in this
session. Their range-looking cvar strings do not, by themselves, prove how
values are sampled. SDK CVar semantics remain under focused investigation.
Hook/timer teardown, actor identity, real trajectories, visible results and
settings restoration need separate acceptance in an owned game session.

Existing MCT scoring currently tracks Human and keeper touches in the Power
Shots chain, leaving defender attribution incomplete. The [offline diagnostic](campaign/outcome-probe-01.md)
reproduces the resulting source behavior; it does not establish a physically
reachable shot. Resolve that policy before adding feeds or more active actors.
