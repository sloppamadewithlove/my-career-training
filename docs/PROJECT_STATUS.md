# Current project status

Updated 24 October 2026. Start here when continuing the project.

## Active repair

The published `native-candidate-2026-10-24` ZIP, compiled from `2fed6cd`, failed
player testing. Two game logs show `Bad name index 309227379/163` while loading
the private `GFX_MainMenu_SF.upk`. The installed source package still matches its
pinned hash. The worker console is a separate packaging problem.

The current repair branch is `fix/windows-startup-and-download`. Work includes
one player executable, a private worker, a Windows test installer, an explicit
early-startup failure message, and diagnosis of the actual game startup failure.
Do not label a replacement playable until its live acceptance checks pass.

## Evidence collected during this repair

- A controlled offline launch through the existing native launcher and file-view
  DLL reached the visible stock main menu using a byte-identical private copy of
  the original menu. BakkesMod was not loaded. This tests the baseline launch
  path, not My Career functionality.
- The actual EAC notice asks whether to view instructions for enabling EAC.
  No dismisses that notice and leaves the offline session running.
- The failed composed menu also crashes with no BakkesMod loaded. Recompressing
  the original movie without changing any export bytes fails with a different
  bad-name index. Adding only an inert movie metadata tag fails with a bad-export
  index. The original package with one unused trailing byte reaches the main
  menu.
- A numeric-only live trace then measured the mismatch: the game queried a
  3,418,271-byte path and opened a 3,450,552-byte private handle. The repair makes
  exact-path attribute queries describe the same private file as the open.
  The recompressed test remained running after this change; visual acceptance
  was paused when Windows switched to its screen saver. Custom-menu and gameplay
  acceptance are still pending. Directory enumeration is not redirected.
- Exact GPT-6 Luna with max reasoning ran through Codex CLI. Its broad source
  run passed 862 tests and skipped 14; four temporary-map tests detected the real
  open game. The four pass with that dependency isolated. Their fixtures are
  fixed; the real recovery refusal is unchanged.
- After isolating the synthetic tests from the real running game/helper, the
  current full Python run passed 881 tests with 15 optional tests skipped.
  Explicit positive helper-refusal checks remain active. Lint passed.
  The native plugin's 25 tests passed with the movie trial both on and off;
  the native launcher's 12 tests also passed.
  These are code checks, not a playable-game acceptance result.
- The frozen app passed its offscreen UI, private-worker protocol and runtime
  checks from a Unicode path. The new installer review added full bundle hashes,
  a clean-source rebuild, a pinned compiler and fresh-output enforcement.
- Existing product registration prevented a safe isolated installer lifecycle
  test on the player PC. A dedicated GitHub-hosted Windows workflow builds and
  tests the exact installer without touching that registration. Its result is
  pending; this is not an installer-pass claim.
- Grok 4.7 High runs through Cursor CLI are investigating the format/runtime
  failure. Agent participation is not evidence of a successful game fix.

## Supported target and remaining acceptance

The candidate pins Steam build `25914621`, Rocket League build
`261013.63066.530866`, and BakkesMod core `229`. Unknown builds are refused.
Epic has not passed its own acceptance test.

Career, Training, Garage, Workshop, Community, Settings, Back and Quit must lead
to real actions. Source routing tests exist. Visible navigation, a complete
career match, practice, stock-screen returns, cosmetics, maps and restoration
still require exact-artifact live evidence.

Necto/Nexto support up to 3v3 here. 4v4 uses Ground Specialists. Creator rank
estimates are not current rank certifications. Full car-body customization,
expert teaching demonstrations, no-idle-kick behavior, arbitrary community
plugins and full online-route suppression remain open.

## Build and release rules

Use the native candidate pipeline in [BUILDING.md](BUILDING.md). The older
`my-career-training.spec` pipeline must not silently replace the native candidate.
A test installer must be labelled as a test; its source commit, package smoke
receipt and hashes must agree. The stable release stays held until
[native acceptance](NATIVE_ACCEPTANCE_SESSION.md) passes. Historical counts and
preparation receipts are not new live game tests.
