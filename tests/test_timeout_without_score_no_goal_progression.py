"""Isolated regression: a timed-out Power Shots attempt cannot auto-advance without a score."""

from types import SimpleNamespace as NS

import pytest

from test_worker import simulated_session
from my_career_training import adapter
from my_career_training.training.engine import TrainingEngine
from my_career_training.training.scenarios import (
    scenario_actor_controllers,
    scenario_descriptors,
)


@pytest.mark.parametrize("phase", [3, 4])
def test_timed_out_attempt_without_score_never_queues_goal_progression(
    tmp_path, monkeypatch, phase
):
    events = []
    session, _packet = simulated_session(tmp_path, monkeypatch, events)
    session.request = {
        "session_id": session.session_id,
        "lesson_id": "power-shots",
        "scenario_id": "low-side-pass",
        "difficulty": "gold",
    }
    session.engine = TrainingEngine(
        "power-shots", scenario_id="low-side-pass", difficulty="gold"
    )
    session.scenario = session.engine.scenario
    session.human_index = session.engine.human_index
    session.training_actor_index = session.human_index
    session.descriptors = scenario_descriptors(session.request)
    session.controllers = scenario_actor_controllers(session.scenario)
    session.engine.state = "finished"
    session.engine.outcome = "timeout"
    # A prior score is already part of this attempt's baseline. No new goal occurred.
    session.engine.scenario_state["score_baseline"] = [2, 1]
    session.engine.scenario_state["score_after"] = [2, 1]
    session.attempt_sent = session.engine.attempt_id
    session.attempt_acked = True
    session.last_frame = {"phase": phase, "scores": [2, 1]}
    before_engine = session.engine
    before_request = dict(session.request)
    session.pending_training_control = None
    session.goal_progression_attempt = None
    writes = []
    session.manager = NS(rlbot_interface=NS(send_msg=writes.append))
    monkeypatch.setattr(
        adapter, "desired_state", lambda state, human, bots=None: (state, human, bots or {})
    )

    session._queue_goal_progression(session.last_frame)

    assert session.pending_training_control is None
    assert session.goal_progression_attempt is None
    assert session.engine is before_engine
    assert session.request == before_request
    assert writes == []
