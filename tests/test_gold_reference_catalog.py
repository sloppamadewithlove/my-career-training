"""Reference geometry and rank-aware progression, independent of game rendering."""
import copy
import math

import pytest

from my_career_training.training.engine import TrainingEngine
from my_career_training.training.scenarios import (
    IMPLEMENTED_SCENARIOS, RANKS, implemented_scenarios, scenario_definition,
    scenario_actor_controllers,
)
from my_career_training.training.scenario_setup import scenario_options, step_setup, validate_setup


@pytest.mark.parametrize("rank", RANKS)
def test_rank_catalog_and_every_neighbor_are_consistent(rank):
    ids = implemented_scenarios(rank)
    assert len(ids) == (12 if rank == "gold" else 2)
    assert ids[:2] == IMPLEMENTED_SCENARIOS
    assert [option["scenario_id"] for option in scenario_options(rank)] == list(ids)
    for index, scenario_id in enumerate(ids):
        setup = {"scenario_id": scenario_id, "difficulty": rank}
        assert validate_setup(setup) == setup
        for direction in (-1, 1):
            assert step_setup(setup, {"direction": direction}) == {
                "scenario_id": ids[(index + direction) % len(ids)], "difficulty": rank}
        engine = TrainingEngine("power-shots", scenario_id=scenario_id, difficulty=rank)
        assert engine.summary()["coaching"]["scenario_index"] == index + 1
        assert engine.summary()["coaching"]["scenario_total"] == len(ids)


@pytest.mark.parametrize("rank", [rank for rank in RANKS if rank != "gold"])
def test_gold_only_ids_are_not_accepted_for_other_ranks(rank):
    for scenario_id in implemented_scenarios("gold")[2:]:
        with pytest.raises(ValueError):
            validate_setup({"scenario_id": scenario_id, "difficulty": rank})


def test_gold_preserves_selected_source_speeds_time_limits_and_distinct_geometry():
    sources = [("6EB1-79B2-33B8-681C", shot) for shot in (1, 3, 7, 8, 9, 12)]
    bounces = [("C9E4-0F05-B71A-C322", shot) for shot in range(1, 7)]
    expected = [item for pair in zip(sources, bounces) for item in pair]
    speeds = [2150, 850, 2400, 1000, 2500, 800, 1500, 1800, 2100, 2600, 1550, 1750]
    shapes = set()
    for index, scenario_id in enumerate(implemented_scenarios("gold")):
        definition = scenario_definition("power-shots", scenario_id, "gold")
        ball = definition["starting_state"]["ball"]
        car = definition["starting_state"]["car"]
        assert (definition["source_pack"]["code"], definition["source_pack"]["shot"]) == expected[index]
        assert math.sqrt(sum(v * v for v in ball["velocity"])) == pytest.approx(speeds[index])
        assert definition["timeout"] == (10.0 if index % 2 == 0 else 5.0)
        assert car["position"][2] < 50
        assert car["velocity"] == [0.0, 0.0, 0.0]
        shapes.add(tuple(ball["position"] + ball["velocity"] + car["position"]))
        assert definition["roles"] == {"keeper": 0, "human": 1}
        assert scenario_actor_controllers(definition)[0].ground_only
    assert len(shapes) == 12
    # UE pitch/yaw rotations must produce the source's steep downward first bounce.
    bounce = scenario_definition("power-shots", "bouncing-side-pass", "gold")["starting_state"]["ball"]
    assert bounce["position"] == [22.336, 958.9754, 606.4634]
    assert bounce["velocity"][2] < -800


def test_mutating_one_returned_definition_does_not_change_later_resets():
    first = scenario_definition("power-shots", "long-outlet", "gold")
    original = copy.deepcopy(first)
    first["starting_state"]["ball"]["position"][0] += 200
    first["starting_state"]["car"]["rotation"][0] += 1
    assert scenario_definition("power-shots", "long-outlet", "gold") == original
