# SDK-DRAWABLE-01 — `UnregisterDrawables` ownership scope

## Result

The installed SDK wrapper does **not** establish whether drawable cleanup is scoped to the calling plugin or reaches other plugins. Its body forwards through an indirect `BMCore` interface slot, and the underlying host implementation is not present in this SDK DLL. I stopped at that boundary; this is not evidence for either per-plugin or process-global cleanup.

## Artifact and REA evidence

- Target: installed 64-bit `pluginsdk.dll`, 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` (same artifact identity as SDK-01/02/03).
- Static provider: Ghidra 12.1.4. No game process, input, attach, or installed-file writes were used. The REA target was closed after the queries.
- Exact exported name: `?UnregisterDrawables@GameWrapper@@QEAAXXZ`, ordinal 5160, non-forwarded, at `0x1800b1ff0`. Export table coverage was complete (8,801 of 8,801 entries).
- Function dossier: `void __thiscall UnregisterDrawables(GameWrapper * this)`, one basic block, complete single range, 14 body bytes (`0x1800b1ff0–0x1800b1ffd`).

Evidence IDs:

- Selected export row and complete export-table coverage: `ev_e2a2ecfdc3a738d75a53fae35c29f8ad8f49456d50b7b1ad3afd2549e53d4c65` (parent export evidence `ev_1ec56e5d3776f7c42066cf5c187c1fc813c153deeaed91f2614766298f1c6796`).
- Exact decorated symbol/name aliases: `ev_25feb558184353e84d20d5710bba12a56500d7052ad0fecde8ea9bbdb1312f0b`.
- Complete function body extent: `ev_86f8c4c0098fb54a4ab820dbe1c65069251f85eab8d2f362ea92ea96f4f459fd`.
- Decompiler observation: `ev_eebcdc8b893ef2852b7abb7c5f2cbaefac6c5ea9e9f347bf958ca30faef5eb0c`.
- Resolved-callee result and limits: `ev_f7a3a8a2830200f904264b045c164b250989a3f6a2fda5386803f96ae571aaaf`.

## What the wrapper shows

Ghidra’s pseudocode renders the only operation as a dispatch to `BMCore::UnregisterDrawable` through a function/interface pointer held by the `GameWrapper` object. The decompiler warns that it could not recover a jump table and treated an indirect jump as a call. The separate direct-callee query returned no resolved targets; its coverage is limited to resolved call references and explicitly leaves computed or indirect targets unknown.

The exported wrapper has no explicit plugin identifier or drawable handle parameter. That fact does not determine the ownership semantics: the instance or host-side interface may encode scope, but the `pluginsdk.dll` body does not reveal it. The public SDK header’s “every drawable” comment is therefore insufficient to distinguish “all drawables registered by this plugin” from cross-plugin cleanup.

## Compatibility implication

For BallPrediction’s call to `GameWrapper::UnregisterDrawables()`, installed-SDK evidence now confirms that the exported wrapper delegates cleanup to an opaque host interface; it does not settle whether another plugin’s overlay is affected. Keep the compatibility report’s conclusion unchanged: **drawable cleanup scope is unverified; test effects on other overlays**. The installed `pluginsdk.dll` wrapper cannot support a claim that the call is safe for concurrent overlays.

The narrowest additional static evidence would be the matching installed host’s `BMCore::UnregisterDrawable` implementation or the exact interface-slot target, with compatible binary identity. Until that implementation is available and joined to this SDK version, cross-plugin scope remains unknown. Runtime overlay testing is still required to establish visible effects.
