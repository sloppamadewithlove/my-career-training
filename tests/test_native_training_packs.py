from pathlib import Path
import re

import pytest

from my_career_training.training.native_packs import (
    NativeTrainingPackController,
    NativeTrainingPackError,
)
from my_career_training.training.packs import get_training_pack, training_packs
from my_career_training.ingame import ALLOWED_ACTIONS


class World:
    def __init__(self):
        self.now = 100.0
        self.frontend = True
        self.fail = False
        self.heartbeat = {}
        self.nonce = "45234854-6e9c-4af5-9c50-e9347f375140"
        self.pid = 888
        self.start_identity = "1234567890.125"
        self.last_request = None
        self.controller = NativeTrainingPackController(
            self.observe, clock=lambda: self.now
        )

    def observe(self, require_frontend):
        if self.fail or (require_frontend and not self.frontend):
            raise RuntimeError("scope unavailable")
        return {
            "nonce": self.nonce,
            "pid": self.pid,
            "start_identity": self.start_identity,
            "frontend": self.frontend,
            "heartbeat": self.heartbeat,
        }

    def start(self, pack_id="powershot-practice"):
        activity = self.controller.start(pack_id)
        self.last_request = self.controller._request.copy()
        return activity

    def ack(self, status="loaded", **changes):
        pending = self.controller._request or self.last_request
        value = dict(pending, status=status, code=get_training_pack(pending["pack_id"])["code"],
                     reason="test")
        value.update(changes)
        self.heartbeat = {"native_training_pack": value}
        return value


def test_native_fixed_table_has_exact_python_catalog_parity():
    assert "start_training_pack" in ALLOWED_ACTIONS
    header = (Path(__file__).resolve().parents[1] / "plugin/include/NativeTrainingPackHost.h").read_text()
    pairs = dict(re.findall(r'^\s*\{"([a-z0-9-]+)", "([0-9A-F-]+)"\},$', header, re.MULTILINE))
    assert pairs == {pack["id"]: pack["code"] for pack in training_packs()}


@pytest.mark.parametrize("pack_id", [None, 7, "", "Powershots", "unknown", "powershots "])
def test_only_exact_fixed_pack_ids_are_accepted(pack_id):
    world = World()
    with pytest.raises((TypeError, ValueError)):
        world.start(pack_id)
    assert world.controller.state()["status"] == "idle"
    assert world.controller.request() is None


def test_start_is_workerless_metadata_and_exact_ack_only():
    world = World()
    activity = world.start("powershots")
    pending = world.controller.request()
    assert set(activity) == {"session_id", "request_id", "lesson_id", "training_pack"}
    assert activity["lesson_id"] == "power-shots"
    assert activity["training_pack"] == get_training_pack("powershots")
    assert set(pending) == {"pack_id", "session_id", "request_id", "nonce", "pid", "start_identity"}
    assert pending["pack_id"] == "powershots" and "code" not in pending and "command" not in pending

    world.ack(request_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    assert world.controller.refresh() is False
    assert world.controller.state()["status"] == "pending"
    world.heartbeat = {}
    assert world.controller.refresh() is False
    world.ack()
    assert world.controller.refresh() is True
    assert world.controller.state()["status"] == "loaded"
    assert world.controller.request() == pending
    assert world.controller.state()["busy"] is False


@pytest.mark.parametrize("receipt", ["missing", "wrong_request"])
def test_loaded_controller_tolerates_brief_receipt_gap_then_fails_closed(receipt):
    world = World()
    world.start()
    expected = world.controller.request()
    world.ack()
    assert world.controller.refresh()
    assert world.controller.state()["status"] == "loaded"
    assert world.controller.request() == expected

    if receipt == "missing":
        world.heartbeat = {}
    else:
        world.ack(request_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    world.now += 1.0
    world.controller.refresh()
    assert world.controller.state()["status"] == "loaded"
    assert world.controller.request() == expected

    world.now += 1.1
    assert world.controller.refresh()
    assert world.controller.state()["status"] == "failed"
    assert world.controller.state()["requires_restart"] is True
    assert world.controller.request() is None


def test_wrong_code_fails_and_never_accepts_a_later_forged_success():
    world = World()
    world.start()
    world.ack(code="7028-5E10-88EF-E83E")
    assert world.controller.refresh()
    assert world.controller.state()["status"] == "failed"
    assert world.controller.state()["requires_restart"] is True
    world.ack()
    assert world.controller.refresh() is False
    assert world.controller.state()["status"] == "failed"


def test_frontend_scope_timeout_and_scope_loss_withdraw_permanently():
    world = World()
    world.frontend = False
    with pytest.raises(NativeTrainingPackError, match="frontend"):
        world.start()
    world.frontend = True
    world.start()
    world.now = 120.001
    assert world.controller.refresh()
    assert world.controller.request() is None
    assert world.controller.state()["requires_restart"] is True
    world.ack()
    assert world.controller.refresh() is False
    with pytest.raises(NativeTrainingPackError, match="Finish or exit"):
        world.start("powershots")

    other = World()
    other.start()
    other.fail = True
    assert other.controller.refresh()
    other.fail = False
    other.ack()
    assert other.controller.refresh() is False
    assert other.controller.state()["status"] == "failed"


def test_loaded_activity_requires_matching_return_identity():
    world = World()
    activity = world.start()
    world.ack()
    world.controller.refresh()
    with pytest.raises(NativeTrainingPackError, match="changed"):
        world.controller.clear_for_return("other")
    world.controller.clear_for_return(activity["session_id"])
    assert world.controller.state()["status"] == "idle"
    assert world.controller.state()["active"] is False
    assert world.controller.request() is None
