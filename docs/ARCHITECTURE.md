# Architecture

My Career Training is a local Python 3.12/PySide6 Qt Quick application. Rocket
League owns the real match, physics, assets and human controls. The application
owns career bookkeeping, lessons, settings and saves. The Windows RLBot v5
integration runs in a separate worker process. No cloud career account or runtime
AI subscription is part of this design.

## Modules and ownership

| Module | Responsibility |
|---|---|
| `app.py`, `ui/` | Qt application, QML pages, focus/accessibility and app controller navigation |
| `bridge.py` | Validated UI actions, durable state transitions, worker requests/events and lifecycle coordination |
| `career.py` | Pure career/squad/season rules, fixtures, seeded simulation, standings, title playoffs and progression |
| `storage.py` | Versioned JSON, validation, atomic replacement, backup/import/export and process-held single-instance lock |
| `game_worker.py` | Owned core process, SDK connection, bounded telemetry handling, bots, training reset/render and durable result outbox |
| `adapter.py` | Exact v5 FlatBuffer configuration, packet normalization, desired states and final-score interpretation |
| `bots/` | Pure perception/tactical/driving rules, role weights, level parameters and provider capability manifest |
| `training/` | Eight data-driven lessons, observations, assistance preferences, bounded recordings, compatibility and ghost geometry |
| `lifecycle.py`, `platforms.py` | Ordered online handoff, launcher detection/normal launch and identity-scoped game closure |
| `content.py` | Curated bot styles, attributed creator links and validated local map-file import |
| `packaging/`, `scripts/` | Windows executables, Inno installer, portable/source archives, licenses and package acceptance checks |

The pure modules do not import the live SDK. Their tests use constructed data;
that makes rules testable without claiming those packets came from Rocket League.
The optional reference starter is not a runtime dependency.

## UI and process boundary

QML reads `backend.state` and calls `backend.dispatch(action, payload)`. The bridge
publishes explicit session state, errors, saved results and capability limits.
Qt's event loop remains responsive while QProcess and the isolated worker handle
game activity. A source run uses `python -m my_career_training --worker`; the
Windows package uses the separate console `MyCareerTrainingWorker.exe` beside
the windowless GUI. Frozen executables are never treated as Python interpreters.

Worker transport is UTF-8 JSON lines, **protocol 1**. Startup emits `ready` with
`protocol: 1`. Requests include an `id` and `type`; acknowledgments retain the
request ID where applicable. `ping` returns `pong`; `shutdown` returns `stopped`
and exits. `start` carries a canonical session UUID, immutable fixture snapshot,
settings and optional career/lesson/preferences. Runtime commands include stop,
retry, preferences, recording playback and attempt acknowledgment. A normal
`stop` stops a session without defining a completed match.

Events report connection state, owned process identity, telemetry, attempts,
results and errors. Startup/stop/exit deadlines and error states expose missing
connections rather than produce fabricated success. The worker bounds/coalesces
high-rate telemetry while retaining terminal packet order. Frame gaps weaken
training conclusions; telemetry and rendering do not write every sample to disk.

## Career and exactly-once result flow

The squad consists of one human and four persistent bot recruit identities.
Each fixture snapshots format, map, seed, lineup, provider parameters, difficulty
and session attempt. Changes apply only to future unstarted rounds; historical
lineups are validated against their own fixture's format.

The default season is a four-club double round-robin with 12 league fixtures:
six for the human club and six rival fixtures. Rival simulations use persisted
seeds/strengths, stay labeled simulated and cannot reroll on restart. Points,
goal difference, goals scored and head-to-head rules lead to persisted-draw
seeded playoffs if the title still needs resolution. A draw seeds a bracket;
it does not award a title.

For a human fixture:

1. Save the pending fixture and fresh session identity before launch.
2. Accept final scores only after observed active play followed by the actual
   terminal match phase, including overtime. A disconnect or clock reaching
   zero does not complete the fixture.
3. Before publishing the result event, atomically write the worker's durable
   `outbox/<session-id>.json` receipt.
4. Validate the fixture/session/result identities, apply score/XP/rewards once,
   then durably replace the career save.
5. Delete the receipt only after that save commits. On restart, replay a valid
   surviving receipt through the same idempotent rule.

A duplicate terminal packet or crash after save but before acknowledgment must
not award twice. A failed write leaves a recoverable receipt. An abandoned
attempt awards nothing and can restart from kickoff. Manual missing-result
recovery is explicitly attributed to the owner and retains an explanation.

## Persistence and recordings

Schema-versioned state lives under `%LOCALAPPDATA%\MyCareerTraining` on Windows.
The installer/runtime directory is read-only application material. The store
validates before replacing data, preserves last-good/imported originals, rejects
unsupported schemas and holds an OS lock to prevent competing application saves.
Domain operations create new dictionaries so rejected changes do not mutate the
active state. Exported save JSON includes recording metadata; recording sample
files live separately under `recordings/` and need preservation alongside it.

Training definitions hold reset states, targets, events, help defaults and
reference status. The engine waits for observed reset/settle conditions, records
actual normalized human actions and qualifies observations when samples are
missing. Recordings retain lesson/setup/physics/provenance compatibility.
Wireframe ghost rendering has no collision object. Personal bests and imported
success claims never become validated expert teaching references automatically.

## Game and launcher ownership

The app refuses pre-existing game/core sessions before career launch. It tracks
an owned Rocket League process by PID, creation time and executable identity,
rather than treating a launcher PID or SDK socket as game ownership. Human slot
mapping is checked before bot controls; the human receives no bot inputs.

The Play Online lifecycle saves first, freezes further career transitions,
stops resets/ghosts/bot work, drains late final-result events, saves again,
gracefully closes only the owned game, waits for actual process exit, then asks
the selected platform for its normal launch. SDK shutdown alone is insufficient.
Timeouts preserve recovery and prevent a conflicting second session. The UI
reports a launch request, not verified matchmaking availability. Existing platform
EAC preferences remain the user's settings.

The shipped code targets EAC-off offline use. Game-tested ownership, Epic startup
behavior, telemetry mapping and graceful close still need Windows receipts;
source inspection and mocked lifecycle tests cannot establish them.

## Scope and evidence

Original specialists are an unranked local baseline. The bot-provider boundary
can support future licensed providers without changing career rules. The map
import boundary validates/copies local packages but does not certify a loader,
creator permission or gameplay. Human inventory grants are absent. Two-captain
network play remains research in `MULTIPLAYER.md`; no hosting/firewall changes
are V1 dependencies. The 22-player project and extra modes are out of scope.

Read `FEATURE_MATRIX.md` for implementation versus local/Steam/Epic evidence,
`COMPATIBILITY.md` for inspected SDK hazards, and `BUILDING.md` for exact build
versions and package checks.
