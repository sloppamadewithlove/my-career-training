import inspect
import json
from pathlib import Path

import pytest

from my_career_training.native_compatibility import (
    DIAGNOSTIC_BAKKESMOD_CORE_VERSION,
    DIAGNOSTIC_EXECUTABLE_SHA256,
    DIAGNOSTIC_FILE_VERSION,
    DIAGNOSTIC_STEAM_BUILD_ID,
    NATIVE_MUTATION_SUPPORTED,
    evaluate,
)

ROOT = Path(__file__).resolve().parents[1]


def _ready():
    return {
        "executable_sha256": DIAGNOSTIC_EXECUTABLE_SHA256,
        "file_version": DIAGNOSTIC_FILE_VERSION,
        "steam_build_id": DIAGNOSTIC_STEAM_BUILD_ID,
        "bakkesmod_core_version": DIAGNOSTIC_BAKKESMOD_CORE_VERSION,
        "owned": True,
        "offline": True,
        "fresh": True,
        "online": False,
    }


def _check(decision):
    assert decision["schema_version"] == 1
    assert decision["mutations_allowed"] is False
    assert decision["verified_compatible"] is False
    assert decision["plugin_api_touch"] is False
    assert decision["launcher_write"] is False
    assert "mutation_not_verified" in decision["blocking_reasons"]
    assert NATIVE_MUTATION_SUPPORTED is False
    if decision["read_only_diagnostic_eligible"]:
        assert decision["trial"] == "opt_in_read_only"
        assert decision["reason"] == "read_only_trial_only"
    else:
        assert decision["trial"] == ""
        assert decision["reason"] == decision["blocking_reasons"][0]
    assert json.loads(json.dumps(decision)) == decision
    return decision


def test_diagnostic_target_stays_read_only_and_unverified():
    decision = _check(evaluate(_ready()))
    assert decision["read_only_diagnostic_eligible"] is True
    assert decision["blocking_reasons"] == ["mutation_not_verified"]


def test_grant_flags_do_not_upgrade_the_read_only_trial():
    observation = _ready()
    observation["allowlist"] = [DIAGNOSTIC_EXECUTABLE_SHA256]
    observation["mutations_permitted"] = True
    observation["verified_compatible"] = True
    observation["ui_state"] = {"confirmed": True}
    before = json.dumps(observation)
    decision = _check(evaluate(observation))
    assert json.dumps(observation) == before
    assert decision["read_only_diagnostic_eligible"] is True
    assert decision["blocking_reasons"] == [
        "mutation_not_verified",
        "caller_authorization_refused",
    ]


def test_caller_allowlist_cannot_repair_or_authorize_a_mismatch():
    observation = _ready()
    observation["executable_sha256"] = "a" * 64
    observation["allowlist"] = [{
        "executable_sha256": DIAGNOSTIC_EXECUTABLE_SHA256,
        "mutations_permitted": True,
    }]
    observation["mutations_allowed"] = True
    observation["read_only_diagnostic_eligible"] = True
    decision = _check(evaluate(observation))
    assert decision["reason"] == "executable_hash_mismatch"
    assert decision["read_only_diagnostic_eligible"] is False
    assert "caller_authorization_refused" in decision["blocking_reasons"]
    assert "allowlist" not in inspect.signature(evaluate).parameters


def test_missing_identity_and_scope_are_refused():
    decision = _check(evaluate({}))
    assert decision["reason"] == "missing_executable_hash"
    assert "missing_file_version" in decision["blocking_reasons"]
    assert "missing_steam_build_id" in decision["blocking_reasons"]
    assert "missing_bakkesmod_core_version" in decision["blocking_reasons"]
    assert "missing_process_scope" in decision["blocking_reasons"]


def test_absent_online_flag_is_not_treated_as_offline():
    observation = _ready()
    del observation["online"]
    assert _check(evaluate(observation))["reason"] == "missing_process_scope"


def test_normal_online_launch_is_refused():
    observation = _ready()
    observation["online"] = True
    observation["offline"] = False
    decision = _check(evaluate(observation))
    assert decision["reason"] == "online_session"
    assert "not_offline" in decision["blocking_reasons"]


def test_stale_owned_session_is_refused():
    observation = _ready()
    observation["fresh"] = False
    assert _check(evaluate(observation))["reason"] == "stale_session"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("executable_sha256", "a" * 64, "executable_hash_mismatch"),
        ("file_version", "1.0.10897.1", "file_version_mismatch"),
        ("steam_build_id", "25914622", "steam_build_mismatch"),
        ("bakkesmod_core_version", "230", "bakkesmod_core_mismatch"),
        ("executable_sha256", "A" * 64, "invalid_executable_hash"),
        ("executable_sha256", "a/b", "invalid_executable_hash"),
        ("file_version", "229", "invalid_file_version"),
        ("steam_build_id", "229", "invalid_steam_build_id"),
        ("bakkesmod_core_version", "1.0.10897.0", "invalid_bakkesmod_core_version"),
        ("bakkesmod_core_version", "2.0.78", "invalid_bakkesmod_core_version"),
        ("owned", False, "unowned_session"),
        ("owned", 1, "invalid_process_scope"),
    ],
)
def test_mismatch_and_invalid_identity_stay_closed(field, value, reason):
    observation = _ready()
    observation[field] = value
    decision = _check(evaluate(observation))
    assert decision["reason"] == reason
    assert decision["read_only_diagnostic_eligible"] is False


def test_version_fields_are_not_interchangeable():
    observation = _ready()
    observation["file_version"] = "229"
    observation["bakkesmod_core_version"] = DIAGNOSTIC_FILE_VERSION
    observation["game_build"] = DIAGNOSTIC_FILE_VERSION
    observation["bakkes_version"] = "229"
    decision = _check(evaluate(observation))
    assert decision["reason"] == "invalid_file_version"
    assert "invalid_bakkesmod_core_version" in decision["blocking_reasons"]


def test_other_version_names_do_not_supply_the_core_version():
    observation = _ready()
    del observation["bakkesmod_core_version"]
    observation["bakkes_version"] = "229"
    observation["game_build"] = "25914621"
    assert _check(evaluate(observation))["reason"] == "missing_bakkesmod_core_version"


@pytest.mark.parametrize("value", [None, [], "allowlist", 229])
def test_non_object_receipt_is_refused(value):
    assert _check(evaluate(value))["reason"] == "not_a_receipt"


def test_policy_source_has_no_game_path_or_mutation_grant():
    sources = [
        ROOT / "src" / "my_career_training" / "native_compatibility.py",
        ROOT / "plugin" / "include" / "NativeBuildGate.h",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert DIAGNOSTIC_EXECUTABLE_SHA256 in text
        assert DIAGNOSTIC_FILE_VERSION in text
        assert DIAGNOSTIC_STEAM_BUILD_ID in text
        assert DIAGNOSTIC_BAKKESMOD_CORE_VERSION in text
        assert "RocketLeague.exe" not in text
        assert ":\\" not in text
        assert "mutations_allowed = True" not in text
        assert "mutationsAllowed = true" not in text
