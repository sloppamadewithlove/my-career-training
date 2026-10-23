"""SDK-independent bot-provider boundary.

This shipped provider is an experimental ground-based controller. Level and
difficulty tune reaction, predictions, precision and tactical options, with no
rank certification. Optional providers must provide their own evaluated manifests.
"""
import math
import random
from .physics import clamp, perceive
from .tactics import ROLE_WEIGHTS, choose
from .driving import execute, neutral

PROVIDER_ID = "mct-specialist-baseline"
PROVIDER_VERSION = "0.1.0"
ROLES = tuple(ROLE_WEIGHTS)


def provider_manifest():
    return {
        "id": PROVIDER_ID, "provider": PROVIDER_ID, "name": "MCT Ground Specialists",
        "version": PROVIDER_VERSION, "status": "experimental", "installed": True,
        "rank_certification": None, "rank_claim": "Unranked experimental baseline",
        "supported_formats": [1, 2, 3, 4], "evaluated_formats": [],
        "roles": list(ROLES), "level_range": [1, 10],
        "capabilities": ["ground_intercepts", "single_jump_hits", "goal_cover", "clears",
                         "passes", "shots", "support_rotation", "boost_pickups", "ground_recovery"],
        "limitations": ["No Windows match evaluation recorded", "No certified competitive rank",
                        "No advanced aerial mechanics", "Fallback ball prediction omits wall bounces"],
        "rank_targets": [{"rank": rank, "available": False, "status": "unevaluated"}
                         for rank in ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Champion",
                                      "Grand Champion", "Supersonic Legend")],
        "optional_providers": [{"id": "nexto", "installed": False, "status": "unavailable",
                                "reason": "No licensed compatible runtime/model packaged or verified"}],
        "role_weights": {role: dict(weights) for role, weights in ROLE_WEIGHTS.items()},
    }


def capability_parameters(level=1, difficulty=.5):
    level = int(clamp(int(level), 1, 10))
    difficulty = float(difficulty)
    if not math.isfinite(difficulty):
        raise ValueError("Bot difficulty must be a finite number")
    difficulty = clamp(difficulty, 0, 1)
    skill = .55 * (level - 1) / 9 + .45 * difficulty
    return {
        "prediction_horizon": round(1.4 + skill * 2.6, 4),
        "prediction_step": round(.18 - skill * .12, 4),
        "reaction_interval": round(.26 - skill * .20, 4),
        "aim_error": round(180 * (1 - skill) + 8, 4),
        "speed_limit": round(1450 + skill * 800, 4),
        "steer_gain": round(1.8 + skill * 1.0, 4),
        "recovery_gain": round(1.0 + skill * 1.6, 4),
        "pass_options": 1 + int(skill * 3),
        "pass_range": round(2100 + skill * 1800, 4),
        "boost_threshold": round(22 + skill * 12, 4),
    }


class SpecialistController:
    def __init__(self, role="all-rounder", level=1, difficulty=.5, seed=0):
        if role not in ROLE_WEIGHTS:
            raise ValueError(f"Unknown bot role: {role}")
        self.role = role
        self.level = int(clamp(int(level), 1, 10))
        self.difficulty = clamp(float(difficulty), 0, 1)
        self.parameters = capability_parameters(self.level, difficulty)
        self.seed = int(seed)
        self._random = random.Random(self.seed)
        self._last_time = None
        self._decision_time = -float("inf")
        self._decision = None
        self._aim_error = 0.0
        self._jump_started = None
        self._jump_cooldown = -float("inf")
        self.last_decision = None
        self.intent = None

    def manifest(self):
        manifest = provider_manifest()
        manifest.update(role=self.role, level=self.level, difficulty=self.difficulty,
                        seed=self.seed, parameters=dict(self.parameters))
        return manifest

    def reset(self):
        self._random.seed(self.seed)
        self._last_time = None
        self._decision_time = -float("inf")
        self._decision = None
        self._jump_started = None
        self._jump_cooldown = -float("inf")
        self.last_decision = None
        self.intent = None

    def step(self, frame, player_index, intents=None):
        p = perceive(frame, player_index, self.parameters)
        if self._last_time is not None and p.time < self._last_time:
            self.reset()
        self._last_time = p.time
        if p.car.get("is_demolished", False) or frame.get("match_ended", False):
            self.intent = {"player_index": player_index, "kind": "inactive", "time": p.time, "eta": 99}
            self.last_decision = dict(self.intent)
            return neutral()
        airborne = not p.car.get("wheel_contact", True)
        if (self._decision is None or p.time - self._decision_time >= self.parameters["reaction_interval"]
                or p.danger > .86 or airborne or self._decision.kind == "recovery"):
            self._decision = choose(p, self.role, self.parameters, intents)
            self._decision_time = p.time
            self._aim_error = self._random.uniform(-self.parameters["aim_error"], self.parameters["aim_error"])
        decision = self._decision
        if self._jump_started is not None and p.time - self._jump_started > .14:
            self._jump_started = None
        # A non-None old jump time prevents a second jump trigger in the cooldown.
        jump_guard = self._jump_started
        if jump_guard is None and p.time < self._jump_cooldown:
            jump_guard = p.time - 1
        controls = execute(p, decision, self.parameters, self._aim_error, jump_guard)
        if controls["jump"] and self._jump_started is None:
            self._jump_started = p.time
            self._jump_cooldown = p.time + .6
        self.last_decision = decision.as_dict()
        self.intent = {**self.last_decision, "player_index": player_index, "team": p.car.get("team", 0),
                       "time": p.time, "provider": PROVIDER_ID}
        return controls


__all__ = ["SpecialistController", "provider_manifest", "capability_parameters", "ROLES"]
