# Native movie composition

## Additional match scenes

`compose_match_movie(scene, original_gfx, mod_abc, session=..., view_url=...)`
accepts only `midgame` and `endgame`. Their fixed profiles and
`native_ui/compiled/match-manifest.json` pin the original package, movie,
original ABC, authored ABC, source hashes, and symbol bindings. The frontend
entry and its compiled ABC remain unchanged.

| Package id | View surface | Root symbol | Document replacement | Authored ABC |
| --- | --- | --- | --- | --- |
| `midgame` | `pause` | 6, `MidGameMenuMovie` | `MctPauseMenuScreen` | `MctPauseMenu.abc` |
| `endgame` | `results` | 23, `EndGameMenuMovie` | `MctResultsMenuScreen` | `MctResultsMenu.abc` |

Both scenes use the same original-name rename and later compiled wrapper
definition as the frontend. They never reparent the original class. Apart from
that one string and document character 0, original ABC bytes, symbols, and other
tags stay unchanged. Each authored ABC contains three project classes and the
seven pinned public JSON codec classes. Scene ids, hashes, byte lengths, and
document/root bindings are validated before composition.

The remainder of this document describes the unchanged frontend profile.

`scripts/native_movie_compose.py` builds one development movie in memory. `compose_movie` accepts the pinned `MainMenu.gfx` bytes and the compiled ABC that contains the three project classes `menus.MctRootMenu`, `MctMainMenuScreen`, and `MctRootMenuMovie` plus the seven vendored `com.adobe.serialization.json` classes, plus a session nonce and a local view URL. It returns `{"data": bytes, "metadata": dict}`. It does not write a file, launch Rocket League, or install a package.

The public entry accepts only two hashes. The movie SHA-256 is `57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`. The class ABC SHA-256 is `d4924678b0e84a689b67de71f600034430f735447361105a453b2424134cbfaa`, the current `native_ui/compiled/MctRootMenu.abc` (17595 bytes, ABC 46.16, 93 method bodies, three project classes and seven library classes, no linked game classes). A mismatch is rejected before the placeholder strings are bound. The manifest records source SHA-256 `bcd0373aaa1d9ef4524521ab9d1b268c01d14c21b30a22b6534e13c4c420a496` for `native_ui/menus/MctRootMenu.as`, `d4d824dc4e62963cdeab65c3f20fd30c1e49bb86cd1a3a923b8b1f8c0c1bfabd` for `native_ui/MctMainMenuScreen.as`, and `9791d1371d8a0b9d1cc2f936e1a30b8cfb0ba9add9dfc289e7443bfc27404432` for `native_ui/MctRootMenuMovie.as`. The composer stores those values and does not read the ActionScript files. The manifest `classes` list is the parsed definition order. `authored_classes` and `library_classes` keep the project classes separate from as3corelib. The receipt pin named `classes` stays the three project classes.

There is no FFDec or Java step inside the composer. It parses the original string pool, renames one class-name string, and checks the pinned superclass and script-code bytes. It is not a general ABC rewriter. Original GFX and the output are limited to 16 MiB. The class ABC is limited to 64 KiB. The view URL is limited to 4096 characters.

## Pinned movie

The owned movie is uncompressed GFX version 20, one frame, 181 tags. DoABC is tag 177, flags 1, with an empty name. SymbolClass is tag 178. It maps character 0 to `MainMenuScreen` and character 83 to `RootMenuMovie`, and it keeps the other symbol bindings in their original order. The original ABC is 46.16 and SHA-256 `97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42`.

The original `RootMenuMovie` class is left in that ABC. Its superclass operand stays multiname 5940, `menus::RootMenu`, the two bytes at original offset 446019. Script 700, method 11548, keeps the 73 code bytes at original offset 1113629, SHA-256 `b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174`. The composer does not rewrite those operands, scopes, or class indexes.

It finds the one constant-pool string `RootMenuMovie` by walking the integer, unsigned, double, and string pools. A missing name, a second copy, or an existing `MctOriginalRootMenuMovie` string is rejected. The length-prefixed entry becomes `MctOriginalRootMenuMovie`. That name is 11 bytes longer and both lengths fit in one U30 byte, so every later byte shifts by 11 and is otherwise unchanged. The renamed entry must end before the superclass operand. After the shift, those superclass bytes and the script 700 code bytes must still equal the pinned originals.

## Authored classes

`MctRootMenuMovie` is compiled under that name because the private SDK already exports `RootMenuMovie`. The tracked ABC keeps the compile name. After the session strings are bound, the composer renames that one authored string to `RootMenuMovie`. A missing or duplicate `MctRootMenuMovie`, or an authored pool that already contains `RootMenuMovie`, is rejected. The wrapper's QName keeps its string index; the text at that index is now `RootMenuMovie`.

Character 83 stays bound to the name `RootMenuMovie`. That name now matches the authored wrapper, while the original class is `MctOriginalRootMenuMovie`. Character 0 is the only SymbolClass edit. Its name changes from `MainMenuScreen` to `MctMainMenuScreen`. Every other binding keeps its character id, name, and order. A missing character 0, a duplicate character 0, a different name, a `MainMenuScreen` entry on a nonzero character, or an existing `MctMainMenuScreen` binding is rejected.

The new DoABC is inserted after the original DoABC and before SymbolClass. Its flags are 1, its name is `MCTNativeMenu`, and its payload is the bound class ABC. Every original tag other than the original DoABC and this one SymbolClass entry is copied unchanged. The output has 182 tags and two DoABC tags.

## Session binding

The class ABC contains one `__MCT_VIEW_URL__` string and one `__MCT_SESSION__` string, plus one `MctRootMenu` string, one `MctMainMenuScreen` string, and one `MctRootMenuMovie` string. The composer walks the pools and replaces the two sentinel entries before renaming the wrapper. It does not search the rest of the ABC for the same bytes. Pool indexes and counts stay the same. A longer URL may widen that entry's U30 length prefix; the following bytes move, and their contents stay the same.

The session must be a canonical lowercase UUID, 36 characters. The view URL must already be a canonical `file:///X:/.../native-view.json` path: an uppercase drive letter, no authority, query, fragment, credentials, dot segments, encoded slash, raw space, or non-ASCII character. Space and non-ASCII path text have to be uppercase UTF-8 percent-encoding. The caller supplies the path. This function does not open it and has no HTTP client. The compiled menu, after that same `file:///` guard, requests `decodeURIComponent` of the path and reads the body with `com.adobe.serialization.json.JSON`. Those calls are in the ABC. The composer still only replaces the placeholder string.

## What this does not show

`production_ready`, `runtime_verified`, `gfx_initialization_order_verified`, `online_suppression_verified`, and `class_loader_verified` stay false. The metadata also records that the file-view read and the `DevUtil.Log` command path are not verified.

A separate minimal diagnostic class, linked by this same rename and not by reparenting the original superclass, rendered text and closed the game on Exit. A separate private full-host control, using this URL conversion and this JSON codec, reported the callback, a ready handshake, and seven buttons. Neither observation is a result for this repository's newly compiled ABC. This ABC's career controls, decoded file request, JSON view, details layout, focus handling, and `DevUtil.Log` path have not been accepted in game. `runtime_verified` and `production_ready` stay false for hash `d4924678b0e84a689b67de71f600034430f735447361105a453b2424134cbfaa`. Rebinding character 0, renaming these two strings, and appending the second DoABC does not show that Scaleform initializes the classes in a particular order or suppresses every online path.
