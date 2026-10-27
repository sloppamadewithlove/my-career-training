research_only

# SETTINGS-01 — Training-first settings state and persistence (source research only)

Read-only source inspection of the frozen candidate. No code written, no tests run, no game operated. Findings are **verified source / test inventory** unless labelled **untested actual effect**. Withdrawn hypotheses are removed, not annotated.

## 1. "Training-first" is presentation ordering, not a stored setting

No `training_first` / `trainingFirst` / `perLesson` symbol exists anywhere in the tree (three searches, zero hits). Training-first is derived at render time:

- `plugin/include/NativeMatchLayout.h:570-575` declares `tabs = [{"training","Training"}, {"game","Game options"}]`; the comment states Training is the first tab and the one the page opens on.
- `native_ui/menus/MctPauseMenu.as:321-329` — on a new generation the tab resets only `if (!panelWasActive) panelTab = ""`. The comment at `:323-325` states tab choice is local presentation and survives ordinary state refreshes.
- `MctPauseMenu.as:422-430` (`normalizePanel`) falls back to `tabs[0].id` only when the current tab id is no longer present (e.g. the Ghost tab disappearing when a pack loads).

There is no settings key, no persistence and no restore for tab position. It is re-derived per panel appearance and preserved within a continuous panel session. Design property, not a defect.

## 2. Settings key / effect / scope / persist / restore

| Key | Producer | Consumer / effect | Scope | Persist | Restore |
|---|---|---|---|---|---|
| `lesson_preferences[lesson][actions]` | `NativeMatchLayout.h:588` → `assistance` | Lesson HUD prompts; `game_worker.py:1342` | per-lesson | `bridge.py:1368-1370` `_commit` | survives restart (`storage.py:28`); no external state |
| `…[explanations]` | `:592` | step text; `game_worker.py:1335` | per-lesson | same | same |
| `…[timing]` | `:595` | timing feedback; `game_worker.py:1345` | per-lesson | same | same |
| `…[auto_reset]` | `:600` | auto retry; `game_worker.py:817`, `:896` | per-lesson | same | same |
| `…[controller_overlay]` | `:609-616` | real `xco_enabled` write, `ControllerOverlaySession.h:166` | per-lesson, lesson-scoped | same | `ControllerOverlaySession.h:227-263` |
| `…[ghost]` | `:632` (Ghost tab) | ghost playback; `game_worker.py:851-852` | per-lesson | same | n/a |
| `settings.training_display.*` | `NativeCareerLayout.h:2452-2463` | coaching/ghost view; `bridge.py:1213-1222`, `:1477-1509` | global | `bridge.py:1219` | survives restart |
| `settings.binding_profile` | `NativeCareerLayout.h:2469-2480` | **labels only** (`Main.qml:599`); no gameplay binding | global | `bridge.py:1292` | n/a |
| `settings.text_scale`, `reduced_motion` | `Main.qml:594-595` | UI only | global | `bridge.py:1292` | n/a |
| `settings.launcher`, `settings.install_path` | `Main.qml:579-583` | **actual launch configuration**: `bootstrap.py:142-193` preflight/launch, `bridge.py:1709-1712` request, `game_worker.py:570` owned-game detection | global | `bridge.py:1292` | survives restart |
| `controller_overlay.installed_by_session` | `plugin_session.py:311-330`, `bridge.py:244-262` | gates the Show-controller row (`NativeMatchLayout.h:607-611`) | session | file journal receipt | file cleanup on session end |

## 3. Implemented vs unavailable checkboxes

Implemented with a real scoped effect:
- Lesson HUD / Instructions / Timing / Retry-after-attempt — validated by `assistance_preferences` (`training/catalog.py:16-31`), applied at `game_worker.py:902-910`.
- Show controller — the only checkbox with an external effect and a genuine readback: `ControllerOverlaySession.h:176-187` writes then re-reads each cvar and compares numerically (`equivalent`, `:273-284`). The readback proves the cvar holds the value; it does **not** prove plugin 707 re-reads it or that the overlay is drawn.
- Ghost practice — real, but only built when ghost choices exist (`NativeMatchLayout.h:617-643`).

Unavailable / not a checkbox:
- Community plugins — `NativeMatchLayout.h:651-652`, `kind="unavailable"`, reason `kActivationReason`; non-interactive because `MctPauseMenu.as:466` requires `control.enabled === true`.
- Game options — `NativeMatchLayout.h:647-650` is `PreserveStockRoute` / `StockRoute::Options`, a link into the stock screen. Stock options are never re-implemented.
- Show controller when the overlay was not staged — `:608-611` passes `available = overlayStaged`; the row renders disabled with the reason "Install the controller overlay for this session, then reopen the pause menu."

