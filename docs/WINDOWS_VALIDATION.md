# Windows identification baseline

This is a read-only identification report for a later native-menu experiment. It does not prove native menus, gameplay, Easy Anti-Cheat, or that the Steam install is unchanged. It hashes only `Binaries/Win64/RocketLeague.exe`. It does not hash the rest of the install.

The script does not launch, stop, install, or modify Steam, Rocket League, or BakkesMod. It does not write registry keys, config files, or anything inside a detected Steam, game, or BakkesMod directory. Exit code 0 means a new JSON file was written, including when fields are unknown. It does not mean those checks passed. Exit code 2 means the report was not written.

Loaded BakkesMod DLL and plugin versions are always `unknown`. An injector file version is metadata from `BakkesMod.exe`, not evidence that a DLL is loaded.

## What the JSON records

- Steam app `252950` build id, when `appmanifest_252950.acf` can be read. The install folder name is used only to find the game and is not copied into the report.
- Whether the selected game folder matches the uniquely discovered Steam install (`matched`, `mismatched`, or `unverified`). An executable gets an `associated_steam_build_id` only with a matched folder and an unambiguous, fully read manifest build ID.
- Size and SHA-256 of `RocketLeague.exe`, plus its Windows file version when that API is available.
- Filenames and sizes of candidate menu packages found in the top level of `TAGame/CookedPCConsole` and `Engine/CookedPCConsole`. Package bytes are not read.
- BakkesMod `version.txt` when it is a short version token, plus file-version metadata for `BakkesMod.exe` and `bakkesmod.dll` when those files are found at bounded locations.
- Whether a process image named `RocketLeague.exe` is running: `true`, `false`, or `"unknown"`. No PID, command line, account, or path.
- `unknowns` and `errors` for anything that was not actually read. Absent, inaccessible, and malformed results stay distinct.

The report omits usernames, Steam account IDs, `LastOwner`, full paths, and raw exception text. An existing output file is never overwritten. Symlinks and reparse points are not followed.

## Paste this to Windows Codex

> Work with https://github.com/sloppamadewithlove/my-career-training on current `main`. Clone it into a dedicated folder outside Steam, Rocket League, and BakkesMod, or fetch current main into a clean existing checkout. Preserve existing work; do not reset or clean it. Read `AGENTS.md`, `docs/INTEGRATION_CONTRACT.md`, and `docs/WINDOWS_VALIDATION.md`. Run `scripts/windows_baseline.py` with Python 3.12, writing a new JSON report outside the game folders. Do not install project packages, launch or stop software, change game files or registry keys, or upload game assets. Review the report for personal paths, usernames, account IDs and credentials. Commit only the sanitized report as `docs/validation/windows-baseline.json` on a new `validation/windows-baseline` branch and push that branch to origin. Do not overwrite an existing branch/report; if one exists, report its URL and stop. Reply with the source commit, report commit, branch URL, script exit code, and unknown/error fields. This identifies the installed game; it does not verify custom menus, gameplay, EAC, or preservation. Do not start a runtime menu test yet.

```powershell
git clone https://github.com/sloppamadewithlove/my-career-training.git
Set-Location my-career-training
git rev-parse HEAD
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\MyCareerReceipts"
py -3.12 scripts/windows_baseline.py --output "$env:USERPROFILE\Documents\MyCareerReceipts\windows-baseline.json"
```

If `py -3.12` is unavailable, use the installed Python 3.12 executable the same way. Do not run `uv sync` or install the project for this command. The script uses the standard library only.

An existing checkout, without discarding local work:

```powershell
git status
git fetch origin main
git switch --detach origin/main
git rev-parse HEAD
```

Optional, only when that install folder is already known. Replace the placeholder. Do not send the real folder path back if it contains an account name.

```powershell
py -3.12 scripts/windows_baseline.py --output "$env:USERPROFILE\Documents\MyCareerReceipts\windows-baseline.json" --game-root "D:\SteamLibrary\steamapps\common\rocketleague"
```

`--game-root` is the folder that contains `Binaries`, not the executable file. `--steam-root` is optional and is the folder that contains `steamapps`.

Review the local JSON before sharing it. Do not upload Rocket League files with it. Unknown process status stays `"unknown"` and is not the same as not running. A later menu, gameplay, or preservation run is a different test; this command does not start it. See `docs/NATIVE_MENU_IMPLEMENTATION_PLAN.md` for those experiments and `docs/WINDOWS_CODEX_HANDOFF.md` for the separate full-install hash helper.
