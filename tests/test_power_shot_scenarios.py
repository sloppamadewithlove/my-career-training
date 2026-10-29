"""Boundary checks for the complete repeatable Power Shots catalog."""

from __future__ import annotations

import copy
import math
from types import SimpleNamespace as NS
import uuid

import pytest

from my_career_training import adapter
from my_career_training.game_worker import GameSession
from my_career_training.training.engine import InvalidTrainingTelemetry, TrainingEngine
from my_career_training.training.scenarios import (
    IMPLEMENTED_SCENARIOS,
    implemented_scenarios,
    RANKS,
    scenario_actor_controllers,
    scenario_definition,
    scenario_descriptors,
)


def _actions():
    return {
        "throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
        "jump": False, "boost": False, "handbrake": False,
    }


def _actor(pose, index, team, is_bot, touch=None):
    actor = copy.deepcopy(pose)
    actor.update({
        "index": index, "player_index": index, "team": team, "is_bot": is_bot,
        "wheel_contact": True, "air_state": "OnGround", "has_jumped": False,
        "has_double_jumped": False, "has_dodged": False, "actions": _actions(),
    })
    if touch is not None:
        actor["latest_touch"] = {
            "game_seconds": touch, "location": [0.0, 0.0, 93.0],
            "normal": [0.0, 0.0, 1.0], "ball_index": 0,
        }
    return actor


def _frame(engine, t, *, setup="settle", touches=None, scores=(0, 0), ball=None):
    state = engine.lesson[f"{setup}_state" if setup == "starting" else "settle_state"]
    actors = []
    for index, pose in sorted(state["bots"].items()):
        actors.append(_actor(pose, index, 1, True, (touches or {}).get(index)))
    human = engine.human_index
    actors.append(_actor(state["car"], human, 0, False, (touches or {}).get(human)))
    value = copy.deepcopy(state["ball"])
    if ball:
        value.update(ball)
    return {
        "time": t, "dt": 1 / 120, "car": actors[human], "cars": actors,
        "ball": value, "scores": list(scores), "actions": _actions(), "packet_gap": False,
    }


def _prepare(engine):
    emitted = []
    for index in range(1, 80):
        emitted.extend(engine.update(_frame(engine, index / 120)))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    launches = [event for event in emitted if event["type"] == "set_state"]
    assert len(launches) == 1
    assert launches[0]["state"]["ball"] == engine.lesson["starting_state"]["ball"]
    go_time = engine.reset_requested_at + 1 / 120
    events = engine.update(_frame(engine, go_time, setup="starting"))
    assert engine.state == "active"
    assert [event["type"] for event in events] == ["go"]
    return go_time


def _update(engine, t, touches, *, scores=(0, 0), ball=None, gap=False):
    frame = _frame(engine, t, setup="starting", touches=touches, scores=scores, ball=ball)
    frame["packet_gap"] = gap
    return engine.update(frame)


@pytest.mark.parametrize(("scenario_id", "rank"), [
    (scenario, rank) for rank in RANKS for scenario in implemented_scenarios(rank)
])
def test_all_situations_and_ranks_build_dynamic_roster_and_controllers(scenario_id, rank):
    request = {"lesson_id": "power-shots", "scenario_id": scenario_id, "difficulty": rank}
    definition = scenario_definition(**request)
    descriptors = scenario_descriptors(request)
    controllers = scenario_actor_controllers(definition)
    beginner = rank in {"bronze", "silver"}
    expected = set() if beginner else {0} if rank in {"gold", "platinum", "diamond", "champion"} else {0, 1}

    assert definition["roles"]["human"] == len(descriptors)
    assert set(descriptors) == set(controllers) == expected
    assert {item["role"] for item in descriptors.values()} == (
        set() if beginner else {"keeper"} if rank in {"gold", "platinum", "diamond", "champion"}
        else {"keeper", "defender"})
    assert definition["teams"] == {
        **{role: 1 for role in definition["roles"] if role != "human"}, "human": 0}
    assert "passer" not in definition["roles"]
    assert "teammate" not in definition["description"].lower()
    if rank != "gold":
        assert definition["arrival_seconds"] > 1.0
        assert definition["shot_window_seconds"] >= 6
    else:
        assert definition["timeout"] in {5.0, 10.0}
        assert definition["implemented_total"] == 12








