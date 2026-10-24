# Native movie composition

`scripts/native_movie_compose.py` builds one development movie in memory. `compose_movie` accepts the pinned `MainMenu.gfx` bytes and the compiled `menus.MctRootMenu` ABC, plus a session nonce and a local view URL. It returns `{"data": bytes, "metadata": dict}`. It does not write a file, launch Rocket League, or install a package.

The public entry accepts only two hashes. The movie SHA-256 is `57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`. The class ABC SHA-256 is `9d423d2e39743473bec792c0ca38f3b28946238183b03bbfb0a4681767721768`, the current `native_ui/compiled/MctRootMenu.abc` (6124 bytes, ABC 46.16, 23 method bodies). A mismatch is rejected before the placeholder strings are bound. The manifest records source SHA-256 `1ba9168d4a32e9c0c3ea4c7d7bbe29fda9aae35d3a985d9f3a6c382d91a49600` for `native_ui/menus/MctRootMenu.as`. The composer stores that value and does not read the ActionScript file.

There is no FFDec or Java step. The transformer uses the pinned offsets below, checks them against the movie, and splices only those sites. It is not a general ABC rewriter. Original GFX and the output are limited to 16 MiB. The class ABC is limited to 64 KiB. The view URL is limited to 4096 characters.

## Pinned movie

The owned movie is uncompressed GFX version 20, one frame, 181 tags. DoABC is tag 177, flags 1, with an empty name. SymbolClass is tag 178 and maps character 83 to `RootMenuMovie`. The original ABC is 46.16 and SHA-256 `97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42`.

| Field | Value |
|---|---|
| String count | 13849 at offset 2048, pool end 274271 |
| `menus` PackageNamespace | index 814, kind `0x16`, URI string index 5806 |
| Multiname count | 12205 at offset 282536, pool end 335281 |
| `RootMenuMovie` superclass | multiname 5940, `menus::RootMenu`, bytes 446019..446021 |
| Script initializer | script 700, method 11548, code at 1113629, 73 bytes |
| Code SHA-256 | `b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174` |

The initializer has no branches and no exception records. PC 46 is `getlex` of multiname 5940, PC 49 is `pushscope`, PC 50 is `getlex` of the same multiname, and PC 53 is `newclass` of class 702. Both 5940 and the appended multiname index 12205 are two-byte U30 values, so those three operands do not move any later instruction.

Before changing a byte, the composer checks the pool counts, the `menus` namespace kind and URI, the three old operands, the nearby opcodes, the code hash, and the SymbolClass mapping. The string pool gains `MctRootMenu` at index 13849 (12 bytes). The multiname pool gains `QName(PackageNamespace("menus"), 13849)` at index 12205 (5 bytes). Those 17 inserted bytes are the only shift. The original `menus::RootMenu` QName at ABC offset 309137 stays in place aside from that shift. `RootMenuMovie` keeps its name and character 83.

The new DoABC is inserted after the original DoABC and before SymbolClass. Its flags are 1, its name is `MCTNativeMenu`, and its payload is the bound class ABC with no SWF header and no SymbolClass of its own. Every original non-ABC tag is copied unchanged. The GFX header length is the only header field rewritten. The output has 182 tags and two DoABC tags.

## Session binding

The class ABC contains one `__MCT_VIEW_URL__` string and one `__MCT_SESSION__` string. The composer walks the integer, unsigned, double, and string pools and replaces those two entries. It does not search the rest of the ABC for the same bytes. Pool indexes and counts stay the same. A longer URL may widen that entry's U30 length prefix; the following bytes move, and their contents stay the same.

The session must be a canonical lowercase UUID, 36 characters. The view URL must already be a canonical `file:///X:/.../native-view.json` path: an uppercase drive letter, no authority, query, fragment, credentials, dot segments, encoded slash, raw space, or non-ASCII character. Space and non-ASCII path text have to be uppercase UTF-8 percent-encoding. The caller supplies the path. This function does not open it and has no HTTP client.

## What this does not show

`production_ready`, `runtime_verified`, and `gfx_initialization_order_verified` stay false. The metadata also records that the file-view read and the `DevUtil.Log` command path are not verified. Keeping the original classes and appending `MctRootMenu` does not show that Scaleform initializes the added DoABC, that `RootMenuMovie` constructs the new subclass, or that a future host consumes the view file. The class still extends the external `BranchingMenu` declared by the private game SDK.
