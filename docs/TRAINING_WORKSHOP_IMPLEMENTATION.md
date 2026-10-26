# Training and Workshop implementation checkpoint

26 October 2026. Source implementation; this is not a released or live-game
acceptance claim. The tested frozen e41 installer remains a separate artifact.

## Training

The native candidate's lesson screen starts practice and keeps explanations,
action display, timing and reset preferences. During a training session, its
authored pause menu offers compatible saved recordings and a ghost On/Off
control. It shows the newest bounded recording list, with local pagination,
personal/imported labels and attempt outcome. Career and results surfaces do
not offer these controls. There is no bundled expert demonstration.

`GhostPractice` anchors the recorded path approximately 300 game units ahead
when enabled, rotating it into the player's heading and preserving relative
motion. It repeats at normal speed until disabled. Rendering uses an original
car outline, including wheels and a nose/roof, plus recorded logical actions.
It does not create a collision actor or apply player controls. This is not a
full car mesh or a physically observed PS4 button/axis display. Missing samples
are not invented. Ball/wall-dependent drills require further scenario support.

`ghost_control {operation:"toggle", enabled:boolean}` and
`play_recording {id:lesson_id, recording_id:UUID}` cross the existing bounded
file/native action bridges. The service validates the active lesson and setup;
the worker validates recording compatibility. Worker `ghost_ack` events bind
the command ID and session. Wrong-session and obsolete acknowledgements do not
restore hidden state. Pending commands have a five-second timeout. Loading
another recording leaves practice Off; Off immediately clears pose, lines and
ghost inputs. Retry re-anchors after the actual reset settles.

`telemetry.ghost_practice`, `ghost_practice_support` and the boolean
`ghost_practice_pending` drive native control availability. Legacy playback
classes remain for compatibility, but native practice does not expose pause,
seek, speed or one-shot controls. The original ImGui build is a separate UI.

Open: real validated speed-flip teaching recording, gameplay left-D-pad edge
binding, physical DS4 acceptance, video playback, bot scenarios and live visual
acceptance of this candidate. A saved personal attempt is not a professional
demonstration.

## Workshop

Training Maps retains installed maps/favorites and adds online browsing. Mods
opens community plugin discovery and the existing release/download flow.
Public sources are Steam Workshop, BakkesPlugins Maps and BakkesPlugins Plugins.
No network request occurs just because state is read or the service starts.

`community_discovery.fetch_catalog` reads one fixed-host HTTPS catalog page,
bounded to 2 MiB and 60 rows. HTML is parsed without executing scripts; Steam's
duplicate image/title links are combined. Source IDs remain exact integers,
including modern Steam IDs above 32-bit range. Query filtering is local to the
fetched page, not a claim of full-site search. Remote challenges and failures
are reported honestly; the official source page can be opened separately.

The bridge publishes `community_catalog` independently from
`community_plugins`. `community_browse {source,page,query}` starts a background
read; `community_browse_cancel {}` invalidates it immediately. Generations
discard late results, and at most two requests can remain outstanding.
`community_open_item {source,id}` and `community_select_plugin {source,id}`
accept only rows in the current catalog. `community_open_source {source}` opens
one fixed official catalog. Caller-supplied URLs, paths and activation commands
are not accepted by these actions.

Catalog browsing is metadata only, keeping the installer small. Plugin downloads
still use server-validated release metadata and the private cache, and remain
labelled downloaded, not enabled. General mod activation, automatic map acquisition,
custom-map launch certification, removable content management and Epic acceptance
remain open. Installed game maps are not replaced. Ball prediction remains off.

## Independent checks

- Training focused Python checks: 80 passed.
- Follow-up compatibility checks: 89 training checks passed after restoring
  the legacy QML personal-best and ImGui watch/lead payloads. An internal boolean
  selects legacy playback versus native practice; incompatible loads validate
  on temporary players before changing the current recording.
- Training native layout targets: 2 passed, including latest-recording selection,
  variant matching, support-loss Off, pending controls and retained legacy guards.
- Workshop/community/bridge Python checks: 439 passed, 7 skipped, including
  60 focused catalog parser/backend tests.
- Workshop native catalog target compiled and passed, including large Steam IDs,
  typed payloads, stale choices, loading/cancellation and bounded pagination.
- Private saved-public-page parsing: 30 Steam rows, 16 Bakkes Maps rows and
  16 plugin rows, with verified title/creator extraction. This is fixture parsing,
  not live-game evidence or proof that every future site layout will parse.

The two source branches were reviewed and combined at `8c7956f`. The integrated
native plugin compiled in Release with the movie trial enabled and passed all
31 plugin CTest checks. The first full Python run found the legacy playback
regression described above (1,152 passed, 15 skipped, one failed); the corrected
full-suite result is recorded after its final run. No live game or physical
controller acceptance is claimed.

## Roles and privacy

DeepSeek V4.1 Flash 1017 via RunInfra authored the implementations. Main reviewed,
returned defects for correction, made targeted integration corrections and merged
the patches. Independent GPT-6 Luna max agents authored/ran tests. Opus did not
author these implementation patches. See DEVELOPMENT_WORKFLOW.md for the complete
owner-approved split and other permitted builders.

The privacy review found no supplied API key, key signatures or encrypted
credential blobs in the scanned tracked tree and reachable history. It did find
a historical personal profile path and a potentially identifying author address.
History is not certified clean; no public-history rewrite was performed. Raw
values, credentials, local agent transcripts and saved page fixtures stay private.