@pytest.mark.parametrize("rank", ["bronze", "silver"])
@pytest.mark.parametrize("scenario_id", IMPLEMENTED_SCENARIOS)
def test_beginner_catalog_has_no_opponents_or_aerial_requirement(rank, scenario_id):
    definition = scenario_definition("power-shots", scenario_id, rank)
    ball = definition["starting_state"]["ball"]
    assert definition["starting_state"]["bots"] == {}
    assert set(definition["roles"]) == {"human"}
    assert ball["position"][2] <= 125.0 and ball["velocity"][2] <= 0.0
    assert definition["execution"] in {
        "grounded-receive", "settled-bounce", "grounded-wall-read", "grounded-rebound"}


def test_rank_pressure_orders_keeper_before_chasing_defender_and_tightens():
    counts = []
    delays = []
    for rank in RANKS:
        definition = scenario_definition("power-shots", "low-side-pass", rank)
        counts.append(len(definition["starting_state"]["bots"]))
        if "defender_reaction_delay" in definition["pressure"]:
            delays.append(definition["pressure"]["defender_reaction_delay"])
    assert counts == [0, 0, 1, 1, 1, 1, 2, 2]
    assert delays == sorted(delays, reverse=True)








@pytest.mark.parametrize("scenario_id", IMPLEMENTED_SCENARIOS)
def test_provisional_situations_scale_across_ranks_without_the_replaced_gold_pack(scenario_id):
    ranks = [rank for rank in RANKS if rank != "gold"]
    definitions = [scenario_definition("power-shots", scenario_id, rank) for rank in ranks]
    speeds = [item["pressure"]["launch_speed"] for item in definitions]
    limits = [item["timeout"] for item in definitions]
    assert speeds == sorted(speeds) and len(set(speeds)) == len(ranks)
    assert limits == sorted(limits, reverse=True)


@pytest.mark.parametrize("rank", ["gold", "platinum"])
def test_forgiving_keeper_starts_far_from_lane_and_waits_before_safe_input(rank):
    definition = scenario_definition("power-shots", "low-side-pass", rank)
    keeper = definition["starting_state"]["bots"][0]
    lane = definition.get("receiving_lane", definition["starting_state"]["car"]["position"])
    controller = scenario_actor_controllers(definition)[0]
    frame = {
        "time": 10.0,
        "cars": [_actor(keeper, 0, 1, True), _actor(definition["starting_state"]["car"], 1, 0, False)],
        "ball": copy.deepcopy(definition["starting_state"]["ball"]), "prediction": [], "boosts": [],
    }
    controls = controller.step(frame, 0)
    assert keeper["position"][1] - lane[1] >= 900
    assert controls == _actions()
    assert controller.reaction_delay >= 1.1
    assert controller.lane_limit_y > lane[1]


@pytest.mark.parametrize(
    ("position_y", "velocity_y"),
    [(4450.0, -800.0), (4350.0, -300.0), (4350.0, 300.0)],
)
def test_keeper_boundary_guard_returns_to_goal_and_reports_actual_intent(
    position_y, velocity_y
):
    definition = scenario_definition("power-shots", "low-side-pass", "gold")
    controller = scenario_actor_controllers(definition)[0]
    keeper = copy.deepcopy(definition["starting_state"]["bots"][0])
    keeper["position"][1] = position_y
    keeper["velocity"][1] = velocity_y
    frame = {
        "time": 10.0,
        "cars": [_actor(keeper, 0, 1, True), _actor(definition["starting_state"]["car"], 1, 0, False)],
        "ball": copy.deepcopy(definition["starting_state"]["ball"]),
        "prediction": [],
        "boosts": [],
    }
    controller.started_at = 0.0

    controls = controller.step(frame, 0)

    assert controls["throttle"] < 0  # Reverse actively opposes motion toward the lane.
    assert controls["boost"] is controls["jump"] is False
    assert controller.last_decision["boundary_override"] == "return_to_goal"
    assert controller.intent["boundary_override"] == "return_to_goal"
    assert controller.intent["target"] == list(controller.home)
    assert controller.intent is not controller.delegate.intent


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("position", None),
        ("position", [0.0, 1.0]),
        ("velocity", [0.0, math.nan, 0.0]),
        ("rotation", [0.0, math.inf, 0.0]),
        ("rotation", [0.0, True, 0.0]),
    ],
)
def test_keeper_with_unavailable_pose_returns_neutral_before_delegating(
    monkeypatch, field, value
):
    definition = scenario_definition("power-shots", "low-side-pass", "gold")
    controller = scenario_actor_controllers(definition)[0]
    keeper = _actor(definition["starting_state"]["bots"][0], 0, 1, True)
    keeper[field] = value
    frame = {
        "time": 10.0,
        "cars": [keeper, _actor(definition["starting_state"]["car"], 1, 0, False)],
        "ball": copy.deepcopy(definition["starting_state"]["ball"]),
        "prediction": [],
        "boosts": [],
    }
    monkeypatch.setattr(
        controller.delegate,
        "step",
        lambda *_args, **_kwargs: pytest.fail("invalid keeper telemetry reached the delegate"),
    )

    assert controller.step(frame, 0) == _actions()
    assert controller.intent == controller.last_decision == {
        "player_index": 0,
        "team": 1,
        "time": 10.0,
        "kind": "unavailable",
        "reason": "keeper pose telemetry unavailable",
    }


