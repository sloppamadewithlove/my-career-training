"""Real session composition with synthetic heartbeats and no game launch."""
import copy
from types import SimpleNamespace

import pytest

from my_career_training import bootstrap, native_community_binding as binding
from my_career_training.native_community import (
    ARCHIVE_SHA256, BUILD_IDENTITY, CORE_IDENTITY, GAME_EXE_SHA256, MEMBER_SHA256, SITE_ID, _Pending,
)
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
                  "executable_sha256": GAME_EXE_SHA256, "bakkes_core": "229",
                  "game_build": BUILD_IDENTITY}}
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
    ("bakkes_core", "Bakkes229"), ("game_build", "other"),
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


def test_pending_request_is_withdrawn_permanently_after_scope_loss(world, monkeypatch):
    pending = {"nonce": world.session.session, "pid": 888, "stem": "generated",
               "start_identity": "1234567890.125"}
    monkeypatch.setattr(world.controller.controller, "request", lambda: pending)
    world.controller.refresh()
    assert world.controller.pending()
    world.status["in_game"] = True
    world.controller.refresh()
    assert world.controller.request() is None
    world.status["in_game"] = False
    world.controller.refresh()
    assert world.controller.request() is None
    assert "changed" in world.controller.state()["message"]


def test_pending_request_expires_without_retry_and_late_ack_is_not_accepted(world, monkeypatch):
    monkeypatch.setattr(world.controller.controller, "request", lambda: {"pending": True})
    monkeypatch.setattr(world.controller.controller, "accept_status", lambda _: pytest.fail("late ack"))
    world.controller._requested_at = 100.0
    monkeypatch.setattr(binding.time, "monotonic", lambda: 111.0)
    world.status["native_community_status"] = {"status": "loaded"}
    world.controller.refresh()
    assert world.controller.request() is None
    assert not world.controller.state()["busy"]
    assert world.controller.state()["requires_restart"]
    assert not world.controller.state()["enabled"]
    assert "in time" in world.controller.state()["message"]


def test_attributed_host_refusal_is_readable_and_withdraws_request(world, monkeypatch):
    pending = {"nonce": world.session.session, "pid": 888, "stem": "generated",
               "start_identity": "1234567890.125"}
    monkeypatch.setattr(world.controller.controller, "request", lambda: pending)
    world.status["native_community_status"] = dict(pending, status="refused", reason="duplicate_loaded")
    world.controller.refresh()
    assert world.controller.request() is None
    view = world.controller.state()
    assert view["requires_restart"] and not view["enabled"]
    assert "already loaded" in view["message"] and "duplicate_loaded" not in view["message"]


def _arm(world):
    nonce = world.session.session
    stem = "MCTCommunity_286_" + nonce.replace("-", "")
    world.controller.controller._pending = _Pending(
        SITE_ID, nonce, stem, ARCHIVE_SHA256, MEMBER_SHA256, 888, "1234567890.125",
        GAME_EXE_SHA256, CORE_IDENTITY, BUILD_IDENTITY,
    )
    world.controller.controller._status = "staged"
    world.controller.controller._message = "The reviewed plugin is staged. It is not loaded."
    world.controller._requested_at = binding.time.monotonic()
    world.controller.refresh()
    return {
        "status": "loaded", "site_id": SITE_ID, "nonce": nonce, "stem": stem,
        "filename": f"{stem}.dll", "pid": 888, "start_identity": "1234567890.125",
        "member_sha256": MEMBER_SHA256, "archive_sha256": ARCHIVE_SHA256,
    }


def _local_match(world):
    world.status["in_game"] = True
    world.status["frontend"] = False
    world.status["in_replay"] = False
    world.status["online"] = False
    world.status["native_movie_trial"]["movie_ready"] = False


def test_exact_ack_during_local_match_is_accepted(world):
    ack = _arm(world)
    assert len(ack) == 9 and world.controller.request() is not None
    _local_match(world)
    world.status["native_community_status"] = ack
    world.controller.refresh()
    view = world.controller.state()
    assert view["enabled"] is True and view["requires_restart"] is False
    assert view["can_prepare"] is False and view["game_verified"] is False
    assert world.controller.request() is None
    world.status["in_game"] = False
    world.status["frontend"] = True
    world.status["native_movie_trial"]["movie_ready"] = True
    del world.status["native_community_status"]
    world.controller.refresh()
    assert world.controller.request() is None and world.controller.state()["enabled"] is True
    assert world.controller.state()["requires_restart"] is False


