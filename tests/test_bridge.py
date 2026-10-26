"""Qt bridge integration checks with local files and a mocked game process."""
from __future__ import annotations

import io
import json
import os
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication
import pytest

from my_career_training import app as application
from my_career_training import bridge, career, game_worker, training


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(["my-career-training-tests"])


@pytest.fixture
def backend(tmp_path, monkeypatch, qt_app):
    game_running = {"value": False}
    launches = []
    monkeypatch.setattr(bridge, "native_launcher_pending", lambda: False)
    monkeypatch.setattr("my_career_training.platforms.native_launcher_pending", lambda: False)
    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    monkeypatch.setattr(
        bridge, "game_processes", lambda: ["mock-rocket-league"] if game_running["value"] else []
    )
    monkeypatch.setattr(bridge, "is_alive", lambda identity: identity is not None and game_running["value"])
    monkeypatch.setattr(bridge, "graceful_close", lambda _identity: None)
    monkeypatch.setattr(bridge, "launch_online", lambda launcher: launches.append(launcher) or "online opened")
    instance = bridge.Backend(tmp_path)
    yield instance, game_running, launches
    instance.timer.stop()
    instance.close()


class FakeProcess:
    def __init__(self, state=QProcess.Running):
        self.current_state = state
        self.writes = []
        self.killed = False

    def kill(self):
        self.killed = True
        self.current_state = QProcess.NotRunning

    def state(self):
        return self.current_state

    def write(self, value):
        self.writes.append(bytes(value))
        return len(value)

    def readAllStandardOutput(self):
        return b""

    def waitForFinished(self, _timeout):
        self.current_state = QProcess.NotRunning
        return True


def unfinished_career(instance):
    instance.dispatch("new_career", {"team_name": "Recovery test", "format": 1})
    state = instance.document.copy()
    state["career"] = career.start_fixture(state["career"], "attempt-a")
    instance._commit(state)
    pending = state["career"]["pending_session"]
    return {"expected_career_id": state["career"]["id"],
            "expected_fixture_id": pending["fixture_id"], "expected_session_id": pending["session_id"]}


def test_native_restart_preserves_career_and_returns_unfinished_match_to_schedule(backend):
    instance, _, _ = backend
    payload = unfinished_career(instance)
    instance.process = FakeProcess(QProcess.NotRunning)
    instance.request = {"fixture": {"id": payload["expected_fixture_id"]}}
    instance.session_state = "Error/Recovery"
    assert instance.state["session"]["worker_running"] is False
    before = json.loads(json.dumps(instance.document["career"]))
    instance.dispatch("abandon_fixture", payload)
    assert instance.error == ""
    saved = instance.store.load()["career"]
    assert saved["pending_session"] is None
    assert saved["id"] == before["id"]
    assert saved["recruits"] == before["recruits"]
    assert saved["rewards"] == before["rewards"]
    fixture = career.next_fixture(saved)
    assert fixture["id"] == payload["expected_fixture_id"]
    assert fixture["status"] == "scheduled"
    assert fixture["result"] is None
    assert instance.state["session"]["state"] == "Idle"
    assert instance.state["session"]["kind"] == "hub"


@pytest.mark.parametrize("change", ["career", "fixture", "attempt", "missing", "extra", "active"])
def test_native_restart_rejects_changed_or_live_attempt_without_saving(backend, change):
    instance, _, _ = backend
    payload = unfinished_career(instance)
    if change in {"career", "fixture"}:
        payload[f"expected_{change}_id"] = "different"
    elif change == "attempt":
        payload["expected_session_id"] = "different"
    elif change == "missing":
        del payload["expected_session_id"]
    elif change == "extra":
        payload["score"] = 7
    else:
        instance.process = FakeProcess()
    before = json.dumps(instance.document, sort_keys=True)
    saved = instance.store.load()
    instance.dispatch("abandon_fixture", payload)
    assert "unfinished match changed" in instance.error
    assert json.dumps(instance.document, sort_keys=True) == before
    assert instance.store.load() == saved
    instance.process = None


def test_dispatch_persists_career_lineup_settings_and_assistance_preferences(backend):
    instance, _, _ = backend

    instance.dispatch("new_career", {"team_name": "Night Shift", "format": 3})
    assert instance.error == ""
    assert instance.document["career"]["team_name"] == "Night Shift"
    assert instance.page == "hub"

    instance.dispatch("lineup", {"ids": ["shield", "relay"]})
    instance.dispatch("settings", {"key": "text_scale", "value": 1.25})
    instance.dispatch("assistance", {"id": "speed-flip", "key": "explanations", "value": False})

    assert instance.error == ""
    assert instance.document["career"]["lineup"] == ["shield", "relay"]
    assert instance.document["settings"]["text_scale"] == 1.25
    assert instance.document["lesson_preferences"]["speed-flip"]["explanations"] is False
    assert instance.store.load() == instance.document


