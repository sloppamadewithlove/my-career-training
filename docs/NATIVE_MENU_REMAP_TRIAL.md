# Native menu remap trial

Development-only calibration for one possible Garage-button experiment. `plugin/include/NativeMenuRemapTrial.h` is a pure state machine. It does not write memory, call the game or the SDK, resolve an `FName` integer to text, or touch files. Root owns CMake, the host probe, and any controlled UI review before a real parameter write.

No in-game mutation has been run with this state machine. User readiness was absent, so the first write-capable session closed without loading this DLL. The read-only evidence remains `docs/validation/native-button-observation-2026-10-24.json`: four pairs, eight pre/post records, not eight pairs. `native_mutations` in that file is false. `NativeBuildGate::mutationSupported` stays false.

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

## Input policy

`start(scope, now, policy)` stores the policy only after the scope, clock, and enumerator validate. The default is `RestoreAtPost`, so existing fixtures keep the POST restore. `status.policy` is the fixed text `restore_at_post` or `leave_input_for_call`. An enumerator other than those two returns false and leaves the machine unarmed, including any calibration already in progress.

Both policies share the four-pair calibration and the one Root `A` replacement proposal. `observe` then sets `offerReplace` and returns `C`'s 8 bytes for the callback parameter the host holds on this call. `parameter_rewrite_applied` stays false until `acknowledgeWrite(true)`. `acknowledgeWrite(false)` records the attempt, leaves that flag false, leaves `post_replacement_observed` false, and refuses every later rewrite. Neither acknowledgement consumes the menu or proves the screen changed.

`post_replacement_observed` becomes true only after that applied write and a later POST on the same opaque identity, still on Root, whose supplied name is the session's `C`. The class compares the caller's name. It does not read process memory. A POST that still reads `A`, a different identity, or a different scope does not set the flag.

`restoration_required` is true only for `RestoreAtPost`, and only after an applied write until `acknowledgeRestore(true)`. It stays true if that POST is refused or the restore acknowledgement is false. `LeaveInputForCall` never sets it.

The opaque identity is compared and then discarded from the result. It is not dereferenced, and it is not present in the proposal or the status. The machine does not keep a pointer.

### RestoreAtPost

The POST of that same callback must still be Root, must use the same opaque parameter identity, and must read `C`. `observe` then sets `post_replacement_observed` and `offerRestore`, and returns the original `A` bytes for that POST parameter. `acknowledgeRestore(true)` ends the shot and clears `restoration_required`. A later PRE does not offer a sixth rewrite.

If the scope, clock, or POST read fails after a replacement was offered or acknowledged, the result sets `restore_aborted`, clears both offer flags, and repeats `A`'s 8 bytes. Those bytes describe the value to restore. They are not an address. This class is not allowed to put them back. Root can copy them only into the POST parameter it still holds. If that call has already returned, this trial cannot repair it. Starting again drops the retained bytes and does not restore the game parameter.

### LeaveInputForCall

Prefer this policy for the next live experiment. A matching POST records `post_replacement_observed`, moves to `done`, and does not set `offerRestore` or return restore bytes. The replacement stays in the parameter of the current call. There is no later write. Root drops its pending write-pointer cache for this pre-only mode. Root still checks the exact current callback, the owned offline scope, and the page, latches a single write, and closes the game after the test.

A mismatched POST refuses with `post_mismatch`. A changed scope refuses with `scope`. Neither refusal sets `restore_aborted`, `restoration_required`, or `originalBytesAvailable`, and neither presents `A` as bytes this mode needed to write back. A later PRE does not offer a sixth rewrite.

Official BakkesMod [MechanicalPlugin](https://github.com/bakkesmodorg/BakkesMod2-Plugins/blob/master/MechanicalPlugin/mechanicalplugin.cpp) changes `ControllerInput` scalar fields in PRE and returns without a POST restore. [`GameWrapper.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/master/include/bakkesmod/wrappers/GameWrapper.h) declares those hooks. That is an analogous scalar input pattern. It is not proof of this `FName` layout or of menu routing. Restoring `A` at POST can mask downstream use of the modified parameter, which is why the live experiment should leave `C` in place for the call.

Process closure ends process memory. It is not an SDK rollback guarantee for side effects of the selected action.

## Refusal

The machine refuses until the next successful `start()` when any of these happen: the PRE and POST names differ, the `FName` is negative or its index is above 1000000, the parameter identity differs, the menu is not the one this step requires, the order is wrong, `A` and `C` are the same name, the UUID or thread token changes, time goes backwards or is not finite, more than 90 seconds have passed, a second PRE arrives before POST, or another event arrives while a proposal is still open. An invalid `start()`, including an unknown policy enumerator, leaves the current state untouched.

`action_consumption_verified`, `menu_rewrite_verified`, and `verified_abi` stay false. `offerReplace` and `offerRestore` mean the reads matched. They do not mean a write occurred.

## Gate

`NativeBuildGate::mutationSupported` remains false. The diagnostic executable hash above is not a mutation allowlist. This trial does not open that gate, does not make an installer release, and does not claim the build is verified-compatible.

The fixture is registered in CMake as `native_menu_remap_trial`, built by
`mct_native_menu_remap_tests`. The host integrates the calibrator behind the
explicit `--menu-remap-trial` flag. The next live experiment should select
`LeaveInputForCall`. Production compatibility remains closed.
