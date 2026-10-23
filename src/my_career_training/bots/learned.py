"""Offline Necto/Nexto policy adapter, derived from Rolv-Arild/Necto.

The action lookup/parser and kickoff sequence are adapted under CC BY-NC-SA
4.0. See _vendor/NOTICE and _vendor/LICENSE. Original model weights and the
observation math are preserved. This module is imported only in the worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from types import SimpleNamespace

import numpy as np
import torch

from ._vendor.necto_obs import NectoObsBuilder
from ._vendor.nexto_obs import BOOST_LOCATIONS, NextoObsBuilder
from .driving import neutral
from .providers import MODELS, ProviderUnavailable, _verified

CONTROL_NAMES = ("throttle", "steer", "pitch", "yaw", "roll", "jump", "boost", "handbrake")
INVERT = np.array([-1., -1., 1.])


def _action_table():
    actions = []
    for throttle in (-1, 0, 1):
        for steer in (-1, 0, 1):
            for boost in (0, 1):
                for handbrake in (0, 1):
                    if boost and throttle != 1:
                        continue
                    actions.append([throttle or boost, steer, 0, steer, 0, 0, boost, handbrake])
    for pitch in (-1, 0, 1):
        for yaw in (-1, 0, 1):
            for roll in (-1, 0, 1):
                for jump in (0, 1):
                    for boost in (0, 1):
                        if (jump and yaw != 0) or pitch == roll == jump == 0:
                            continue
                        handbrake = jump == 1 and (pitch != 0 or yaw != 0 or roll != 0)
                        actions.append([boost, yaw, pitch, yaw, roll, jump, boost, handbrake])
    return np.asarray(actions, dtype=np.float32)


ACTION_TABLE = _action_table()
# Upstream's 120 Hz speed-flip kickoff. Policy inference resumes after it.
KICKOFF = np.asarray(
    44 * [[1, 0, 0, 0, 0, 0, 1, 0]]
    + 16 * [[1, -1, 0, 0, 0, 0, 1, 0]]
    + 8 * [[1, 0, 0, 0, 0, 1, 1, 0]]
    + 4 * [[1, 0, 0, 0, 0, 0, 1, 0]]
    + 4 * [[1, 0, -.7, .8, 0, 1, 1, 0]]
    + 52 * [[1, 0, 1, 0, 0, 0, 1, 0]]
    + 40 * [[1, 0, .5, 0, 1, 0, 0, 0]], dtype=np.float32)


def _vector(values, name):
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (3,) or not np.isfinite(array).all():
        raise ProviderUnavailable(f"The learned bot received invalid {name} telemetry.")
    return array


def rotation_matrix(rotation):
    """Rocket League pitch/yaw/roll to the RLGym forward/left/up basis."""
    pitch, yaw, roll = _vector(rotation, "rotation")
    cp, cy, cr = np.cos([pitch, yaw, roll])
    sp, sy, sr = np.sin([pitch, yaw, roll])
    return np.array([[cp * cy, cy * sp * sr - cr * sy, -cr * cy * sp - sr * sy],
                     [cp * sy, sy * sp * sr + cr * cy, -cr * sy * sp + sr * cy],
                     [sp, -cp * sr, cp * cr]])


@dataclass(eq=False)
class _Physics:
    position: np.ndarray
    linear_velocity: np.ndarray
    angular_velocity: np.ndarray
    matrix: np.ndarray

    def rotation_mtx(self):
        return self.matrix

    def forward(self):
        return self.matrix[:, 0]

    def up(self):
        return self.matrix[:, 2]

    def inverted(self):
        return _Physics(self.position * INVERT, self.linear_velocity * INVERT,
                        self.angular_velocity * INVERT, self.matrix * INVERT[:, None])


@dataclass(eq=False)
class _Player:
    car_id: int
    team_num: int
    car_data: _Physics
    inverted_car_data: _Physics
    is_demoed: bool
    on_ground: bool
    ball_touched: bool
    has_flip: bool
    boost_amount: float


def _physics(data):
    return _Physics(_vector(data.get("position"), "position"),
                    _vector(data.get("velocity", [0, 0, 0]), "velocity"),
                    _vector(data.get("angular_velocity", [0, 0, 0]), "angular velocity"),
                    rotation_matrix(data.get("rotation", [0, 0, 0])))


@lru_cache(maxsize=8)
def _boost_order(positions):
    distances = np.linalg.norm(np.asarray(positions)[:, None, :2] - np.asarray(BOOST_LOCATIONS)[None, :, :2], axis=2)
    order = tuple(int(index) for index in np.argmin(distances, axis=0))
    if len(set(order)) != 34 or any(distances[index, target] > 25 for target, index in enumerate(order)):
        raise ProviderUnavailable("This arena's boost layout is not supported by Necto or Nexto.")
    return order


def build_state(frame, player_index):
    """Map actual normalized RLBot data into the licensed observation interface.

    Boost pad order is determined by position, because RLBot v5 order differs
    from the historical RLGym order. Missing/unsupported fields fail explicitly.
    """
    cars, pads = frame.get("cars", []), frame.get("boosts", [])
    if not 2 <= len(cars) <= 6 or any(sum(c.get("team") == team for c in cars) > 3 for team in (0, 1)):
        raise ProviderUnavailable("Necto and Nexto require a standard 1v1, 2v2 or 3v3 fixture.")
    if len(pads) != 34:
        raise ProviderUnavailable("Necto and Nexto require standard-arena boost pad telemetry (34 pads).")
    positions = tuple(tuple(_vector(pad.get("position"), "boost pad")) for pad in pads)
    boost_states = [float(bool(pads[index].get("active", False))) for index in _boost_order(positions)]
    players, main = [], None
    now = float(frame["time"])
    for car in cars:
        index, team = car.get("index"), car.get("team")
        if type(index) is not int or type(team) is not int or team not in (0, 1):
            raise ProviderUnavailable("The learned bot received invalid player identity telemetry.")
        physics = _physics(car)
        touched = car.get("latest_touch") or {}
        touch_time = float(touched.get("game_seconds", -1000))
        # RLBot's dodge timeout is remaining flip time. A car which never jumped
        # retains its flip after falling off a wall; consumed flips stay consumed.
        flip = not car.get("has_dodged", False) and not car.get("has_double_jumped", False)
        timeout = float(car.get("dodge_timeout", 0))
        flip = flip and (not car.get("has_jumped", False) or car.get("air_state") == "Jumping"
                         or timeout == -1 or timeout > 0)
        boost = float(car.get("boost", 0)) / 100
        if not math.isfinite(boost) or not 0 <= boost <= 1:
            raise ProviderUnavailable("The learned bot received invalid boost telemetry.")
        player = _Player(index, team, physics, physics.inverted(), bool(car.get("is_demolished", False)),
                         bool(car.get("wheel_contact", False)), 0 <= now - touch_time < 8 / 120, flip, boost)
        players.append(player)
        if index == player_index:
            main = player
    if main is None or len({p.car_id for p in players}) != len(players):
        raise ProviderUnavailable("The learned bot's player index is missing or duplicated.")
    # Match upstream RLBot policy: main player, teammates, opponents.
    players = [main] + [p for p in players if p is not main and p.team_num == main.team_num] + [
        p for p in players if p.team_num != main.team_num]
    ball = _physics(frame["ball"])
    return SimpleNamespace(players=players, ball=ball, inverted_ball=ball.inverted(),
                           boost_pads=np.asarray(boost_states),
                           blue_score=int(frame.get("blue_score", 0)),
                           orange_score=int(frame.get("orange_score", 0))), main


@lru_cache(maxsize=2)
def _load_actor(provider_id, path):
    if not _verified(path, MODELS[provider_id]["sha256"], force=True):
        raise ProviderUnavailable("The learned policy failed its integrity check before loading.")
    torch.set_num_threads(1)
    # Python opens Unicode Windows paths correctly. Passing a filename directly
    # delegates to Torch 2.6's narrow-character native fopen and can fail for a
    # player's account name or install folder. A binary stream uses its buffer API.
    with path.open("rb") as stream:
        actor = torch.jit.load(stream, map_location="cpu").eval()
    # Real model warmup before a match: catches unsupported runtime/operators.
    with torch.inference_mode():
        actor((torch.zeros(1, 1, 32), torch.zeros(1, 41, 24), torch.zeros(1, 41)))
    return actor


class LearnedController:
    def __init__(self, provider_id, path, seed=0):
        self.provider_id = provider_id
        self.seed = int(seed)
        self.actor = _load_actor(provider_id, path)
        self.reset()

    def reset(self):
        self.obs_builder = NextoObsBuilder() if self.provider_id == "nexto" else NectoObsBuilder()
        self.action = np.zeros(8, dtype=np.float32)
        self.controls = neutral()
        self.ticks = 8
        self.previous_tick = None
        self.previous_time = None
        self.update_action = True
        self.kickoff_index = -1
        self.intent = self.last_decision = None

    def manifest(self):
        from .providers import provider_catalog
        return next(m for m in provider_catalog() if m["id"] == self.provider_id)

    def _infer(self, observation):
        tensors = tuple(torch.from_numpy(np.asarray(part, dtype=np.float32)) for part in observation)
        with torch.inference_mode():
            out, _ = self.actor(tensors)
        if self.provider_id == "nexto":
            logits = out.reshape(-1)
            if logits.numel() != len(ACTION_TABLE) or not torch.isfinite(logits).all():
                raise ProviderUnavailable("Nexto produced an invalid policy response.")
            return ACTION_TABLE[int(torch.argmax(logits))].copy()
        choices = []
        for logits in out:
            if not torch.isfinite(logits).all():
                raise ProviderUnavailable("Necto produced an invalid policy response.")
            choices.append(int(torch.argmax(logits.reshape(-1))))
        if len(choices) != 5 or choices[0] > 2 or choices[1] > 2 or any(c > 1 for c in choices[2:]):
            raise ProviderUnavailable("Necto produced an invalid action response.")
        throttle, steer, jump, boost, brake = choices
        throttle, steer = throttle - 1, steer - 1
        return np.array([throttle, steer, throttle, steer * (1 - brake), steer * brake,
                         jump, boost, brake], dtype=np.float32)

    def _kickoff(self, frame, main, ticks_elapsed):
        active = frame.get("is_kickoff", False) or frame.get("phase") == "Kickoff"
        if not active:
            self.kickoff_index = -1
            return
        ball = _vector(frame["ball"]["position"], "ball position")
        if self.kickoff_index >= 0:
            self.kickoff_index += ticks_elapsed
        elif self.kickoff_index == -1:
            distances = {car["index"]: float(np.linalg.norm(np.asarray(car["position"])[:2] - ball[:2]))
                         for car in frame["cars"]}
            mine = distances[main.car_id]
            taking = abs(min(distances.values()) - mine) <= 10
            for car in frame["cars"]:
                if car["team"] == main.team_num and car["index"] != main.car_id:
                    if abs(distances[car["index"]] - mine) <= 10:
                        # Preserve upstream convention: blue higher x / orange lower x goes left.
                        other_is_right = (car["position"][0] < main.car_data.position[0]) if main.team_num == 0 else (
                            car["position"][0] > main.car_data.position[0])
                        if not other_is_right:
                            taking = False
            self.kickoff_index = 0 if taking else -2
        if 0 <= self.kickoff_index < len(KICKOFF) and abs(ball[1]) < 1:
            self.action = KICKOFF[self.kickoff_index].copy()
            self.controls = controls_dict(self.action)

    def step(self, frame, player_index, intents=None):
        now = float(frame["time"])
        if not math.isfinite(now):
            raise ProviderUnavailable("The learned bot received invalid clock telemetry.")
        tick = int(frame.get("frame_num", round(now * 120)))
        if self.previous_time is not None and (now < self.previous_time or tick < self.previous_tick):
            self.reset()
        if frame.get("match_ended", False):
            self.controls = neutral()
            return dict(self.controls)
        elapsed = 0 if self.previous_tick is None else tick - self.previous_tick
        if self.previous_tick == tick:
            return dict(self.controls)
        self.previous_tick, self.previous_time = tick, now
        state, main = build_state(frame, player_index)
        if main.is_demoed:
            self.controls = neutral()
            self.intent = {"provider": self.provider_id, "player_index": player_index,
                           "team": main.team_num, "kind": "inactive", "time": now}
            return dict(self.controls)
        self.ticks += elapsed
        if self.update_action:
            self.update_action = False
            observation = self.obs_builder.build_obs(main, state, self.action)
            self.action = self._infer(observation)
        # The original model runs at 120 Hz / tick_skip 8 with one-tick action delay.
        apply_threshold = 7 if self.provider_id == "nexto" else 8
        if self.ticks >= apply_threshold:
            self.controls = controls_dict(self.action)
        if self.ticks >= 8:
            self.ticks = 0
            self.update_action = True
        self._kickoff(frame, main, elapsed)
        self.intent = {"provider": self.provider_id, "player_index": player_index,
                       "team": main.team_num, "kind": "learned_policy", "time": now,
                       "rank_certification": None}
        self.last_decision = dict(self.intent)
        return dict(self.controls)


def controls_dict(action):
    values = np.asarray(action, dtype=np.float64)
    if values.shape != (8,) or not np.isfinite(values).all() or np.any(np.abs(values) > 1):
        raise ProviderUnavailable("The learned bot produced an invalid controller action.")
    return {key: float(values[i]) if i < 5 else bool(values[i] > 0)
            for i, key in enumerate(CONTROL_NAMES)}
