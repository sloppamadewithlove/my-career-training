# Native movie composition

`scripts/native_movie_compose.py` builds one development movie in memory. `compose_movie` accepts the pinned `MainMenu.gfx` bytes and the compiled ABC that contains `menus.MctRootMenu` and `MctMainMenuScreen`, plus a session nonce and a local view URL. It returns `{"data": bytes, "metadata": dict}`. It does not write a file, launch Rocket League, or install a package.

The public entry accepts only two hashes. The movie SHA-256 is `57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`. The class ABC SHA-256 is `abc2d56ae90bcf764e75d9108ae8a0a6219a53fc299f3b28805fcfed5dcffc3e`, the current `native_ui/compiled/MctRootMenu.abc` (7836 bytes, ABC 46.16, 35 method bodies, two authored classes, no linked game classes). A mismatch is rejected before the placeholder strings are bound. The manifest records source SHA-256 `dd27703fb36a8959f47b8de68fc7c23dc51f177f1ce4b80470c1bc0b0cc61194` for `native_ui/menus/MctRootMenu.as` and `ed2528a5dc08fc2c522a8c9816282b50670ea9dafe402876da403caecad1ff6e` for `native_ui/MctMainMenuScreen.as`. The composer stores those values and does not read the ActionScript files.

There is no FFDec or Java step. The transformer uses the pinned offsets below, checks them against the movie, and splices only those sites. It is not a general ABC rewriter. Original GFX and the output are limited to 16 MiB. The class ABC is limited to 64 KiB. The view URL is limited to 4096 characters.

## Pinned movie

The owned movie is uncompressed GFX version 20, one frame, 181 tags. DoABC is tag 177, flags 1, with an empty name. SymbolClass is tag 178. It maps character 0 to `MainMenuScreen` and character 83 to `RootMenuMovie`, and it keeps the other symbol bindings in their original order. The original ABC is 46.16 and SHA-256 `97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42`.

| Field | Value |
|---|---|
| String count | 13849 at offset 2048, pool end 274271 |
| `menus` PackageNamespace | index 814, kind `0x16`, URI string index 5806 |
| Multiname count | 12205 at offset 282536, pool end 335281 |
| `RootMenuMovie` superclass | multiname 5940, `menus::RootMenu`, bytes 446019..446021 |
| Script initializer | script 700, method 11548, code at 1113629, 73 bytes |
| Code SHA-256 | `b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174` |

The initializer has no branches and no exception records. PC 46 is `getlex` of multiname 5940, PC 49 is `pushscope`, PC 50 is `getlex` of the same multiname, and PC 53 is `newclass` of class 702. Both 5940 and the appended multiname index 12205 are two-byte U30 values, so those three operands do not move any later instruction.

Before changing a byte, the composer checks the pool counts, the `menus` namespace kind and URI, the three old operands, the nearby opcodes, the code hash, and both SymbolClass entries. The string pool gains `MctRootMenu` at index 13849 (12 bytes). The multiname pool gains `QName(PackageNamespace("menus"), 13849)` at index 12205 (5 bytes). Those 17 inserted bytes are the only shift inside the original ABC. The original `menus::RootMenu` QName at ABC offset 309137 stays in place aside from that shift, and the original `MainMenuScreen` class and its constant-pool strings stay in that ABC. `RootMenuMovie` keeps its name and character 83. Its superclass references are the three splices above.

Character 0 is the only SymbolClass edit. Its name changes from `MainMenuScreen` to `MctMainMenuScreen`. Every other binding keeps its character id, name, and order. A missing character 0, a duplicate character 0, a different name, a `MainMenuScreen` entry on a nonzero character, or an existing `MctMainMenuScreen` binding is rejected. The caller cannot choose another document name.

The new DoABC is inserted after the original DoABC and before SymbolClass. Its flags are 1, its name is `MCTNativeMenu`, and its payload is the bound class ABC with no SWF header and no SymbolClass of its own. That payload carries both authored classes. Every original tag other than the original DoABC and this one SymbolClass entry is copied unchanged. The SymbolClass tag header and the GFX header length are rebuilt for the longer document name. The output has 182 tags and two DoABC tags.

## Session binding

The class ABC contains one `__MCT_VIEW_URL__` string and one `__MCT_SESSION__` string, plus one `MctRootMenu` string and one `MctMainMenuScreen` string. The composer walks the integer, unsigned, double, and string pools and replaces the two sentinel entries. It does not search the rest of the ABC for the same bytes. Pool indexes and counts stay the same. A longer URL may widen that entry's U30 length prefix; the following bytes move, and their contents stay the same.

The session must be a canonical lowercase UUID, 36 characters. The view URL must already be a canonical `file:///X:/.../native-view.json` path: an uppercase drive letter, no authority, query, fragment, credentials, dot segments, encoded slash, raw space, or non-ASCII character. Space and non-ASCII path text have to be uppercase UTF-8 percent-encoding. The caller supplies the path. This function does not open it and has no HTTP client.

## What this does not show

`production_ready`, `runtime_verified`, `gfx_initialization_order_verified`, `online_suppression_verified`, and `class_loader_verified` stay false. The metadata also records that the file-view read and the `DevUtil.Log` command path are not verified. The original game classes remain in the first ABC. `MctMainMenuScreen` extends that movie's `MainMenuScreen`, and `MctRootMenu` still extends the external `BranchingMenu`. Rebinding character 0 and appending the second DoABC does not show that Scaleform loads either authored class, initializes them in this order, suppresses every online path, or that `URLLoader` and a future host consume the view file.