def test_training_browser_favorite_resolves_live_item_and_persists_snapshot(backend):
    instance, _, _ = backend
    instance.dispatch("browser_favorite", {"type": "lesson", "id": "speed-flip"})
    favorite, = instance.document["browser_favorites"]
    assert favorite["type"] == "lesson" and favorite["id"] == "speed-flip"
    assert favorite["title"] == "Speed flip"
    assert set(favorite) == {"type", "id", "title", "subtitle", "detail"}
    assert instance.store.load()["browser_favorites"] == [favorite]

    instance.dispatch("browser_favorite", {"type": "lesson", "id": "speed-flip"})
    assert instance.document["browser_favorites"] == []
    instance.dispatch("browser_favorite", {"type": "plugin", "id": "999999"})
    assert "changed" in instance.error
    assert instance.document["browser_favorites"] == []


def _synthetic_recording():
    lesson = training.configure_lesson("speed-flip")
    actions = {
        "throttle": 0.0,
        "steer": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
        "roll": 0.0,
        "jump": False,
        "boost": False,
        "handbrake": False,
    }
    return {
        "schema_version": 1,
        "lesson_id": lesson["id"],
        "lesson_version": lesson["version"],
        "variant": lesson.get("variant"),
        "metadata": {
            "game_version": "test fixture",
            "framework_version": "test fixture",
            "car_hitbox": "test fixture",
            "map": lesson["map"],
            "mutators": {},
            "starting_state": lesson["starting_state"],
            "time_base": "game_seconds",
            "source": {"kind": "synthetic_test_fixture", "origin": "test only; no game telemetry"},
            "permission": {"distribute": False, "basis": "Test fixture only"},
            "success_evidence": [],
        },
        "outcome": "unfinished",
        "duration": 0,
        "events": [],
        "samples": [
            {
                "time": 0,
                "position": [0, 0, 17],
                "rotation": [0, 0, 0],
                "actions": actions,
            }
        ],
        "truncated": False,
        "label": "Synthetic test fixture",
    }


def test_import_recording_uses_real_dialog_action_and_preserves_fixture_provenance(
    backend, tmp_path, monkeypatch
):
    instance, _, _ = backend
    source = tmp_path / "synthetic recording.json"
    source.write_text(json.dumps(_synthetic_recording()), encoding="utf-8")
    monkeypatch.setattr(bridge.QFileDialog, "getOpenFileName", lambda *_args: (str(source), ""))

    instance.dispatch("import_recording", {})

    assert instance.error == ""
    assert "not independently certified" in instance.notice
    entry, = instance.document["recordings"]
    stored = json.loads((tmp_path / "recordings" / entry["filename"]).read_text(encoding="utf-8"))
    assert entry["lesson_id"] == "speed-flip"
    assert stored["metadata"]["source"]["kind"] == "synthetic_test_fixture"
    assert stored["import_status"] == "Imported personal recording"
    assert stored["outcome"] == "unfinished"


@pytest.mark.parametrize("cancelled_start", [False, True])
def test_result_receipt_survives_save_failure_and_replays_exactly_once(backend, monkeypatch, tmp_path, cancelled_start):
    instance, _, _ = backend
    started = career.new_career("Receipt Test", seed=841)
    fixture = career.next_fixture(started)
    session_id = str(uuid.uuid4())
    instance.session_id = session_id
    if cancelled_start:
        instance.startup_cancelled_session = session_id
        instance.session_state = "Error/Recovery"
        instance.error = "Starting took too long."
    instance.request = {"lesson_id": None}
    state = dict(instance.document)
    state["career"] = career.start_fixture(started, session_id)
    instance._commit(state)
    result = {
        "type": "result",
        "session_id": session_id,
        "fixture_id": fixture["id"],
        "home_score": 3,
        "away_score": 2,
        "provenance": "game",
    }
    receipt = game_worker.persist_result(tmp_path, result)
    real_save = instance.store.save

    def fail_completed_save(document):
        if document["career"]["pending_session"] is None:
            raise OSError("simulated result save failure")
        return real_save(document)

    monkeypatch.setattr(instance.store, "save", fail_completed_save)
    instance._recover_outbox()

    assert receipt.exists()
    assert instance.document["career"]["pending_session"]["session_id"] == session_id
    assert instance.store.load()["career"]["pending_session"]["session_id"] == session_id

    monkeypatch.setattr(instance.store, "save", real_save)
    instance._recover_outbox()
    assert not receipt.exists()
    instance._event(result)

    saved = instance.store.load()
    current = saved["career"]["seasons"][saved["career"]["current_season"]]
    completed = [f for f in current["fixtures"] if f["id"] == fixture["id"] and f["status"] == "completed"]
    awards = [item for item in saved["career"]["rewards"] if item["type"] == "match_experience"]
    assert len(completed) == 1
    assert len(awards) == 1
    assert completed[0]["result"]["session_id"] == session_id


