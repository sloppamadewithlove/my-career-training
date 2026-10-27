# BROWSER-ACCEPTANCE-TESTS-01 — focused offline browser and identity checks

Date: 2026-10-27
Scope: existing Python tests in the frozen `work/reviewed-training` candidate.
No test or product code was authored or changed. No game, native build, network
download, installation, or actual browser launch was performed.

## Prior evidence and selection provenance

The frozen candidate is based on `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`
and had a dirty worktree before this run. Source hashes below identify the
current reviewed-candidate bytes. I read `AGENTS.md`, current status/task files,
the testing workflow/privacy guidance, and the task's prior persistence,
download, favorites, and map-arrival reports. The Python 3.12.13 / pytest 9.0.2
environment was the parent-specified existing virtual environment. `PYTHONPATH`
was set to this checkout's `src`; a read-only import check resolved
`my_career_training` there. The checkout has no `conftest.py` and `pyproject.toml`
declares `pythonpath = ["src"]`.

To avoid inflating previous totals:

- PERSIST-TEST-01 records its exact 21-node selection. None of its listed nodes
  are selected below. LESSON-ACCEPTANCE-TESTS-01 and
  SCENARIO-ACCEPTANCE-TESTS-01 cover engine/worker and scenario tests in other
  modules; their 40 and 130 results are not added here.
- FAVORITES-02 says the main agent already ran a five-test favorite selection.
  This run excludes the cited favorite creation/removal, bounded snapshot,
  legacy favorite filtering, cached image, and native favorite-route checks.
- DOWNLOAD-01 inventories catalog/download tests but did not run them. Current
  project status separately reports 106 download checks (four skipped) and a
  133-check preference/overlay/bridge aggregate, without their exact node lists.
  I did not rerun the plugin ZIP/download suite or the bridge download
  cancel/retry tests because the aggregate receipts do not resolve their exact
  overlap. The catalog `community_browse` cancellation and pagination retry
  tests below are a different boundary from cancelling a ZIP transfer.
- The Power Shots setup persistence node below is not in the exact 21-, 40-, or
  130-node receipts. It could overlap the historical 133-check bridge aggregate,
  whose node list is unavailable; the run is reported as one invocation and is
  not counted as unique coverage across campaign runs.

## Fixture and side-effect review

Before running, I read every selected test body and its fixture. The
`test_community_discovery_bridge.py` fixture creates an offscreen Qt app, uses
pytest temporary storage, and replaces installation/process checks and online
launch. Selected catalog reads are replaced with local parser fixtures or
event-controlled stubs; page-open calls are monkeypatched to collect the URL;
plugin selection replaces the asynchronous lookup starter. These tests do not
perform HTTP requests or open a browser.

The selected `test_workshop.py` cases build fake Steam library directories and
small synthetic `.udk` bytes only under `tmp_path`; they pass explicit fixture
roots and do not inspect the user's Steam library. The selected `test_bridge.py`
fixture uses a temporary store and replaces game-process and launch checks. Its
Power Shots case only changes and re-reads the selected lesson setup; it does
not start a worker. No pytest `conftest.py` exists. The process used
`QT_QPA_PLATFORM=offscreen`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
`PYTHONDONTWRITEBYTECODE=1`, and `-p no:cacheprovider`. Ignored `__pycache__`
files already existed in the dirty checkout after the run; no clean-cache claim
is made.

## Exact pytest selection

From the frozen checkout root, the command used the explicit existing Python
3.12 virtual-environment interpreter. Its private absolute path is omitted from
this report:

```text
& <specified Python 3.12 venv interpreter> -m pytest -q -p no:cacheprovider `
  tests/test_community_discovery_bridge.py::test_browse_runs_async_and_publishes_only_the_requested_page `
  tests/test_community_discovery_bridge.py::test_invalid_browse_payload_does_not_start_worker `
  tests/test_community_discovery_bridge.py::test_cancel_invalidates_generation_allows_switch_and_discards_late_result `
  tests/test_community_discovery_bridge.py::test_cancelled_append_retries_same_page_without_skipping `
  tests/test_community_discovery_bridge.py::test_open_item_uses_only_id_and_source_from_current_page `
  tests/test_community_discovery_bridge.py::test_open_item_rejects_unlisted_or_untrusted_payload `
  tests/test_community_discovery_bridge.py::test_open_item_rechecks_displayed_details_url `
  tests/test_community_discovery_bridge.py::test_select_plugin_routes_only_current_plugin_id_to_existing_lookup `
  tests/test_community_discovery_bridge.py::test_select_plugin_rejects_non_plugin_or_unlisted_rows `
  tests/test_community_discovery_bridge.py::test_open_source_uses_fixed_canonical_url_only `
  tests/test_community_discovery_bridge.py::test_open_source_rejects_caller_supplied_urls `
  tests/test_community_discovery_bridge.py::test_ingame_allowlist_contains_catalog_actions_but_no_activation_action `
  tests/test_workshop.py::test_discovery_follows_real_library_manifest_and_preserves_source `
  tests/test_workshop.py::test_multi_package_item_requires_exact_selection `
  tests/test_workshop.py::test_imported_records_cannot_authorize_arbitrary_paths_or_changed_bytes `
  tests/test_workshop.py::test_epic_does_not_claim_steam_maps_or_a_working_loader `
  tests/test_bridge.py::test_power_shots_selection_persists_whole_setup_and_switching_situation_keeps_rank
