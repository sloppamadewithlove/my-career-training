# PACKAGE-02 — Offline inspection path for training menus

Date: 2026-10-27. Read-only local artifact and source audit. No REA call was repeated or substituted. No package/movie bytes were written or published. The two target menus were inventoried as metadata; a separate browser movie was decoded in memory solely to compare its hash.

## Result

The installed training packages can be inventoried offline with the existing `scripts/native_package_reader.py` and the already-staged private decoder configuration. I verified header/table metadata for both requested packages; I did **not** materialize their movie bytes. In a separate read-only provenance check, I hashed the embedded `TrainingBrowserMenu` movie in memory and compared it with the already-existing private `TrainingBrowserMenu.gfx`; they match exactly. No movie bytes were written or published, and I ran no decompiler. The package reader can return one selected `SwfMovie.RawData` as an in-memory buffer but has no output-path or decompilation API. Follow-up tooling discovery found the existing private FFDec and Temurin installs outside `PATH`; extracting one of the two requested menu movies for FFDec would still need a small private temp-file bridge.

## Current installed package evidence

Hashes/sizes agree with `work/campaign/artifact-01.md` and the current installed files. `inspect_menu_package` succeeded when given the existing decrypt callback; it read the package tables and compression-frame metadata without extracting the `RawData` movie.

| Installed package | Bytes / SHA-256 | Header and tables | `SwfMovie` export discovered |
|---|---|---|---|
| `GFX_TrainingMenu_SF.upk` | 1,146,549 / `BF9BAA4238D077F35F8041204EA4AEC8E9E7C9BB943D1E3DF2DA07DD07A57663` | UE package v868, licensee 34, flags `0x0288028D` (no full-CTR flag); decrypted header; 54 names, 9 imports, 10 exports, 3 chunks | `TrainingMenu` (serial 894,439 bytes) |
| `GFx_CustomTrainingSelectShotMenu_SF.upk` | 384,325 / `CE5407B03ED248171493575532C29DAB47FBEED09E2ADEF842DEB35B4409B567` | UE package v868, licensee 32, same flags/no full-CTR; decrypted header; 34 names, 8 imports, 4 exports, 1 chunk | `CustomTrainingSelectShotMenu` (serial 871,798 bytes) |

Both match the reader’s declared support (`version=868`, licensee 32 or 34). The first is the smallest available package boundary for the built-in training entry/difficulty flow. The second is a distinct custom-pack shot-selection surface; its metadata does not establish how stock built-in lessons choose difficulty or rank.

The no-callback reader attempt on each package fails while decoding a string (`string length is outside 1..1024`). Reading the unencrypted 12-byte package summary still reports the supported version/licensee and table offsets. With the existing callback, the metadata inventory succeeds. I did not call `read_movie_bytes` on these packages.

## Existing entrypoints and boundaries

- `scripts/native_package_reader.py:107-110`: `inspect_menu_package(path, decrypt_header=None)` returns package names/imports/exports/chunks and capability flags, not payload bytes.
- `scripts/native_package_reader.py:113-124`: `read_movie_bytes(path, exact_export_name, decrypt_header=None)` selects one exact, unique `SwfMovie`, parses its `RawData`, validates the GFX/SWF header, and returns `MovieBytes.data` in process memory. There is no path parameter or save method (`tests/test_native_package_reader.py:408-414` checks that API shape).
- `scripts/native_package_reader.py:22-44,343-420,564-670,692-814`: supported package version is 868; licensee versions are 32 and 34; full CTR is rejected. The reader caps files at 64 MiB, headers at 4 MiB, export/movie data at 16 MiB, logical streams at 256 MiB, and chunks at 16 MiB. It validates chunk frames and selectively inflates data only when reading the selected export. It recognizes `GFX`/`FWS` and `CFX`/`CWS`; compressed movie data is not decompressed into a new SWF by this reader.
- The encrypted-header callback must return a same-length buffer for the aligned header region (`:387-429`). The CNG helper uses an explicit 32-byte AES-256-ECB key on Windows (`:126-143`); the reader never discovers a key. The current `work/reviewed-training/runtime/native-menu/decoder_config.bin` is 32 bytes and its recorded receipt hash matches. The key bytes were not printed or included in command arguments.
- `scripts/stage_native_runtime.py:31-50,210-300` pins UEViewer source commit `a0bfb468d42be831b126632fd8a0ae6b3614f981`, verifies the source length/SHA-256, and derives the decoder configuration privately. If building it offline, the CLI takes `--source` and `--license` together. It stages the decoder configuration and authored menu tooling, not any `.upk`, `.gfx`, `.swf`, or game executable (`:757-763`). It is not an inspector CLI for arbitrary packages.
- `scripts/native_movie_compose.py` is a hash-pinned movie composer for MainMenu, MidGameMenu, and EndGameMenu authored ABCs; it is not an ABC decompiler. `scripts/native_package_rewrite.py` returns rewritten package bytes in memory and is bounded by exact expected hashes/export identities. The preparation path in `src/my_career_training/native_menu_assets.py:211-270` rejects a different MainMenu package hash. These composer/writer paths do not turn the two training packages into writable or supported targets. `docs/NATIVE_PACKAGE_REWRITE.md:152` also says the legacy `replace_final_movie` route refuses licensee 32.

Existing reader tests are synthetic fixtures, not retail-package validation: they cover both compression-table licensee layouts (`tests/test_native_package_reader.py:432-450`), encrypted callbacks (`:496-537`), version/licensee and CTR refusals (`:540-564`), GFX/CWS/CFX handling (`:600-618`), and the no-output API contract (`:408-414`). The package probe above supplies separate metadata evidence for these two installed files, not a reader correctness certification beyond that use.

## Existing training-browser export and parser tools

