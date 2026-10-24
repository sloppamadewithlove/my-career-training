# Historical Windows handoff

For the current candidate and repair, start at [PROJECT_STATUS.md](PROJECT_STATUS.md)
and [BUILDING.md](BUILDING.md). The notes below describe earlier checkpoints.

Installing Codex CLI on the Windows PC does not automatically connect that PC
to this Mac session. A local Codex session can perform the checks below. No remote
access is configured by this project.

For supported remote desktop access, use the current ChatGPT desktop app on the
Windows PC: **Settings → Connections → Control this PC → Set up/Add**. Pair the
device that should control it; on another supported desktop app, use **Control
other devices**. Keep the Windows PC awake and unlocked for Computer Use. This
requires setup on the Windows host; signing into the CLI alone is insufficient.
See [OpenAI's remote connections guide](https://learn.chatgpt.com/docs/remote-connections).
The CLI also exposes experimental remote-control commands, but this project
does not start a listener, expose ports or configure access automatically.

This handoff is **read-only preparation**. The native-menu trial is unfinished,
and the public installer hold still applies. Do not install or run the current
development mod automatically. A file comparison cannot prove that menus, bots,
Steam online play or Easy Anti-Cheat work.

## Prepare a receipt now

In a Windows Codex CLI session, give Codex this instruction:

> Work with https://github.com/sloppamadewithlove/my-career-training. Clone it
> outside my Steam/game folders, or update an existing clean checkout without
> discarding local changes. Read AGENTS.md and docs/WINDOWS_CODEX_HANDOFF.md.
> Identify my existing Steam Rocket League installation and confirm that its
> Binaries/Win64/RocketLeague.exe exists. Record the repo commit. Do not install,
> launch, stop or alter Rocket League, BakkesMod, Steam, anti-cheat or the mod.
> Use the read-only integrity helper to create a baseline outside the install.
> Report errors and the receipt path. Do not claim this proves the mod works.

Steam's **Manage → Browse local files** shows the game folder. Finish game updates
and close Rocket League before collecting a baseline. Avoid running an update,
Steam file verification or another installer during collection. Hashing the full
installation may take several minutes and reads a large amount of disk data.
Python 3.12 is sufficient; no project packages need to be installed.

For example, from the repository in PowerShell, replacing the game path with
the actual installation:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\MyCareerReceipts"
py -3.12 scripts/verify_game_files.py baseline --game-dir "D:\SteamLibrary\steamapps\common\rocketleague" --output "$env:USERPROFILE\Documents\MyCareerReceipts\before.json"
```

The helper records each ordinary file's relative path, size and SHA-256. It never
writes inside the game folder, follows links/reparse points, starts processes or
uses the network. An unreadable file, a link, a detected change during inspection
or the 50,000-entry limit makes the receipt incomplete. Existing receipt files
are never overwritten. A baseline is the installed bytes at that time; it is
not an official publisher checksum list or proof that those bytes were healthy.

## After an explicitly approved Windows trial

Only after a particular development build has been authorized for testing:

1. Record the exact Git commit, downloaded artifact hash, plugin DLL hash, game
   executable hash, game build and BakkesMod version. PowerShell's
   `Get-FileHash -Algorithm SHA256 -LiteralPath "<actual file path>"` can record
   individual artifact hashes without loading them.
2. Follow [the native trial checks](NATIVE_DIALOG_TRIAL.md). Observe the real game:
   native dialog appearance, controller focus, navigation, practice, match start,
   closing/reopening and return to the frontend. Capture results and errors.
   Current trial dialogs do not replace or lock the stock main menu.
3. Close the offline session normally. Confirm mod session cleanup. Collect an
   after receipt with the same helper:

   ```powershell
   py -3.12 scripts/verify_game_files.py compare --game-dir "D:\SteamLibrary\steamapps\common\rocketleague" --baseline "$env:USERPROFILE\Documents\MyCareerReceipts\before.json" --output "$env:USERPROFILE\Documents\MyCareerReceipts\after.json"
   ```

4. Inspect changed, missing, added and error lists. Exit code 0 means a complete
   baseline or an unchanged comparison; exit code 2 means differences or inability
   to verify. An incomplete baseline cannot be used for a clean comparison.
   Game updates between receipts legitimately change hashes; record them rather
   than attributing all differences to the mod. Do not automatically restore or
   delete files based on a report.
5. Launch normally from Steam, separately from the mod shortcut, and personally
   verify normal menus, settings, saves and EAC-enabled online play. Record the
   actual outcome. The integrity helper does not inspect account data, cloud
   saves, Steam launch options or files outside the chosen installation.

There is no single instant snapshot of a live filesystem. Metadata checks detect
many changes during hashing, but a clean receipt cannot prove no transient change
occurred between reads. Keep the game and updates closed for useful evidence.
