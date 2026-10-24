# Private native menu assets

`scripts/stage_native_runtime.py` builds a private runtime directory.
`native_menu_assets.prepare_native_menu` reads one pinned Rocket League
install and writes a private package under a per-session directory. Neither
step installs that package, launches the game, or queries BakkesMod.

`runtime_verified` and `production_ready` stay false. A prepared file is not
evidence that Scaleform initialized the menu or that a match can start.

## What the end-user install does not need

Preparation uses the Python process that already ships with the app, plus
Windows CNG inside the staged reader and rewrite helpers. It does not run a
compiler, Java, FFDec, a UEViewer executable, or a separate crypto install.
The only network use is optional and build-time: the stage script can fetch
two pinned UEViewer files. The runtime module does not fetch anything.

## Pins

These are constants, not caller choices. A different executable or package
hash refuses preparation. That executable hash is the supported runtime build
`261013.63066.530866`. BakkesMod core `229` is the host pin that belongs to
that build. This module does not read BakkesMod.

| Item | Value |
| --- | --- |
| Executable | `Binaries/Win64/RocketLeague.exe` |
| Executable SHA-256 | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` |
| Package | `TAGame/CookedPCConsole/GFX_MainMenu_SF.upk` |
| Package SHA-256 | `d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65` |
| Export | `MainMenu` |
| Movie SHA-256 | `57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0` |

The staged ABC, manifest, and `native_movie_compose.py` pins must agree,
including both authored classes `menus::MctRootMenu` and `MctMainMenuScreen`
and document character `0` bound to `MctMainMenuScreen`. A mismatch refuses
staging. The stage script does not edit those files and does not unpin them.

## Decoder configuration

The key is the public 32-byte Rocket League parameter in
`FFileReaderRocketLeague` from MIT UEViewer commit
`a0bfb468d42be831b126632fd8a0ae6b3614f981`. The stage script checks the
normalized source against SHA-256
`72e7700ea05b937b473451e05db873b8eb8dd9e4b41c329d6e9a0d2e7e56132d`
(15390 bytes, CRLF converted to LF only) before it reads the key. The license
file is SHA-256
`23831a13a99f726e62388efade7f0b8a778f1b84e40dec8a4bf4a1e481ccbdfe`
(1080 bytes) and is copied in full.

Default URLs, with a timeout and a size cap, are only:

- `https://raw.githubusercontent.com/gildor2/UEViewer/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/UnrealPackage/UnPackageReader.cpp`
- `https://raw.githubusercontent.com/gildor2/UEViewer/a0bfb468d42be831b126632fd8a0ae6b3614f981/LICENSE.txt`

Pass `--source` and `--license` together to build offline. The generated
`decoder_config.bin` stays in the gitignored runtime directory. Receipts
record its length and SHA-256 and do not contain the key bytes. No cooked
GFX, UPK, SWC, or game executable is staged.

When the destination already exists, staging writes a sibling directory whose
name contains `.staging-`, then renames the previous allowlisted directory
aside and the new directory into place. Unexpected names are left in place.
The script does not recursively delete unrelated trees.

## Runtime API

```python
prepare_native_menu(
    game_root,
    session,
    bridge_directory,
    private_root,
    runtime_directory=None,
) -> PreparedNativeMenu
```

`session` is the service bridge nonce. It must be a canonical lowercase UUID.
`runtime_directory` defaults to `<repo>/runtime/native-menu` from this source
layout. Paths must be absolute Windows drive paths. UNC paths, device names,
and reparse aliases are refused. `private_root` and `bridge_directory` must
sit outside the game installation and outside each other.

The view URL is always the `file:///` URL of `bridge_directory/native-view.json`.
This function does not create that file.

On success the only new files are:

- `private_root/<session>/GFX_MainMenu_SF.upk`
- `private_root/<session>/prepare-receipt.json`

An existing session directory is left unchanged. A failure after the session
directory has been created does not delete it. The installed executable and
package are only read, then hashed again after preparation.

`PreparedNativeMenu` fields:

| Field | Meaning |
| --- | --- |
| `private_package` | Absolute path of the private package |
| `private_package_sha256` | SHA-256 of that file |
| `source_package_sha256` | SHA-256 of the installed package that was read |
| `source_movie_sha256` | SHA-256 of the installed `MainMenu` movie |
| `session` | Canonical nonce |
| `environment_variable` | `MCT_NATIVE_MOVIE_SESSION` |
| `environment_value` | The same nonce |
| `view_url` | Fixed `native-view.json` URL |
| `runtime_build` | `261013.63066.530866` |
| `supported_bakkesmod_core` | `229`, not a live query |
| `bakkesmod_queried` | `False` |
| `runtime_verified` | `False` |
| `production_ready` | `False` |
| `installed` | `False` |
| `launched` | `False` |

`environment()` returns `{MCT_NATIVE_MOVIE_SESSION: session}`.
`receipt()` returns the JSON-serializable record written next to the package.
The process environment is not modified.

Staged helper hashes are checked against `receipt.json` before those modules
are imported. A missing, truncated, oversized, or hash-mismatched file refuses
before import. A receipt that sets a capability flag true is refused.

Runtime helpers, including the rewrite helper's sibling reader, execute their
source without writing bytecode caches. The runtime directory is immutable
across successive sessions. The normal fixture tests use the checked-in MIT
license; only the optional source-provenance check needs a private UEViewer
checkout.

On 24 October 2026, the staged runtime prepared two different private sessions
from the pinned installed package. The original package hash remained unchanged;
neither preparation started Rocket League. See
`validation/staged-native-menu-preparation-2026-10-24.json`. This is package
preparation evidence, not game rendering or loader compatibility evidence.

## Work still owned by root

1. Run `python scripts/stage_native_runtime.py` on the build machine, or pass
   `--source` and `--license` for an offline build. Do this only after
   `native_movie_compose.py` agrees with `native_ui/compiled/manifest.json`.
   This package does not edit the composer, the ABC, or the manifest.
2. Keep `runtime/native-menu/` out of git. Package that directory with the
   Windows app. `decoder_config.bin` is build output, not a source file.
3. Frozen builds should pass `runtime_directory`. The default path is the
   source checkout's `runtime/native-menu`, three parents above
   `native_menu_assets.py`.
4. Choose a per-user `private_root` outside the game install. Pass the real
   game root, the service bridge directory, and that bridge's canonical
   lowercase nonce.
5. Set `MCT_NATIVE_MOVIE_SESSION` from `result.environment_value` for the
   plugin host. Do not treat this module as having set it.
6. Do not copy the private package onto
   `TAGame/CookedPCConsole/GFX_MainMenu_SF.upk`. The owned native launcher
   provides the separate process view; its game behavior still needs validation.
7. Leave `runtime_verified` and `production_ready` false in packaging,
   bootstrap, and UI. Do not add a compatibility grant.
8. `NativeOfflineSession` connects preparation to the explicit development
   startup path and retains the launcher owner. Frozen native packaging still
   needs to include and verify both native runtime components. Public release
   remains held pending native game validation.
