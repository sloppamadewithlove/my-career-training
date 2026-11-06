import pytest

from my_career_training.training.native_reset_observation import NativeResetObservation


class World:
    def __init__(self, enabled=True):
        self.now = 20
        self.observed = {"nonce": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "pid": 42,
                         "start_identity": "100.000", "frontend": False, "heartbeat": {}}
        self.calls = 0
        self.probe = NativeResetObservation(self.observe, enabled=enabled,
                                            clock=lambda: self.now, wall=lambda: 80 + self.now)

    def observe(self, frontend):
        assert frontend is False
        self.calls += 1
        return self.observed

    def terminal_report(self, request=None):
        request = self.probe.request() if request is None else request
        return dict(request, status="complete", reason="deadline", semantics_verified=False,
                    reset_generation=None, teaching_recording=False, samples=[{
                        "round": 2, "shot_attempt": 3, "seconds_remaining": 10,
                        "world_seconds": 40, "remaining": 10, "total_played": 4,
                        "elapsed_monotonic": 0,
                        "car_rb_state": {"location": [1, 2, 3], "linear_velocity": [4, 5, 6],
                                         "angular_velocity": [7, 8, 9], "quaternion_xyzw": [0.1, 0.2, 0.3, 0.4],
                                         "time": 40, "sleeping": False, "new_data": True},
                        "ball_rb_state": {"location": [-1, -2, -3], "linear_velocity": [-4, -5, -6],
                                          "angular_velocity": [-7, -8, -9], "quaternion_xyzw": [0, 0, 0, 1],
                                          "time": 41, "sleeping": True, "new_data": False},
                        "observed_controls": {"throttle": 1, "steer": -1, "pitch": 0.5, "yaw": -0.5,
                                              "roll": 0.25, "dodge_forward": 0, "dodge_strafe": 0,
                                              "jump": True, "handbrake": False, "boost": True,
                                              "activate_boost": False, "holding_boost": True, "jumped": True},
                    }])


def test_default_off_never_calls_observer():
    world = World(False)
    with pytest.raises(ValueError):
        world.probe.start()
    assert world.calls == 0 and world.probe.request() is None


def test_server_identity_explicit_intent_and_nonrenewable_deadline():
    world = World()
    assert world.probe.request() is None
    world.probe.start()
    request = world.probe.request()
    assert set(request) == {"request_id", "nonce", "pid", "start_identity", "issued_at", "expires_at"}
    assert request["pid"] == 42 and request["expires_at"] - request["issued_at"] == 5
    request["pid"] = 77
    assert world.probe.request()["pid"] == 42
    world.now = 24
    assert world.probe.request()["expires_at"] == 105
    world.now = 25
    assert world.probe.request()["expires_at"] == 105
    assert world.probe.state()["status"] == "awaiting_ack"
    world.now = 26
    assert world.probe.request() is None
    with pytest.raises(ValueError):
        world.probe.start()


@pytest.mark.parametrize("key,value", [("nonce", "other"), ("pid", 43),
                                       ("start_identity", "101.000"), ("frontend", True)])
def test_scope_loss_withdraws_permanently(key, value):
    world = World()
    world.probe.start()
    world.observed[key] = value
    assert world.probe.request() is None
    with pytest.raises(ValueError):
        world.probe.start()


def test_only_attributed_acknowledgment_completes_and_data_is_not_promoted():
    world = World()
    world.probe.start()
    request = world.probe.request()
    report = world.terminal_report()
    report["request_id"] = "wrong"
    world.observed["heartbeat"]["native_reset_observation"] = report
    assert world.probe.request() is not None
    report["request_id"] = request["request_id"]
    assert world.probe.request() is None
    assert world.probe.state() == {"status": "complete", "enabled": True}
    assert "samples" not in world.probe.state()
    assert world.observed["heartbeat"]["native_reset_observation"]["samples"][0]["round"] == 2


@pytest.mark.parametrize("delay", [0, 0.5, 0.9])
def test_terminal_heartbeat_at_or_after_deadline_is_retained(delay):
    world = World()
    world.probe.start()
    report = world.terminal_report()
    world.now = 25
    assert world.probe.request()["expires_at"] == 105
    world.now += delay
    world.observed["heartbeat"]["native_reset_observation"] = report
    assert world.probe.request() is None
    assert world.probe.state()["status"] == "complete"
    assert world.observed["heartbeat"]["native_reset_observation"]["samples"] == report["samples"]
    with pytest.raises(ValueError):
        world.probe.start()


