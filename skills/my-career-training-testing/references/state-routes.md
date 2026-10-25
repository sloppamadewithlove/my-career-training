# Native state routes

These are observed routes and candidate acceptance recipes as of 25 October
2026. Read current project status first. Revision labels identify historical
evidence, not permission to skip checks on changed controls. Use current visible
labels and refreshed view/status files; coordinates depend on the window.

| Target | Route | Required observation | Evidence / limit |
| --- | --- | --- | --- |
| Authored hub | Launch the coherent candidate using the isolated app helper; if the actual title is present, press Enter once | Actual RootMenuMovie, fresh matching frontend READY, visible My Career root | Repeated source runs through e5dec4c; a title screen alone is insufficient |
| Career playing | Hub → My Career → Play Next Match, using the actual native button | Matching session/fixture, worker Playing, real game packets and controllable match | Native Play passed on 374c85d and later source runs; a private bridge dispatch does not prove this button |
| Pause | While playing, ordinary Escape; use the physical controller separately for Start | Actual MidGameMenuMovie and fresh pause READY | Keyboard/mouse observed; physical-controller acceptance remains open |
| Options and resume | Pause → Game options → Back → Resume | Actual OptionsMenuMovie, return to authored pause, then active play | Source 374c85d / 714f3c2; check focus again after each transition |
| Practice and Retry | Hub → Training → an offered lesson → Start; activate Retry in the lesson's authored controls | Training session runs, retry is accepted and the exercise resets | Source 374c85d; do not use career fixture controls as practice evidence |
| Cancel unfinished Return | Active career → pause → Return to My Career → Back | Back is the default; fixture remains active and unsaved | Source 374c85d; Return is not a loss |
| Confirm unfinished Return | Same confirmation → explicit confirm | Worker cleanup and exact ACK, typed shell attempt, fresh visible hub; pending fixture remains replayable | Source 374c85d; observe saved-state semantics separately |
| Delayed cleanup | In a disposable practice session, use the existing bounded cleanup-delay helper around confirmed Return; try Escape/Resume | Leaving screen retained during the bounded hold; after worker resumes, exact ACK and fresh hub in same game | Source 24a8bbe passed Escape during a 3.5-second hold; not every possible screen-unload path |
| Natural results | Start a real native career fixture and let the game finish; start the transition observer before kickoff | Actual score persists once, pending clears, durable receipt is ACKed, actual EndGameMenuMovie and fresh results READY | e5dec4c saved actual 0–24; older results auto-travelled after about 60 seconds; mostly unattended score is not skill evidence |
| Saved-results retention | On current candidate, remain on natural results for more than 60 seconds; also test Options/Back over that interval | Countdown actually refreshes, same saved score, results remain/reacquire fresh READY; no automatic map travel | d95f4cc passed plain results beyond 80 seconds; intermediate OptionsEndGameMenuMovie failed retention. Fix/retest required |
| Saved-results Return | Click the actual results Return after the exact save acknowledgement | Fresh frontend READY + actual RootMenuMovie + visible authored hub; start another activity in same PID | Live UNVERIFIED; service Idle or leaving the match is not arrival |
| Forfeit | Active career → pause → red Forfeit Match → Back first; reopen and explicitly confirm | Cancel preserves fixture; confirm saves labelled forfeited loss once, advances schedule, then exact ACK and fresh hub; restart preserves it | d95f4cc source passed cancel, confirm, saved observed 0–1 loss, Schedule and next native fixture in same game. Restart/frozen checks remain open |
| Normal Steam | Close owned game/helpers normally, settle recovery journals, verify restoration, launch normal Steam route | No offline arguments, visible original root; close normally | Visually verified separately on 25 October; online play / anti-cheat certification remain unverified |

## Observe before intervening

The existing private `watch-game-transition.py` observes screen, service and
timer transitions. It takes screenshots only when the owned game is foreground;
it does not claim a failed capture succeeded. `observe-live.py` is a shorter
read-only snapshot/wait helper. Inspect their current CLI help before use. Keep
long observers asynchronous so the operator can react when results arrive and
keep the user informed. An observer log alone is not a user notification; active
notification integration is separate. The private `wait-live-milestone.py` now
checks explicit candidate/activity/fixture and fresh matching snapshots, emits
one compact semantic signal, and bounds each wait to 55 seconds. Main can forward
actionable events while continuing independent work. It has observed Playing,
returned hub and natural results on d95f4cc; it does not replace foreground
screenshots or independent disk-save verification. Treat its normal timeout as
pending, not success. Propagate the Python exit code explicitly in PowerShell,
or parse the emitted event; a shell's generic nonzero result is not the event.

Use `owned-game.ps1` only with the current ownership record and a fresh visible
screen. Use the existing `check-delayed-cleanup.py` only for its disposable
practice scenario: it suspends the exact owned leaf worker briefly and resumes
it in `finally`. Verify that safeguard before running it. Never suspend the
game, an unrelated worker, or a career fixture to manufacture an outcome.

## Known traps

- SDK `OnOpenPauseMenu` did not reopen the pause screen in the bounded live test.
  Do not infer behavior from the method name. Ordinary Escape recovered the
  preserved Return intent in earlier builds; recheck current state before it.
- SDK `IsFinished()` stayed false during actual EndGame. The implementation's
  match-ended flag, saved-result proof and timer observations are separate facts.
- An old READY, historical Return arrival or old receipt can belong to a different
  activity. Match nonce, process, session, fixture, generation and freshness.
- Inputs blocked by focus or screen saver are not executed test steps. Stop and
  recover focus before continuing; do not screenshot another application.
- The current HUD uses logical game actions. USB DualShock 4 physical buttons,
  D-pad/right stick and community plugin 707 still need their own real tests.
- A private short-match mutator has only been researched. It is not an available
  tested shortcut and cannot replace normal frozen-release acceptance.
- Results Game options first opened `OptionsEndGameMenuMovie` with Change Preset
  and Settings on d95f4cc. Do not assume it directly opens `OptionsMenuMovie`.
  This intermediate route exposed a retention failure; verify both submenu and
  Settings/Back beyond the former expiry after the fix.
