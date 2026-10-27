# NATIVE-CONFIG-01: shipped training config and resource inventory

## Scope

Read-only inspection under the installed game's `TAGame` tree. No game input/capture/attach, package extraction, product edits, or tests. I enumerated `.ini`, `.int`, and filename-filtered training/tutorial/HUD `.upk` paths, read only the four plain `.ini` files, and hashed the bounded package candidates listed below. Package names and hashes establish on-disk identity, not class contents or behavior.

## Text configuration

The `TAGame` path inventory returned four `.ini` files and no standalone `.int` files:

| Relative file | Bytes | SHA-256 | Training-related observation |
|---|---:|---|---|
| `TAGame/Config/DefaultInput.ini` | 34,238 | `a38dbed5b6a1fa163eefa201502ee5049ced418cd9e447eb80e0051a1b898d46` | Contains the input defaults below. It declares `BasedOn=..\Engine\Config\BaseInput.ini` at line 2, so this file alone is not the effective merged/user binding state. |
| `TAGame/Config/DefaultRLBot.ini` | 282 | `11679d5493b9e5ed64d652c81fefb9d1815446177fe88f1500eb44d965a4d7b0` | The targeted search found no training, shot, tutorial, timer, or difficulty entries. |
| `TAGame/Config/DefaultStatsAPI.ini` | 396 | `7d6c053c69a1e2375f40e6939043595d7c548c8d3763c153beb075052e193427` | The targeted search found no training, shot, tutorial, timer, or difficulty entries. |
| `TAGame/Config/DefaultSystemSettings.ini` | 17,550 | `541d10b2a511384375d19d4abd60dc67494699fefba31f66ab338b8c9e94d28b` | No training-specific timer/difficulty or localized HUD text was found by the targeted search. |

`DefaultInput.ini` declares these defaults (line references are in that file):

| Action name in config | Keyboard | Gamepad | Steam Input section | Source lines |
|---|---|---|---|---|
| `ResetTraining` | Backspace | Xbox-style right shoulder, tap | Xbox-style right shoulder, tap | 140, 302, 429 |
| `TrainingOpenShotSelectionMenu` | Enter | Xbox-style Back | No matching Steam Input row in this file | 150, 312 |
| `TrainingPreviousShot` / `TrainingNextShot` | Left / Right | D-pad Left / Right | No matching Steam Input rows in this file | 151–152, 313–314 |
| `TrainingToggleShuffle` / `TrainingMirrorShot` | Up / Down | D-pad Up / Down | No matching Steam Input rows in this file | 153–154, 315–316 |
| `TutorialHelper` | One | Left thumbstick | Left thumbstick | 142, 304, 430 |
| `SkipTutorial` | Commented out | Commented out | No matching Steam Input row | 141, 303 |

These are declared defaults, not proof that the current user has those bindings or that an action produces the behavior its name suggests. The PC `One` key also appears for a Freeplay action in this config, and other input contexts/merging are not resolved here. The file contains no training rank/tier values, shot-clock duration, timeout rule, ball visibility rule, or localized prompt text.

## Training-related package names on disk

The current package hashes below match the earlier bounded inventory in [ARTIFACT-01](artifact-01.md). Roles remain filename-based candidates only.

| Relative package | Bytes | SHA-256 | What the name suggests only |
|---|---:|---|---|
| `TAGame/CookedPCConsole/GFX_TrainingMenu_SF.upk` | 1,146,549 | `bf9baa4238d077f35f8041204ea4aec8e9e7c9bb943d1e3df2da07dd07a57663` | Training entry/difficulty movie candidate |
| `TAGame/CookedPCConsole/GFx_CustomTrainingSelectShotMenu_SF.upk` | 384,325 | `ce5407b03ed248171493575532c29dab47fbeed09e2adef842deb35b4409b567` | Custom-pack shot selection candidate |
| `TAGame/CookedPCConsole/GFX_TrainingBrowserMenu_SF.upk` | 417,006 | `a16834dba4a9ac1fd72e50a81dd37db9dbfcca4c5d3f3f9cb835f818e359ae4d` | Custom Training browser candidate |
| `TAGame/CookedPCConsole/GFx_TrainingEditorMenu_SF.upk` | 793,453 | `6de6febc6f7aa8219f5a259059e3a76e3469d864e8330b20340c8ddd8a1a3f95` | Training Editor menu candidate |
| `TAGame/CookedPCConsole/GameInfo_TrainingEditor_SF.upk` | 3,343,310 | `c4c8501c1a1fbf3ebf181d55bddd42233e00b421417851bc382a997399081d21` | Training Editor game/event candidate |
| `TAGame/CookedPCConsole/GameInfo_Tutorial_SF.upk` | 2,562,133 | `12f72470bed3225ee24815b3bade0a3d4d50938fd3c7f9975c31d5890fc922cf` | Tutorial game/event candidate |
| `TAGame/CookedPCConsole/GFX_Hud_SF.upk` | 1,260,419 | `1a6c92191333c5612711b84fa4570d4f088bc977feb7cad58f4ec4343d0e5a59` | Gameplay HUD candidate |
| `TAGame/CookedPCConsole/GFX_HudMatchInfo_SF.upk` | 2,207,064 | `3bc8f2bf57c57df3281a81295174a2fa728d9452abbb0a10eb168d780495f088` | Match/HUD information candidate |

The filename-only inventory also returned `GFxSounds_Tutorial_SF.upk`, `Tutorial_FX.upk`, `TutorialBeginner.upk`, `TutorialAdvanced.upk`, `TutorialAdvanced_B.upk`, and `TutorialTest_K.upk`. They were not inspected or hashed in this pass. No `.upk` filename matching `*Difficulty*.upk` was returned by the bounded filename query; this does not establish that a difficulty screen/resource is absent from another named package.

## Evidence categories and boundary

- **Declared defaults:** The readable config exposes input action names and default keyboard/controller keys, with `DefaultInput.ini` explicitly layered on a base input config. It does not expose the handler implementation or effective per-user binding state.
- **Translated labels:** No standalone `.int` file exists in the bounded `TAGame` file listing. This does not show that localized strings are absent from compiled packages or other roots; no package strings were decoded.
- **Available package names:** The listed `.upk` files and hashes identify current on-disk package candidates. They do not identify exported movie classes, event callers, labels, or lifecycle code.
- **Actual behavior:** Unestablished here. The previous [ARTIFACT-01](artifact-01.md) records that REA 6.8.0 reported the selected UE3 package as unsupported and that the bounded package reader needs a valid decrypt callback. I did not retry that query or attempt broad decryption/extraction. The SDK-03 getter evidence shows only direct reads of stored timer/ball-flag fields; it does not establish their writers or causal semantics (`sdk-03.md:11-26`).

## Smallest next lifecycle observation contract

When an offline game session is available under this campaign’s ownership, use one built-in lesson and record each action as: **owner and exact candidate/game identity; starting screen and selected lesson/difficulty; one intentional input and timestamp; observed menu/HUD/ball/timer state; expected transition and deadline; ending state and recovery.** Capture the actual difficulty label and focused/activated row, then one launch, one natural timeout, one `ResetTraining` retry, and one next-shot action. At each transition correlate selected shot/difficulty text, any visible input legend, both timer getters, ball object presence plus fade/hidden getters, and the actual destination state. Do not infer a timeout or fade cause from matching names or a changing getter alone; include writer/runtime evidence if causal ordering is required.

Skipped package extraction and runtime observation. Risk: these defaults and package names cannot certify stock menu, timeout, HUD, or ball-reset behavior.