```

Environment was `PYTHONPATH=src`, `QT_QPA_PLATFORM=offscreen`,
`PYTHONDONTWRITEBYTECODE=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

## Result

**29 passed, 0 failed, 0 skipped; pytest 45.10 seconds; measured process
46.842 seconds; exit code 0.** This is this invocation's collected-case count,
including parameterized cases; it is not added to earlier aggregate counts.
The output is retained privately at
`work/campaign-tests/browser-acceptance-tests-01-pytest.txt` (102 bytes,
SHA-256 `763aa05771c1549ac5bfa3b9efc633d1b7f3b3ba873c1a44f86670afe8a31337`).

Capture caveat: an earlier shell wrapper for this same selection returned after
30 seconds without exposing its running-session handle or retaining output. No
pytest log or process remained when checked. It may have started or partially
executed the selection before the session ended. The complete retained run
above is the only result counted here; exact per-case execution count across
those two shell attempts cannot be established, and no total is presented as
unique campaign coverage.

## What this run establishes

- **Lesson setup model:** the Power Shots bridge test changes the selected
  situation while keeping the chosen rank and verifies the whole setup in both
  current state and saved state (`test_bridge.py:152-163`). This is persistence
  evidence; it does not prove the eight-rank native picker, all lesson pages, or
  a playable game result.
- **Community browser routing:** catalog browsing publishes the requested
  source/query/page and leaves catalog rows non-downloadable/non-activatable;
  invalid payloads do not start the fetch path (`test_community_discovery_bridge.py:64-120`).
  A canceled generation can be replaced by a new source, and a late stale result
  is discarded (`:122-157`). A canceled append retries the same page rather
  than skipping it (`:195-235`). These fetch calls are mocked.
- **Exact item routing:** only a currently listed `(source, numeric ID)` opens
  the canonical page; an untrusted displayed URL is rejected. Plugin-row
  selection starts lookup with the current numeric plugin ID, rejects
  non-plugin/unlisted rows, and exposes no `community_activate` action in the
  in-game allowlist (`:238-341`). The browser link is captured by a mock; no
  external browser opens.
- **Workshop file model:** a fixture library manifest discovers the expected
  Workshop package without claiming a tested/launchable map; a catalog item
  with multiple packages requires exact selection; imported identity is
  rejected when its path is escaped or its bytes change; Epic mode does not
  claim Steam packages or a working loader (`test_workshop.py:21-47,120-162`).
  All paths and contents are temporary fixtures.

## Existing download/favorite test inventory and remaining gaps

The earlier DOWNLOAD-01 inventory identifies existing `test_community_plugins.py`
checks for cancellation/truncation before publish, cancel during archive
inspection and staging, valid archive caching as `downloaded_not_enabled`, and
cache identity/symlink checks. It also identifies bridge checks for lookup
cancellation, failure returning to retryable state, and a late cancellation
that keeps a committed cache visible. Those concern actual plugin-archive
workflow code, but this run did **not** execute them. The status file's 106 and
133 aggregates lack exact selector receipts, so these remain prior reported
test totals rather than fresh results here.

FAVORITES-02 records existing live-item snapshot/removal, bounded favorite
metadata, legacy Workshop filtering, cached favorite-image rehydration, and
native browser favorite-route/stale-generation tests. They were not repeated.
The earlier report also found no focused Python test for resolving a saved
remote favorite after its catalog page is gone or after restart; no test for a
removed local package's snapshot tombstone, legacy-only favorites after
uninstall, remote ID reuse/version change, or focus after catalog reorder.
These gaps remain. The present catalog tests validate current-page routing,
not the stale saved-favorite resolver.

No result here proves a public website is reachable, a plugin ZIP is actually
downloaded, progress/cancellation works against a live transfer, a map loads,
map arrival is verified, a lesson uses that map, a plugin activates, or a native
menu renders/focuses correctly. DOWNLOAD-01 and MAP-ARRIVAL-01 remain the
source-level references for those boundaries.

## Fingerprints

Hashes identify the selected test/source bytes used by this run. The report
keeps relative paths only.

| File | Bytes | SHA-256 |
|---|---:|---|
| `tests/test_community_discovery_bridge.py` | 13,446 | `24c024a1debe357601cf0551f1fbdc6dbf58b888074700a21e6cc18c0ca100c3` |
| `tests/test_workshop.py` | 7,722 | `07778050151f170934b750c79db0efe76611466a8b55db6cb93730f25a268a47` |
| `tests/test_bridge.py` | 83,171 | `5b3bafe6819319a9b77d332a9c9c0db78dcdc5aaf95781482429d275b1d39cec` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/community_discovery.py` | 37,834 | `015787c05fa9388c86fc598b475e1b549688181532993ceac7937287262ae8dd` |
| `src/my_career_training/workshop.py` | 13,655 | `4dea4b359f612389d6186c6fed640c2ee207bf92b4ad1bd6b4e4d56bfb9eb945` |
| `src/my_career_training/content.py` | 10,722 | `da2530e3b0894ab40b030017e09c79326d90f296c00930a4da30d55c95cbcfd4` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `pyproject.toml` | 1,221 | `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b` |
