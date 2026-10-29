"""Pure validation and presentation data for the Power Shots setup menu."""
from __future__ import annotations

from copy import deepcopy

from .scenarios import IMPLEMENTED_SCENARIOS, LESSON_ID, RANKS, scenario_definition

DEFAULT_SCENARIO_ID = IMPLEMENTED_SCENARIOS[0]
DEFAULT_DIFFICULTY = RANKS[0]


def validate_setup(value) -> dict:
    """Return one exact, validated persisted setup without coercion."""
    if not isinstance(value, dict) or set(value) != {"scenario_id", "difficulty"}:
        raise ValueError("A Power Shots setup requires exactly scenario_id and difficulty.")
    scenario_id = value.get("scenario_id")
    difficulty = value.get("difficulty")
    if not isinstance(scenario_id, str) or not isinstance(difficulty, str):
        raise ValueError("Power Shots scenario_id and difficulty must be text.")
    scenario_definition(LESSON_ID, scenario_id, difficulty)
    return {"scenario_id": scenario_id, "difficulty": difficulty}


def setup_for(value=None) -> dict:
    """Resolve missing state to safe defaults; present state must be valid."""
    if value is None:
        return {"scenario_id": DEFAULT_SCENARIO_ID, "difficulty": DEFAULT_DIFFICULTY}
    return validate_setup(value)


def validate_lesson_scenarios(value) -> dict:
    """Validate the optional top-level per-lesson setup preference map."""
    if not isinstance(value, dict) or set(value) - {LESSON_ID}:
        raise ValueError("Lesson scenario preferences are malformed.")
    result = {}
    if LESSON_ID in value:
        result[LESSON_ID] = validate_setup(value[LESSON_ID])
    return result


def validate_action(payload) -> dict:
    """Validate the bounded ``lesson_scenario`` command payload."""
    if not isinstance(payload, dict) or set(payload) != {"id", "scenario_id", "difficulty"}:
        raise ValueError("Choose one lesson, scenario, and intended difficulty without extra fields.")
    if payload.get("id") != LESSON_ID:
        raise ValueError("Scenario selection is currently available only for Power Shots.")
    setup = validate_setup({"scenario_id": payload.get("scenario_id"),
                            "difficulty": payload.get("difficulty")})
    return {"id": LESSON_ID, **setup}


def step_setup(current, payload) -> dict:
    """Wrap one validated situation step while retaining the selected rank."""
    setup = validate_setup(current)
    if (not isinstance(payload, dict) or set(payload) != {"direction"}
            or type(payload.get("direction")) is not int
            or payload["direction"] not in {-1, 1}):
        raise ValueError("Move exactly one Power Shots situation backward or forward.")
    index = IMPLEMENTED_SCENARIOS.index(setup["scenario_id"])
    return {
        "scenario_id": IMPLEMENTED_SCENARIOS[(index + payload["direction"]) % len(IMPLEMENTED_SCENARIOS)],
        "difficulty": setup["difficulty"],
    }


def start_setup(payload, saved=None) -> dict:
    """Resolve a Power Shots start request, validating an explicit pair as a unit."""
    if not isinstance(payload, dict):
        raise ValueError("Choose a Power Shots situation before starting it.")
    if payload.get("id") != LESSON_ID:
        raise ValueError("That Power Shots request changed. Choose the situation again.")
    keys = set(payload)
    if keys == {"id"}:
        return setup_for(saved)
    if keys != {"id", "scenario_id", "difficulty"}:
        raise ValueError("Power Shots start requires both scenario_id and difficulty without extra fields.")
    return validate_setup({"scenario_id": payload.get("scenario_id"),
                           "difficulty": payload.get("difficulty")})


def scenario_options() -> list[dict]:
    """Return menu metadata for the complete implemented catalog."""
    result = []
    for scenario_id in IMPLEMENTED_SCENARIOS:
        definition = scenario_definition(LESSON_ID, scenario_id, DEFAULT_DIFFICULTY)
        result.append({key: deepcopy(definition[key]) for key in ("scenario_id", "title", "description")})
    return result