## 4. Reachability of the aid rows

`NativeMatchLayout.h:95-100` computes `trainingLive = kind == "training" && !busy && ((worker && phase == "training") || loadedTrainingPack) && lesson present`. `syncTrainingOptions` (`:539-546`) runs **before** `buildTrainingOptions` and resets the options page when `!live`; `choose` (`:199-216`) revalidates `live` on activation. A pending or failed pack with no running lesson therefore cannot reach the aid rows, and the dispatch gate at `bridge.py:738-748` / `:812-814` is consistent with that. No mismatch exists.

## 5. #707 visibility ownership, journal and restoration

Two **separate** restoration mechanisms, which must not be conflated:

**(a) C++ cvar restoration** (`plugin/include/ControllerOverlaySession.h`):
- Five owned cvars: `xco_x`, `xco_y`, `xco_scale`, `xco_skin`, `xco_enabled` (`:108-114`).
- `apply()` (`:151-190`) reads all priors first; any failed read returns `Missing` with nothing owned. It then writes each value and sets `owned = true` **before** the readback (`:178`), so a failed write is still restored. Any readback mismatch calls `restore()` and sets `blocked_`.
- `restore()` (`:227-263`) iterates in reverse and writes each `prior` value back. **The reverse order is not inherently "disable first"**: it writes `xco_enabled`'s prior value, which is `0` only when the overlay was hidden before the lesson. If the user had the overlay enabled pre-lesson, restore re-enables it. The ordering only guarantees the visibility write precedes the artwork writes.
- If the current value is neither the applied nor the pending value, `restore()` checks whether it already equals the prior (then releases ownership silently) else records `Conflict` and releases ownership **without writing** — the user's edit is preserved.
- `enabledPending_` (`:119`, `:213`, `:239-249`) prevents an in-flight visibility write being mistaken for a user edit during cleanup.
- `reconcileEnabled()` (`:194-225`) follows a changed per-lesson preference while active; a value differing from what we applied is treated as a user edit, ownership is released, and the session blocks.
- Session-installed vs preexisting (`:41-61`): `installedBySession && ownedOffline && !baselineConfirmed_` → `disableOwnedInstall()` (`:126-149`) forces `xco_enabled=0` with readback, up to 3 attempts, before eligibility. A preexisting install never enters that branch, so the user's own enabled state is untouched outside lessons.
- Eligibility (`:46-48`) requires `owned && offline && fresh && inGame && !online && !replay && kind=="training" && state=="training" && !lesson.empty()`; anything else restores.
- Producer: `plugin/src/MyCareerTraining.cpp:1443-1468` builds the scope, including `installedBySession` from `state.controller_overlay.installed_by_session` (`:1454-1455`) and `enabled` from `lesson_preferences[lesson].controller_overlay` defaulting to true (`:1461-1463`). Called from `:1286`.
- Clean shutdown: `onUnload()` (`:258-274`) calls `shutdown()` up to 3 times and logs `outcomeText` plus `remainingOwned()` if it fails.

**(b) File journal** (`src/my_career_training/plugin_session.py`): `JOURNAL_DIRNAME = "plugin-session"` (`:21`), `journal`/`receipt_path`/`report_path` (`:184-186`), `_write_receipt`/`_write_backups` (`:460-474`), `_receipt()` validation (`:475-543`), `_restore()` (`:544-587`), `_restore_resource()` (`:588-636`), `_prior_bytes` (`:637-649`), `_replace_if_unchanged` (`:650`). This journal covers **installed plugin files and autoload lines**, not cvars. `controller_overlay.py` has no journal of its own (search for `journal` returned zero hits); it stages, validates and inspects files (`:76-283`).

So: file-level overlay installation is journaled and recoverable; cvar-level visibility/placement is restored only by the in-process `ControllerOverlaySession`. **No durable cvar journal was identified**, and whether abnormal exit or config persistence leaves lesson values behind remains unverified.

## 6. Six-part player action contract

