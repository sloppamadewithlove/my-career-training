# SDK-02 — installed plugin imports versus installed SDK exports

Read-only REA PE inspection at 2026-10-27 07:39:54 UTC. No binary was loaded,
replaced or executed. This continues SDK-01 by comparing an actual installed
plugin file with the installed SDK, rather than only comparing header names.

## Artifact identity

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| MyCareerTraining.dll, installed on disk | 591360 | `18569d2b321f30f20c018e8ba14a596d1ebb89ab785addda9777662c73b9887e` |
| pluginsdk.dll, installed on disk | 1947136 | `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` |

Plugin import inspection was complete: 243 functions across
16 DLL descriptors, no delay imports. SDK export
inspection was complete: 8801 exports. Every one of the
plugin's 64 named imports from pluginsdk.dll has an exact
decorated-name match in that SDK export inventory; none of those matches is an
export forwarder. Other system/runtime DLL resolution was not audited.

REA evidence: `ev_0bd50ae09781663abbde87b9d80b742b92415d2e1e21449b19566c1eb42ad0b6` (plugin imports),
`ev_e9afb11d9bd78476e44ad657dca30f3a4ec65012f9b5409da4c2ee5691c5a247` (SDK exports).

## Feature-related symbols

| API family | Installed plugin import table | Installed SDK export table |
| --- | --- | --- |
| `GetGameTimeRemaining` | No named import observed | Present |
| `GetGameStateTimeRemaining` | No named import observed | Present |
| `GetbFadeOut` | No named import observed | Present |
| `GetbEndOfGameHidden` | No named import observed | Present |
| `GetGfxTrainingData` | No named import observed | Present |
| `GetCamera` | No named import observed | Present |
| `GetCameraSettings` | No named import observed | Present |
| `SetCameraSettings` | No named import observed | Present |
| `IsKeyPressed` | No named import observed | Present |
| `GetPsyBuildID` | Present | Present |
| `GetBakkesModVersion` | Present | Present |
| `GetAllProducts` | Present | Present |
| `GetCurrentMap` | No named import observed | Present |

The installed file does not establish that the research source candidate is
currently deployed. For example, the candidate's built-in training observer
calls GetGfxTrainingData and the isolated lifecycle extension reads timer and
ball-visibility values; those named imports are not present in this installed
file. Build flags, source revision and deployment identity must be joined before
using a game observation to accept the candidate. Do not infer a specific build
flag or source revision from absent imports alone.

## Limits and next proof

This is exact static name compatibility, not proof of loaded-module identity,
DLL search order, ABI/layout compatibility, game-build compatibility or a successful
call. Standard/delay import absence does not rule out dynamic resolution or another
implementation. The file on disk is not proof of the file already loaded in memory.

For a future candidate: retain its source snapshot and build receipt; hash the
actual output and staged copy; inspect its exact imports against the intended SDK;
then, in the owned game session, establish which artifact loaded and collect the
specific getter observations. Do not reuse the currently installed file's clean
name comparison as acceptance of a newly built candidate.

The sanitized [machine-readable comparison](../evidence/sdk-02-import-comparison.json) records exact symbols, artifact hashes, coverage and limitations.