def test_online_transition_clears_stop_reason_and_allows_later_dispatch(backend):
    instance, game_running, launches = backend
    process = FakeProcess()
    instance.process = process
    instance.session_id = str(uuid.uuid4())
    instance.request = {"session_id": instance.session_id, "lesson_id": None}
    instance.session_state = "Playing"
    instance.owned_game = bridge.ProcessIdentity(12345, 1.0, "C:/mock/RocketLeague.exe")
    game_running["value"] = True

    instance.dispatch("online_request", {})
    instance.dispatch("online_confirm", {"yes": True})
    assert instance.lifecycle.frozen is True
    assert instance.stop_reason == "online"
    assert json.loads(process.writes[-1])["type"] == "shutdown"

    instance._event({"type": "stopped", "session_id": instance.session_id, "id": "shutdown-1"})
    assert instance.lifecycle.state == "Waiting for Game Exit"
    assert instance.lifecycle.frozen is True

    process.current_state = QProcess.NotRunning
    instance._process_finished(0, QProcess.NormalExit)
    game_running["value"] = False
    instance._tick()

    assert launches == ["steam"]
    assert instance.lifecycle.state == "Online Launch Requested"
    assert instance.lifecycle.frozen is False
    assert instance.stop_reason is None

    instance.dispatch("settings", {"key": "reduced_motion", "value": True})
    assert instance.error == ""
    assert instance.document["settings"]["reduced_motion"] is True


@pytest.mark.parametrize("conflicting_dll", [False, True])
def test_online_handoff_restores_actual_staged_files_before_launcher(
    backend, tmp_path, monkeypatch, conflicting_dll
):
    instance, _, launches = backend
    root = tmp_path / "temporary-bakkes"
    (root / "plugins").mkdir(parents=True)
    (root / "cfg").mkdir()
    dll = root / "plugins" / "MyCareerTraining.dll"
    cfg = root / "cfg" / "plugins.cfg"
    original_dll = b"previous-user-plugin\x00\xff"
    original_cfg = b"plugin load alpha\r\n"
    dll.write_bytes(original_dll)
    cfg.write_bytes(original_cfg)
    source = tmp_path / "MyCareerTraining.dll"
    source.write_bytes(b"temporary-career-build")
    setup = bridge.PluginSession(instance.store.directory, root=root, game_running=lambda: False)
    setup.begin(source)
    assert dll.read_bytes() == source.read_bytes()
    assert b"plugin load MyCareerTraining" in cfg.read_bytes()
    if conflicting_dll:
        dll.write_bytes(b"new-user-file")

    def launch(launcher):
        assert dll.read_bytes() == original_dll
        assert cfg.read_bytes() == original_cfg
        assert not setup.outstanding()
        launches.append(launcher)
        return "online requested"

    monkeypatch.setattr(bridge, "launch_online", launch)
    instance.dispatch("online_request", {})
    instance.dispatch("online_confirm", {"yes": True})
    instance.lifecycle.worker_stopped()
    if conflicting_dll:
        assert launches == []
        assert instance.lifecycle.state == "Error/Recovery"
        assert dll.read_bytes() == b"new-user-file"
        assert setup.outstanding()
    else:
        assert launches == ["steam"]
        assert instance.lifecycle.state == "Online Launch Requested"


def test_online_handoff_refuses_deferred_plugin_restoration(backend, monkeypatch):
    instance, _, launches = backend
    monkeypatch.setattr(bridge.PluginSession, "finish", lambda self: {"status": "deferred"})
    instance.dispatch("online_request", {})
    instance.dispatch("online_confirm", {"yes": True})
    instance.lifecycle.worker_stopped()
    assert launches == []
    assert instance.lifecycle.state == "Error/Recovery"
    assert "still active" in instance.lifecycle.message


def test_online_handoff_waits_for_native_helper_before_restoring(backend, monkeypatch):
    instance, _, launches = backend
    pending = [True]
    restored = []
    monkeypatch.setattr(bridge, "native_launcher_pending", lambda: pending[0])
    monkeypatch.setattr(bridge.PluginSession, "finish", lambda self: restored.append(True) or {"status": "restored"})
    instance.dispatch("online_request", {})
    instance.dispatch("online_confirm", {"yes": True})
    instance.lifecycle.worker_stopped()
    assert instance.lifecycle.state == "Waiting for Game Exit"
    assert not restored and not launches
    pending[0] = False
    instance.lifecycle.tick()
    assert restored == [True] and launches == ["steam"]


def test_completed_worker_state_ignores_late_telemetry(backend):
    instance, _, _ = backend
    instance.session_id = str(uuid.uuid4())
    instance.request = {"lesson_id": None}
    started = career.new_career("Late Telemetry", seed=204)
    fixture = career.next_fixture(started)
    state = dict(instance.document)
    state["career"] = career.start_fixture(started, instance.session_id)
    instance._commit(state)

    instance._event({
        "type": "result",
        "session_id": instance.session_id,
        "fixture_id": fixture["id"],
        "home_score": 2,
        "away_score": 1,
        "provenance": "game",
    })
    instance._event({"type": "session", "session_id": instance.session_id, "state": "completed"})

    instance._event({"type": "telemetry", "session_id": instance.session_id})

    assert instance.session_state == "Career Ready"


