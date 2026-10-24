"""Real session composition with synthetic heartbeats and no game launch."""
import copy
from types import SimpleNamespace

import pytest

from my_career_training import bootstrap, native_community_binding as binding
from my_career_training.native_community import BUILD_IDENTITY, CORE_IDENTITY, GAME_EXE_SHA256
from my_career_training.platforms import ProcessIdentity


@pytest.fixture
def world(tmp_path, monkeypatch):
    executable = tmp_path / "game/Binaries/Win64/RocketLeague.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"game sentinel")
    data = tmp_path / "data"
    data.mkdir()
    root = tmp_path / "bakkes"
    (root / "plugins").mkdir(parents=True)
    nonce = "45234854-6e9c-4af5-9c50-e9347f375140"
    identity = ProcessIdentity(888, 1234567890.125, str(executable))
    owner = SimpleNamespace(identity=identity, poll=lambda: "ready")
    session = SimpleNamespace(directory=data, session=nonce, owner=owner,
                              executable=executable.resolve(), prepared=object())
    status = {"protocol": 1, "pid": 888, "bridge_session": nonce, "published_at": 100.0,
              "online": False, "in_game": False, "in_replay": False, "frontend": True,
              "bakkesmod_version": 229, "game_build": BUILD_IDENTITY,
              "native_movie_trial": {"trial_enabled": True, "movie_ready": True,
                  "executable_sha256": GAME_EXE_SHA256, "core_identity": CORE_IDENTITY,
                  "build_identity": BUILD_IDENTITY}}
    bridge = SimpleNamespace(session=nonce, plugin_status=lambda: copy.deepcopy(status))
    monkeypatch.setattr(binding.time, "time", lambda: 100.0)
    monkeypatch.setattr(bootstrap, "verify_owned_offline", lambda _: True)
    controller = binding.NativeCommunityBinding(session, bridge, root)
    return SimpleNamespace(controller=controller, session=session, bridge=bridge,
                           status=status, root=root, data=data)


def test_capability_comes_from_actual_native_owner_and_fresh_heartbeat(world):
    controller = world.controller
    assert controller.state()["can_prepare"] is False
    controller.refresh()
    assert controller.state()["available"] is True
    assert controller.state()["can_prepare"] is True
    assert controller.state()["enabled"] is False
    scope, runtime, _ = controller._observation()
    assert scope.nonce == world.session.session and scope.pid == 888
    assert scope.start_identity == "1234567890.125"
    assert runtime.core_identity == CORE_IDENTITY
    assert controller.request() is None


@pytest.mark.parametrize("key,value", [
    ("pid", 777), ("pid", True), ("protocol", True), ("bridge_session", "old"),
    ("published_at", 94.9), ("published_at", float("nan")), ("published_at", True),
    ("online", True), ("in_game", True), ("in_replay", True), ("frontend", False),
    ("bakkesmod_version", 230), ("game_build", "different"),
])
def test_heartbeat_refusal_removes_action_without_staging(world, key, value):
    world.controller.refresh()
    world.status[key] = value
    world.controller.refresh()
    assert world.controller.state()["can_prepare"] is False
    assert world.controller.request() is None
    with pytest.raises(binding.NativeCommunityError):
        world.controller.prepare({"id": "286"})
    assert not (world.data / "community-session").exists()


@pytest.mark.parametrize("key,value", [
    ("movie_ready", False), ("trial_enabled", False), ("executable_sha256", "a" * 64),
    ("core_identity", "229"), ("build_identity", "other"),
])
def test_native_movie_must_attest_matching_build(world, key, value):
    world.status["native_movie_trial"][key] = value
    world.controller.refresh()
    assert not world.controller.state()["can_prepare"]


@pytest.mark.parametrize("owner_status", ["reaping", "degraded", "exited"])
def test_helper_failure_withdraws_pending_request(world, owner_status):
    world.session.owner.poll = lambda: owner_status
    world.controller.refresh()
    assert world.controller.request() is None
    assert not world.controller.state()["can_prepare"]


def test_prepare_rechecks_owned_process_after_button_was_enabled(world, monkeypatch):
    world.controller.refresh()
    assert world.controller.state()["can_prepare"]
    monkeypatch.setattr(bootstrap, "verify_owned_offline", lambda _: False)
    with pytest.raises(binding.NativeCommunityError, match="owned"):
        world.controller.prepare({"id": "286"})


@pytest.mark.parametrize("selected", [None, {}, {"id": "223"}, {"id": 286}, "286"])
def test_no_arbitrary_plugin_can_be_prepared(world, selected):
    with pytest.raises(binding.NativeCommunityError, match="reviewed"):
        world.controller.prepare(selected)


def test_recovery_without_journal_has_no_discovery_or_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "bakkes_directory", lambda: pytest.fail("no journal"))
    binding.recover_native_community(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_helper_and_game_guard_both_reach_recovery(world, monkeypatch):
    journal = world.data / "community-session/active.json"
    journal.parent.mkdir()
    journal.write_text("sentinel", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "bakkes_directory", lambda: world.root)
    running = [False, True]
    monkeypatch.setattr(binding, "game_processes", lambda: [1] if running[0] else [])
    monkeypatch.setattr(binding, "native_launcher_pending", lambda: running[1])
    probes = []
    class Recovery:
        def __init__(self, directory, root, *, game_running):
            assert directory == world.data and root == world.root
            self.probe = game_running

        def recover(self):
            pending = self.probe()
            probes.append(pending)
            return SimpleNamespace(journal_kept=pending, status="deferred" if pending else "recovered",
                                   reason="Keep journal until both exit")
    monkeypatch.setattr(binding, "CommunitySession", Recovery)
    with pytest.raises(binding.CommunitySessionError, match="both exit"):
        binding.recover_native_community(world.data)
    running[:] = [True, False]
    with pytest.raises(binding.CommunitySessionError):
        binding.recover_native_community(world.data)
    running[:] = [False, False]
    binding.recover_native_community(world.data)
    assert probes == [True, True, False]
    assert journal.read_text(encoding="utf-8") == "sentinel"


def test_bootstrap_refuses_plugin_restore_on_community_conflict(tmp_path, monkeypatch):
    def conflict(_):
        raise binding.CommunitySessionError("foreign trial file")
    monkeypatch.setattr(binding, "recover_native_community", conflict)
    monkeypatch.setattr(bootstrap, "_plugin_session", lambda *_: pytest.fail("must wait"))
    for operation in (bootstrap.recover_plugin_session, bootstrap.restore_plugin_session):
        with pytest.raises(bootstrap.PluginSessionError, match="foreign trial file"):
            operation(tmp_path)