def test_local_match_hides_the_pending_request_without_a_restart(world):
    _arm(world)
    published = world.controller.request()
    assert published is not None
    _local_match(world)
    world.controller.refresh()
    assert world.controller.request() is None
    assert world.controller.state()["requires_restart"] is False
    assert "changed" not in world.controller.state()["message"]
    world.status["in_game"] = False
    world.status["frontend"] = True
    world.status["native_movie_trial"]["movie_ready"] = True
    world.controller.refresh()
    assert world.controller.request() is None
    assert world.controller.request() != published
    assert world.controller.state()["can_prepare"] is False
    assert world.controller.state()["requires_restart"] is False
    assert world.controller.state()["enabled"] is False


def test_prepare_in_a_local_match_writes_nothing(world):
    world.controller.refresh()
    _local_match(world)
    with pytest.raises(binding.NativeCommunityError, match="Community menu"):
        world.controller.prepare({"id": "286"})
    assert not (world.data / "community-session").exists()


def test_hidden_inflight_request_keeps_activity_locked(world):
    _arm(world)
    _local_match(world)
    world.controller.refresh()
    assert world.controller.request() is None
    assert world.controller.state()["busy"] is True
    assert world.controller.state()["requires_restart"] is False


def test_loaded_trial_scope_loss_revokes_enabled_status(world):
    world.status["native_community_status"] = _arm(world)
    world.controller.refresh()
    assert world.controller.state()["enabled"] is True
    world.status["online"] = True
    world.controller.refresh()
    assert world.controller.state()["enabled"] is False
    assert world.controller.state()["requires_restart"] is True
    world.status["online"] = False
    world.controller.refresh()
    assert world.controller.state()["enabled"] is False


@pytest.mark.parametrize("mutate", [
    lambda world, ack: world.status.update(online=True),
    lambda world, ack: setattr(world.session.owner, "poll", lambda: "exited"),
    lambda world, ack: world.status.update(published_at=90.0),
    lambda world, ack: world.status["native_movie_trial"].update(executable_sha256="ab" * 32),
    lambda world, ack: ack.update(nonce="12345678-1234-4234-8234-123456789abd"),
    lambda world, ack: ack.update(member_sha256="cd" * 32),
])
def test_online_unowned_stale_hash_and_nonce_reject_the_ack(world, mutate):
    ack = _arm(world)
    _local_match(world)
    mutate(world, ack)
    world.status["native_community_status"] = ack
    world.controller.refresh()
    assert world.controller.state()["enabled"] is False
    assert world.controller.request() is None
    assert world.controller.state()["requires_restart"] is True
    ack["nonce"] = world.session.session
    ack["member_sha256"] = MEMBER_SHA256
    world.status["online"] = False
    world.status["published_at"] = 100.0
    world.status["native_movie_trial"]["executable_sha256"] = GAME_EXE_SHA256
    world.session.owner.poll = lambda: "ready"
    world.status["native_community_status"] = ack
    world.controller.refresh()
    assert world.controller.state()["enabled"] is False
    assert world.controller.request() is None


@pytest.mark.parametrize("mutate", [
    lambda status: status.update(frontend=None),
    lambda status: status.update(in_game=1),
    lambda status: status.update(online=0),
    lambda status: status.update(frontend=False),
    lambda status: status.update(in_game=True),
    lambda status: status["native_movie_trial"].update(movie_ready=1),
    lambda status: status.pop("frontend"),
])
def test_malformed_heartbeat_flags_do_not_grant_or_accept(world, mutate):
    ack = _arm(world)
    mutate(world.status)
    world.status["native_community_status"] = ack
    world.controller.refresh()
    view = world.controller.state()
    assert view["enabled"] is False and view["can_prepare"] is False
    assert world.controller.request() is None
    assert not (world.data / "community-session").exists()
