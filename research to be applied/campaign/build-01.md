# BUILD-01: source-to-frozen-app provenance

Read-only build-path audit of the `work/research-publish` publication-baseline copy, not the requested `work/reviewed-training` candidate source. No compile, CTest, freeze, game launch, or runtime installation was performed. In that publication-baseline copy, `build/` and `runtime/` are absent; this does not establish whether the separately staged candidate has current build receipts or artifacts.

## Artifact chain

| Stage | Current project mechanism | What its evidence can establish |
|---|---|---|
| Authored menu source → ABC | `native_ui/README.md:74-126` documents Flex `mxmlc` compilation (`-debug=false`, player 32, SWF 20) against a private game SDK SWC and the checked-in as3corelib source closure. The output SWF is inspected and only its DoABC payload is retained as `.abc`. Root, pause, and results inputs/outputs are listed in `native_ui/compiled/manifest.json` and `match-manifest.json`. | Manifest hashes and class lists can establish that the checked-in ABC matches the recorded authored sources and expected class inventory. They do not show Scaleform loading or displaying the movie. Flex/SDK tool binaries and private SWCs are not supplied as a fully locked, offline toolchain in those manifests.
| ABC → staged native-menu runtime | `scripts/stage_native_runtime.py:410-440,455-493,509-552,623-639` checks source, screen, wrapper, ABC, library, match-manifest, and composer pins before staging. `:262-303` stages the allowlisted payload and receipt; it does not invoke Flex or regenerate an ABC. Payload names are at `:102-112`; `receipt.json` is added by `:191`. A pinned UEViewer source/license pair can be provided for offline staging; otherwise the script fetches the two pinned files (`:262-290`). | `runtime/native-menu/receipt.json` is a file-level hash and provenance receipt with runtime/gameplay flags false. It establishes staging consistency, not game compatibility. The actual runtime preparation later reads and rechecks the installed game package and produces session-private packages (`docs/NATIVE_MENU_ASSETS.md:3-30,97-146`).
| C++ sources → plugin DLL | `plugin/CMakeLists.txt:21-63` enables the plugin only on 64-bit Windows/MSVC, pins BakkesMod SDK and nlohmann JSON archives by URL/hash, and defines the development-only host probe. `scripts/build_plugin.py:22-64` builds the ordinary plugin in `build/plugin`, forces `MCT_ENABLE_NATIVE_MOVIE_TRIAL=OFF` and `MCT_BUILD_HOST_PROBE=OFF`, runs CTest, inspects the real PE, then writes `runtime/plugins/plugin-build-receipt.json` with DLL SHA-256, source commit, all plugin-file hashes, dependencies, source archives, and false gameplay/native-trial flags. | That receipt, if regenerated from the final source commit, ties a specific DLL byte image to the plugin source tree and build configuration. PE inspection (`scripts/plugin_artifact.py:8-83`) checks AMD64 DLL shape, required exports, and imports; it does not prove BakkesMod loaded it or validate gameplay.
| Candidate build → staged runtime | `scripts/build_native_candidate.py:162-212` builds in isolated `build/native-candidate/plugin` and `native-launcher` directories, runs both CTest suites, requires the host probe OFF, copies in an already-staged `runtime/native-menu`, and verifies source/dependency/image/staged hashes. Candidate CMake explicitly sets movie trial ON and host probe OFF (`:162-170`). | `candidate-manifest.json` binds commit, source hashes, dependency/source archive records, image hashes, file hashes for `plugins`, `native`, and `native-menu`, plus explicit false verification flags (`:444-500`). This is a developer candidate, not the normal release.
| Staged runtime → frozen application | `packaging/my-career-training-native.spec` stages only the candidate runtime allowlists and the native GUI/worker, into `build/native-candidate/dist/MyCareerTrainingNativeCandidate`; `build_native_candidate.py --freeze` is explicit (`:148-177,182-212`). `scripts/smoke_native_candidate.py` validates the bundle and runs an offscreen package smoke. | The smoke receipt can bind the exact frozen bundle files to a candidate manifest. It does not execute the helper or start Rocket League (`docs/NATIVE_CANDIDATE.md:30-49,95-112`).

The AS/ABC and C++/DLL builds are separate build products. The frozen candidate contains the native-menu runtime and plugin DLL as separate files; the DLL is not evidence that it embeds or matches a particular authored ABC. The bundle manifest and receipts are the intended join between them.

## Publication-baseline pins and source-provenance limits

The present frontend manifest records `MctRootMenu.abc` as 33,506 bytes, SHA-256 `7b69e6845163d5684de3c8962727af664848274d30ca8453dfda2e69500bd975`, with authored source hash `f6a12acb25680687dc7dd02c3cf8f35e0efd51e12da007cdd7d0e5a28234cf64` (`native_ui/compiled/manifest.json:2-9,49-54`). The match manifest records pause ABC SHA-256 `f6d57a96920e65c5ea0a1af8be3730cbfcf8ffc9340ad32312502864bac2e610` (21,655 bytes) and results ABC SHA-256 `c7c365db1c31f826356af576149ef88374a1531728940ba3468378dbdd854315` (25,630 bytes), plus their source/package pins (`native_ui/compiled/match-manifest.json:1-29,30-118`). All manifests explicitly keep `game_classes_linked`, `runtime_verified`, and `production_ready` false.

