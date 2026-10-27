# PACK-01: training-pack identity, progress and offline boundary

Read-only source and public-source review of `work/reviewed-training`. No game
input, game attachment, compilation, or tests were performed for this report.
Source declarations and previous recorded playtest evidence are separated from
runtime behavior; this report does not claim current in-game acceptance.

## Findings

### Catalog and identity

The app has a fixed six-row excerpt of Psyonix-featured community packs from a
2020 post. Each row stores a stable app ID, creator, title, creator-listed rank,
code, source and `lesson_id: power-shots`; the copy is metadata, not pack data.
The cited post lists nine entries, so the catalog is deliberately incomplete
and has no SSL entry. A displayed Grand Champion rank is not an app rank or
competitive-rank assertion. (`src/my_career_training/training/packs.py:1-26,
28-102`; `docs/TRAINING_PACKS.md:3-26, 28-40`.)

The Lessons browser adds six rows with identity `lesson:pack:<id>`, and details
show the listed rank, creator and pack code. The primary action is explicitly
disabled as “Unavailable offline”; the saved favorite can still be removed.
There is no pack file import, pack-content download, live catalog refresh, or
account inventory path in this adapter. (`plugin/include/NativeCareerLayout.h:655-670,
1552-1598, 1600-1632`;
`src/my_career_training/training/packs.py:105-132`.)

Favorites are app-owned snapshots keyed by type and ID. For a pack, the key is
`lesson` plus `pack:<id>`; storage keeps display text and does not persist an
action or game progress. The stock game’s History tab and its own Favorites are
separate features. (`src/my_career_training/bridge.py:668-731`;
`src/my_career_training/storage.py:24-61`.)

### Browse, play, and the boundary of “loaded”

`training_packs()` publishes static metadata into bridge state. A requested play
would accept only a fixed catalog ID, create a session/request identity, and
send `load_training <catalog-code>` once. The native host is restricted to the
owned offline frontend and rechecks process, nonce, build, movie and session
scope. It marks the request loaded only after `IsInCustomTraining()` and an
exact matching code are observed; it keeps verifying that identity while
loaded. This proves an exact pack code is active, not that a shot was attempted
or completed. (`src/my_career_training/bridge.py:255-262, 1213-1224`;
`plugin/include/NativeTrainingPackHost.h:23-80, 158-220, 255-365`;
`plugin/src/MyCareerTraining.cpp:1119-1165`.)

The active native observer reads the current code from
`TrainingEditorWrapper::GetTrainingData()->GetTrainingData()->GetCode()`; it
does not call the progress, completion, history or reset APIs described below.
The Python session receipt likewise checks request identity and exact code. A
loaded status carries no shot index, total, completed-shot list or game-history
record. Return clears the app session; its pause help directs players to the
game’s own Custom Training controls for retry and shot selection.
(`plugin/src/MyCareerTraining.cpp:1119-1165`;
`src/my_career_training/training/native_packs.py:70-112, 140-220`;
`plugin/include/NativeMatchLayout.h:95-106, 525-530`.)

Project documentation records a previous exact-code load attempt against the
offline training service returning `FeatureDisabled`; the game remained at the
frontend and no pack or shot was loaded. This is the reason the current browser
keeps the row but disables play. Cached/reopened-pack behavior is explicitly
unverified; the SDK’s editor `Load2` declaration is not evidence of a frontend
offline loader. (`docs/TRAINING_PACKS.md:53-71`.)

### Official progress and SDK interfaces