def test_attempt_event_acknowledges_the_worker_summary_id(backend):
    instance, _, _ = backend
    instance.session_id = str(uuid.uuid4())
    instance.request = {"lesson_id": "speed-flip"}
    process = FakeProcess()
    instance.process = process
    summary = {"id": "attempt-7", "lesson_id": "speed-flip", "outcome": "unfinished"}

    instance._event({"type": "attempt", "session_id": instance.session_id, "summary": summary})

    ack = json.loads(process.writes[-1])
    assert ack["type"] == "attempt_ack"
    assert ack["attempt_id"] == summary["id"]


def test_source_worker_ready_ping_and_shutdown_protocol():
    class FakeThread:
        def __init__(self):
            self.started = False

        def start(self):
            self.started = True

        def is_alive(self):
            return self.started

        def join(self, timeout=None):
            self.started = False

    class FakeSession:
        def __init__(self, command, _emit):
            self.session_id = command["session_id"]
            self.thread = FakeThread()
            self.commands = []
            self.cleanup_complete = True

        def command(self, command):
            self.commands.append(command)

        def stop_owned_core(self):
            pass

    session_id = str(uuid.uuid4())
    output = io.StringIO()
    commands = "\n".join(
        [
            json.dumps({"type": "start", "session_id": session_id}),
            json.dumps({"type": "ping", "id": "bridge-probe"}),
            json.dumps({"type": "shutdown", "id": "shutdown-2"}),
            "",
        ]
    )
    process = game_worker.Worker(output, session_factory=FakeSession)

    assert process.run(io.StringIO(commands)) == 0
    events = [json.loads(line) for line in output.getvalue().splitlines()]

    assert events[0] == {"type": "ready", "protocol": 1, "session_id": None}
    assert events[1] == {"type": "pong", "id": "bridge-probe", "session_id": session_id}
    assert process.closed is True
    assert process.session.commands == [{"type": "shutdown", "id": "shutdown-2"}]


@pytest.mark.parametrize("ready", [False, True])
def test_start_deadline_cancels_worker_without_abandoning_fixture(backend, monkeypatch, ready):
    instance, _, _ = backend
    payload = unfinished_career(instance)
    before = instance.store.load()
    process = FakeProcess()
    instance.process = process
    instance.session_id = payload["expected_session_id"]
    instance.request = {"fixture": {"id": payload["expected_fixture_id"]}}
    instance.worker_ready = ready
    instance.start_deadline = bridge.time.monotonic() - 1
    instance.session_state = "Starting Career"
    closed_games = []
    monkeypatch.setattr(bridge, "graceful_close", closed_games.append)
    instance._tick()
    assert instance.session_state == "Error/Recovery"
    assert instance.startup_cancelled_session == instance.session_id
    assert instance.stop_reason is None and instance.stopping_worker
    assert process.killed is not ready
    sent = [json.loads(value) for value in process.writes]
    assert ([value["type"] for value in sent] == ["shutdown"]) is ready
    if ready:
        assert sent[0]["session_id"] == instance.session_id
    for event in ({"type": "ready"}, {"type": "session", "state": "running"},
                  {"type": "session", "state": "starting"}, {"type": "telemetry", "time": 2}):
        instance._event(dict(event, session_id=instance.session_id))
    assert instance.session_state == "Error/Recovery" and instance.telemetry == {}
    assert process.writes == [json.dumps(value).encode() + b"\n" for value in sent]
    process.current_state = QProcess.NotRunning
    instance._process_error(None)
    instance._process_finished(2, None)
    assert "took too long" in instance.error
    assert instance.store.load() == before and instance.document == before
    assert not closed_games


@pytest.mark.parametrize("via_receipt", [False, True])
def test_cancelled_start_still_saves_matching_result_once(backend, tmp_path, via_receipt):
    instance, _, _ = backend
    session_id = str(uuid.uuid4())
    started = career.new_career("Timeout receipt test", seed=43)
    fixture = career.next_fixture(started)
    state = dict(instance.document)
    state["career"] = career.start_fixture(started, session_id)
    instance._commit(state)
    instance.session_id = instance.startup_cancelled_session = session_id
    instance.request = {"fixture": fixture}
    instance.session_state = "Error/Recovery"
    instance.error = "Starting took too long."
    result = {"type": "result", "session_id": session_id, "fixture_id": fixture["id"],
              "home_score": 3, "away_score": 2, "provenance": "game"}
    receipt = game_worker.persist_result(tmp_path, result)
    if via_receipt:
        instance._recover_outbox()
    else:
        instance._event(result)
    instance._event(result)
    instance._event({"type": "session", "state": "running", "session_id": session_id})
    assert instance.session_state == "Career Ready" and not instance.error
    assert instance.document["career"]["pending_session"] is None and not receipt.exists()
    awards = [item for item in instance.document["career"]["rewards"] if item["type"] == "match_experience"]
    assert len(awards) == 1


