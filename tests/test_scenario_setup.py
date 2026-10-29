"""Pure setup contracts for the twelve implemented Power Shots situations."""
import pytest

from my_career_training.training.scenario_setup import (
    DEFAULT_DIFFICULTY,
    DEFAULT_SCENARIO_ID,
    scenario_options,
    setup_for,
    start_setup,
    step_setup,
    validate_action,
    validate_lesson_scenarios,
    validate_setup,
)
from my_career_training.training.scenarios import IMPLEMENTED_SCENARIOS, RANKS


def test_missing_setup_uses_safe_first_scenario_and_bronze():
    assert setup_for() == {"scenario_id": DEFAULT_SCENARIO_ID, "difficulty": DEFAULT_DIFFICULTY}
    assert DEFAULT_SCENARIO_ID == "low-side-pass"
    assert DEFAULT_DIFFICULTY == "bronze"
    assert [item["scenario_id"] for item in scenario_options()] == list(IMPLEMENTED_SCENARIOS)
    assert all(item["description"] for item in scenario_options())
    assert all("teammate" not in item["description"].lower() for item in scenario_options())


@pytest.mark.parametrize("scenario_id", IMPLEMENTED_SCENARIOS)
@pytest.mark.parametrize("difficulty", RANKS)
def test_every_implemented_setup_validates_exactly(scenario_id, difficulty):
    setup = {"scenario_id": scenario_id, "difficulty": difficulty}
    assert validate_setup(setup) == setup
    assert validate_action({"id": "power-shots", **setup}) == {"id": "power-shots", **setup}


@pytest.mark.parametrize("value", [
    None,
    [],
    {"scenario_id": "low-side-pass"},
    {"scenario_id": "low-side-pass", "difficulty": "bronze", "extra": True},
    {"scenario_id": 1, "difficulty": "bronze"},
    {"scenario_id": "unknown", "difficulty": "bronze"},
    {"scenario_id": "low-side-pass", "difficulty": "Bronze"},
])
def test_present_setup_rejects_missing_unknown_wrong_type_or_spurious_fields(value):
    with pytest.raises(ValueError):
        validate_setup(value)


def test_start_explicit_pair_never_falls_back_and_saved_pair_is_used_only_when_omitted():
    saved = {"scenario_id": "bouncing-side-pass", "difficulty": "diamond"}
    assert start_setup({"id": "power-shots"}, saved) == saved
    explicit = {"id": "power-shots", "scenario_id": "low-side-pass", "difficulty": "silver"}
    assert start_setup(explicit, saved) == {"scenario_id": "low-side-pass", "difficulty": "silver"}
    with pytest.raises(ValueError):
        start_setup({"id": "power-shots", "scenario_id": "unknown"}, saved)
    with pytest.raises(ValueError):
        start_setup({"id": "power-shots", "difficulty": "bronze"}, saved)


def test_optional_preferences_map_is_strict_when_present():
    assert validate_lesson_scenarios({}) == {}
    expected = {"power-shots": {"scenario_id": "low-side-pass", "difficulty": "champion"}}
    assert validate_lesson_scenarios(expected) == expected
    with pytest.raises(ValueError):
        validate_lesson_scenarios({"speed-flip": expected["power-shots"]})


def test_step_wraps_twelve_situations_and_keeps_rank():
    first = {"scenario_id": IMPLEMENTED_SCENARIOS[0], "difficulty": "champion"}
    last = {"scenario_id": IMPLEMENTED_SCENARIOS[-1], "difficulty": "champion"}
    assert step_setup(first, {"direction": -1}) == last
    assert step_setup(last, {"direction": 1}) == first
    assert step_setup(first, {"direction": 1}) == {
        "scenario_id": IMPLEMENTED_SCENARIOS[1], "difficulty": "champion"}


@pytest.mark.parametrize("payload", [None, {}, {"direction": 0}, {"direction": True},
                                      {"direction": -1, "extra": 1}])
def test_step_payload_is_exact(payload):
    with pytest.raises(ValueError):
        step_setup({"scenario_id": "low-side-pass", "difficulty": "bronze"}, payload)