`research to be applied/source-provenance.json:2-10` calls itself a selected-file research snapshot, not a full source/build manifest, and says its base commit alone does not reproduce captured uncommitted source. It records observation time 2026-10-27 07:33 UTC, base `1fe8c858`, and per-file SHA-256s. At that observation, it explicitly records snapshot/comparison-checkout hash differences for `bridge.py`, game worker, training catalog/scenarios/engine, `NativeCareerLayout.h`, `NativeMatchLayout.h`, and `MctPauseMenu.as`; several selected files were equal. Those differences are consistent with the JSON's stated scope of captured uncommitted source and reviewed isolated patches. They are observations only: without mapping the comparison checkout to the final candidate and build tree, they do not establish staleness. This report did not perform that candidate-source comparison.

The publication-baseline compiled-menu manifests pin source and ABC hashes, but this audit did not find a staged receipt or candidate manifest in that copy joining them to a DLL and frozen app. The historical `docs/validation/native-candidate-headless-2026-10-24.json` reports an earlier candidate commit (`2fed6cd9`), plugin SHA-256 beginning `9a73c7eb`, and a passing headless smoke; it explicitly has `game_verified=false` and `production_ready=false`. The historical `staged-native-menu-preparation-2026-10-24.json` uses authored ABC hash `fbcedd36…`, different from this publication baseline's frontend ABC hash `7b69e684…`; it is not evidence for the requested candidate. Root's separate SDK-02 observation of the installed 591,360-byte DLL (SHA-256 prefix `18569d2…`) is an identity for that installed file only. It does not identify a candidate build or prove deployment of these sources.

## Flags, traps, and reproducibility limits

- Use `scripts/build_native_candidate.py` for the development native-menu candidate: Release x64; `MCT_ENABLE_NATIVE_MOVIE_TRIAL=ON`; `MCT_BUILD_HOST_PROBE=OFF`. The normal release path `scripts/build_plugin.py` intentionally forces trial OFF. `docs/NATIVE_CANDIDATE.md:11-28,51-68` says not to substitute the normal release spec/cache/runtime for the candidate.
- Do not read green `tests/test_native_candidate.py` as a real build. Its module docstring (`:1`) says no compiler or freeze runs. Its injected runner (`:363-385`) materializes synthetic PE files, and `_plugin_pe`/`_tiny_pe` (`:515-549`) create minimal fake AMD64 images with expected marker exports/imports; `_write_menu` (`:420-500`) uses synthetic ABC bytes. These fixtures exercise isolation, manifests, allowlists, and refusal paths—not C++ code generation, Flex output, a real SDK link, frozen runtime imports, or a game loader.
- CMake FetchContent pins the SDK and JSON source hashes but may require a populated cache or network. Menu source compilation requires Apache Flex 4.16.1 and private SDK SWCs not included in the player bundle; the menu manifest does not pin the exact compiler executable/SWC bytes. `stage_native_runtime.py` can avoid its two network fetches with both pinned local UEViewer source and license inputs, but this does not make the entire plugin/app build offline by itself. The docs require Windows x64/MSVC for Windows artifacts (`docs/BUILDING.md:6-18`).
- The PE inspector verifies image format/exports/import names only. Even a current candidate receipt and successful headless smoke are insufficient for menu visibility, BakkesMod loading, gameplay, or runtime acceptance; all relevant flags remain false.

## Minimum acceptance sequence for the next final source snapshot

1. Identify and freeze the exact final candidate source tree, then refresh its build provenance to include every native/UI source actually compiled. Do not use the publication-baseline copy or the research snapshot's base as the candidate build identity.
2. For every changed `.as`, compile against the correct private menu SDK with Flex; extract and inspect the single DoABC; verify class inventory/version/debug-path constraints; update the source/ABC manifests and composer/stager pins together. Check those hashes before staging so a stale checked-in ABC is rejected.
3. Stage the private runtime and retain its receipt. Compare each staged file hash to the manifest; keep `runtime_verified=false` and `production_ready=false`.
4. Run a clean, isolated candidate build with trial ON/probe OFF, CTest, real DLL PE inspection, and verify the emitted plugin receipt source hashes and DLL SHA match the same final commit. Check candidate manifest `source_files` and `staged_hashes` equal the current source/runtime.
5. Freeze only with the native spec and inspect the final bundle inventory/hashes against the candidate smoke receipt. Keep normal-release outputs and flags separate.
6. Defer the heavy gates until after the lightweight hash/manifest checks: actual Windows C++ compile and tests, native asset staging, PyInstaller freeze/smoke, disposable installer lifecycle, then an owned offline game session. Only that final live check can move runtime/gameplay claims beyond false.

No build/test command was run for BUILD-01; this is a dependency/evidence map, not a build-complete report.

## Coordinator addendum: actual isolated candidate identity

A separate selected comparison at 08:05:55 UTC inspected the actual isolated
research candidate. All twelve recorded menu-source/screen/wrapper/ABC hashes
match their candidate manifests. The machine-readable [comparison receipt](../evidence/candidate-menu-identity.json)
records the individual hashes. Its scope does not include the full library,
composer or staging closure, compilation, or runtime behavior.

| Candidate ABC | Bytes | SHA-256 |
| --- | ---: | --- |
| Root menu | 55,346 | `3f20a2ef392cdfb2ea0881222f223231a03869c657d07f6db3a1a5c06644d4d2` |
| Pause menu | 25,736 | `237a82c4c060a2090be5c48f22c85340f70b6e6485795dc2ee5b9033431ee829` |
| Results menu | 25,630 | `c7c365db1c31f826356af576149ef88374a1531728940ba3468378dbdd854315` |

The candidate CMake SHA-256 is
`489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7`,
matching the selected source-provenance record. Comparing the older publication
baseline CMake with this candidate's receipt would not establish staleness.
The candidate also has a lightweight build cache; the baseline's absent build
folder says nothing about that cache. No full candidate DLL build, freeze or
live deployment was performed by this addendum.
