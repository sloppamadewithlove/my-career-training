# Native community trial controller

`native_community.py` is the developer-only controller for one reviewed
Speedflip Trainer build. It stages that build through the existing
`CommunitySession` and remembers whether the native host confirmed the load.
It does not download, launch Rocket League, load a DLL, run a console
command, or write BakkesMod config.

Normal production profiles stay empty. `production_eligible()` stays false.
`game_verified` and `can_activate` stay false. The pinned source commit and
the pinned DLL are separate artifacts; nothing here proves they are the same
bytes, and nothing here proves current game ABI or behavior. A plausible PE
header check inside `CommunitySession` remains a file-shape check only.

The official cache receipt is not rewritten. Its `can_activate` value stays
false. The private community journal may still contain the command text that
`CommunitySession` derives. That journal is not the movie view and is not a
bridge action. Do not publish it.

## Pinned profile

| Field | Value |
| --- | --- |
| Site id | `286` |
| API version | `3` |
| Member | `plugins/SpeedFlipTrainer.dll` |
| Archive SHA-256 | `b75ff28a86e4d54b0083b4ea09068a93b409bc18746b150b70030cab1d4f795d` |
| Member SHA-256 | `2203874a6921df54d06c1042a4281c7694d3e415b9c6b0618e33769db401ef11` |
| Source | `https://github.com/tynidev/SpeedFlipTrainer` |
| Commit | `8a4a94fc120db4919c3155052dbd7099ef834ba7` |
| License | `GPL-3.0` |
| Download identity | `https://cdn.bakkesplugins.com/uploads/4_3af4e39dddc7eb76e136f32052d7b3dfdaf152719074cef7cd01347c6a08a478.zip` |
| Game executable SHA-256 | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` |
| Core identity | `Bakkes229` |
| Build identity | `261013.63066.530866` |

`pinned_profile()` returns that `ReviewedPluginProfile`. The Python core
string `Bakkes229` is this controller's pin for BakkesMod core 229. A runtime
callback that returns `"229"` does not match.

Only site id 286 can be staged. `prepare` accepts no site id, path, URL,
hash, console text, or enable flag. The cached archive, receipt id, API
version, download URL, and member hash have to match the profile
`CommunitySession` is given. The player bridge must not call
`_use_synthetic_profile`. That helper exists so tests can point the same
checks at a synthetic archive. It still refuses every locked field other
than archive hash, member hash, and download URL.

## Signatures

```python
def pinned_profile() -> ReviewedPluginProfile: ...

def owned_start_identity(created: float) -> str: ...

class NativeCommunityController:
    def __init__(
        self,
        app_state: Path,
        bakkes_root: Path,
        cache_directory: Path,
        *,
        lease: Callable[[], OwnedTrialScope],
        runtime: Callable[[], RuntimeIdentity],
        heartbeat: Callable[[], dict],
        movie_ready: Callable[[], bool],
        game_running: Callable[[], bool],
        helper_pending: Callable[[], bool],
    ) -> None: ...

    def prepare(self) -> dict: ...
    def state(self) -> dict: ...
    def request(self) -> dict | None: ...
    def accept_status(self, ack: object) -> dict: ...
    def recover(self) -> dict: ...
