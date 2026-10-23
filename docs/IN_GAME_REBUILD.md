# Offline in-game rebuild

Owner direction, 23 October 2026: the desktop shortcut starts the current installed Rocket League in its supported offline/EAC-off mode. The player uses an in-game My Career interface for Career, Training, Schedule, Season, Squad, Workshop, Garage and Settings. No online features in this experience. Preserve existing AppData careers.

## Shared implementation contract

The existing Python career/save engine runs as a background service (`--in-game`). A BakkesMod C++ plugin owns the visible interface. Custom plugin windows run inside Rocket League; full native Scaleform replacement is not yet demonstrated. No proprietary game assets are redistributed. Use installed-game assets only through verified runtime APIs.

IPC is local files under `%LOCALAPPDATA%/MyCareerTraining/bridge/`: `state.json` is atomically published by Python every 100 ms when changed; `commands/<uuid>.json` contains `{protocol:1,id:<canonical uuid>,session:<bridge session nonce>,action:<allowlisted action>,payload:{...}}`. Commands are atomic rename from `.tmp`; max64KiB; at most32 per tick. State adds `protocol:1`, `bridge_session`, `published_at` (Unix seconds), `offline:true`, `telemetry`, `recordings`, `providers`, `workshop`, `plugin` and `command_ack:{id,ok,error}` to Backend.state. Never accept stale-session commands or arbitrary executable/path requests. Plugin ignores stale state and never modifies the save directly.

Plugin uses Backend action names from INTEGRATION_CONTRACT.md; additional actions: `return_hub {abandon:bool}`, `quit_game {}`, `workshop_favorite {id}`, `play_workshop {id}`, `choose_provider {id}`, `install_provider {id}`, `play_recording {id,recording_id?,mode?,lead_seconds?}`, `stop_ghost {}`, `training_settings {key,value}`. `settings` remains available for UI preferences while playing but launcher paths require idle. Online actions are rejected in in-game mode.

State `telemetry` includes observed logical controller actions, car/ball physics, phase and active lesson ID. Controller graphic is PlayStation by default; bindings must be configurable and logical action displays must not claim raw physical button capture. Ghost demo provenance must remain explicit; no synthetic animation advertised as a verified expert run. Show unavailable demonstration explanation and allow player recording/import until a real permitted teaching recording is supplied.

## Ownership

- Root: app entry/background service, local bridge IPC, Windows offline bootstrap, Python bridge/session/worker/adapter integration, final review/release.
- Plugin worker: `plugin/` including CMake, pinned SDK/ImGui/json dependencies, C++ plugin lifecycle/UI/controller overlay, in-game controls and cosmetic capability probes. No Python changes.
- Training worker: `training/` plus new training tests; pure overlay/ghost playback APIs and clear teaching provenance. No game_worker.py edits.
- Bot worker: `bots/`, provider package scripts and provider tests. No career.py/worker edits; send integration API to root.
- Community worker: content.py, workshop.py and related tests/docs; local installed Steam Workshop discovery/catalog/favorites, verified map launch metadata. No bridge edits.
- Package worker: `.github/workflows/`, `packaging/`, packaging scripts/tests only; compile plugin on Windows and include in package, preserve saves.
- QA: read-only integration review and targeted tests; report failures to owners.

## Required evidence

Local contracts, Windows DLL compilation/package checks, and actual Steam game behavior are separate gates. Initial target: launch → in-game hub → lineup → fixture → saved result → hub → working training, with controller display and accessible ghost controls. Test team lock, idle protection, named teams, menu input/focus, repeat transitions and current game/Bakkes compatibility on Windows. Do not label these game-tested based on compilation or mocks.

## Design refinement

Opus 5.5 handoff, optional after functional verification: refine original blue/orange sports-menu typography, spacing, focus states and controller visualization. Keep actions, accessibility, save semantics and capability labels intact. Model availability is not a runtime dependency.