def test_timed_out_writer_can_finish_and_close_worker_without_game_exit(backend, monkeypatch):
    instance, _, _ = backend
    instance.process = FakeProcess()
    instance.session_id = instance.startup_cancelled_session = str(uuid.uuid4())
    instance.session_state = "Error/Recovery"
    closed_games = []
    monkeypatch.setattr(bridge, "graceful_close", closed_games.append)
    for _ in range(2):
        instance._event({"type": "stopped", "session_id": instance.session_id})
    sent = [json.loads(value) for value in instance.process.writes]
    assert len(sent) == 1 and sent[0]["type"] == "shutdown"
    assert sent[0]["session_id"] == instance.session_id
    assert not instance.process.killed and not closed_games
    assert instance.session_state == "Error/Recovery"


def test_explicit_return_after_start_timeout_keeps_transition_priority(backend):
    instance, _, _ = backend
    instance.process = FakeProcess()
    instance.in_game = True
    instance.session_id = instance.startup_cancelled_session = str(uuid.uuid4())
    instance.stop_reason = "return_hub"
    instance._event({"type": "stopped", "session_id": instance.session_id})
    assert instance.session_state == "Waiting for Worker"
    assert not instance.startup_stop_acknowledged


def _load_main_window(instance, qt_app):
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", instance)
    qml = bridge.Path(__file__).resolve().parents[1] / "src" / "my_career_training" / "ui" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    roots = engine.rootObjects()
    assert roots, "Main.qml must load for the close-event integration test."
    window = roots[0]
    window.setVisible(True)
    qt_app.processEvents()
    return engine, window


def test_request_close_saves_before_waiting_and_emits_exit_only_after_worker_and_game_exit(backend):
    instance, game_running, _ = backend
    process = FakeProcess()
    instance.process = process
    instance.session_id = str(uuid.uuid4())
    instance.request = {"session_id": instance.session_id, "lesson_id": None}
    instance.session_state = "Playing"
    instance.owned_game = bridge.ProcessIdentity(12346, 1.0, "C:/mock/RocketLeague.exe")
    game_running["value"] = True
    exit_spy = QSignalSpy(instance.exitRequested)

    assert instance.request_close() is False
    assert instance.store.path.exists()
    assert instance.stop_reason == "exit"
    assert instance.session_state == "Stopping Career"
    assert json.loads(process.writes[-1])["type"] == "shutdown"

    process.current_state = QProcess.NotRunning
    instance._event({"type": "stopped", "session_id": instance.session_id, "id": "shutdown-close"})
    instance._tick()
    assert instance.session_state == "Waiting for Game Exit"
    assert exit_spy.count() == 0

    game_running["value"] = False
    instance._tick()
    assert instance.stop_reason is None
    assert instance.session_state == "Idle"
    assert exit_spy.count() == 1


def test_qml_window_close_is_vetoed_while_backend_waits_for_game_exit(backend, qt_app):
    instance, game_running, _ = backend
    process = FakeProcess()
    instance.process = process
    instance.session_id = str(uuid.uuid4())
    instance.request = {"session_id": instance.session_id, "lesson_id": None}
    instance.session_state = "Playing"
    instance.owned_game = bridge.ProcessIdentity(12347, 1.0, "C:/mock/RocketLeague.exe")
    game_running["value"] = True
    exit_spy = QSignalSpy(instance.exitRequested)
    engine, window = _load_main_window(instance, qt_app)

    accepted = window.close()
    qt_app.processEvents()

    assert accepted is False
    assert window.isVisible()
    assert instance.stop_reason == "exit"
    assert json.loads(process.writes[-1])["type"] == "shutdown"

    process.current_state = QProcess.NotRunning
    instance._event({"type": "stopped", "session_id": instance.session_id, "id": "shutdown-qml"})
    instance._tick()
    assert exit_spy.count() == 0
    game_running["value"] = False
    instance._tick()
    assert exit_spy.count() == 1

    assert window.close() is True
    qt_app.processEvents()
    assert not window.isVisible()
    engine.deleteLater()


def test_qml_window_close_is_accepted_when_idle(backend, qt_app):
    instance, _, _ = backend
    engine, window = _load_main_window(instance, qt_app)

    assert window.close() is True
    qt_app.processEvents()

    assert not window.isVisible()
    assert instance.store.path.exists()
    engine.deleteLater()