def test_defender_with_unavailable_pose_returns_neutral_before_delegating(monkeypatch):
    definition = scenario_definition("power-shots", "bouncing-side-pass", "grand-champion")
    index = definition["roles"]["defender"]
    controller = scenario_actor_controllers(definition)[index]
    cars = [_actor(definition["starting_state"]["bots"][i], i, 1, True) for i in (0, 1)]
    cars[index]["velocity"] = [0.0, math.nan, 0.0]
    frame = {"time": 10.0, "cars": cars, "ball": copy.deepcopy(
        definition["starting_state"]["ball"]), "prediction": [], "boosts": []}
    monkeypatch.setattr(controller.delegate, "step",
                        lambda *_args, **_kwargs: pytest.fail("invalid defender telemetry reached delegate"))

    assert controller.step(frame, index) == _actions()
    assert controller.intent["kind"] == "unavailable"
    assert controller.intent["reason"] == "defender pose telemetry unavailable"


def _fake_flat():
    def enum(**values):
        return NS(**values)

    return NS(
        Launcher=enum(NoLaunch=0, Steam=1, Epic=2),
        MatchLengthMutator=enum(Unlimited=1, FiveMinutes=2), MaxScoreMutator=enum(Unlimited=1),
        OvertimeMutator=enum(Unlimited=1), MultiBallMutator=enum(One=1),
        BoostAmountMutator=enum(NormalBoost=1), GameMode=enum(Soccar=1),
        ExistingMatchBehavior=enum(Restart=1), DebugRendering=enum(OnByDefault=1),
        PerformanceMonitor=enum(NeverShow=1), Human=lambda: NS(kind="human"),
        CustomBot=lambda **values: NS(kind="bot", **values), PlayerLoadout=lambda **values: NS(**values),
        PlayerConfiguration=lambda **values: NS(**values), MutatorSettings=lambda **values: NS(**values),
        RespawnTimeMutator=NS(DisableGoalReset="DisableGoalReset"),
        MatchConfiguration=lambda **values: NS(**values),
    )


@pytest.mark.parametrize(("rank", "expected_human"),
                         [("bronze", 0), ("silver", 0), ("gold", 1), ("diamond", 1)])
def test_adapter_supports_zero_or_one_scenario_bot(monkeypatch, rank, expected_human):
    monkeypatch.setattr(adapter, "flat_module", _fake_flat)
    config, descriptors, human = adapter.match_config({
        "lesson_id": "power-shots", "scenario_id": "low-side-pass", "difficulty": rank,
        "settings": {"launcher": "steam"},
    })
    assert human == expected_human
    assert len(config.player_configurations) == expected_human + 1
    assert set(descriptors) == set(range(expected_human))
    assert config.player_configurations[human].variety.kind == "human"


@pytest.mark.parametrize("scenario_id", IMPLEMENTED_SCENARIOS)
def test_launch_state_is_emitted_once_per_attempt_and_never_forces_active_physics(scenario_id):
    engine = TrainingEngine("power-shots", scenario_id=scenario_id, difficulty="bronze")
    first = _prepare(engine)
    active_events = []
    for step in range(1, 8):
        active_events.extend(_update(engine, first + step / 120, {}))
    assert not any(event["type"] == "set_state" for event in active_events)

    parked = engine.reset()
    assert parked["ball"]["velocity"] == [0.0, 0.0, 0.0]
    assert parked["ball"]["position"][:2] == engine.lesson["starting_state"]["ball"]["position"][:2]
    _prepare(engine)  # A retry earns exactly one new launch write.


