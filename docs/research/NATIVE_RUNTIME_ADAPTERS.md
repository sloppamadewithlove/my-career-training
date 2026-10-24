# Runtime adapter follow-up

Checked 23 October 2026. This is source research, not a successful game test.

The pinned BakkesMod SDK exposes menu-stack names, event-name hooks, specific
game wrappers and native modal dialogs. It does not expose a GFx movie, menu
node or generic Unreal property wrapper. Opaque hook parameters are not a
validated menu ABI. The schema-2 route trace remains diagnostic only.

Three additional implementation leads were checked:

| Lead | Evidence | Missing proof |
| --- | --- | --- |
| [MIT Rocket League type map](https://github.com/ObscuritySRL/rlsdk/tree/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01) | September Steam layout includes GFx and menu types; external memory reader examples | Match to October game build, object lifetimes, game-thread invocation and pre-action interception |
| [MIT UE3 generator](https://github.com/CodeRedModding/CodeRed-Generator) | A maintained generator for independently validated engine profiles | No current Rocket League 2.78 profile; the separate Rocket League generator profile located is from 2023 |
| [USVFS](https://github.com/ModOrganizer2/usvfs) | A process-local virtual file view can leave backing files unchanged | No demonstrated Rocket League package round-trip, launch compatibility or Career callback bridge |

None is a ready native-menu adapter. No numeric offsets, generated game headers
or package contents from these leads have been copied into the project.

The SDK also exposes `ExecuteUnrealCommand`, but returns no output callback.
[Epic's UE3 console reference](https://docs.unrealengine.com/udk/Three/ConsoleCommands.html)
describes read-only `OBJ LIST`, `OBJ DUMP` and `GETALL` operations. Their presence
and output channel in the current retail Rocket League client remain unknown.
The same reference describes `SET` as affecting every instance of a class and
its subclasses: **do not use that command to edit an individual menu button**.
Offline mod support does not establish that these engine commands are present.

The next evidence is the user's sanitized Windows baseline, followed by a
separately identified offline host test. Native integration then needs a
read-only observation of actual home-menu objects, one reversible label change,
and one callback that consumes the original action. A route trace or a successful
DLL build does not satisfy those steps. The public installer stays held.
