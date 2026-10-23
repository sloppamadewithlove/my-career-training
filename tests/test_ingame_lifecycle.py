"""Same-game in-game transitions across worker restarts."""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess as QtProcess
from PySide6.QtWidgets import QApplication
import pytest

from my_career_training import bridge, career, game_worker
from my_career_training.platforms import ProcessIdentity


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(["my-career-training-tests"])


class Signal:
    def connect(self, _callback):
        pass


class FakeWorkerProcess:
    """QProcess-shaped worker stub; it never starts or owns Rocket League."""

    NotRunning = QtProcess.NotRunning
    Running = QtProcess.Running

    def __init__(self, _parent=None):
        self.current_state = self.NotRunning
        self.writes = []
        self.started = None
        self.readyReadStandardOutput = Signal()
        self.readyReadStandardError = Signal()
        self.errorOccurred = Signal()
        self.finished = Signal()

    def setWorkingDirectory(self, directory):
        self.working_directory = directory

    def start(self, program, arguments):
        self.started = (program, list(arguments))
        self.current_state = self.Running

    def state(self):
        return self.current_state

    def write(self, value):
        self.writes.append(bytes(value))
        return len(value)

    def readAllStandardOutput(self):
        return b""

    def readAllStandardError(self):
        return b""

    def waitForFinished(self, _timeout):
        self.current_state = self.NotRunning
        return True


class FakeProcessFactory:
    NotRunning = QtProcess.NotRunning
    Running = QtProcess.Running

    def __init__(self, instances):
        self.instances = instances

    def __call__(self, parent=None):
        process = FakeWorkerProcess(parent)
        self.instances.append(process)
        return process


@pytest.fixture
def in_game_backend(tmp_path, monkeypatch, qt_app):
    game_identity = ProcessIdentity(24680, 1234.5, r"C:\Games\RocketLeague.exe")
    process_instances = []
    verified_identities = []

    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    monkeypatch.setattr(bridge, "game_processes", lambda: ["owned-rocket-league"])
    monkeypatch.setattr(bridge, "is_alive", lambda identity: identity == game_identity)
    monkeypatch.setattr(
        bridge,
        "graceful_close",
        lambda _identity: pytest.fail("A worker restart must leave the owned game open."),
    )
    monkeypatch.setattr(bridge, "launch_online", lambda _launcher: pytest.fail("Offline mode launched online."))
    monkeypatch.setattr(bridge, "QProcess", FakeProcessFactory(process_instances))

    instance = bridge.Backend(tmp_path)
    instance.timer.stop()
    instance.in_game = True
    instance.setup_required = False
    instance.owned_game = game_identity

    # Only the bridge module needs Windows launch semantics. Keep the actual
    # interpreter and filesystem platform unchanged for Qt and the save store.
    monkeypatch.setattr(bridge, "sys", SimpleNamespace(
        platform="win32", executable=sys.executable, frozen=False,
    ))
    from my_career_training import bootstrap
    monkeypatch.setattr(bootstrap, "verify_owned_offline", lambda identity: (
        verified_identities.append(identity) or identity == game_identity
    ))
    monkeypatch.setattr(bootstrap, "launch_offline", lambda _settings: pytest.fail(
        "The owned offline game must not be relaunched between fixtures."
    ))
    from my_career_training.bots import providers
    monkeypatch.setattr(providers, "ensure_provider", lambda *_args, **_kwargs: None)

    yield instance, game_identity, process_instances, verified_identities

    instance.timer.stop()
    instance.close()


@pytest.mark.parametrize("stale_field", ["expected_career_id", "expected_fixture_id", "missing_fixture"])
def test_native_match_choice_is_revalidated_before_save_or_worker(in_game_backend, stale_field):
    instance, _, process_instances, _ = in_game_backend
    instance.dispatch("new_career", {"team_name": "Native Club", "format": 3})
    before = json.dumps(instance.document, sort_keys=True)
    fixture = career.next_fixture(instance.document["career"])
    payload = {"expected_career_id": instance.document["career"]["id"], "expected_fixture_id": fixture["id"]}
    if stale_field == "missing_fixture":
        del payload["expected_fixture_id"]
    else:
        payload[stale_field] = "stale"

    instance.dispatch("play_match", payload)

    assert "match changed" in instance.error
    assert json.dumps(instance.document, sort_keys=True) == before
    assert not process_instances


def test_current_native_match_choice_starts_same_owned_game(in_game_backend):
    instance, identity, process_instances, _ = in_game_backend
    instance.dispatch("new_career", {"team_name": "Native Club", "format": 3})
    fixture = career.next_fixture(instance.document["career"])
    instance.dispatch("play_match", {"expected_career_id": instance.document["career"]["id"],
                                     "expected_fixture_id": fixture["id"]})
    assert not instance.error
    assert instance.request["fixture"]["id"] == fixture["id"]
    assert instance.request["owned_game"] == identity.as_dict()
    assert len(process_instances) == 1


def test_completed_fixture_worker_restart_keeps_same_owned_game(in_game_backend):
    instance, game_identity, process_instances, verified_identities = in_game_backend

    instance.dispatch("new_career", {"team_name": "Same Game", "format": 3})
    assert instance.error == ""

    instance.dispatch("play_match", {})
    assert instance.error == ""
    first_process = process_instances[-1]
    assert first_process.started is not None
    assert first_process.started[1] == ["-m", "my_career_training", "--worker"]
    first_session = instance.session_id
    first_fixture = instance.request["fixture"]
    assert instance.request["owned_game"] == game_identity.as_dict()

    # Simulate the worker's durable result receipt, then deliver that result to
    # the bridge as its JSON-lines event would be delivered in production.
    result = {
        "type": "result",
        "session_id": first_session,
        "fixture_id": first_fixture["id"],
        "home_score": 3,
        "away_score": 2,
        "provenance": "game",
    }
    receipt = game_worker.persist_result(instance.store.directory, result)
    assert receipt.is_file()
    instance._event(result)

    assert not receipt.exists()
    assert instance.document["career"]["pending_session"] is None
    assert instance.latest_result["session_id"] == first_session
    second_fixture = career.next_fixture(instance.document["career"])
    assert second_fixture["id"] != first_fixture["id"]

    # Starting fixture two asks the old worker to stop, then waits for that
    # worker before creating a replacement connected to the same game process.
    instance.dispatch("play_match", {})
    assert instance.error == ""
    assert instance.stop_reason == "restart"
    assert instance.session_state == "Stopping Career"
    assert len(process_instances) == 1
    assert json.loads(first_process.writes[-1])["type"] == "shutdown"
    second_session = instance.document["career"]["pending_session"]["session_id"]
    assert second_session != first_session

    first_process.current_state = FakeWorkerProcess.NotRunning
    instance._event({"type": "stopped", "session_id": first_session})
    assert instance.session_state == "Waiting for Worker"
    assert instance.owned_game is game_identity

    instance._tick()

    assert instance.error == ""
    assert instance.stop_reason is None
    assert instance.session_state == "Starting Career"
    assert len(process_instances) == 2
    second_process = process_instances[-1]
    assert second_process.started[1] == ["-m", "my_career_training", "--worker"]
    assert instance.session_id == second_session
    assert instance.request["fixture"]["id"] == second_fixture["id"]
    assert instance.request["owned_game"] == game_identity.as_dict()
    assert instance.owned_game is game_identity
    assert verified_identities == [game_identity, game_identity]