@pytest.mark.parametrize(("rank", "expected_bots"), [("bronze", set()), ("gold", {0})])
def test_retry_and_telemetry_recovery_reset_the_entire_dynamic_roster(
    monkeypatch, rank, expected_bots
):
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty=rank)
    session = GameSession({"session_id": str(uuid.uuid4())}, lambda _event: None)
    session.engine = engine
    session.scenario = engine.scenario
    session.human_index = engine.human_index
    session.training_actor_index = engine.human_index
    session.descriptors = {
        index: {"team": 1} for index in engine.bot_indices
    }
    session.mapping = {1: [0]} if expected_bots else {}
    session.relays = {1: NS(send_msg=lambda _message: None)} if expected_bots else {}
    reset_calls = []
    session.controllers = {
        index: NS(reset=lambda index=index: reset_calls.append(index)) for index in expected_bots
    }
    state_sets = []
    session.manager = NS(rlbot_interface=NS(send_msg=state_sets.append))
    monkeypatch.setattr(
        adapter, "desired_state",
        lambda state, human, bots=None: (copy.deepcopy(state), human, copy.deepcopy(bots or {})),
    )

    flat = NS(ControllerState=lambda **values: values, PlayerInput=lambda index, value: (index, value))
    session._wait_for_training_telemetry(
        InvalidTrainingTelemetry("missing", ("ball.position",)), 3, flat
    )
    assert session._reset_after_training_telemetry(flat) is True

    state, human, bots = state_sets[-1]
    assert human == len(expected_bots) == engine.human_index
    assert set(bots) == expected_bots
    assert state["bots"] == bots
    assert state["ball"]["velocity"] == [0.0, 0.0, 0.0]
    assert reset_calls == sorted(expected_bots)


def test_telemetry_recovery_budget_waits_for_active_phase(monkeypatch):
    events = []
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    session = GameSession({"session_id": str(uuid.uuid4())}, events.append)
    session.engine = engine
    session.scenario = engine.scenario
    session.human_index = session.training_actor_index = engine.human_index
    session.descriptors = {}
    session.mapping = {}
    session.relays = {}
    session.controllers = {}
    writes = []
    session.manager = NS(rlbot_interface=NS(send_msg=writes.append))
    monkeypatch.setattr(adapter, "desired_state", lambda state, human, bots=None:
                        (copy.deepcopy(state), human, copy.deepcopy(bots or {})))
    flat = NS(MatchPhase=NS(Active=3), ControllerState=lambda **values: values,
              PlayerInput=lambda index, value: (index, value))

    session._wait_for_training_telemetry(
        InvalidTrainingTelemetry("missing", ("ball.position",)), 1, flat)
    assert session.telemetry_recovery_pending is True
    assert session.telemetry_recovery_deadline is None
    assert session._reset_after_training_telemetry(flat, 2) is True
    assert session.telemetry_recovery_deadline is None and writes == []
    assert session._reset_after_training_telemetry(flat, 3) is True
    assert session.telemetry_recovery_pending is False
    assert writes and writes[-1][0]["ball"]["velocity"] == [0.0, 0.0, 0.0]


def test_settle_requires_configured_ball_and_every_configured_actor():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="gold")
    wrong_ball = _frame(engine, .01)
    wrong_ball["ball"]["position"][0] += 500
    assert not engine._scenario_ball_ready(wrong_ball, engine.lesson["settle_state"])
    missing_keeper = _frame(engine, .02)
    missing_keeper["cars"][0] = None
    assert not engine._bots_ready(missing_keeper, engine.lesson["settle_state"])


def test_fresh_human_shot_and_actual_score_edge_succeeds_without_a_passer():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    human = engine.human_index
    touches = {human: start + .01}
    _update(engine, start + .01, touches)
    _update(engine, start + .02, touches, ball={"position": [0.0, 5110.0, 200.0]})
    _update(engine, start + .03, touches, scores=(1, 0), ball={"position": [0.0, 5130.0, 200.0]})
    assert engine.outcome == "success"
    assert engine.scenario["scenario_id"] == "low-side-pass"
    assert engine.scenario_state["launch_baseline"]
    assert "passer_touch" not in engine.scenario_state


