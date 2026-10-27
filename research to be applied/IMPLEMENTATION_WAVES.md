# Implementation waves from the research

This is a proposed build order, not a claim that the changes are built or game-tested. Reconcile the current checkout with [source provenance](source-provenance.json) before assigning files. Preserve Lessons, Workshop, Mods and Favorites and direct selection of every supported practice tier. The separate rank menu is an explicit user requirement.

## 1. Make each attempt and result trustworthy

**Player result:** the selected lesson starts in its authored setup, the timer follows an explicit pause policy, and Retry cannot silently lose a completed attempt.

- Keep a session/attempt/profile identity through setup, ready, active, completed and saved acknowledgement. Confirm the observed whole-actor setup before starting the clock. Ball angular velocity is currently outside the confirmation gate.
- Decide whether a real pause suspends a legacy lesson or interrupts it. An open MCT overlay alone does not establish a real pause. The documented RLBot elapsed clock advances during pause; actual installed packet delivery still needs observation.
- Specify terminal ball behavior separately from timeout detection. The current terminal path does not hide the ball. Installed fade wrappers are replay-gated, so they are not a supported Soccar solution. Generic actor hiding remains a candidate whose visibility, collisions, scoring and restore effects need testing.
- Keep save acknowledgement separate from visual feedback. Cover delayed/lost acknowledgement, write failure, duplicate completion and Return, not only successful Retry.

Start in `training/engine.py`, `game_worker.py`, `bridge.py` and the relevant native observer/host adapter. Evidence: [reset readiness](campaign/reset-ready-01.md), [pause clocks](campaign/pause-clock-01.md), [attempt end](campaign/attempt-end-01.md), [persistence](campaign/persist-01.md), [fade restriction](campaign/sdk-fade-01.md), [generic visibility](campaign/sdk-actor-visibility-01.md).

Acceptance needs an owned offline session with exact artifact identities: settle failure, ordinary launch, actual pause/resume, timer expiry, retry after saved acknowledgement, delayed acknowledgement and Return. Synthetic fixtures can prove engine transitions; they cannot prove game rendering or physics.

## 2. Define profiles, then wire lesson to rank to situation

**Player result:** selecting a lesson opens Bronze through Supersonic Legend on a separate page; Back restores the selected lesson and the chosen tier reaches setup and grading.

The frozen candidate has an unused `LessonDifficulty` page builder, a side-panel rank route for Power Shots, and direct launches for the other lessons. Wiring the page is necessary but does not create the missing rank content. Only Power Shots currently has twelve situations and eight profiles. Author real geometry, timing, required evidence and failure conditions for the other lesson/tier combinations. Keep target completion distinct from technique grading where current completion rules do not establish the named mechanic.

Start in `NativeCareerLayout.h`, authored menu actions, `bridge.py`, `training/catalog.py` and scenario/profile selection. Carry stable lesson/tier/situation/version IDs rather than row indices. Evidence: [navigation](campaign/native-navigation-01.md), [curriculum](campaign/curriculum-01.md), [eight-lesson matrix](LESSON_EVIDENCE_MATRIX.md), [shot picker](campaign/custom-shot-flow-01.md).

Acceptance: all eight rank choices per supported lesson, Back/reopen/favorite routes, matching setup and grading, one qualifying example and a meaningful near miss for each declared profile. An unavailable profile must remain visibly unavailable until authored; labels alone are insufficient.

## 3. Apply the stock browser and HUD composition

**Player result:** the browser retains MCT content while using a consistent row hierarchy, selection feedback, controller prompts and in-level information.

Stock row metadata now establishes title/classification, alternate creator or publication/date information, favorite and loading states, shrinking text and focus transitions. Local geometry is available, but imported fonts/art and final screen transforms are separate. Use the metadata to author MCT's own layout. Preserve stable selection through refresh and meaningful empty/error/loading states. HUD time formatting and <=3 countdown-label behavior do not establish ball expiry.

Start in native layout builders, authored menu/HUD views and their state producers. Evidence: [browser rows](campaign/native-pack-row-01.md), [browser flow](campaign/native-pack-browser-01.md), [HUD flow](campaign/hud-flow-01.md), [HUD timeline](campaign/hud-timeline-01.md), [controller evidence](campaign/controller-evidence-01.md).

Acceptance: mouse and controller focus, Back, refresh during selection, long titles, text scaling/aspect ratios and a real attempt's lesson/tier/timer/progress identity. Keep controller artwork, effective bindings and sampled logical inputs distinct.

## 4. Make Training settings show actual feature status

**Player result:** Training opens first, checkboxes persist preferences, pending/conflict/unavailable states explain whether the requested effect is active.

Use a feature-specific adapter for each external effect. Downloads, installation, loaded plugin, applicable game context, successful value readback and visible effect are different milestones. One-shot ball feeds should be actions, not invented persistent enabled modes. Capture written values and restore only values still owned by the session; preserve later player edits. A stored preference must not masquerade as observed active state.

Start in `NativeMatchLayout.h`, the pause view, bridge preference routes and individual adapters. Evidence: [settings](campaign/settings-01.md), [stock checkbox route](campaign/stock-training-settings-01.md), [control matrix](PLUGIN_CONTROL_MATRIX.md), [download lifecycle](campaign/download-01.md), [modifier context](campaign/mod-measurement-01.md).

Acceptance: On/Off/readback/visible effect, rapid toggle, missing or incompatible plugin, online/replay exclusion, user edit conflict, Return and abnormal recovery. Add each plugin only after its own context and lifecycle are established.

## 5. Extend ghosts, maps and garage through explicit contracts

These can proceed as separate file-owned tasks after the shared lifecycle contract is fixed.

| Feature | Next concrete result | Required proof |
| --- | --- | --- |
| Ghost | One declared clock for synchronized car/ball/input, profile and assistance compatibility, clear capture origin and terminal policy | Synthetic interpolation/gap controls, then owned-session alignment on observed setup, pause, retry and cleanup; current outline is not a simulated car actor |
| Workshop | Selected package request tied to observed playable arrival, dependencies and supported geometry | Exact map identity after transition, spawn/geometry validation, Pause and Return; command completion alone is insufficient |
| Garage | Valid product/paint preview and local apply with per-field restore ownership | Visible appearance and compatibility, later player edits preserved, partial failure and Return; catalog availability is not account ownership or online visibility |
| Native packs/favorites | Exact stable destination, honest offline availability, separate application and game favorites | Reopen/remove/missing source, exact pack load and progression where supported; never substitute a different drill silently |

Evidence: [paired ghost](campaign/ghost-02.md), [ghost lifecycle](campaign/ghost-playback-01.md), [recording trust](campaign/import-identity-01.md), [map arrival](campaign/map-arrival-01.md), [garage catalog](campaign/garage-catalog-01.md), [restore reproducer](campaign/cosmetic-restore-probe-01.md), [favorite recovery](campaign/favorites-02.md).

## Assignment and completion rules

Give each research question one Luna max owner. Give each code change a DeepSeek builder and a different DeepSeek reviewer, with explicit files and acceptance conditions. Reconcile review findings against actual source; a review is not a runtime receipt. Keep full native compilation and game acceptance coordinated with the active game owner. Publish source findings, offline observations and game acceptance as separate evidence levels. This document orders future work; it does not mark any wave complete.
