# SDK-01: installed PluginSDK/BakkesMod symbol compatibility

## Scope and evidence boundary

Read-only local artifact inspection. I used the connected REA offline PE export/import inspectors and the existing CMake-pinned SDK headers. No process attach, game launch/input, compile, or whole-game executable analysis was used. Installation paths are kept out of this sanitized report; the exact paths were sent privately to the coordinator.

The two DLLs are identified by SHA-256 and byte length below. Windows FileVersionInfo returned null for both FileVersion and ProductVersion. A complete PE symbol table proves that names are present in these files; it does not prove a runtime call succeeds or that an arbitrary plugin was linked against this same SDK build.

## Artifacts and PE coverage

| Installed file | Bytes | SHA-256 | File/product version metadata | Static inspection coverage |
|---|---:|---|---|---|
| `pluginsdk.dll` | 1,947,136 | `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` | FileVersionInfo fields: null | Exports: 8,801/8,801, complete. Imports: 218 functions across 2 DLLs, complete; no delay imports. |
| `bakkesmod.dll` | 4,638,208 | `1b3226b447606f5552396907e34655de099202f371441bd4ce09bb6c74f20e3e` | FileVersionInfo fields: null | Exports: 4,471/4,471, complete. Imports: 290 functions across 13 DLLs, complete; no delay imports. |

REA Evidence: `ev_1ec56e5d3776f7c42066cf5c187c1fc813c153deeaed91f2614766298f1c6796` (PluginSDK exports), `ev_98139dec10aadea732835d05b03ed46b1d37b94bd5cfa3c141e3f47443c48ad2` (BakkesMod exports), `ev_cc856149fb00dc127f43d9a9a067cfa9466ade5a228b983cffa5e1a78be61913` (PluginSDK imports), and `ev_c941e8429cc7797924423a0167beb737ba37a2674fad5a1bf1ae9b23d075f1d6` (BakkesMod imports). All four report complete table coverage.

## SDK pin and declarations

The project CMake configuration fetches `BakkesModSDK` at commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, with archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`; it includes that cache's headers and links `lib/pluginsdk.lib` (`plugin/CMakeLists.txt:26-28,46-47`). The local dependency is an extracted FetchContent cache; its ancestor Git identity is not treated as the SDK revision.

The cached headers in the configured dependency path declare:

- `BallWrapper::GetbFadeOut()` and `GetbEndOfGameHidden()` returning `unsigned long` (`BallWrapper.h:31-37`). These flag accessors are not declared as a separate `BoolWrapper` value type.
- `ServerWrapper::GetGameTimeRemaining()` returning `float` (`ServerWrapper.h:61`) and `GameEventWrapper::GetGameStateTimeRemaining()` returning `int` (`GameEventWrapper.h:73`).
- `GameWrapper::GetPsyBuildID()` and `GetBakkesModVersion()` (`GameWrapper.h:65,157`).
- `ActorWrapper::IsNull()` const and non-const, plus explicit bool conversions (`ActorWrapper.h:25-28`). `BallWrapper` derives through `RBActorWrapper` from that actor wrapper hierarchy.

## Name comparison

| SDK API | `pluginsdk.dll` exports | `bakkesmod.dll` exports | Import observation |
|---|---|---|---|
| `BallWrapper::GetbFadeOut`, `GetbEndOfGameHidden` | Present | Present | Not imported by PluginSDK from the host; each is exported in both complete tables. |
| `ServerWrapper::GetGameTimeRemaining`, `GameEventWrapper::GetGameStateTimeRemaining` | Present | Present | Exported wrapper names exist in both complete tables. |
| `GameWrapper::GetPsyBuildID`, `GetBakkesModVersion` | Present | Present as `BMCore` functions | PluginSDK's complete import table imports the two `BMCore` version/build functions from `bakkesmod.dll`. |
| `ActorWrapper::IsNull` | Present (const and non-const forms) | Present (const and non-const forms) | Confirms the base wrapper null-check symbols; no separate `BallWrapper::IsNull` export is needed for its inherited declaration. |
| A class/symbol named `BoolWrapper` | Not found in pinned wrapper headers or either complete export-name inventory | Not found | This is an exact-name absence only; it does not rule out aliases or another representation. The two `Getb...` declarations use `unsigned long`. |

The symbol presence is a positive static compatibility signal: the installed shared DLLs expose the requested wrapper entry points, and the SDK DLL resolves its version/build probes through `bakkesmod.dll`. It is not runtime-call evidence. FileVersionInfo returned null fields, and this inspection did not hash the import library or inspect the import table of a produced plugin binary, so it cannot establish which `pluginsdk.lib` was used by a particular build or prove loader resolution on this installation.

## Next useful probe

If a built plugin artifact is available, inspect its PE import table against these two complete export inventories and the pinned import library, without loading the game. That will establish which exact decorated symbols the candidate plugin requests. Any claim that a getter returns correct live state still requires an explicitly authorized runtime observation; no such observation is made here.