def test_same_packet_target_crossing_and_fresh_score_edge_succeeds():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    touches = {engine.human_index: start + .01}
    _update(engine, start + .01, touches)
    _update(
        engine,
        start + .02,
        touches,
        scores=(1, 0),
        ball={"position": [0.0, 5130.0, 200.0]},
    )
    assert engine.outcome == "success"


def test_score_edge_observed_before_target_crossing_stays_stale():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    touches = {engine.human_index: start + .01}
    events = _update(engine, start + .01, touches, scores=(1, 0))
    _update(engine, start + .02, touches, scores=(1, 0), ball={"position": [0.0, 5130.0, 200.0]})
    assert engine.outcome == "interrupted"
    assert any(event["type"] == "completed" for event in events)
    assert not any(event["type"] == "scenario_success" for event in engine.events)
    assert any("No technique credit" in message for message in engine.observations)


def test_missing_configured_keeper_invalidates_active_success_chain():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="gold")
    start = _prepare(engine)
    touches = {engine.human_index: start + .01}
    frame = _frame(
        engine,
        start + .01,
        setup="starting",
        touches=touches,
        scores=(1, 0),
        ball={"position": [0.0, 5130.0, 200.0]},
    )
    frame["cars"][0] = None
    frame["car"] = frame["cars"][engine.human_index]
    engine.update(frame)
    assert engine.scenario_state["chain_valid"] is False
    assert engine.outcome != "success"


@pytest.mark.parametrize(
    "case", ["untouched", "keeper", "keeper-own-goal", "stale", "gap", "ambiguous-score"]
)
def test_unattributable_goals_never_succeed(case):
    rank = "gold" if case in {"keeper", "keeper-own-goal"} else "bronze"
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty=rank)
    stale = {engine.human_index: .01} if case == "stale" else None
    start = _prepare(engine)
    human = engine.human_index
    touches = dict(stale or {})
    if case not in {"untouched", "stale", "keeper-own-goal"}:
        touches[human] = start + .01
    _update(engine, start + .01, touches)
    if case in {"keeper", "keeper-own-goal"}:
        touches[0] = start + .02
        _update(engine, start + .02, touches)
    if case == "gap":
        _update(engine, start + .02, touches, gap=True)
    _update(engine, start + .03, touches, ball={"position": [0.0, 5110.0, 200.0]})
    score = (2, 0) if case == "ambiguous-score" else (1, 0)
    _update(engine, start + .04, touches, scores=score, ball={"position": [0.0, 5130.0, 200.0]})
    assert engine.outcome != "success"


def test_bouncing_beginner_settles_earlier_than_gold_low_volley():
    bronze = scenario_definition("power-shots", "bouncing-side-pass", "bronze")
    gold = scenario_definition("power-shots", "bouncing-side-pass", "gold")
    assert bronze["execution"] == "settled-bounce"
    assert gold["execution"] == "reference-power-shot"
    assert bronze["starting_state"]["ball"]["position"][2] < gold["starting_state"]["ball"]["position"][2]
    assert math.hypot(*bronze["starting_state"]["ball"]["velocity"][:2]) < 1000


def test_bouncing_launch_is_confirmed_in_the_pre_bounce_next_packet_window():
    engine = TrainingEngine("power-shots", scenario_id="bouncing-side-pass", difficulty="bronze")
    for index in range(1, 80):
        engine.update(_frame(engine, index / 120))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    confirmation_time = engine.reset_requested_at + 1 / 60
    engine.update(_frame(engine, confirmation_time, setup="starting"))
    assert engine.state == "active"
    assert confirmation_time - engine.reset_requested_at <= engine.tolerances["max_packet_interval"]


def test_ready_confirmation_waits_for_active_play_phase_without_spending_two_seconds():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    for index in range(1, 80):
        engine.update(_frame(engine, index / 120))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    for phase, timestamp in [(1, 5.0), (2, 12.0), (4, 20.0)]:
        frame = _frame(engine, timestamp, setup="starting")
        frame.update(phase=phase)
        assert engine.update(frame) == []
        assert engine.state == "ready"
    resumed = _frame(engine, 20.01, setup="starting")
    resumed.update(phase=3)
    assert [event["type"] for event in engine.update(resumed)] == ["go"]
    assert engine.state == "active"


