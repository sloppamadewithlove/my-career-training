# CONTROLLER-OVERLAY-SOURCE-01 — Controller Overlay Pro #707 evidence boundary

## Scope

This is read-only research on the exact Controller Overlay Pro 1.0.7 package pinned by the frozen MCT source. I inspected an already-present, hash-matching local archive/DLL and its existing private static-inspection receipts, read the frozen MCT adapter, checked the official plugin listing, and queried the author's public repository metadata/source. I did not download or extract a new package, execute the DLL, use a game/controller, inspect controller configuration, install anything, or use the shared REA/Ghidra workspace.

## Exact artifact and source identity

The official listing identifies Controller Overlay Pro by ABWxASSASSIN as version 1.0.7, updated April 11, 2026. Its release notes claim PlayStation raw-input handling was changed for DS4/DualSense devices, with Raw Input enabled by default. Those are publisher statements, not measured device results. ([BakkesPlugins listing](https://bakkesplugins.com/plugin/707), lines 17–24 and 76–91.)

An existing local review cache contained the exact archive MCT pins; its bytes and DLL member were re-hashed for this task. No matching package was present in the current app-owned community-plugin cache, so findings use only the pre-existing review artifact.

| Artifact/source | Bytes | SHA-256 or source identity |
|---|---:|---|
| Official CDN archive `Bakkesplugin_707-public-20260411-204747.zip` | 850,492 | `9377316bb9649c9ee131d265e8fd08b14a792ad7c03f6adb15e3aee72bad72d7` |
| Archive member `plugins/ControllerOverlayPro.dll` | 473,088 | `a56759e12fc302180c782cff44f332c07a7a6c3106b0e345b90c238e1fc5ae4d` |
| Existing archive audit | 21,533 | `e9d7c7f9c87aad474c11a7e0ab5a93dc827cf639381538e1ec38bc392b1b3e44` |
| Existing static PE report | 30,105 | `25a1e445c2683eedefd34536d10d11832f3ceffe3b254b1c813ebc47097025e2` |
| Existing artifact receipt | 31,745 | `a76ae259a21bd84f898fb7b2fb6fe570b61ce5383131a8fb76a1b14a8a9a086d` |
| Frozen MCT `controller_overlay.py` | 13,002 | `27b255ac1cbafc37d39358922aa349c217d3012db075d40d5d749f3f38293e95` |
| Frozen MCT `ControllerOverlaySession.h` | 10,805 | `8289082e59c226e08ebe2ec06c42e4f1f848958c916367745fda4a695e992482` |
| Frozen MCT `MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| Existing MCT native overlay-session tests | 20,545 | `cb0360d21f3726b1bdfe0263933cd1c96bed9342ae683be5eefb9ac67c52eb71` |
| Existing MCT Python package tests | 6,470 | `c3db1eaa0e7214a848c1d57923b1fc892c5957876ef48bccc9b02228d142563b` |

The frozen MCT source pins public version 1.0.7, archive hash/size, DLL hash/size, five expected cvar names, and asset-family counts (`controller_overlay.py:24–45`). Its `supported` property requires matching DLL bytes, all expected cvar names, and complete image-family counts (`:62–64`); that is a package-compatibility check, not proof the overlay is drawing or reading the intended controller. MCT records an embedded cvar version of 1.0.5 separately from public package version 1.0.7 (`:25–27,114–122`).

The official listing has no GitHub repository link in its captured link set; it points to the package download and Discord. The author does have a public repository, but the only public branch is `main` at commit `45c5a46ae6e5ac0690ce80fa253b1b606a134131`, whose commit removes the README and points to the canonical empty Git tree. The public tags stop at `v1.0.4`. The inspected `v1.0.4` source file `src/ControllerOverlayPro.cpp` is 18,737 bytes, Git blob `6c611601e117a1e4fbb03efcd56906e776913ad8`, SHA-256 `2e2c25d3778574435d40b7ad0fff22586d73828a5d21c6168ef75c1a33be97fc`. It uses XInput to read the selected pad and implements a skin-folder cvar; it contains no Raw Input references (`:208–221,328–368`). This historical source is not linked from the v1.0.7 artifact and does not identify how the 1.0.7 DLL was built. ([Author repository](https://github.com/ABWASSASSIN/ControllerOverlayPro), [current empty-tree commit](https://github.com/ABWASSASSIN/ControllerOverlayPro/commit/45c5a46ae6e5ac0690ce80fa253b1b606a134131), [historical v1.0.4 source](https://github.com/ABWASSASSIN/ControllerOverlayPro/blob/v1.0.4/src/ControllerOverlayPro.cpp).)

## What the v1.0.7 binary supports statically

The existing static PE report is marked static-only and says the DLL was not loaded or executed. It identifies a 64-bit Windows DLL. Its import table includes `XINPUT1_4.dll` (ordinal 2) and these `USER32.dll` input functions: `RegisterRawInputDevices`, `GetRawInputDeviceInfoA`, `GetRawInputData`, and `DefWindowProcA`; `GetAsyncKeyState` is also imported. The DLL contains a `XcoRawInputSink` string and UI strings for a PS4/PS5 Raw Input calibration flow that describes connecting by USB and mapping button/axis reports. The current official release notes make the intended DS4/DualSense support clearer. Together these are good evidence that the binary was built to use both XInput and Windows Raw Input and exposes a PS4/PS5 calibration feature. They do not prove that the Raw Input path receives a given device, maps its reports correctly, or drives each displayed control. (Static-report hash above; exact DLL hash above; official listing lines 76–86.)

The binary also contains strings describing an XInput pad selector (`-1` for auto or slots 0–3), an overlay skin-folder setting, and a setting that changes the artwork folder. A byte-presence check against the hash-matched DLL confirmed MCT's five cvar names, including `xco_skin`. The matching archive contains 61 PNGs under the `Default`, `ps4`, `ps5`, `xbox`, and EasterEgg families; the handler expects 10 Default images and 15 for each named controller skin (`controller_overlay.py:39–45`). These are evidence of artwork choices and setting names. A selected `ps4` skin is not evidence that the physical controller was detected as a DS4.

No `dinput8.dll` or `hid.dll` dependency appears in the recorded PE import table. That absence does not rule out device handling through Windows Raw Input or undocumented dynamic lookup. The import table and embedded strings alone cannot establish support for arbitrary DirectInput/HID controllers, Bluetooth DS4/DualSense mappings, or any particular third-party wrapper configuration.

## MCT integration boundary

The MCT adapter reads/writes the plugin's five cvars: `xco_x`, `xco_y`, `xco_scale`, `xco_skin`, and `xco_enabled` (`ControllerOverlaySession.h:32–39,108–114`). It applies only for an owned, fresh, offline, in-game training lesson outside online/replay contexts (`:41–60`; host scope population in `MyCareerTraining.cpp:1452–1476`). Position and scale are computed from the viewport; the adapter sets `xco_skin` to `ps4` unconditionally and derives visibility from the lesson's `controller_overlay` preference (`ControllerOverlaySession.h:108–114,151–189`; `MyCareerTraining.cpp:1468–1476`). It does not detect a controller model or receive the plugin's raw button/axis samples through this adapter.

The existing native tests use fake cvar read/write callbacks and assert the MCT apply/restore behavior, including the `ps4` skin target (`controller_overlay_session_tests.cpp:103–117`). The Python package tests create a synthetic `MZ-fixture` DLL and tiny placeholder images (`test_controller_overlay.py:11–25`); they test strict archive staging and validation, not device input or rendered output. Neither test set establishes that the v1.0.7 plugin loads successfully, that the overlay is visible, or that a physical DS4/DualSense report reaches the UI. No tests were run for this report.

## Supported and unknown claims

| Claim | Evidence label | Boundary |
|---|---|---|
| Exact 1.0.7 release and binary identity | **Verified bytes / listing** | Archive and DLL match frozen MCT hashes; the publisher lists v1.0.7. Hash identity does not verify author/source provenance. |
| XInput input path | **API dependency; historical code path** | Current DLL imports XInput and exposes an XInput slot selector. The old v1.0.4 code reads XInput state, but no v1.0.7 source mapping is available. |
| PS4/DualSense Raw Input | **Strong intent evidence, runtime unknown** | Current binary imports Raw Input APIs and includes calibration UI strings; official v1.0.7 notes claim the Raw Input fix. No same-build source or device test ties those clues to correct report-to-overlay behavior. |
| Xbox/PS4/PS5 controller artwork | **Package/API labels** | Asset folders and `xco_skin` are present. The current binary's valid values, default selection, and error handling are not source-traced. |
| Physical device type detection | **Unknown** | MCT forces PS4 artwork and does not detect device type in this adapter. The binary's XInput slot selector is not proof of brand detection. |
| MCT coaching can observe plugin input samples | **Not exposed by this adapter** | The adapter controls cvars only. Use MCT's own game-input/telemetry source for coaching; do not treat the overlay image as a controller-data API. |

## Minimum next evidence for a product claim

1. Obtain a 1.0.7 source revision or build provenance that is explicitly tied to the pinned DLL, or perform bounded function-level static analysis of that exact DLL without treating imports/strings as executed paths.
2. In an explicitly owned offline test, verify the overlay output using known Xbox/XInput and native DS4/DualSense devices, including USB and Bluetooth where support is claimed. Compare deliberate button, trigger, stick, and d-pad changes with what the overlay shows. Keep that separate from MCT lesson scoring/coaching.
3. Make the selected artwork explicit or verified against the detected controller. If MCT continues forcing `ps4`, label it as a visual skin choice rather than a detected-device claim; test when the preference is hidden, the plugin is missing, and values conflict/restoration occurs.
4. Keep two acceptance layers separate: current mock tests for cvar ownership/restoration, and a future plugin-visible/device-input smoke test for the external DLL. Passing the first must not mark the second as complete.

## Provenance artifacts and source links

- The prior private artifact receipt, archive audit, and static PE report are identified by hashes in the table above; they contain the per-member inventory/import list and were not copied into this sanitized report.
- Captured official page observation: 536 bytes, SHA-256 `5a55ab9574ef49d5a091c4773eb941b26e0f0389343a857f9f968c125456307e` (page link set has no GitHub repository URL).
- [Official Controller Overlay Pro listing](https://bakkesplugins.com/plugin/707)
- [Author repository](https://github.com/ABWASSASSIN/ControllerOverlayPro)
- [Current main deletion commit](https://github.com/ABWASSASSIN/ControllerOverlayPro/commit/45c5a46ae6e5ac0690ce80fa253b1b606a134131)
- [Historical v1.0.4 source file](https://github.com/ABWASSASSIN/ControllerOverlayPro/blob/v1.0.4/src/ControllerOverlayPro.cpp)