```

`prepare`, `state`, `accept_status`, and `recover` all include this view:

| Key | Value |
| --- | --- |
| `enabled` | False until an exact ack is accepted |
| `status` | `idle`, `staged`, `loaded`, `refused`, `outstanding`, `deferred`, `retained`, `ambiguous`, or `recovered` |
| `message` | Short text. No command and no path |
| `site_id` | `286` |
| `production_eligible` | False |
| `game_verified` | False |
| `can_activate` | False |
| `outstanding` | Whether the community journal file is present |

`accept_status` adds `accepted` and `reason`. `reason` is `loaded`,
`duplicate`, `stale`, `foreign`, or `unknown`. `recover` adds `dll_removed`
and `journal_kept`.

`state()` is the only dictionary safe to show in the shell. `request()` is
for the trusted native host. It is present only after a successful stage and
before a terminal ack or recovery, and only while `enabled` is false.

| Request key | Meaning |
| --- | --- |
| `site_id` | `286` |
| `nonce` | Owned bridge nonce |
| `stem` | `MCTCommunity_286_` plus the nonce without dashes |
| `archive_sha256`, `member_sha256` | Pinned hashes for the profile that was staged |
| `pid`, `start_identity` | Owned process id and creation token |
| `game_exe_sha256`, `core_identity`, `build_identity` | Runtime pin that was live at stage time |

The host builds the filename as `stem + ".dll"`. It builds the console text
as `plugin load` plus the stem. Neither string is in `request()` or `state()`.

## Lease callbacks

Root wires these from `NativeOfflineSession` and the backend. Each call reads
the live session again. A boolean captured from QML is not a callback.

`lease()` returns an `OwnedTrialScope`:

- `pid` and creation time come from the owned game identity.
- `start_identity` is `owned_start_identity(created)`, three digits after the
  decimal. The ack has to use that same string.
- `nonce` is the fresh `FileBridge` session nonce for this launch.
- `fresh`, `offline`, `steam`, `frontend`, and `development_trial` are all
  true. Steam comes from the owned Steam launch. Offline and frontend come
  from that same owned session, not from a checkbox.

`runtime()` returns a `RuntimeIdentity` whose three strings equal the table
above.

`heartbeat()` returns the current `FileBridge.plugin_status()` dictionary.
An empty or stale status fails. These fields have to match exactly: `protocol`
is 1, `bridge_session` is the scope nonce, `pid` is the scope pid, `online`
is false, `in_game` is false, and `published_at` is a number. Other diagnostic
fields may be present. `published_at` may move between checks. The identity
fields may not.

`movie_ready()` is true only when the native movie host has the ready
handshake for this same nonce. The integer 1 is not true.

`prepare` reads the four callbacks, then passes the scope into
`CommunitySession.stage`. That session calls `verify_scope` before the
journal write, again before the DLL create, and again after the bytes are
confirmed. Each of those calls reads the four callbacks again. A lost or
changed lease stops the stage. A journal that was already published stays in
place under the existing `CommunitySession` rules.

`game_running()` is true when any Rocket League process exists. It is the
probe `CommunitySession` already uses. `helper_pending()` is true when
`MctNativeLauncher.exe` may still be running. Root should pass
`native_launcher_pending()`, which stays true when process enumeration fails.
Any result other than false, including an exception, blocks recovery.

## Status ack

The host confirms through PluginManager's loaded filename. `accept_status`
accepts only this dictionary:

| Key | Required value |
| --- | --- |
| `status` | `loaded` |
| `site_id` | The pending site id |
| `nonce` | The pending nonce |
| `stem` | The pending stem |
| `filename` | `stem + ".dll"`, with no directory |
| `pid` | The pending process id |
| `start_identity` | The pending creation token |
| `member_sha256`, `archive_sha256` | The pending hashes |

A wrong pid, nonce, or start identity is `stale`. A wrong site, stem,
filename, or hash is `foreign`. A bad shape, an unload status, a command
field, or a missing pending request is `unknown`. The live lease is read
again before a matching ack can enable the trial. If that live pid, nonce,
or start identity has moved, the ack is `stale`. A second ack after a
successful confirmation is `duplicate` and does not enable anything. The
first confirmation is what sets `enabled` to true.

`enabled` stays false for every other result. `game_verified` stays false
after a confirmation. Confirmation means the host reported the filename. It
does not prove ABI, training behavior, or a safe online handoff.

## Recovery

Call `recover()` on the next app startup before the normal online handoff.
It does not need the live lease. It does not issue `plugin unload`.

The staged DLL stays until `game_running()` and `helper_pending()` are both
false. A deferred result leaves the journal, the DLL, and any pending
request alone. `enabled` stays true when a confirmation already happened and
the process is still alive, so the shell does not treat that deferral as an
unload. Online handoff stays blocked while the result is `deferred`,
`retained`, `ambiguous`, or `outstanding`, and while `journal_kept` is true.

A hash change or a new file id on the same path is `retained`. The journal's
`owned_file_id` and `member_sha256` are left as `CommunitySession` recorded
them. A conflict, such as a journal path that does not match the recomputed
plugin path, is also left in place. An empty prepared journal is the
existing no-file cleanup: the journal is removed and no DLL is deleted.

There is no config backup, no config parser, and no write to `plugins.cfg`,
`config.cfg`, autoload lines, or binds.

## C++ host obligations

Root wires the button and the host after this controller. The movie click
stays the five fields already defined by the native movie protocol:
protocol, session, generation, revision, and control id. The host, not the
movie, maps that control onto `prepare()` and then reads `request()`.

After `request()` returns, the host:

1. Re-checks the owned pid, creation time, executable hash, BakkesMod 229,
   build `261013.63066.530866`, fresh nonce, offline Steam frontend, and
   native-movie handshake.
2. Re-hashes the staged file and refuses unless the hash is the pending
   member hash and the Windows file id still matches the journal.
3. Refuses when PluginManager already has that exact filename loaded.
4. Executes only `plugin load` followed by the derived stem. It does not
   execute an unload, a path, `exec config.cfg`, or `writeconfig`.
5. Confirms that PluginManager lists that exact filename.
6. Only then calls `accept_status` with the dictionary above.

Setting cvars is not confirmation. After step 5, and still inside the owned
process, the host uses `CVarWrapper` live values to force
`sf_remember_speed=0`, `sf_change_speed=0`, and `sf_save_attempts=0`. The
plugin's default Manual mode stays. The host snapshots `sv_soccar_gamespeed`
before those writes and restores it if this load changed it, while the
process is still owned. A failed cvar write does not authorize a config file
write, and it does not authorize marking the trial loaded before the
PluginManager filename check.

Do not unload the plugin while the owned game or the native helper is alive.
Source for this plugin creates speedflip, attempts, and bots data
directories. Do not delete that user data during recovery. DLL removal does
not undo it.

`saveToCfg` is global BakkesMod behavior and the serializer is unknown. Do
not claim that a later user-triggered global save preserves the previous
config bytes.

These host steps are still not game-ABI verification. Leave the public
installer hold and every production flag unchanged.
