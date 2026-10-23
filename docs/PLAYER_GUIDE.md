# Playing the 0.1.0 testing prerelease

This is an early Windows test build. Its actual Rocket League connection has not
yet been verified on Steam or Epic. Expert teaching demonstrations are missing,
and the bots have no verified rank. Use the steps below to test your own game
and keep the evidence separate from the application's local checks.

## Install

1. Open [GitHub Releases](https://github.com/sloppamadewithlove/my-career-training/releases).
   Download `MyCareerTraining-0.1.0-windows-x64-setup.exe` **if that actual asset is
   attached**. If only source archives are listed, a Windows download is not ready.
2. Run the installer. It installs for your Windows user, offers a desktop
   shortcut, and adds a Start menu entry. The build is unsigned unless the
   release explicitly documents a verified signature. Do not disable Windows
   protection to run it; use only a release you choose to trust.
3. Alternatively, download `MyCareerTraining-0.1.0-windows-x64-portable.zip`,
   extract the **whole folder**, and open `MyCareerTraining.exe`. Keep its worker
   and `_internal` folder beside it. Running from inside the ZIP will not work.

Use Windows x64 with your current Rocket League install and signed-in Steam or
Epic launcher. The game is a separate prerequisite. Python, Git, Cursor and a
terminal are not needed for the packaged application. This is not a Mac game
build. Both package formats keep player data outside the program folder.

`SHA256SUMS.txt` identifies the release files. The third-party source ZIP is for
licenses and rebuilding; it is not another application to install.

## First launch

1. Close any already-running Rocket League or RLBot session. The app must launch
   its own offline session so it can identify the game safely.
2. Open My Career Training. In **Settings**, select **Steam** or **Epic Games**.
   Steam is the first user's default; choose Epic for an Epic installation.
3. Check **Game location**. Use your Rocket League installation folder if
   detection did not find it. Select **Check setup**, then **Use selected launcher**.
4. You can adjust text size, reduced motion and the input display here too.
   The display does not guess your custom boost or air-roll binding. Your actual
   gameplay controls remain configured in Rocket League.

Career and practice sessions use Rocket League's supported EAC-off environment.
They are for offline matches and training. Keep your launcher signed in normally;
the app does not collect a platform password or require a new game account.
An “Opening” or “Starting” message is not proof of a successful game connection.
If the game does not open, use **Run diagnostics** and keep the error message.

## Start a career and play

1. Choose **New Career**, name your club, choose 1v1, 2v2, 3v3 or 4v4, and choose
   four recruits. Anchor, Shield, Relay and Comet are the default selection;
   Orbit is the other recruit. Your squad is always **you plus four bots**.
2. In **Career hub**, select **Play match**. You always drive your own car.
   Teammate counts are 0 in 1v1, 1 in 2v2, 2 in 3v3 and 3 in 4v4.
3. Play the normal five-minute match and any overtime. The app is designed to
   capture the real final score automatically. Wait for the saved result, then
   select **Continue**. Training is optional and never required before the next match.

Your season has four clubs and six ordinary rounds. The other clubs' fixtures
are clearly marked simulations. Wins earn three points; losses earn zero.
A still-tied title can add playoffs. **Start next season** keeps your squad,
progress and career history.

The bots use role-specific rules and level-dependent parameters. They are an
experimental baseline, not verified Diamond opponents or certified ranked bots.
The optional calibration exhibition earns no league points.

After a match, **Review this match** opens optional timestamped observations and
coaching suggestions when evidence is available. Score changes and touches are
separate from positioning heuristics; a suggestion never blocks your next match.

## Change your team

Between completed matches, open **Squad**, bench/start recruits, then select
**Save lineup**. Use **Recruitment** to swap the fifth recruit into your four-bot
roster. Their identity and earned progress remain in the career when rehired.
Pending or active fixtures lock these changes.

In **Season**, apply a new format or difficulty curve for future unstarted
rounds. Past results keep their original format and lineup. In **Garage**, save
local bot presets. Your human car uses your ordinary in-game garage; app rewards
and bot styles do not become items in your Steam/Epic inventory.

## Choose training help and retry

Open **Training**, choose a lesson, then **Start practice**. All eight lesson
groups are available without earning career levels or downloading maps. Where
shown, choose goal targets, angles, practice side, or the shorter flip-reset
approach before starting.

**Help settings** are saved separately for each lesson:

- Ghost demonstration.
- Step-by-step explanations.
- Action input display.
- Timing feedback.
- Automatic reset.
- Demonstration playback speed.

Use **Retry attempt** for a fresh setup, or **Stop session** to leave practice.
Use **Restore explanations** whenever you want skipped help back. Reduced
playback speed affects the demonstration; it does not make a normal-speed record.

No validated expert demonstration is bundled. Ghost playback needs a compatible
real personal recording or a permitted imported recording. **Replay your best
attempt** becomes useful after a successful compatible attempt exists. Your
personal best is your own recording, not an expert demonstration. Packet gaps
and uncertain contacts can limit the observations; a flip-reset flag by itself
is not proof of correct technique.

Community links credit their creators. **Choose local map** imports an eligible,
locally obtained Steam map file into the app's data folder; it does not certify
its contents or demonstrate successful game loading. Epic map import is
unavailable. Core career arenas and lessons do not need these downloads.

## Save and recover

Progress saves automatically. Use **Settings → Export backup…** before changing
computers or starting another career. **Import backup…** validates an exported
save before replacing the active career. Close the game session before importing.

Use **Open save folder** to find `%LOCALAPPDATA%\MyCareerTraining`. The folder
contains `career.json`, the last-good backup, recordings and diagnostic files.
An exported JSON preserves career/settings/attempt history and recording
metadata. To preserve the separate recording files too, keep a copy of the
`recordings` folder. Installation upgrades and uninstall preserve player data.

An interrupted match stays unfinished and earns no score, XP or rewards.
At the hub, **Abandon unfinished attempt** allows a restart from kickoff.
If a genuinely completed result is missing, a durable worker receipt may restore
it automatically. **Repair a missing result…** is a manual fallback: enter the
observed final score, including overtime, and explain how you confirmed it. It
is recorded as an unverified owner repair, not an automatically observed result.

On a save error, preserve the files and use the offered recovery/backup options.
Do not invent a result or repeatedly create new careers to clear an error.

## Play Online

Select **Play Online**. The app asks exactly:

> Are you sure you want to close this and play online?

**No**, Escape or closing the dialog leaves the session unchanged. **Yes** saves
completed progress, stops the career worker, requests closure of the owned game
window, waits for that actual game to exit, and asks your selected launcher to
open Rocket League normally.

If the game stays open, close that game window and select **Retry**. The app must
not start a second conflicting session. A launch request does not prove online
matchmaking is ready. If Steam asks which launch mode to use, choose the normal
EAC-enabled online option. Check any existing remembered Steam mode or Epic
`-noeac` option yourself if the normal launch stays offline; the app does not
silently rewrite unrelated launcher preferences.

## Report your first game test

Record the app version/commit, Windows version, Steam or Epic, installed game
version, selected format, observed connection/result, lesson and any error.
Keep Steam and Epic reports separate. Use **Run diagnostics → Open logs & reports**
for the app's report; inspect anything you share and never send launcher passwords,
authentication arguments or raw platform session logs.
