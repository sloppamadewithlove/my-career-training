"""Fail-closed native-menu policy. This does not launch a game or touch a plugin.

Mutation stays closed: there is no reviewed source compatibility record.
The pinned Steam identity below is an opt-in read-only diagnostic trial, not
compatibility verification and not a mutation allowlist. Caller allowlists,
UI state, and grant flags are ignored as authorization.

Scope booleans are separate inputs from the existing owned-session check.
They do not grant verified compatibility. This module does not read process
lists, hashes, or paths.
"""
from __future__ import annotations

SCHEMA_VERSION = 1
NATIVE_MUTATION_SUPPORTED = False

# Observed Steam executable identity for the read-only trial only.
DIAGNOSTIC_EXECUTABLE_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
DIAGNOSTIC_FILE_VERSION = "1.0.10897.0"
DIAGNOSTIC_STEAM_BUILD_ID = "25914621"
DIAGNOSTIC_BAKKESMOD_CORE_VERSION = "229"

_GRANT_TRUE_KEYS = (
    "mutations_allowed",
    "mutations_permitted",
    "verified_compatible",
    "compatible",
    "read_only_diagnostic_eligible",
    "diagnostic_eligible",
    "authorized",
    "confirmed",
    "caller_authorization",
)


def evaluate(observation: object) -> dict[str, object]:
    """Return the mutation and read-only diagnostic decisions for one receipt."""
    if type(observation) is not dict or any(type(key) is not str for key in observation):
        return _decision(False, "not_a_receipt", ["not_a_receipt", "mutation_not_verified"])
    reasons = [
        *_identity_reasons(observation),
        *_scope_reasons(observation),
    ]
    eligible = not reasons
    if eligible:
        reason = "read_only_trial_only"
        reasons = ["mutation_not_verified"]
    else:
        reason = reasons[0]
        reasons = [*reasons, "mutation_not_verified"]
    if _caller_authorization(observation):
        reasons.append("caller_authorization_refused")
    return _decision(eligible, reason, reasons)


def _decision(eligible: bool, reason: str, blocking: list[str]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mutations_allowed": False,
        "verified_compatible": False,
        "read_only_diagnostic_eligible": eligible,
        "plugin_api_touch": False,
        "launcher_write": False,
        "trial": "opt_in_read_only" if eligible else "",
        "reason": reason,
        "blocking_reasons": blocking,
    }


def _caller_authorization(observation: dict) -> bool:
    if "allowlist" in observation:
        return True
    if any(observation.get(key) is True for key in _GRANT_TRUE_KEYS):
        return True
    ui_state = observation.get("ui_state")
    return type(ui_state) is dict and ui_state.get("confirmed") is True


def _identity_reasons(observation: dict) -> list[str]:
    reasons = []
    for reason in (
        _hash_reason(observation),
        _file_version_reason(observation),
        _steam_reason(observation),
        _core_reason(observation),
    ):
        if reason:
            reasons.append(reason)
    return reasons


def _hash_reason(observation: dict) -> str | None:
    status, value = _text(observation, "executable_sha256")
    if status == "missing":
        return "missing_executable_hash"
    if status != "present" or not _hex64(value):
        return "invalid_executable_hash"
    if value != DIAGNOSTIC_EXECUTABLE_SHA256:
        return "executable_hash_mismatch"
    return None


def _file_version_reason(observation: dict) -> str | None:
    status, value = _text(observation, "file_version")
    if status == "missing":
        return "missing_file_version"
    if status != "present" or not _dotted_numbers(value, 4):
        return "invalid_file_version"
    if value != DIAGNOSTIC_FILE_VERSION:
        return "file_version_mismatch"
    return None


def _steam_reason(observation: dict) -> str | None:
    status, value = _text(observation, "steam_build_id")
    if status == "missing":
        return "missing_steam_build_id"
    if status != "present" or not (5 <= len(value) <= 12 and _digits(value)):
        return "invalid_steam_build_id"
    if value != DIAGNOSTIC_STEAM_BUILD_ID:
        return "steam_build_mismatch"
    return None


def _core_reason(observation: dict) -> str | None:
    status, value = _text(observation, "bakkesmod_core_version")
    if status == "missing":
        return "missing_bakkesmod_core_version"
    if status != "present" or not (1 <= len(value) <= 8 and _digits(value)):
        return "invalid_bakkesmod_core_version"
    if value != DIAGNOSTIC_BAKKESMOD_CORE_VERSION:
        return "bakkesmod_core_mismatch"
    return None


def _scope_reasons(observation: dict) -> list[str]:
    fields = ("owned", "offline", "fresh", "online")
    if any(key not in observation or observation[key] is None for key in fields):
        return ["missing_process_scope"]
    if any(type(observation[key]) is not bool for key in fields):
        return ["invalid_process_scope"]
    reasons = []
    if observation["owned"] is not True:
        reasons.append("unowned_session")
    if observation["online"] is True:
        reasons.append("online_session")
    if observation["offline"] is not True:
        reasons.append("not_offline")
    if observation["fresh"] is not True:
        reasons.append("stale_session")
    return reasons


def _text(observation: dict, key: str) -> tuple[str, str]:
    if key not in observation or observation[key] is None or observation[key] == "":
        return "missing", ""
    value = observation[key]
    if type(value) is not str or len(value) > 128 or _path_text(value):
        return "invalid", ""
    return "present", value


def _path_text(value: str) -> bool:
    return "\\" in value or "/" in value or ":" in value


def _hex64(value: str) -> bool:
    return len(value) == 64 and all("0" <= char <= "9" or "a" <= char <= "f" for char in value)


def _digits(value: str) -> bool:
    return bool(value) and all("0" <= char <= "9" for char in value)


def _dotted_numbers(value: str, count: int) -> bool:
    parts = value.split(".")
    return len(parts) == count and all(_digits(part) for part in parts)