def test_application_connects_graceful_exit_signal_to_quit(backend, monkeypatch, qt_app, tmp_path):
    instance, _, _ = backend
    quit_calls = []
    monkeypatch.setattr(application, "Backend", lambda _directory: instance)
    monkeypatch.setattr(QApplication, "quit", lambda app: quit_calls.append(app))

    def run_event_loop(app):
        instance.exitRequested.emit()
        return 0

    monkeypatch.setattr(QApplication, "exec", run_event_loop)

    result = application.run(tmp_path, smoke_test=True)

    assert result == 0
    assert quit_calls == [qt_app]


def test_optional_match_review_persists_once_across_restart_and_rejects_late_score(backend):
    instance, _, _ = backend
    started = career.new_career("Review Persistence", seed=452)
    fixture = career.next_fixture(started)
    session_id = str(uuid.uuid4())
    instance.session_id = session_id
    instance.request = {"lesson_id": None}
    state = dict(instance.document)
    state["career"] = career.start_fixture(started, session_id)
    instance._commit(state)
    review = [
        {
            "time": 18.25,
            "title": "Observed score change",
            "evidence": "The scoreboard changed from 0–0 to 1–0.",
            "suggestion": "",
            "kind": "score",
        },
        {
            "time": float("nan"),
            "title": "Malformed optional note",
            "evidence": "This must be discarded.",
            "suggestion": "",
            "kind": "score",
        },
    ]
    result = {
        "type": "result",
        "session_id": session_id,
        "fixture_id": fixture["id"],
        "home_score": 2,
        "away_score": 1,
        "provenance": "game",
        "review": review,
    }

    instance._event(result)
    expected_review = [review[0]]
    assert instance.latest_result["review"] == expected_review
    duplicate = {**result, "review": [{**review[0], "title": "Duplicate packet"}]}
    instance._event(duplicate)
    assert instance.latest_result["review"] == expected_review

    before_conflict = instance.store.load()
    with pytest.raises(ValueError, match="different final result"):
        instance._event({**result, "home_score": 3, "away_score": 1})
    assert instance.store.load() == before_conflict

    instance.timer.stop()
    instance.close()
    restarted = bridge.Backend(instance.store.directory)
    try:
        assert restarted.latest_result["session_id"] == session_id
        assert restarted.latest_result["review"] == expected_review
    finally:
        restarted.timer.stop()
        restarted.close()


def _finish_community(instance, seconds=2):
    import threading
    import time
    deadline = time.monotonic() + seconds
    while instance.community_state["busy"] and time.monotonic() < deadline:
        instance._poll_community()
        threading.Event().wait(0.002)
    assert not instance.community_state["busy"], "Community job did not settle"


def test_community_download_uses_checked_release_without_touching_game(backend, monkeypatch):
    instance, game_running, launches = backend
    from my_career_training import community_plugins as plugins
    record = {"id": "223", "title": "Example plugin", "version": 21, "site_verified": True,
              "download_url": "https://example.invalid/fixture.zip", "can_activate": False}
    calls = []
    monkeypatch.setattr(plugins, "lookup_plugin", lambda plugin_id: record if plugin_id == "223" else None)
    monkeypatch.setattr(plugins, "cached_plugins", lambda _directory: [])

    def download(checked, directory, *, cancelled):
        calls.append((checked, directory, cancelled()))
        return {"id": "223", "status": "downloaded_not_enabled", "can_activate": False}

    monkeypatch.setattr(plugins, "download_plugin", download)
    instance.dispatch("community_lookup", {"id": "223"})
    _finish_community(instance)
    assert instance.community_state["selected"] == record
    instance.dispatch("community_download", {"download_url": "https://attacker.invalid/evil.zip"})
    _finish_community(instance)
    assert calls == [(record, instance.store.directory / "community-plugins", False)]
    assert instance.community_state["can_activate"] is False
    assert "Not enabled" in instance.community_state["message"]
    assert instance.owned_game is None and instance.process is None and not game_running["value"]
    assert launches == []
    assert instance.error == ""


def test_community_lookup_does_not_block_ui_and_cancellation_discards_result(backend, monkeypatch):
    import threading
    instance, _, _ = backend
    from my_career_training import community_plugins as plugins
    entered, release = threading.Event(), threading.Event()

    def lookup(_plugin_id):
        entered.set()
        assert release.wait(2)
        return {"id": "223", "title": "Late result"}

    monkeypatch.setattr(plugins, "lookup_plugin", lookup)
    monkeypatch.setattr(plugins, "cached_plugins", lambda _directory: [])
    try:
        instance.dispatch("community_lookup", {"id": "223"})
        assert entered.wait(1)
        assert instance.community_state["busy"]
        instance.dispatch("navigate", {"page": "training"})
        assert instance.page == "training"
        instance.dispatch("community_lookup", {"id": "99"})
        assert "Wait" in instance.error
        instance.dispatch("community_cancel", {})
    finally:
        release.set()
    _finish_community(instance)
    assert instance.community_state["selected"] is None
    assert "cancelled" in instance.community_state["message"]


