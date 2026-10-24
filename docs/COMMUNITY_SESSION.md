# Community development trial

`community_session.py` stages one reviewed community DLL into a trusted BakkesMod `plugins` folder for an explicit development trial. After every Rocket League process has closed, recovery can delete that same file when its bytes are unchanged.

`production_profiles()` is empty. `production_eligible()` stays false for every object, including a complete development profile. No production profile is defined. The private community cache continues to store the original ZIP and its receipt with `can_activate` false. Staging does not rewrite that receipt.

A trial writes two local records:

- `<app state>/community-session/active.json`, the private journal
- `plugins/MCTCommunity_<site id>_<nonce without dashes>.dll`, created only when that exact name is absent

The DLL name comes from the site id and the trial nonce. `plugins.cfg`, cvars, and every other file stay as they were. The module does not autoload a plugin, load a binary, or read the installed game. Returned console text is fixed for the generated stem. It is not executed, and it is not a `Backend.dispatch` action.

## Profile, runtime, and scope

`ReviewedPluginProfile` is immutable and has to be built in developer code. A filesystem path or URL is refused. These fields are all required:

| Field | Role |
| --- | --- |
| `site_id` | BakkesPlugins numeric page id |
| `api_version` | Integer version from the metadata service, not a page label such as `1.0.3` |
| `archive_sha256` | SHA-256 of the cached ZIP |
| `member` | Exact canonical DLL path inside that ZIP |
| `member_sha256` | SHA-256 of that DLL member |
| `plugin_name` | Expected upstream name, recorded and not used as the console stem |
| `source_url`, `source_commit`, `license` | Provenance record |
| `download_url` | Cache identity URL from the validated receipt |
| `game_exe_sha256`, `core_identity`, `build_identity` | Expected runtime identity |

`RuntimeIdentity` must match the profile's game, core, and build strings. The host supplies those strings. This module does not open the game executable.

`OwnedTrialScope` carries the canonical nonce, owned PID, start identity, and the fresh, offline, Steam, and frontend flags. `development_trial` must be true. The host's `verify_scope` callback is the live lease. It runs before the journal is written, again immediately before the DLL is created, and again after the written bytes are confirmed. A lost lease leaves the journal in place. When the DLL was written and any Rocket League process is still running, the file stays until recovery is allowed to run. `verify_scope` and `game_running` are process checks. They are not atomic with an external game launch.

## Cache and the single member

Staging lists the cache with `community_plugins.cached_plugins` and reads the ZIP bytes again. The archive hash, site id, API version, and download URL have to match that receipt. A receipt is not accepted without those bytes.

The ZIP is checked with the cache module's name, mode, duplicate, and size rules. Integrity streaming discards member bytes. The only bytes kept are the one reviewed DLL. License and readme files may be present beside it. A second DLL, a data directory, a config file, or any other runtime resource is refused, because this pilot has no dependency installer. The member hash has to match.

The member also has to look like a Windows PE32+ AMD64 DLL in a bounded header read. That shape check is not ABI, behavior, or safety proof, and the file is not loaded. A source URL and license are provenance, not compatibility proof. The BakkesPlugins verified flag remains a site review state.

## Journal and recovery

The journal is an exclusive private receipt and trusted local state. Recovery checks its shape and its binding to this BakkesMod root, site id, and nonce. It does not authenticate the journal against another process running as the same user. The DLL is created with an exclusive create, so an existing file is left unchanged. Symlinks, junctions, other reparse points, device names, `..`, UNC paths, and path aliases are refused. The journal directory and the BakkesMod directory have to be separate trees.

The intent journal is published from an exclusive scratch file in that same directory. The scratch is flushed, then renamed to `active.json`. On Windows that rename leaves an existing destination in place, and the published file has one link, so a crash after publication can still drop the journal. A scratch that never got renamed is not the journal. Scratch cleanup deletes a file only on the Windows handle that confirmed the expected file id, while writers and deleters are denied. A replacement at that path is left. That cleanup does not authorize plugin deletion, and other operating systems do not get this delete.

`state: prepared` records intent only. It has `owned_file_id: null` and does not authorize deletion. If the generated path already has a file, including one with the same bytes, `recover` reports `ambiguous` and leaves that file and the journal for manual review. If the path is empty, `recover` closes the intent journal and deletes nothing else.

`state: staged` is written only after the exclusive create returns a Windows file id from that handle. The id is the volume serial and file index (`volume:index`, lowercase hex). Recovery deletes the DLL only when the recomputed path still has that same id and the bytes still hash to `member_sha256`. A replacement file with the same bytes and a new id is `retained`. A hash change on the original id is `retained`. The path stored in the journal is checked against the recomputed path and is never the path that is opened.

On Windows the delete opens the recomputed path for read and delete, shares only read, and checks the id and hash on that handle. `game_running` is checked again immediately before the handle is marked for deletion. An unknown game-state result leaves the file and the journal. This handle lock is the Windows implementation. It is not claimed for any other operating system.

A crash after the file is created and before the staged id is durable leaves a prepared journal. Recovery keeps the file for review. The same rule applies when exclusive create loses a race or the pre-create check finds a file that appeared after the intent was journaled: that file is not cleaned up. A scratch this operation did not create, or whose file id no longer matches, is left in place.

`recover` returns `deferred` while any Rocket League process is running and does not change files in that case. Shared folders, config files, and neighboring plugins stay. Recovery does not recurse and does not restore cvars or `plugins.cfg`.

## Speedflip Trainer research record

Speedflip Trainer is a source candidate, not an approved profile. The official download was inspected without extracting, installing, or loading its DLL. Its exact archive, API version, member, and hashes are recorded in [the artifact receipt](validation/community-plugin-286-2026-10-24.json). Current game ABI and runtime behavior remain unverified. No profile constant for this plugin is included.

| Record | Value |
| --- | --- |
| Site id | 286 |
| Page version label | 1.0.3. This is not the integer API version. |
| Author | tyni |
| Source | https://github.com/tynidev/SpeedFlipTrainer |
| Pinned commit | `8a4a94fc120db4919c3155052dbd7099ef834ba7` |
| License | GPL-3.0 |
| API version | 3 |
| Member | `plugins/SpeedFlipTrainer.dll`, 691200 bytes, PE32+ AMD64 |
| Archive and member SHA-256 | See the artifact receipt |
| Current game ABI and runtime behavior | Unverified |

Source reading, recorded only: the project defaults to manual saving rather than autoload, creates `data/speedflip` directories, and registers `sf_*` cvars with the save-to-config flag. That flag alone does not prove when a config file is written. The outer `LoadRound` and `Destroyed` hooks do not show an explicit unload. Those notes are not compatibility evidence. A real profile would have to name the exact artifact and account for those side effects before any trial could use it.

## What root still integrates

The shell supplies the trusted BakkesMod root, the owned-process `verify_scope` callback, and the any-Rocket-League `game_running` callback. It passes a complete profile from developer code. It keeps the returned commands out of the app bridge, leaves `plugins.cfg` alone, and calls `recover` after the game has closed. A staged DLL is a development file with a journal, not an activation.
