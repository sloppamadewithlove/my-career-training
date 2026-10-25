# Paused session handoff — 24 October 2026

The user explicitly paused for a new session. Completed work is committed in
`fix/windows-startup-and-download`; draft [PR #7](https://github.com/sloppamadewithlove/my-career-training/pull/7)
tracks it. Continue the repair when the user supplies this handoff in the next
session. Do not present this checkpoint as a finished player release.

## Mission and working agreement

Build an easy-to-install Windows offline career and training mod inside the
player's existing Rocket League. The normal experience should be one Setup,
one shortcut, and the actual game's menu style with buttons mapped to My Career.
The automatic worker belongs in a private support folder and must not open a
console. Ordinary players should not need Python or developer tools.

Career combines a human captain with four bot squad members, 1v1–4v4 formats,
lineup changes before every fixture, persistent squads and clubs, seasons,
standings, results, progression, and optional mechanics practice. Career menus
must not offer Casual, Competitive, Tournaments, or store routes. The original
Steam game must remain available separately. Do not replace installed game
packages, redistribute proprietary game assets, or bypass online anti-cheat.

Training, useful coaching/ghosts/controller visualization, Garage, Workshop and
Community remain part of the longer product specification. Do not claim expert
demonstrations, all cosmetics, arbitrary plugin gameplay, Epic compatibility,
certified bot ranks, or complete controller/online-boundary acceptance without
evidence. Read `BUILD_SPEC.md` for the complete mission and `PROJECT_STATUS.md`
for current evidence.

The user authorizes temporary Windows worktrees, builds, app launches and tests,
and wants changes committed to the canonical GitHub repository. Avoid unrelated
permanent PC installations. Preserve the real career and use copied profiles
for tests. Explain progress in simple language. Ask when a material fact is
missing; do not repeatedly request permission for already authorized work.

## What was repaired

- Replaced the intended ZIP player workflow with one Windows test Setup, one
  player shortcut and a private windowless worker. The old public ZIP remains
  failed historical testing material.
- Repaired private package file-size handling that caused startup crashes;
  preserved the stock menu initializer and authored wrapper; used the decoded
  Windows view path and a pinned public AS3 JSON codec supported by this game.
- Integrated separate authored main, pause and results movies with real career
  actions, session-bound confirmations and durable result-save checks.
- Removed conflicting `-noeac` from owned RLBot launches. Use exactly `-rlbot`,
  the fixed local controller endpoint, packet rate 240, and `-nomovie`.
- Fixed a Windows NumPy import deadlock by initializing it in the worker before
  stdin is read. Actual redirected Python/Pythonw tests reproduced the old hang;
  the repaired process loaded the actual Necto controller in about four seconds.
- Fixed native command-line formatting: quote the validated executable path,
  but do not individually quote the four fixed whitespace-free options.
  Controlled game comparisons isolated the old formatting as a connection
  failure. The exact canonical launch guard remains enforced.
- Added bounded startup cancellation, rejection of late startup messages and
  retained ownership during worker/core cleanup and durable result writes.
- Improved frontend text bounds/line wrapping and separated active fixtures
  from unfinished-fixture recovery.
- Organized documentation, privacy guidance, reproducible build recipes,
  exact artifact receipts and corresponding source archives.

The canonical site is [my-career-training.vercel.app](https://my-career-training.vercel.app/).
Its repaired production page shows the hold instead of offering the broken ZIP.
Do not recreate the site or repeat the expired Vercel access request from earlier
in the session. The existing project connection worked when the optional team
parameter was omitted.

## Real game evidence and the remaining blocker

Integrated source `68448b7` completed an actual offline 1v1 in a copied Unicode
profile. Necto played and the actual 0–54 result saved once with game provenance.
The pending fixture cleared and the durable outbox receipt was acknowledged.
This was mostly unattended, not a player-skill assessment. Starting this run
used a private bridge test command; do not call it a native Play-button test.

Actual Escape opened the custom pause menu with Resume, Game options and Return
to My Career. Options/Back and Resume worked. Return showed the unfinished-match
confirmation; canceling it preserved the match. The authored results screen
became ready and displayed the saved-result state.

The actual results Return click exposed the current blocker. Service state
correctly became Idle/hub with the worker stopped. The host's fixed SDK
`disconnect` left the match at `StartMenuMovie`, not the authored `RootMenuMovie`.
The old fullscreen ImGui interface then covered the title screen while native
READY was false. Leaving the match or reporting Idle is not successful Return.

Completed fix `3cdaad0` prevents native builds from drawing that legacy menu,
capturing its input, enabling its navigation, or using its old menu shortcuts
during READY gaps. The nonblocking gameplay training HUD remains. Ordinary
non-native builds retain their old behavior. Focused C++ tests passed, including
an independent Luna rerun; Grok reviewed the diff. Source/native CI checks for
`2a3f960` passed. This fix has not yet had its combined live test.

The correct Return destination still needs implementation. An unfinished
snapshot is preserved separately on `fix/native-return-shell-ready`:

- `dd1c176`: partial gate/protocol headers, based on `68448b7`.
- `5c643f1`: explicit WIP documentation.
- Read [RETURN_NAVIGATION_WIP.md](https://github.com/sloppamadewithlove/my-career-training/blob/fix/native-return-shell-ready/docs/RETURN_NAVIGATION_WIP.md).
- **Do not merge, build or deploy that branch as a candidate.** Its gate API
  changed, but host callers, ActionScript, compiled assets/pins and tests have
  not been converted. Whitespace checking and CMake configuration are not tests.

## Agreed Return design for the next builder

Use the verified typed AS3 `Shell.ExitToMainMenu` after the exact durable service
acknowledgement. Preserve the stock pause `m_bExitingMatch` flag. Keep native
intent bound to nonce, activity, fixture and a one-shot token. Fixed navigation
authorization must change the view signature/generation; same-generation polling
otherwise refreshes only timestamps. Validate native consumption, distinguish
attempt from arrival, and block new activities while Return is pending.

Complete only after fresh authored frontend READY and the fresh SDK menu stack
reports `RootMenuMovie` in the same owned offline process. A title or loading
screen must not clear intent. Preserve intent when a pause movie unloads while
the worker drains. Revoke it on changed activity, nonce, ownership or unsafe
online/replay/build scope.

The pinned SDK declares `OnOpenPauseMenu`; its actual opening behavior has not
been established. One bounded call on a fresh controller after the exact ACK
has been authorized for live testing. Require observed pause plus READY before
using it; keep intent and a diagnostic if it has no effect. Never loop blindly.
Stock screen removal unloads the movie, so retaining its AS3 timer is unreliable.
Do not invent engine ABIs, offsets, console routes or calls to stale objects.

## Agents and division of work

The main agent owns architecture, integration, source review, release decisions,
privacy checks and all live PC input. Delegate separate file scopes to avoid
collisions. Research and testing agents may inspect evidence, but only one
controller should click or send keys to the live game.

The user's requested research/exploration/test model is actual **GPT-6 Luna with
max reasoning through Codex CLI**. Difficult implementation/advice/review uses
actual **Grok 4.7 High through Cursor CLI** alongside the main/coordinating agent.
Verify the model in CLI output; do not silently substitute or claim that a
coordinator's name proves the requested model ran.

This session used source-exploration, dependency/artifact-testing, menu-repair
and return-navigation coordinators. Actual requested models were used. The
final Return architecture run reported `Grok 4.7 256K High`; the code-writing
run was stopped before edits. The two partial WIP headers were written by its
coordinator alongside that architecture advice. All agent subprocesses were
stopped for the user-requested pause. Raw prompts/logs remain private.

## Test method and exact artifacts

Keep source contracts, compiled native tests, frozen smoke, installer lifecycle
and real gameplay as separate evidence. Run relevant regressions after each
change; avoid rerunning unrelated suites without a reason.

Windows tests use private copied career profiles, including Unicode paths, and
record process PID plus creation time. Main-agent screenshots/inputs target only
the verified game window. Foreground checks prevent typing into another app.
Windows screen saver repeatedly prevented control; an independent query found
`Screen-saver` versus `Default` desktops in the same Windows session. The user
woke the PC and actual native UI tests then passed. Do not claim a blocked input
was a successful game action.

Private console-Pause and initial clock-observer probes were inconclusive helper
tests, not product failures. Actual Escape and the visible countdown resolved
those questions. Total packet elapsed time includes goal replay/kickoff time;
it is not the five-minute countdown. Normal replay-skip clicks did not alter or
fabricate the score.

The [exact `68448b7` CI run](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40153114788)
passed source/native checks, frozen smoke and disposable-runner install/reinstall/
old-worker cleanup/uninstall/save-preservation tests. Luna checked all 4,470
downloaded bundle files against that run's smoke inventory and verified nine
source archives. Setup size: 178,305,803 bytes. SHA-256:
`bf8c047f2bc6d15144cd83fe101ff613cfff3c62d61329e6076d64a328844bf4`.
This exact package contains the observed Return defect and has an explicit
acceptance hold. It was not installed or launched on the player's PC.

The [later `2a3f960` CI run](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40155909420)
had passed source/native staging and was building its installer at pause. Check
its final state on resume; do not infer that unfinished steps passed. No artifacts
from that run were downloaded. Handoff-only commits skip CI to avoid starting
new builds during the requested pause.

The source game/app exited, the temporary plugin journal was restored, and the
owned injector closed. Original My Career files, game configuration, BakkesMod
configuration/plugin and checked installed EXE/main-package hashes matched.
Rocket League itself changed its own ordinary save files during normal use;
do not claim every game/cloud save byte was unchanged or restore those blindly.
A subsequent normal Steam launch produced a game without offline arguments,
but the user paused before original-menu/anti-cheat behavior was visually tested.

## Resume in this order

1. Inspect the repair branch, this handoff, `PROJECT_STATUS.md`, `AGENTS.md`,
   `INTEGRATION_CONTRACT.md`, `BUILDING.md` and `REPOSITORY_PRIVACY.md`. Recheck
   local/remote status and running processes; do not assume old PIDs are current.
2. Finish and independently review the Return implementation in isolation.
   Integrate it with `3cdaad0`; retain the WIP warning until it is actually done.
3. Rebuild authored bytecodes/pins and one coherent native candidate. Run focused
   gate/protocol/lifecycle/stale-scope tests and required complete build checks.
4. Use a private copied saved career. Verify native frontend, Play, practice,
   retry, pause/options/resume, unfinished Return, results Return and the
   resume-during-cleanup race. Require visible hub plus fresh READY, then start
   another activity without another game process. Check keyboard/controller
   paths and absence of actionable online routes.
5. Freeze/produce one clean exact revision. Run its actual installer input only
   after complete same-run inventory verification, then prove a full real
   fixture/save/Return/restart cycle. Do not replace the registered PC install
   just for developer testing; installer lifecycle belongs on disposable CI.
6. Recheck restoration and complete normal Steam/menu behavior. Keep untested
   features explicitly open. Preserve private evidence and publish only sanitized
   receipts, required sources/notices and artifact hashes.
7. Only after acceptance publish the exact tested Setup and update the existing
   Vercel site to it. No replacement release was published in this paused session.

Secrets, environment files, credentials, account identifiers, private paths,
raw game/agent logs, player saves, extracted movies and game packages must never
enter GitHub or release attachments. Use generic contributor commit identity.
Local compiler metadata and release contents require review too.