Psyonix’s Season 7 Custom Training notes say game save data records per-pack
progress, shots can be completed out of order, the Pause menu can reset a
started or completed pack, and the native History tab lists recent packs and
can add them to the game’s Favorites. The End Training screen shows progress.
These are stock-game behaviors; they do not establish that MCT exposes or
persists them. [Official Season 7 Custom Training notes](https://www.rocketleague.com/news/season-7-changes-coming-to-custom-training/?lang=en).

The project pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`
with archive SHA-256
`e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`
(`plugin/CMakeLists.txt:26-29`). That header surface is more useful than the
current pack host exposes:

- `GameWrapper` declares `IsInCustomTraining`, `GetGameEventAsServer` and
  `GetGfxTrainingData` ([pinned header, lines 47-66 and 123](https://raw.githubusercontent.com/bakkesmodorg/BakkesModSDK/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h)).
- `GfxDataTrainingWrapper` declares current/total round and per-shot progress
  reads, completed/perfected checks, and `ResetTrainingProgress`
  ([pinned header, lines 16-19 and 32-40](https://raw.githubusercontent.com/bakkesmodorg/BakkesModSDK/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/gfx/GfxDataTrainingWrapper.h)).
  `TrainingRoundProgress` exposes a round number and status byte
  ([pinned struct, lines 1051-1055](https://raw.githubusercontent.com/bakkesmodorg/BakkesModSDK/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/wrapperstructs.h));
  the byte’s enum mapping and meanings remain unknown here.
- `TrainingEditorWrapper` separately declares shot attempt, current save data,
  round count, `ResetBalls`, `SwitchToRoundNumber`, `RestartPlayTest`, and an
  editor `Load2` ([pinned header, lines 28-38, 54-65 and 80-83](https://raw.githubusercontent.com/bakkesmodorg/BakkesModSDK/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameEvent/TrainingEditorWrapper.h)).
  These signatures do not prove availability or semantics in the public Custom
  Training flow.

The existing native built-in-training probe already calls
`GetGfxTrainingData()` and reads mode, difficulty, current round and total
rounds (`plugin/src/MyCareerTraining.cpp:411-490`). That is source evidence the
wrapper is used for a different, built-in-training observation path; it does
not prove pack progress semantics. The pack observer itself does not use these
getters. No call to `GetProgressPerShot`, `HasCompletedTraining`,
`HasPerfectedTraining` or `ResetTrainingProgress` was found in the pack path.
SDK declarations are interfaces only, not runtime proof.

## Current support matrix

| Player action/state | Evidence in this checkout | Limit |
| --- | --- | --- |
| Browse featured packs | Six fixed metadata rows, with title, author, listed rank and code. | Not a live or complete catalog; 2020 metadata excerpt. |
| Favorite a pack | App saves and removes a bounded `pack:<id>` display snapshot. | Separate from Rocket League favorites/history; records no viewed/selected state. |
| Launch a featured pack | Development native host has a fixed one-shot load and exact-code receipt. | Browser launch is disabled offline; prior recorded request failed with `FeatureDisabled`. Not a supported working MCT play route. |
| View progress / completion | Stock game docs describe saved per-shot progress and End Training summary; pinned SDK has progress/completion declarations. | MCT does not query, display, store, or acknowledge pack completion; SDK applicability to a live pack is unproven. |
| Reset / next / select shot | Stock game documents native controls and pause reset. | MCT does not implement these as pack operations; no reset call in the adapter. |
| Import or use offline cache | None in the MCT pack adapter. | No pack contents are bundled or imported; reopening a downloaded pack offline is unknown. |

## Six-part player action contract

1. **Preconditions:** A supported current game session, a known exact pack
   identity, and a pack source that can actually load in that session. Today,
   the MCT row must say it is unavailable offline; its static metadata is not
   proof of service availability.
2. **Input:** Browse or favorite a fixed row. A future play action must resolve
   only its catalog ID to its fixed code; never accept a caller-supplied code.
3. **Visible/state outcome:** Distinguish `selected`, `load pending`, `loaded
   (exact code confirmed)`, `failed`, and `shot progress`. Current source has the
   first four states only; “loaded” is not a completed attempt.
4. **Persist:** Keep MCT favorites in MCT storage. Let the native game own its
   progress/history unless an explicit, verified bridge is added; do not mirror
   a favorite snapshot into game history or infer completion from launch.
5. **Failure/recovery:** On unavailable service, timeout, wrong code, lost
   heartbeat or changed session, show failure and keep retry disabled until the
   documented session recovery. Do not substitute a built-in drill or claim an
   offline cache works.
6. **Acceptance proof:** In a permitted controlled game session, compare the
   exact active code and any exposed progress array with the native UI through
   shot navigation, one completion, out-of-order completion, exit/reopen and
   explicit Reset Progress. Confirm which data survives game restart and that
   browsing/favoriting alone changes only MCT’s favorite file. Separately
   confirm the offline-unavailable state without claiming a loaded pack.

## Smallest future integration and tests

Keep the current static catalog/favorite identity. If pack loading becomes
available, extend the existing pack observer to read the exact active code and,
only after controlled runtime validation, the pinned `GfxDataTrainingWrapper`
round/progress/completion values. Bind each snapshot to the already checked
session and code. Keep reset behind an explicit game action only after verifying
that `ResetTrainingProgress` resets the intended pack and save data. Do not
reimplement the game’s History tab from guessed metadata.

Existing coverage pins six catalog records and exact-ID/code validation
(`tests/test_training_packs.py:30-106`), Python/native catalog parity, request
identity, exact acknowledgements, timeout/wrong-code/scope failure and return
identity (`tests/test_native_training_packs.py:53-160`;
`plugin/tests/native_training_pack_host_tests.cpp:44-202`), plus disabled pack
rows and favorite removal (`plugin/tests/native_training_browser_tests.cpp:299-331,
440-483`). It does not test a live pack, game-owned favorites/history, progress,
shot completion, reset, or offline cache reopening.

Minimum future runtime acceptance is a controlled pack with known saved
progress: verify exact code, compare wrapper current/total/progress values with
the game UI, exercise one out-of-order completion and re-entry, check native
Reset Progress effect, and prove MCT browsing/favorite operations do not mutate
game progress. Until then, progress/completion/reset support in MCT remains
unimplemented and the SDK path is only a candidate interface.