The files are in the private research tree `<private research root>/private-workshop-movies/`: `TrainingBrowserMenu.gfx` and an `export-training/` directory containing exactly `scripts/menus/TrainingBrowserMenu.as`, `scripts/TrainingBrowserMenuScreen.as`, and `scripts/tagame/constants/MenuName.as`. The GFX is 921,910 bytes, SHA-256 `c55ff890a0255a9ee5cdd347c255271cb78ce61e137f45ded1d9cfb18f925098`. The AS files are respectively 30,434 bytes / `B5E1890C1F891BE6887508E27A13ACF3D1C40C26554B72463A53E6C96A49C5EB`, 1,468 bytes / `00E557CA0EB544C3AEC99B9CCBE1988B5113DC9A36743F0BECDAEF54BDC885FA`, and 7,666 bytes / `1830F29E84C6700D6FE7EBCC2ABC4E30FDECAA0E71A2374B283DA0B3CB570120`. A read-only in-memory `read_movie_bytes` call on the currently installed `GFX_TrainingBrowserMenu_SF.upk` (`A16834DBA4A9AC1FD72E50A81DD37DB9DBFCCA4C5D3F3F9CB835F818E359AE4D`) found one `TrainingBrowserMenu` `SwfMovie`; its `RawData` byte count/hash exactly match the sibling `.gfx`. This establishes exact asset identity with the current package. The export directory and its parent have no Git root, and the bounded file search found no adjacent manifest, extraction command log, or export script. Thus the movie payload is identified exactly, but the AS export’s decompiler version/settings and command provenance remain unknown. These exports establish the Custom Training browser’s list/detail/focus and direct-play route only (`work/campaign/nativeui-01.md`, `artifact-01.md`). They do not contain the `TrainingMenu` or `CustomTrainingSelectShotMenu` implementation.

`docs/NATIVE_MENU_PATCH.md:1-9,50` documents FFDec 26.4.0 plus Java as explicit CLI paths for an existing MainMenu-only patch script. `Get-Command` did not find these tools on `PATH`, but bounded file-name searches found an existing private toolchain under `<private tool root>`:

| Tool file (relative to the private tool root) | Version evidence | Bytes / SHA-256 |
|---|---|---|
| `ffdec-26.4.0/ffdec-cli.exe` | Windows product/file version 26.4.0 | 46,360 / `179B38A2B4B16019FA50FD627AAAD093D5F0A74A0C3F5A166946A353815B287B` |
| `ffdec-26.4.0/ffdec-cli.jar` | `Main-Class` is `CommandlineInterface`; sibling executable reports 26.4.0 | 1,575 / `84573B0E260F2288DDB12AFD54CDBA853E1DF77CA2514D6CFF0C3A875F1E70CD` |
| `ffdec-26.4.0/ffdec.jar` | sibling `ffdec.exe` reports 26.4.0 | 5,271,501 / `80F8CED0BFDE98B434C28E9807E91FE5558255B2F712051A0E65221519BD392A` |
| `temurin-jre-21.0.9/jdk-21.0.9+10-jre/bin/java.exe` | JRE release metadata says 21.0.9+10-LTS | 50,344 / `5F6248F9C0F32B38FFABA813819BF3331536A48C7DDC45B18E73ACD15A6CF7EF` |
| `apache-flex-sdk-4.16.1/bin/mxmlc.bat` | SDK directory/archive is 4.16.1 | 1,261 / `2831CFDBD2D707D8A7E2E4369B07868AF2FE9ED4F29C73373029FCA0488C18D9` |


The current repo’s `scripts/native_menu_patch.py:890-915` is the existing FFDec export caller for its owned `menus.RootMenu` candidate: it invokes Java headless with explicit Java/JAR/home paths, then `-config`, `-format`, `-selectclass menus.RootMenu`, `-export script`, output directory, and movie path. The AS check uses `-format script:as`; the pcode pass uses `-format script:pcode`; method-id export adds `showMethodBodyId=true`. `docs/NATIVE_MENU_PATCH.md:1-9,50` limits that script to the MainMenu candidate. The separate builder note `<private builder notes>/native-menu-patch.txt` records the same explicit portable Java/FFDec path and RootMenu export flow. Neither is a recorded TrainingBrowser extraction receipt. No tool was installed or executed for this follow-up. The checked-in composer handles only narrow, hash-pinned ABC/string operations, so it cannot replace FFDec’s class/pcode export for the two unknown movies.

## Smallest route to answer the menu questions

1. Use the existing parser and current package decoder receipt to query metadata for `GFX_TrainingMenu_SF.upk`; this step is already complete. Export/import names and `SwfMovie` identities can narrow the needed class boundary without producing a movie file.
2. Extract only the chosen `SwfMovie.RawData` to a private temporary file for the requested focused source inspection; use the already-found FFDec 26.4.0 and Temurin JRE 21.0.9 with explicit paths, never the decoder key on a command line. This bridge does not yet exist in `native_package_reader.py` and was not built in this research task.
3. Query `CustomTrainingSelectShotMenu` only if comparison with the custom-pack flow is useful. Inspect package imports before widening to a `GameInfo_*` package; do not scan the whole game tree.

Metadata inspection can answer which movie/export and dependencies belong to each package. A targeted FFDec pass could answer which menu classes, labels, navigation callbacks, and difficulty/shot-selection path the movie implements. Neither route proves runtime menu invocation, actual controller focus, nor shot-timer/ball lifecycle; those remain runtime questions.

## Tooling correction from the first inspector run

The first private inspector run read the exact Training movie but FFDec refused an incorrectly shortened format argument. Its own CLI help and the existing caller at `native_menu_patch.py:295` require `-format script:as`. The earlier report said `-format script`; that claim is withdrawn. No ActionScript was exported by that failed invocation.