def test_disruptive_phase_explicitly_interrupts_and_retry_restores_full_timer():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    active = _frame(engine, start + 1.0, setup="starting")
    active.update(phase=3)
    engine.update(active)
    before = engine.summary()["coaching"]
    paused = _frame(engine, start + 40.0, setup="starting")
    paused.update(phase=6)
    events = engine.update(paused)
    during = engine.summary()["coaching"]

    assert events[-1]["type"] == "completed"
    assert engine.state == engine.outcome == "interrupted"
    assert before["time_remaining_seconds"] == during["time_remaining_seconds"]
    assert during["match_phase"] == "MatchPhase.Paused"
    assert all(key in during for key in (
        "scenario_index", "scenario_total", "scenario_title", "rank_title",
        "time_limit_seconds", "time_remaining_seconds", "phase", "countdown"))
    assert during["scenario_index"] == 1 and during["scenario_total"] == len(IMPLEMENTED_SCENARIOS)
    engine.reset()
    assert engine.summary()["coaching"]["time_remaining_seconds"] == engine.scenario["timeout"]


def test_goal_score_phase_packet_can_complete_existing_strict_chain():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    touches = {engine.human_index: start + .01}
    _update(engine, start + .01, touches)
    _update(engine, start + .02, touches, ball={"position": [0.0, 5130.0, 200.0]})
    goal = _frame(engine, start + .03, setup="starting", touches=touches, scores=(1, 0),
                  ball={"position": [0.0, 5130.0, 200.0]})
    goal.update(phase=4)

    events = engine.update(goal)

    assert engine.outcome == "success"
    assert events[-1]["type"] == "completed"
    assert engine.summary()["coaching"]["match_phase"] == "MatchPhase.GoalScored"


def test_replay_or_cadence_gap_never_resumes_or_credits_a_goal():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    touches = {engine.human_index: start + .01}
    _update(engine, start + .01, touches)
    replay = _frame(engine, start + .5, setup="starting", touches=touches, scores=(1, 0),
                    ball={"position": [0.0, 5130.0, 200.0]})
    replay.update(phase=5, packet_gap=True)
    engine.update(replay)
    engine.update(dict(replay, time=start + .51, phase=3, packet_gap=False))
    assert engine.outcome == "interrupted"


def test_active_clock_really_times_out_without_advancing_the_situation():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    start = _prepare(engine)
    frame = _frame(engine, start + engine.scenario["timeout"] + .01, setup="starting")
    frame.update(phase=3)
    events = engine.update(frame)
    assert engine.finished and engine.outcome == "timeout"
    assert engine.scenario["scenario_id"] == "low-side-pass"
    assert events[-1]["type"] == "completed"


@pytest.mark.parametrize(("rank", "start_id", "direction", "expected"), [
    ("diamond", "low-side-pass", -1, "bouncing-side-pass"),
    ("diamond", "bouncing-side-pass", 1, "low-side-pass"),
    ("diamond", "low-side-pass", 1, "bouncing-side-pass"),
    ("gold", "low-side-pass", -1, "central-return-bounce"),
    ("gold", "central-return-bounce", 1, "low-side-pass"),
    ("gold", "bouncing-side-pass", 1, "left-diagonal-pass"),
])
@pytest.mark.parametrize("saved_result", [False, True])
def test_worker_scenario_step_wraps_same_rank_and_resets_engine_controllers_and_request(
    monkeypatch, rank, start_id, direction, expected, saved_result
):
    events = []
    request = {"session_id": str(uuid.uuid4()), "lesson_id": "power-shots",
               "scenario_id": start_id, "difficulty": rank}
    session = GameSession(request, events.append)
    session.engine = TrainingEngine("power-shots", scenario_id=start_id, difficulty=rank)
    session.scenario = session.engine.scenario
    session.human_index = session.training_actor_index = session.engine.human_index
    session.descriptors = scenario_descriptors(request)
    session.controllers = scenario_actor_controllers(session.scenario)
    if saved_result:
        session.engine.state, session.engine.outcome = "finished", "timeout"
        session.attempt_sent = session.engine.attempt_id
        session.attempt_acked = True
    previous_engine = session.engine
    previous_controllers = session.controllers
    writes = []
    session.manager = NS(rlbot_interface=NS(send_msg=writes.append))
    monkeypatch.setattr(adapter, "desired_state", lambda state, human, bots=None:
                        (copy.deepcopy(state), human, copy.deepcopy(bots or {})))

    session.handle_command({"id": "step-1", "type": "training_scenario_step",
                            "session_id": session.session_id, "direction": direction})

    assert session.request["scenario_id"] == expected
    assert session.request["difficulty"] == rank
    assert session.engine is not previous_engine and session.engine.state == "settling"
    assert session.controllers is not previous_controllers and set(session.controllers) == {0}
    assert writes and writes[-1][1] == session.human_index and set(writes[-1][2]) == {0}
    assert events[-1] == {"type": "training_scenario_step_ack", "session_id": session.session_id,
                          "id": "step-1", "accepted": True,
                          "scenario_id": expected, "difficulty": rank}