def test_community_paste_reads_only_on_request_and_uses_normal_lookup(backend, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from types import SimpleNamespace
    instance, _, _ = backend
    reads, lookups = [], []
    def clipboard():
        reads.append(True)
        return SimpleNamespace(text=lambda: "  https://bakkesplugins.com/plugin/286/  ")
    monkeypatch.setattr(QGuiApplication, "clipboard", clipboard)
    monkeypatch.setattr(instance, "_community_job", lambda *args: lookups.append(args))
    instance._poll_community()
    assert not reads
    instance.dispatch("community_paste_link", {})
    assert not instance.error
    assert reads == [True]
    assert lookups == [("lookup", "https://bakkesplugins.com/plugin/286/")]
    instance.dispatch("community_paste_link", {"url": "https://example.com/plugin"})
    assert instance.error and reads == [True]


@pytest.mark.parametrize("text", ["", " " * 6, "x" * 2049])
def test_community_paste_rejects_missing_or_oversized_text(backend, monkeypatch, text):
    from PySide6.QtGui import QGuiApplication
    from types import SimpleNamespace
    instance, _, _ = backend
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda: SimpleNamespace(text=lambda: text))
    monkeypatch.setattr(instance, "_community_job", lambda *_: pytest.fail("invalid clipboard lookup"))
    instance.dispatch("community_paste_link", {})
    assert "Copy a BakkesPlugins" in instance.error


def test_community_unchecked_download_and_activation_are_rejected(backend, monkeypatch):
    instance, _, _ = backend
    from my_career_training import community_plugins as plugins
    monkeypatch.setattr(plugins, "download_plugin", lambda *a, **k: pytest.fail("Unchecked download"))
    instance.dispatch("community_download", {"id": "223"})
    assert "Check a plugin" in instance.error
    assert not instance.community_state["busy"]
    instance.dispatch("community_activate", {"id": "223"})
    assert instance.error
    from my_career_training.ingame import ALLOWED_ACTIONS
    assert "community_activate" not in ALLOWED_ACTIONS


@pytest.mark.parametrize("action", ["community_lookup", "community_library"])
def test_community_cancel_during_library_read_discards_uncommitted_result(backend, monkeypatch, action):
    instance, _, _ = backend
    from my_career_training import community_plugins as plugins
    monkeypatch.setattr(plugins, "lookup_plugin", lambda _id: {"id": "223"})

    def cached(_directory):
        instance._community_cancel.set()
        return [{"id": "223", "status": "downloaded_not_enabled"}]

    monkeypatch.setattr(plugins, "cached_plugins", cached)
    instance.dispatch(action, {"id": "223"})
    _finish_community(instance)
    assert instance.community_state["selected"] is None
    assert instance.community_state["downloaded"] == []
    assert "cancelled" in instance.community_state["message"]


def test_community_failure_returns_to_retryable_state(backend, monkeypatch):
    instance, _, _ = backend
    from my_career_training import community_plugins as plugins

    def lookup(_plugin_id):
        raise plugins.CommunityPluginError("Plugin metadata unavailable.")

    monkeypatch.setattr(plugins, "lookup_plugin", lookup)
    instance.dispatch("community_lookup", {"id": "223"})
    _finish_community(instance)
    assert instance.error == "Plugin metadata unavailable."
    assert instance.community_state["selected"] is None


def test_native_community_action_requires_attached_capability_and_empty_payload(backend):
    from types import SimpleNamespace
    instance, _, _ = backend
    instance.dispatch("community_trial_prepare", {})
    assert "native offline developer trial" in instance.error
    calls = []
    instance.native_community = SimpleNamespace(prepare=calls.append,
        state=lambda: {"available": True}, request=lambda: None)
    instance.community_state["selected"] = {"id": "286", "can_activate": False}
    instance.dispatch("community_trial_prepare", {"stem": "arbitrary"})
    assert calls == [] and instance.error
    instance.dispatch("community_trial_prepare", {})
    assert calls == [{"id": "286", "can_activate": False}]
    assert not instance.error
    assert instance.state["native_community_trial"] == {"available": True}
    assert instance.community_state["can_activate"] is False


def test_online_handoff_waits_for_community_recovery(backend, monkeypatch):
    from my_career_training import native_community_binding
    instance, _, launches = backend
    def fail(_):
        raise RuntimeError("Community file recovery conflict")
    monkeypatch.setattr(native_community_binding, "recover_native_community", fail)
    instance.dispatch("online_request", {})
    instance.dispatch("online_confirm", {"yes": True})
    instance.lifecycle.worker_stopped()
    for _ in range(8):
        instance._tick()
    assert launches == []
    assert instance.lifecycle.state == "Error/Recovery"
    assert "Community file recovery conflict" in instance.lifecycle.last_error