1. **Open** — pause menu publishes a view; `MctPauseMenu.as:321-329` resets the tab only when the panel was previously inactive; `normalizePanel` selects Training.
2. **Read state** — rows built from `state.lesson_preferences[lesson]` (`NativeMatchLayout.h:551-560`); a stored value is the only way a box shows Off; defaults from `ASSISTANCE_DEFAULTS` (`catalog.py:5-13`), all On.
3. **Toggle** — click dispatches `assistance` with `{id, key, value: !on}` (`:561-566`); the checkbox mark is non-interactive (`MctPauseMenu.as:504-526`).
4. **Persist** — `bridge.py:1361-1372` validates through `assistance_preferences`, deep-copies the document, writes `lesson_preferences[lesson]`, then `_commit`. One durable commit; no pending fixture touched.
5. **Live apply** — only if the worker is active **and** the request lesson matches (`:1371-1372`), a `preferences` command is sent; `game_worker.py:902-910` applies each key.
6. **Restore/exit** — overlay restores on ineligibility (`ControllerOverlaySession.h:49-53`); lesson preferences persist and are re-read on the next open.

## 7. Source-contract limitations awaiting actual effect

- **Checkbox can disagree with the overlay.** The panel reads `lesson_preferences`, not the cvar. After a `Conflict` (`ControllerOverlaySession.h:203-209`) the overlay stays in the user's state while the row still shows the stored preference. The presented preference is therefore not proof of the runtime state. Untested actual effect.
- **Rejected toggle feedback.** `bridge.py:816-817` sets a generic `self.error`; the row value is rebuilt from the committed document, so the box correctly stays at the old value, but there is no per-row reason. Untested actual effect.
- **No durable cvar journal identified** (see §5). Untested actual effect.

## 8. Developer integration points

- `plugin/include/NativeMatchLayout.h:548-654` — the Training options page; `:95-100` and `:539-546` — the live gate.
- `plugin/include/ControllerOverlaySession.h:108-114` (owned cvar set), `:151-190` (apply), `:227-263` (restore).
- `plugin/src/MyCareerTraining.cpp:1443-1468` (scope producer), `:258-274` (unload cleanup).
- `src/my_career_training/bridge.py:1361-1372` (single durable preference commit), `:738-748` and `:808-814` (editability gating).
- `src/my_career_training/training/catalog.py:5-31` — authoritative key set; a new checkbox must be added here or `assistance_preferences` raises.
- `native_ui/menus/MctPauseMenu.as:442-499` (row rendering) and `:974-996` (`usablePanel` rejects unknown `kind` and unknown control ids — both places must change together).

## 9. Existing tests (inventory only, not executed)

- `plugin/tests/controller_overlay_session_tests.cpp` — ~20 cases: apply/restore (`:109-128`), failed apply leaks nothing (`:150`), write failure (`:167-176`), read failure (`:185-195`), hub→lesson→career→shutdown (`:215-227`), preexisting enabled preserved (`:233-241`), missing cvar (`:246`), write ordering (`:252-269`), user edit not overwritten (`:329-332`), on/off/on follows the checkbox (`:306-320`), failure paths (`:352-421`).
- `plugin/tests/native_match_movie_tests.cpp:350-447` — panel opens on Training tab, checkbox rows carry real values, stored Off is the only way to show unchecked, rows unusable after Back.
- `plugin/tests/native_training_options_tests.cpp:47-49` — pack-loaded state fixture.
- `plugin/tests/native_career_layout_tests.cpp:487` — legacy ghost checkbox must not remain in the lesson flow.
- `tests/test_training.py:83-107` — `controller_overlay` is an independent boolean.
- `tests/test_bridge.py:133-147`, `:90` — settings and lesson-preference persistence.
- `tests/test_plugin_session.py:181-268` — overlay files temporary, preexisting identical overlay not session-owned, partial write rolls back.
- `tests/test_game_worker_ghost_practice.py:352` — `training_display.ghost` persisted.

## 10. Precise next acceptance

1. Prove on the exact candidate that each of the five aid checkboxes changes observable in-lesson behaviour, not just stored JSON.
2. Prove overlay restoration after crash/timeout/restart, given no durable cvar journal was identified.
3. Prove a deliberate user edit during a lesson survives cleanup and that the row then reflects reality rather than the stored preference.
4. Prove the file journal recovers a session-installed overlay after an abnormal exit (`plugin_session.py:544-587`).
5. Prove the Show-controller row's disabled reason is visible to the player when the overlay was not staged.

## Limits

I did not read `plugin/src/CareerUI.cpp`, `src/my_career_training/controller_overlay.py` in full, `src/my_career_training/plugin_session.py` in full, or `src/my_career_training/storage.py` validation. The ImGui settings page, archive validation internals and receipt schema are therefore unverified. No test was executed and no game was observed. This is source research, not approval of runtime behaviour, and it does not cover the nine-plugin compatibility matrix, mod download, or Ghost replay research owned elsewhere.