def test_delivery_window_cannot_be_renewed_by_observing_heartbeat():
    world = World()
    world.probe.start()
    report = world.terminal_report()
    report["status"] = "observing"
    world.observed["heartbeat"]["native_reset_observation"] = report
    world.now = 25.9
    assert world.probe.request()["expires_at"] == 105
    world.now = 26
    assert world.probe.request() is None
    report["status"] = "complete"
    assert world.probe.request() is None and world.probe.state()["status"] == "stopped"


def test_scope_loss_during_ack_grace_still_retires_request():
    world = World()
    world.probe.start()
    report = world.terminal_report()
    world.now = 25.2
    world.observed["nonce"] = "other"
    world.observed["heartbeat"]["native_reset_observation"] = report
    assert world.probe.request() is None
    assert world.probe.state()["status"] == "stopped"


@pytest.mark.parametrize("now", [19, float("nan"), float("inf")])
def test_bad_monotonic_clock_retires_request(now):
    world = World()
    world.probe.start()
    world.now = now
    assert world.probe.request() is None


def test_backend_private_opt_in_and_empty_action_payload(tmp_path):
    from PySide6.QtCore import QCoreApplication
    from my_career_training.bridge import Backend

    app = QCoreApplication.instance() or QCoreApplication([])
    backend = Backend(tmp_path)
    backend.timer.stop()
    backend.dispatch("native_reset_observe", {})
    assert "disabled" in backend.error
    world = World()
    backend.native_reset_observation = world.probe
    backend.dispatch("native_reset_observe", {"pid": 42})
    assert world.calls == 0 and backend.error
    backend.dispatch("native_reset_observe", {})
    assert not backend.error
    assert backend.state["native_reset_observation_request"]["pid"] == 42
    backend.dispatch("native_reset_observe", {})
    assert "spent" in backend.error
    backend.store.close()
    assert app is not None


def test_file_bridge_routes_explicit_request_and_acknowledgment(tmp_path):
    import json
    import uuid
    from PySide6.QtCore import QCoreApplication
    from my_career_training.bridge import Backend
    from my_career_training.ingame import FileBridge

    app = QCoreApplication.instance() or QCoreApplication([])
    backend = Backend(tmp_path, native_reset_observation=True)
    backend.timer.stop()
    bridge = FileBridge(tmp_path, backend.dispatch, lambda: backend.state)
    world = World()
    world.observed["nonce"] = bridge.session
    backend.native_reset_observation._observe = world.observe
    command_id = str(uuid.uuid4())
    (bridge.commands / f"{command_id}.json").write_text(json.dumps({
        "protocol": 1, "id": command_id, "session": bridge.session,
        "action": "native_reset_observe", "payload": {},
    }), encoding="utf-8")
    bridge.poll()
    published = json.loads((bridge.directory / "state.json").read_text(encoding="utf-8"))
    assert published["command_ack"] == {"id": command_id, "ok": True, "error": ""}
    request = published["native_reset_observation_request"]
    assert request["nonce"] == bridge.session and request["pid"] == 42
    assert request["expires_at"] - request["issued_at"] == 5
    report = world.terminal_report(request)
    report["samples"] *= 150
    report["controls_source"] = "PlayerControllerWrapper::GetVehicleInput"
    heartbeat = dict(report)
    (bridge.directory / "plugin-status.json").write_text(json.dumps({
        "bridge_session": bridge.session, "published_at": bridge.clock(),
        "native_reset_observation": heartbeat,
    }), encoding="utf-8")
    assert (bridge.directory / "plugin-status.json").stat().st_size < 2 * 1024 * 1024
    assert bridge.plugin_status()["native_reset_observation"] == report
    world.observed["heartbeat"]["native_reset_observation"] = report
    backend.plugin_status = world.observed["heartbeat"]
    bridge.poll()
    published = json.loads((bridge.directory / "state.json").read_text(encoding="utf-8"))
    assert published["native_reset_observation_request"] is None
    assert published["plugin"]["native_reset_observation"]["samples"] == report["samples"]
    assert "samples" not in published["native_reset_observation"]
    backend.store.close()
    assert app is not None