@pytest.mark.parametrize("payload", [{}, {"direction": 0}, {"direction": True},
                                      {"direction": 1, "extra": 1}])
def test_worker_invalid_scenario_step_never_mutates_live_setup(monkeypatch, payload):
    events = []
    request = {"session_id": str(uuid.uuid4()), "lesson_id": "power-shots",
               "scenario_id": "low-side-pass", "difficulty": "bronze"}
    session = GameSession(request, events.append)
    session.engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    session.scenario = session.engine.scenario
    session.human_index = session.training_actor_index = session.engine.human_index
    session.descriptors = {}
    session.controllers = {}
    session.manager = NS(rlbot_interface=NS(send_msg=lambda _message: pytest.fail("invalid step wrote state")))
    before_engine = session.engine

    session.handle_command({"id": "bad", "type": "training_scenario_step", **payload})
    assert session.engine is before_engine
    assert session.request["scenario_id"] == "low-side-pass"
    assert events[-1]["type"] == "training_scenario_step_ack" and not events[-1]["accepted"]


@pytest.mark.parametrize("completed", [False, True])
def test_worker_scenario_step_does_not_discard_pending_or_completed_result(completed):
    events = []
    request = {"session_id": str(uuid.uuid4()), "lesson_id": "power-shots",
               "scenario_id": "low-side-pass", "difficulty": "bronze"}
    session = GameSession(request, events.append)
    session.engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    session.scenario = session.engine.scenario
    session.human_index = session.training_actor_index = 0
    session.descriptors = {}
    session.controllers = {}
    session.manager = NS(rlbot_interface=NS(send_msg=lambda _message: pytest.fail("result was discarded")))
    if completed:
        session.engine.state, session.engine.outcome = "finished", "timeout"
    else:
        session.attempt_sent = session.engine.attempt_id
    before = session.engine

    session.handle_command({"id": "late", "type": "training_scenario_step", "direction": 1})
    assert session.engine is before and session.request["scenario_id"] == "low-side-pass"
    assert session.pending_training_control["command"]["id"] == "late"
    assert session.pending_training_control["attempt_id"] == before.attempt_id
    assert not any(event["type"] == "training_scenario_step_ack" for event in events)


def test_scenario_metadata_is_additive_and_legacy_recordings_remain_readable():
    from my_career_training.training.recordings import validate_recording

    scenario = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="gold")
    _prepare(scenario)
    recording = scenario.recording()
    validate_recording(recording)
    assert recording["metadata"]["scenario_id"] == "low-side-pass"
    assert recording["metadata"]["scenario_version"] == 4
    assert "no validated teaching" in scenario.scenario["reference_status"].lower()

    legacy = TrainingEngine("power-shots").recording()
    assert legacy["schema_version"] == 1 and legacy["lesson_id"] == "power-shots"
    assert not ({"scenario_id", "difficulty", "scenario_version"} & set(legacy["metadata"]))


def test_power_shots_hud_shows_only_challenge_timer_controls_and_state():
    from contextlib import nullcontext
    session = GameSession({"session_id": str(uuid.uuid4()), "lesson_id": "power-shots",
        "scenario_id": "low-side-pass", "difficulty": "bronze"}, lambda event: None)
    session.engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="bronze")
    session.scenario = session.engine.scenario
    drawn = []
    session.renderer = NS(can_render=True, context=lambda _: nullcontext(),
        draw_string_2d=lambda text, *_: drawn.append(text))
    session.render({})
    assert drawn == ["1/2    0:15", "Left / Right: challenge    Up: retry", "Release controls to reset"]
    drawn.clear()
    session.engine.state, session.engine.outcome = "finished", "timeout"
    session.engine.active_elapsed = session.engine.scenario["timeout"]
    session.render({})
    assert drawn == ["1/2    0:00", "Left / Right: challenge    Up: retry", "Time up"]


