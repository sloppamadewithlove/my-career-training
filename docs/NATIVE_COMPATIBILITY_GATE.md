# Native compatibility gate

This is a source policy, not a game receipt. It does not launch Rocket League, load a plugin, write BakkesMod configuration, or touch the separate opt-in host trial.

Native menu mutation is closed. No reviewed source compatibility record is present, and the observed Steam identity below is not a mutation allowlist. A detected hash or build is not compatibility verification.

## Decisions

`evaluate` returns these operations separately. Only the read-only trial can become eligible, and only for the exact identity and scope below.

| Field | Meaning |
| --- | --- |
| `mutations_allowed` | Always false. Menu mutation stays closed. |
| `verified_compatible` | Always false. Identity is not verification. |
| `read_only_diagnostic_eligible` | True only for the opt-in read-only trial. |
| `plugin_api_touch` | Always false. This decision does not authorize a plugin call. |
| `launcher_write` | Always false. This decision does not authorize a launch or launcher write. |
| `trial` | `opt_in_read_only` when eligible, otherwise empty. |

Python: `my_career_training.native_compatibility.evaluate(observation)`. There is no allowlist argument. C++: `mct::NativeBuildGate::evaluate(observation, callerAllowlist)`. A non-empty `callerAllowlist` is not read and cannot change the identity decision; it only adds `caller_authorization_refused`.

## Read-only trial identity

All four values must match exactly, in their own fields. `229` is the BakkesMod core version only. It is not the executable file version, not a Steam build id, and not a game-build alias. `1.0.10897.0` is the executable file version only.

| Field | Required value |
| --- | --- |
| `executable_sha256` | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` |
| `file_version` | `1.0.10897.0` |
| `steam_build_id` | `25914621` |
| `bakkesmod_core_version` | `229` |

The hash identifies those executable bytes. It does not establish an ABI or object lifetime. The policy stores no game path.

Scope is separate and exact: `owned` true, `offline` true, `fresh` true, and `online` false. Missing or non-boolean scope is refused. These booleans must come from the existing owned-session check (`OwnedSession::ownedSession` or `bootstrap.verify_owned_offline`). A UI flag, `confirmed` state, or caller boolean cannot grant `verified_compatible` or mutation. Unknown, missing, and malformed hashes, file versions, Steam build ids, and BakkesMod core versions are refused with their own reasons.

## Reasons

The first blocking reason is `reason`, except for an eligible trial, whose reason is `read_only_trial_only` while `mutation_not_verified` stays in `blocking_reasons`.

Identity, in order: `missing_executable_hash`, `invalid_executable_hash`, `executable_hash_mismatch`, `missing_file_version`, `invalid_file_version`, `file_version_mismatch`, `missing_steam_build_id`, `invalid_steam_build_id`, `steam_build_mismatch`, `missing_bakkesmod_core_version`, `invalid_bakkesmod_core_version`, `bakkesmod_core_mismatch`.

Scope: `missing_process_scope`, `invalid_process_scope`, `unowned_session`, `online_session`, `not_offline`, `stale_session`. The C++ observation always has the four booleans, so a default C++ value is unowned and online rather than `missing_process_scope`.

A caller `allowlist`, `mutations_allowed`, `verified_compatible`, or confirming UI state adds `caller_authorization_refused` and does not open mutation. A receipt that is not an object is `not_a_receipt`.

## Tests and integration

Python: `.venv\Scripts\python.exe -m pytest tests/test_native_compatibility.py`

The native test is `plugin/tests/native_build_gate_tests.cpp`. It includes only `NativeBuildGate.h` and is registered in CMake:

```cmake
add_executable(mct_native_build_gate_tests tests/native_build_gate_tests.cpp)
target_include_directories(mct_native_build_gate_tests PRIVATE include)
target_compile_features(mct_native_build_gate_tests PRIVATE cxx_std_17)
add_test(NAME native_build_gate COMMAND mct_native_build_gate_tests)
```

Do not treat a passing test, a matching hash, or read-only eligibility as permission to install a plugin, write a launcher file, or mutate a menu. Opening mutation later requires a reviewed source compatibility record with evidence, not a caller-supplied allowlist. The host trial remains its own opt-in path.
