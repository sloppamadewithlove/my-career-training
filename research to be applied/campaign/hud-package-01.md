# HUD-PACKAGE-01 — HUD movie package metadata

## Scope and method

Read-only package metadata inspection of only `GFX_Hud_SF.upk` and `GFX_HudMatchInfo_SF.upk` under `TAGame/CookedPCConsole`. I used the existing `scripts/native_package_reader.py` with the already-staged decoder callback held in process memory. I called `inspect_menu_package` only: no movie payload was read, extracted, written, or sent to a decompiler. The decoder key was not printed or passed in command arguments. The reader reports all production capabilities as false.

The package hashes and byte sizes match the earlier bounded file inventory in `work/campaign/artifact-01.md`. This is package table evidence, not proof of which class owns a screen at runtime.

## Package identity and exports

| Package | Bytes / SHA-256 | Format and table counts | `SwfMovie` export |
|---|---|---|---|
| `GFX_Hud_SF.upk` | 1,260,419 / `1A6C92191333C5612711B84FA4570D4F088BC977FEB7CAD58F4EC4343D0E5A59` | UE v868, licensee 34, flags `0x0288028D`, decrypted header 26,449 B; 121 names, 9 imports, 73 exports, 5 chunks | export 3: `HUD`, class `SwfMovie`, serial size 1,145,956 B |
| `GFX_HudMatchInfo_SF.upk` | 2,207,064 / `3BC8F2BF57C57DF3281A81295174A2FA728D9452ABBB0A10EB168D780495F088` | UE v868, licensee 34, flags `0x0288028D`, decrypted header 21,185 B; 72 names, 9 imports, 23 exports, 6 chunks | export 3: `HudMatchInfo`, class `SwfMovie`, serial size 995,829 B |

Both import the same external movie: package `GFxUI`, name `SharedComponents`, class `SwfMovie`. Their other imports are the Core classes `Package`, `ObjectReferencer`, `Texture2D`, and `SwfMovie`, plus package references to `Core`, `Engine`, `GFX_Shared`, and `GFxUI`. Those are package import-table facts; they do not establish what ActionScript code calls the imported movie.

## What the names suggest, and what they do not prove

`GFX_Hud_SF.upk` contains texture exports named `TrainingView_Background`, `TrainingView_Background_v2`, `TrainingView_Glow`, `TrainingView_TimeBackground`, and `TrainingView_TimerBackground_v2`. It also has `ItemsModeView_TimerBackground` and `ItemsModeView_TimerFill`. These are the strongest metadata clues for a training view and a time display in the two inspected packages. The package’s one movie export is the broad `HUD` symbol. No name-table entry identifies a top-left label, shot counter, rank label, timer event, input legend, or `GfxDataTraining` consumer. No symbol named `ButtonLegend`, `Controller`, or `Legend` appears in this package’s name table.

`GFX_HudMatchInfo_SF.upk` has a separate `HudMatchInfo` movie and textures named `MatchTimer_Background`, `MatchTimer_CaptionBackground`, `MatchTimer_SafeZoneBorder`, score icons, and scoreboard elements. Its name table has no training-view asset names. This makes it a lower-priority match-clock comparison target; the names alone do not prove that it is excluded from training or establish which timer it displays.

Neither metadata inventory exposes internal ActionScript classes, text fields, coordinates, anchoring, event handlers, or host-side writers. A `TrainingView_*` texture name is not evidence of its screen position or that it is active in the current training mode. Likewise, the `GFxUI.SharedComponents` import makes that one shared movie a concrete dependency candidate for later legend inspection, but does not prove that it contains the controller legend or that either HUD movie instantiates it for training.

## Comparison with the pinned BakkesMod wrapper API

The project CMake pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` and archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` (`work/reviewed-training/plugin/CMakeLists.txt:26-28`; also recorded in `work/campaign/sdk-01.md`). The populated SDK header `work/reviewed-training/build/native-candidate/plugin/_deps/mct_sdk-src/include/bakkesmod/wrappers/gfx/GfxDataTrainingWrapper.h:35-43` declares accessors for training type, score, current/total round, difficulty, tutorial tip, progress per shot, and playlist index. Those are callable C++ API declarations, not fields imported by these Scaleform packages and not proof the `HUD` movie consumes them. The wrapper declarations do not identify a HUD position, controller prompt, or a timer getter. Separate server/game-event timer getters are recorded in `work/campaign/sdk-03.md`, but that static wrapper evidence does not assign a timer to this movie or establish countdown/expiry behavior.

Consequently, metadata supports a bounded next source query of the `HUD` movie, while the API comparison only gives a list of state values an external host might expose. No package import links `GfxDataTrainingWrapper` by name. That absence is limited to the two package import/name tables and does not exclude native host-side population or dynamic binding.

## Smallest useful next export order

1. **`GFX_Hud_SF.upk` → `HUD`**: highest priority. A focused export could identify whether the training-view textures are composed into the HUD movie, what text fields and timer elements are present, how they are anchored, and whether the movie declares a legend component. It still would not prove a runtime writer or activation condition.
2. **`GFxUI.upk` → `SharedComponents`**: conditional second target for controller glyph/legend structure, because both inspected movies explicitly import that exact `SwfMovie`. Inspect only that movie export, not the whole shared package. This does not prove that the training HUD uses it.
3. **`GFX_HudMatchInfo_SF.upk` → `HudMatchInfo`**: optional comparison only if the focused `HUD` export points to match info or if distinguishing match clock from training time remains necessary.

No metadata reference from either inspected package requires widening to `GameInfo_*`. The minimal evidence needed to establish who fills a top-left shot/progress field or updates a timer is still a targeted movie export plus a host/game caller path or a scoped read-only runtime observation. Package names and wrapper signatures alone cannot establish those behaviors.
