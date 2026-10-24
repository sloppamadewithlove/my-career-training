# Native menu remap trial

Development-only calibration for one possible Garage-button experiment. `plugin/include/NativeMenuRemapTrial.h` is a pure state machine. It does not write memory, call the game or the SDK, resolve an `FName` integer to text, or touch files. Root owns CMake, the host probe, and any controlled UI review before a real parameter write.

## One session of evidence

Host probe 0.4 loaded and unloaded on executable SHA-256 `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`, BakkesMod 229, game build `261013.63066.530866`. The caller matched the SDK menu stack and the candidate class and metaclass for `GFxData_MenuStack_TA.ButtonTriggered`. Four clicks, Garage, Back, Settings, and Back, produced these pre/post `FName` pairs:

| Click | FName (index, number) | Menu at both PRE and POST |
| --- | --- | --- |
| Garage | (94486, 0) | `RootMenuMovie` |
| Back | (135714, 0) | `GarageMainMenuMovie` |
| Settings | (135715, 0) | `RootMenuMovie` |
| Back | (135724, 0) | `OptionsMenuMovie` |

The screen changed after POST, not inside it. `SetStringValue` and the menu-tree click hook did not fire. Those indexes belong to that session. The state machine does not store them and will not reuse them for a later UUID or thread token.

The 8-byte value is a candidate layout: little-endian `int32` index, then little-endian `int32` number. That layout comes from the RLSDK parameter metadata at commit `99c4330f8e26e037f7f343dbe75b6dd5c08c4a01` (`plugin/licenses/rlsdk-LICENSE.MIT`). It is not a verified ABI.

## What the four pairs teach

The only accepted calibration is:

1. PRE Root `A`, POST Root `A`
2. PRE Garage `B`, POST Garage `B`
3. PRE Root `C`, POST Root `C`
4. PRE Options `D`, POST Options `D`

Each POST still carries the menu from before navigation. The next PRE is what shows the result: `A` opened Garage, `B` returned to Root, and `C` opened Options.

## The one shot

After those four pairs, the next PRE must be Root and the same session's `A`. `observe` then sets `offerReplace` and returns `C`'s 8 bytes for the callback parameter the host holds on this call. `parameter_rewrite_applied` stays false.

`acknowledgeWrite(true)` records that the host attempted the copy and believes it landed. `acknowledgeWrite(false)` records the attempt, leaves the applied flag false, and refuses every later rewrite. Neither acknowledgement consumes the menu or proves the screen changed.

The POST of that same callback must still be Root, must use the same opaque parameter identity, and must read `C`. `observe` then sets `offerRestore` and returns the original `A` bytes for that POST parameter. The machine does not keep a pointer and write through it. `acknowledgeRestore(true)` ends the shot. A later PRE does not offer a sixth rewrite.

The opaque identity is compared and then discarded from the result. It is not dereferenced, and it is not present in the proposal or the status.

## Refusal

The machine refuses until the next successful `start()` when any of these happen: the PRE and POST names differ, the `FName` is negative or its index is above 1000000, the parameter identity differs, the menu is not the one this step requires, the order is wrong, `A` and `C` are the same name, the UUID or thread token changes, time goes backwards or is not finite, more than 90 seconds have passed, a second PRE arrives before POST, or another event arrives while a proposal is still open. An invalid `start()` leaves the current state untouched.

## Evidence versus acknowledgement

`offerReplace` and `offerRestore` mean the reads matched. They do not mean a write occurred. `action_consumption_verified`, `menu_rewrite_verified`, and `verified_abi` stay false. `parameter_rewrite_applied` becomes true only in `acknowledgeWrite(true)`.

## An aborted restore is not solved

This class is not allowed to put the original bytes back. If the scope, clock, or POST read fails after a replacement was offered or acknowledged, the result sets `restore_aborted`, clears both offer flags, and repeats `A`'s 8 bytes. Those bytes describe the value to restore. They are not an address.

Root can copy them only into the POST parameter it still holds. If that call has already returned, this trial cannot repair it. Starting again drops the retained bytes and does not restore the game parameter.

## Gate

`NativeBuildGate::mutationSupported` remains false. The diagnostic executable hash above is not a mutation allowlist. This trial does not open that gate, does not make an installer release, and does not claim the build is verified-compatible.

The fixture is registered in CMake as `native_menu_remap_trial`, built by
`mct_native_menu_remap_tests`. The host integrates the calibrator behind the
explicit `--menu-remap-trial` flag. Its exact current POST-parameter cleanup is
separate from the observation timer; see `NATIVE_HOST_TRIAL.md`. Production
compatibility remains closed.
