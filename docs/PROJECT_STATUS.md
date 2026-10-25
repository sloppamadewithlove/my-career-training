# Current project status

Updated 24 October 2026. Start here; older research and validation notes describe
individual checkpoints, not the current player's complete experience.

## Download and source

The published `native-candidate-2026-10-24` ZIP from `2fed6cd` failed player
testing. The [correct website](https://my-career-training.vercel.app/) now shows
the repair status instead of offering that broken ZIP. The replacement is one
Windows test Setup executable, one player shortcut, and a private windowless
worker. Its exact frozen build must pass live acceptance before publication.

GitHub is canonical. The repair branch is `fix/windows-startup-and-download`;
[PR #7](https://github.com/sloppamadewithlove/my-career-training/pull/7) tracks it.
Match-menu integration is being assembled separately before merging into that
branch. Local integration commits are not published player releases.

## Verified observations

- The startup crash came from querying the original menu's file size while
  opening a larger private replacement. Exact-path attributes now describe
  the same private file as the open. Controlled game tests reached the menu
  without changing the installed package.
- The authored menu needed the original root initializer preserved and a
  wrapper around its renamed class. This Scaleform runtime reads the decoded
  Windows view path; its `file:///` loader and native JSON parser did not work.
  The menu now uses that path and a pinned BSD-licensed AS3 JSON codec.
- Live source `5535a2d` displayed all seven My Career routes in a Unicode
  profile. Native unfinished-fixture recovery preserved completed results and
  requeued the fixture. Career Rules changed the copied test career to 1v1.
  Starting the match then failed because no game data reached the worker.
- A controlled comparison isolated that connection failure: both `-noeac`
  and `-rlbot` prevented the game connecting. RLBot's official Steam arguments
  (`-rlbot`, fixed local controller endpoint, rate 240, `-nomovie`) connected
  before the start screen was dismissed. The official SDK opened a one-human
  practice field and received live packets. This proves the diagnostic
  connection, not the complete My Career workflow. See the pinned
  [official launcher](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/Steam.Windows.cs).
- The [Windows build for `5535a2d`](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40142680788)
  passed its installer pipeline. Install/reinstall/uninstall checks use a
  disposable Windows runner and preserve its test career. That artifact
  predates the connection and pause/results repairs.

## Current integration

The connection fix removes conflicting `-noeac` from owned RLBot launches and
updates the Python, native-launcher and plugin checks. Normal Steam launch and
generic BakkesMod-only guidance remain separate. Fixed endpoint/rate, process
identity, executable hashes and original-file protections remain enforced.

Main, pause and results are separate movies. New pause/results classes retain
stock pause/input cleanup and expose career actions. Both authored bytecodes
were independently rebuilt to identical bytes, containing only project classes
and the public JSON codec. Private game SDKs and movies are not distributed.

The bounded match-package writer preserves other exports and appends the
selected movie's new serial. Tests checked unchanged, grown and subsequently
shortened movies in both actual packages. Three-package composition/preparation
also passed without changing installed files. These are format/code checks;
live loading and native navigation still require acceptance.

Return and Retry bind to the current activity. Final score receipts must save
before the activity clears. Results offers Retry saving after a failure;
automatic receipt recovery also unlocks current results. Final Return navigation
is separate: shutting down RLBot alone does not open the game's frontend.

Actual GPT-6 Luna with max reasoning runs through Codex CLI for research and
independent checks. Actual Grok 4.7 High runs through Cursor CLI for difficult
implementation and review. Coordinators also implement alongside those reviews.
Agent participation is not gameplay evidence.

## Remaining live acceptance

1. Build/freeze one clean integrated revision with matching runtime receipts.
2. Open the player executable: one game, no worker console, readable menus.
3. Complete a real 1v1 career fixture, save it once, return home and start the
   next activity without a second game process.
4. Test practice/retry, native pause/options/resume, unfinished-match
   confirmation, results saving/return, and keyboard/controller controls.
   Replacement menus must not expose online routes.
5. Restart and verify progress. Check installed files, player saves, temporary
   plugin restoration and the normal Steam launch boundary.
6. Publish only the exact tested Setup, hashes, required sources/notices and a
   sanitized receipt; update the existing website to that artifact.

Target: Steam `25914621`, Rocket League `261013.63066.530866`, BakkesMod `229`.
Unknown builds are refused. Epic has no separate acceptance yet. Full cosmetic
coverage, expert demonstrations, no-idle-kick behavior and arbitrary community
plugins remain open. Necto/Nexto support up to 3v3; 4v4 uses Ground Specialists.
No current bot rank certification is claimed.

Use [BUILDING.md](BUILDING.md), [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md),
[NATIVE_ACCEPTANCE_SESSION.md](NATIVE_ACCEPTANCE_SESSION.md) and
[REPOSITORY_PRIVACY.md](REPOSITORY_PRIVACY.md). Source tests, private diagnostics
and historical installer receipts are distinct from end-to-end game acceptance.