@pytest.mark.parametrize("rank", ["gold", "platinum"])
def test_ground_keeper_suppresses_delegate_jump_and_boost(monkeypatch, rank):
    definition = scenario_definition("power-shots", "low-side-pass", rank)
    controller = scenario_actor_controllers(definition)[0]
    car = _actor(definition["starting_state"]["bots"][0], 0, 1, True)
    car["position"][1] = 5050.0
    frame = {"time": 10.0, "cars": [car], "ball": definition["starting_state"]["ball"]}
    calls = []
    def delegate(*_args, **_kwargs):
        calls.append(True)
        return {**_actions(), "jump": True, "boost": True}
    monkeypatch.setattr(controller.delegate, "step", delegate)
    controller.step(frame, 0)
    frame["time"] += 5
    controls = controller.step(frame, 0)
    assert calls and controls["jump"] is controls["boost"] is False


@pytest.mark.parametrize("manual", [None, "retry_lesson", "training_scenario_step"])
@pytest.mark.parametrize("goal_phase", [3, 4])
def test_goal_progression_waits_for_save_and_active_play_and_manual_control_wins(monkeypatch, manual, goal_phase):
    events, writes = [], []
    request = {"session_id": str(uuid.uuid4()), "lesson_id": "power-shots",
               "scenario_id": "low-side-pass", "difficulty": "gold"}
    session = GameSession(request, events.append)
    session.engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="gold")
    session.scenario = session.engine.scenario
    session.human_index = session.training_actor_index = session.engine.human_index
    session.descriptors = scenario_descriptors(request)
    session.controllers = scenario_actor_controllers(session.scenario)
    session.manager = NS(rlbot_interface=NS(send_msg=writes.append))
    monkeypatch.setattr(adapter, "desired_state", lambda *args: args)
    session.engine.state, session.engine.outcome = "finished", "interrupted"
    session.engine.scenario_state["score_baseline"] = [0, 0]
    old = session.engine
    session.last_frame = {"phase": goal_phase, "scores": [1, 0]}
    session._queue_goal_progression(session.last_frame)
    assert session.pending_training_control["automatic"]
    assert not writes and session.engine is old
    if manual:
        session.handle_command({"id": "manual-a", "type": manual, "direction": -1})
        assert session.pending_training_control["command"]["id"] == "manual-a"
        assert not session.pending_training_control["automatic"]
    session.handle_command({"type": "attempt_ack", "attempt_id": "stale"})
    session._try_training_control()
    assert not writes
    session.handle_command({"type": "attempt_ack", "attempt_id": old.attempt_id})
    session._try_training_control()
    if goal_phase == 4:
        assert not writes  # No setup write into the stock goal/replay phase.
    session.last_frame = {"phase": 3}
    session._try_training_control()
    assert len(writes) == 1 and session.pending_training_control is None
    assert session.request["scenario_id"] == ("low-side-pass" if manual == "retry_lesson" else
        "central-return-bounce" if manual == "training_scenario_step" else "bouncing-side-pass")
    if manual != "retry_lesson":
        assert old.outcome == "interrupted"  # Progression did not forge technique credit.
    session._try_training_control()
    assert len(writes) == 1

def test_stop_cancels_queued_training_control_without_state_write():
    session = GameSession({"session_id": str(uuid.uuid4())}, lambda event: None)
    session.pending_training_control = {"command": {"id": "queued"}}
    session.handle_command({"type": "stop", "id": "stop-a"})
    assert session.pending_training_control is None and session.stopping


def test_active_goal_on_transport_gap_ends_without_inventing_technique_credit():
    engine = TrainingEngine("power-shots", scenario_id="low-side-pass", difficulty="gold")
    start = _prepare(engine)
    frame = _frame(engine, start + .025, setup="starting", scores=(1, 0))
    frame.update(phase=3, packet_gap=True)
    events = engine.update(frame)
    assert engine.outcome == "interrupted" and engine.finished
    assert any(event["type"] == "completed" for event in events)
    assert not any(event["type"] == "scenario_success" for event in engine.events)
    assert any("No technique credit" in message for message in engine.observations)
