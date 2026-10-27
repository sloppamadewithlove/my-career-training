# My Career Training research handoff

The requested eight-hour window ran from 06:54:12 to 14:54:12 UTC on 27 October 2026 (02:54–10:54 Eastern). The folder contains 111 campaign reports, ten initial findings, source archives, diagnostic evidence and isolated reviewed patches. All eight hourly monitor checkpoints were recorded.

The research is organized around preserving **Lessons, Workshop, Mods and Favorites**, opening a **separate Bronze–Supersonic Legend menu** after lesson selection, and improving the native browser and training experience. Completed research is not completed product functionality.

## What builders should address first

1. **Make the attempt lifecycle consistent.** Setup, ready/go, pause, timeout, result saving and retry must share an attempt identity. Power Shots interrupts on a real pause; the other lessons can continue accumulating time from advancing paused packets. Ball disappearance on timeout is absent from the audited implementation. The inspected replay fade functions are not a supported ordinary-training solution; the public actor visibility wrapper is a candidate requiring owned-game verification. See [pause contract](campaign/pause-policy-01.md), [attempt end](campaign/attempt-end-01.md), and [visibility evidence](campaign/sdk-actor-visibility-01.md).

2. **Extend actual lesson profiles.** Power Shots has twelve situations and eight rank profiles, including a separate rank screen. The other seven lessons still need that authored coverage. Its rank parameters change setup pressure and timeout, while grading criteria remain shared; projected arrival/window values are estimates, not measured physics or enforced extra scoring windows. Preserve twelve situations per lesson, with eight variants, and distinguish target completion from the named technique. See [lesson matrix](LESSON_EVIDENCE_MATRIX.md) and [profile propagation](campaign/rank-profile-propagation-01.md).

3. **Finish native browser and HUD acceptance.** Stock row hierarchy, local geometry, selection feedback, loading states and input routes are documented. Match MCT content and stable identities to those conventions, then verify the actual composed movie with mouse/controller input, remaps, long titles, resize, Back and resume. Extracted class names and fonts do not prove runtime availability or final appearance. See [stock row evidence](campaign/native-pack-row-01.md), [motion](campaign/stock-menu-motion-01.md), and [HUD](campaign/hud-timeline-01.md).

4. **Give each checkbox an honest effect and restoration contract.** A saved preference, downloaded file, loaded plugin, cvar readback and visible effect are separate states. Unsupported plugins need individual adapters; one-shot ball feeds remain actions. Normal Return, disconnect, unload and crash are different recovery boundaries. See [plugin control matrix](PLUGIN_CONTROL_MATRIX.md), [download lifecycle](campaign/download-01.md), and [settings](campaign/settings-01.md).

5. **Complete the remaining feature contracts.** Ghost playback currently draws a generic car outline and drops recorded ball samples in its pose path; a synchronized car/ball/input demonstration remains work. Workshop command completion does not prove arrival at the selected playable map. Garage catalog entries do not establish exhaustive historical skin coverage, valid preview/apply, ownership or online visibility. App favorites and game pack history remain separate. See [ghost lifecycle](campaign/ghost-playback-01.md), [map arrival](campaign/map-arrival-01.md), [garage catalog](campaign/garage-catalog-01.md), and [favorites](campaign/favorites-02.md).

The intended full curriculum is 64 lesson-tier profiles containing 12 situations each: 96 situation/tier cells per lesson, or 768 across eight lessons. That is the requested coverage matrix, not a count of completed implementations or game passes.

## Reproducible work included

The [diagnostic reconstruction instructions](campaign/reproducibility-handoff-01.md) identify the frozen project source, preserved licenses, dependencies and five recorded invocations across four Python diagnostics. They cover outcome attribution, import trust, pause clocks and serialized rendering. These are bounded offline observations using the stated fixtures, not game acceptance.

The [cosmetic conflict experiment](campaign/cosmetic-conflict-prototype-01.md) was built by a DeepSeek worker, reviewed by a separate DeepSeek worker, compiled and run, then reconstructed from its published files. All 22 declared scenarios produced the expected 44 production/prototype records. The proposed coupled-pair policy preserves later edits but can leave an MCT-written field behind; it is not a selected production fix and is not installed.

The [defender-attribution candidate](campaign/defender-attribution-candidate-01.md) supplies a small engine patch and focused regression tests. Its independent review, 15 focused passes, 298 selected regression passes and original six-case probe support the isolated fix. The unchanged baseline failed six new attribution assertions. Reconstructing the published source and patch also passed the focused suite. These are separate invocation results, not a combined all-feature or game pass. The patch is not integrated into the shared product checkout.

The [stock component inventory](campaign/stock-component-reuse-01.md) confirms that MainMenu already defines the button legend, category button and modal list classes. The training-specific row classes are absent from that movie's class table. Reference the existing definitions where appropriate and validate symbol/timeline dependencies in the composed runtime.

The [Bridge transport inspection](campaign/bridge-waiter-artifact-01.md) narrows render cleanup and message-budget risks in a pinned build-input DLL. It does not prove those bodies are the ones linked into the staged native server or that a live failure occurred.

## Before implementation or game testing

Reconcile the active checkout with [source provenance](source-provenance.json), assign one file-owned task per builder, and keep separate DeepSeek review. Luna max workers remain researchers and testers. Use the [implementation waves](IMPLEMENTATION_WAVES.md) for dependency order.

The campaign did not take control of the other chat's game, replace installed components, or compile the full native plugin. Game acceptance still needs an owned offline session on the exact source/movie/plugin/runtime combination. Keep historical game observations attached to their original artifacts; do not transfer them to the research snapshot by assumption.

The [hourly checkpoints](CHECKPOINTS.md) record actual document-monitor observations and separate coordinator checks. The monitor cannot wake Codex or prove uninterrupted worker activity. Its initial observation was at 07:04:03 UTC, after the campaign began at 06:54:12 UTC.

## Final source reconciliation

The active canonical checkout still requires comparison before integration. The [final source receipt](evidence/final-source-freshness.json) records all 21 selected paths and the 55 archived Python files. The shared research checkout changed during the final hour; those edits were left untouched. Research and test claims apply to their recorded hashes, especially the published source archive used for the defender patch. No source or runtime equivalence is inferred from a branch name.