def test_native_career_name_paste_changes_only_draft_then_creates_career(backend, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from types import SimpleNamespace
    instance, _, _ = backend
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda: SimpleNamespace(text=lambda: "  Slava FC  "))
    instance.dispatch("career_name_clipboard", {})
    assert not instance.error
    assert instance.document["career"] is None
    assert instance.state["career_draft"] == {"team_name": "Slava FC"}
    instance.dispatch("new_career", dict(instance.career_draft, format=2))
    assert not instance.error
    assert instance.document["career"]["team_name"] == "Slava FC"
    assert instance.document["career"]["format"] == 2
    old_id = instance.document["career"]["id"]
    instance.dispatch("new_career", {"team_name": "Second Club", "format": 3})
    backup = instance.store.directory / f"career-{old_id}.json"
    assert json.loads(backup.read_text(encoding="utf-8"))["career"]["team_name"] == "Slava FC"


def test_pending_community_load_blocks_other_activity_but_keeps_exit_available(backend, monkeypatch):
    from types import SimpleNamespace
    instance, _, _ = backend
    instance.native_community = SimpleNamespace(state=lambda: {"busy": True}, request=lambda: {})
    assert instance.state["session"]["busy"]
    assert instance.state["session"]["can_exit"]
    instance.dispatch("new_career", {"team_name": "Wait", "format": 3})
    assert "community plugin confirmation" in instance.error
    assert instance.document["career"] is None
    stops = []
    monkeypatch.setattr(instance, "_begin_stop", stops.append)
    instance.dispatch("quit_game", {})
    assert not instance.error and stops == ["exit"]


@pytest.mark.parametrize("value", ["", "x" * 41, "club\nname", "club\x7fname"])
def test_native_career_name_rejects_bad_clipboard(backend, monkeypatch, value):
    from PySide6.QtGui import QGuiApplication
    from types import SimpleNamespace
    instance, _, _ = backend
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda: SimpleNamespace(text=lambda: value))
    instance.dispatch("career_name_clipboard", {})
    assert instance.error and instance.career_draft["team_name"] == "My Career Club"


def test_native_recruit_paste_and_manual_backup_use_existing_domain_validation(backend, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from types import SimpleNamespace
    instance, _, _ = backend
    instance.dispatch("new_career", {"team_name": "Home", "format": 3})
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda: SimpleNamespace(text=lambda: "Keeper"))
    instance.dispatch("rename_recruit_clipboard", {"id": "anchor"})
    assert not instance.error and instance.document["career"]["recruits"]["anchor"]["name"] == "Keeper"
    instance.dispatch("rename_recruit_clipboard", {"id": "unknown"})
    assert "Unknown recruit" in instance.error
    instance.dispatch("backup_save", {"path": "arbitrary"})
    assert instance.error and not list(instance.store.directory.glob("career-backup-*.json"))
    instance.dispatch("backup_save", {})
    assert not instance.error
    backups = list(instance.store.directory.glob("career-backup-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["career"] == instance.document["career"]


def test_new_career_clears_previous_clubs_latest_result(backend):
    instance, _, _ = backend
    instance.dispatch("new_career", {"team_name": "First", "format": 3})
    instance.latest_result = {"fixture_id": "old-fixture", "home_score": 5, "away_score": 2}
    instance.dispatch("new_career", {"team_name": "Second", "format": 3})
    assert not instance.error
    assert instance.latest_result is None
    assert instance.document["career"]["team_name"] == "Second"


def test_community_late_cancel_keeps_committed_download_visible(backend, monkeypatch):
    instance, _, _ = backend
    from my_career_training import community_plugins as plugins
    receipt = {"id": "223", "status": "downloaded_not_enabled", "can_activate": False}
    instance.community_state["selected"] = {"id": "223"}

    def committed_download(*_args, **_kwargs):
        instance._community_cancel.set()  # Cancel races after service commits.
        return receipt

    monkeypatch.setattr(plugins, "download_plugin", committed_download)
    monkeypatch.setattr(plugins, "cached_plugins", lambda _directory: [receipt])
    instance.dispatch("community_download", {})
    _finish_community(instance)
    assert instance.community_state["downloaded"] == [receipt]
    assert "Downloaded" in instance.community_state["message"]


def test_community_cancel_is_available_during_game_transition(backend):
    instance, _, _ = backend
    instance.community_state["busy"] = True
    instance.session_state = "Starting Career"
    instance.dispatch("community_cancel", {})
    assert instance._community_cancel.is_set()
    assert instance.error == ""


def test_community_page_renders_idle_and_downloaded_states_without_qml_errors(backend, qt_app):
    instance, _, _ = backend
    engine, window = _load_main_window(instance, qt_app)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(message.toString() for message in messages))
    try:
        instance.dispatch("navigate", {"page": "community"})
        qt_app.processEvents()
        instance.community_state.update(selected={"id": "223", "title": "Fixture plugin"},
            downloaded=[{"id": "223", "status": "downloaded_not_enabled"}])
        instance.stateChanged.emit()
        qt_app.processEvents()
        assert not warnings
    finally:
        window.close()
        engine.deleteLater()
        qt_app.processEvents()
