# GAMEINFO-METADATA-01 — Training Editor and Tutorial package metadata

## Scope and method

I inspected only the two pinned installed packages with the existing `inspect_menu_package(path, decrypt_header)` API from `work/reviewed-training/scripts/native_package_reader.py`. The existing decoder callback was used in memory; its private input was not printed, hashed, or passed on the command line. No movie/asset export was extracted or decompiled, and no REA session was opened.

The API returns UE package header, name, import, export, and compression-chunk metadata (`native_package_reader.py:107–111, 814–842`). It reports all production capabilities false (`:96–104`). For package validation it reads compressed chunk bytes and validates their frame boundaries (`:317–319, 670–674`), but does not inflate movie exports or return serial payloads; `read_movie_bytes` was not called. The method can identify object/class labels and declared table references, but cannot inspect function bytecode, determine which object is active, or order events.

## Exact package identity and table shape

| Package | Bytes / SHA-256 | UE version / licensee | Names / imports / exports / chunks |
|---|---|---|---:|
| `GameInfo_TrainingEditor_SF.upk` | 3,343,310 / `c4c8501c1a1fbf3ebf181d55bddd42233e00b421417851bc382a997399081d21` | 868 / 34 | 2,917 / 594 / 2,711 / 6 |
| `GameInfo_Tutorial_SF.upk` | 2,562,133 / `12f72470bed3225ee24815b3bade0a3d4d50938fd3c7f9975c31d5890fc922cf` | 868 / 34 | 3,043 / 676 / 3,543 / 5 |

These size/hash pins agree with `work/campaign/native-config-01.md` and were rechecked before reading. The name, import, and export tables decrypted successfully for both files.

## Metadata relevant to native training lifecycle

`GameInfo_TrainingEditor_SF.upk` imports native `TAGame`/`Core` class and default-object references for `GameInfo_TrainingEditor_TA`, `GameEvent_TrainingEditor_TA`, `EndRoundComponent_TrainingEditor_TA`, `FXActor_TrainingEditor_TA`, `Ball_GameEditor_TA`, and `Ball_Trajectory_TA`. Its object exports include `GameInfo_TrainingEditor` (class `GameInfo_TrainingEditor_TA`), `GameEvent_TrainingEditor` (class `GameEvent_TrainingEditor_TA`), `TrainingEditor_FXActor`, `Ball_GameEditor`, and `Ball_Trajectory`. This is metadata linking the package to editor-specific game/event/ball classes; it does not establish which methods run or when.

`GameInfo_Tutorial_SF.upk` imports `GameInfo_Tutorial_TA`, `GameEvent_Tutorial_Advanced_TA`, `GameEvent_Tutorial_Basic_TA`, `GameEvent_Tutorial_FreePlay_TA`, `Ball_Tutorial_TA`, `Ball_TA`, `Ball_Trajectory_TA`, and tutorial end-round classes. Its object exports include `GameEvent_Tutorial_Aerial`, `GameEvent_Tutorial_Goalie`, and `GameEvent_Tutorial_Striker` with classes `GameEvent_Training_Aerial_TA`, `GameEvent_Training_Goalie_TA`, and `GameEvent_Training_Striker_TA`; it also exports Basic, Advanced, FreePlay, and `GameInfo_Tutorial` objects. The different class labels distinguish tutorial assets/configuration in metadata, not their runtime lifecycle.

Both packages’ name tables contain `TimeRemaining` and `ExcitementTimeRemaining`. Those are names only: the tables do not attach them to a visible timer, expiry callback, ball reset, or specific event object. Neither package’s metadata contains `GFxData`/`GfxData` names (including `GfxData_Training`), or the exact names `FadeOutBall`, `FadeInBall`, `bFadeOut`, `bEndOfGameHidden`, `DestroyBall`, `ResetBalls`, or `HandleNextGame` in its name/import/export tables. The SDK wrapper declarations for those operations remain separate API evidence; these package tables do not show those wrappers being called.

Each package has two `SwfMovie` exports named `HudMatchInfo` and `PlayerNameplatesRTX`. Their exported metadata does not identify a training/tutorial shot HUD, nor does it prove the movies are instantiated by these game modes.

## Functions versus object data

The export tables report **zero `Function` and zero `State` class exports** in both packages (1,251 `Class` exports for Training Editor and 1,236 for Tutorial). There are many serialized object exports with native class labels, including game-event, game-info, ball, and UI movie objects. The reader provides no script/function body parser, so the result does not establish that the runtime contains no native code; it establishes only that these package export tables expose no standalone UE `Function` or `State` exports.

## Lifecycle conclusion and next evidence

The metadata identifies the smallest package-level connection to Training Editor and tutorial classes and confirms timer-related names, but it cannot establish ball spawn/despawn/fade ordering, timer start or expiry, reset/next-shot sequencing, or HUD field ownership. No call-order conclusion follows from matching class, object, or property-like names.

To answer ball/timer lifecycle, the next causal query must trace the matching installed native `GameInfo_TrainingEditor_TA` / `GameEvent_TrainingEditor_TA` and tutorial event implementations or observe an owned offline stock lesson. Correlate timer getters and ball visibility state with one launch, expiry, retry, and next-shot transition. The package metadata alone is not enough to attribute timer start, ball fade, destruction, or reset to any one event.
