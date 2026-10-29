"""Repeatable ball-launch Power Shot scenarios (version 3)."""

from copy import deepcopy
import math

from ..bots import SpecialistController
from ..bots.driving import execute
from ..bots.physics import perceive
from ..bots.tactics import Decision

LESSON_ID = "power-shots"
SCENARIO_VERSION = 3
PLANNED_TOTAL = 12
IMPLEMENTED_SCENARIOS = ("low-side-pass", "bouncing-side-pass")
RANKS = (
    "bronze", "silver", "gold", "platinum", "diamond", "champion",
    "grand-champion", "supersonic-legend",
)
_RANK_TITLES = {rank: rank.replace("-", " ").title() for rank in RANKS}
_SIDE_WALL_X = -4096.0
_BACK_WALL_Y = 5120.0
_GOAL_MOUTH_HALF_WIDTH = 893.0
_BALL_RADIUS = 93.15

# Intended exercise pressure, not certified player rank. The roster stays
# stable within a rank so situations can change inside the same match.
_PRESSURE = {
    "bronze": {"speed": 1.00, "timeout": 15.0},
    "silver": {"speed": 1.06, "timeout": 14.0},
    "gold": {"speed": 1.11, "timeout": 14.0, "keeper": (2, .20, 850.0, 1.40, 4400.0, 4860.0)},
    "platinum": {"speed": 1.17, "timeout": 13.0, "keeper": (3, .30, 950.0, 1.10, 4380.0, 4830.0)},
    "diamond": {"speed": 1.22, "timeout": 12.0, "keeper": (4, .42, 1050.0, .85, 3500.0, 4780.0)},
    "champion": {"speed": 1.28, "timeout": 11.0, "keeper": (5, .55, 1150.0, .65, 3300.0, 4720.0)},
    "grand-champion": {"speed": 1.33, "timeout": 10.0, "keeper": (6, .68, 1250.0, .48, 4290.0, 4660.0),
                       "defender": (5, .62, 1200.0, .62)},
    "supersonic-legend": {"speed": 1.39, "timeout": 9.0, "keeper": (7, .80, 1350.0, .34, 4260.0, 4600.0),
                          "defender": (6, .76, 1350.0, .42)},
}
_HUMAN = {
    "position": [0.0, 2250.0, 17.0],
    "velocity": [0.0, 0.0, 0.0],
    "rotation": [0.0, math.pi / 2, 0.0],
    "angular_velocity": [0.0, 0.0, 0.0],
    "boost": 100.0,
}
_SCENARIOS = {
    "low-side-pass": {
        "title": "Low side pass",
        "description": (
            "A repeatable grounded ball launches from the left side into your central "
            "shooting lane. Meet it and shoot toward goal."
        ),
        "origin": [-2200.0, 3000.0, 93.0],
        "lane": [-250.0, 3900.0, 93.0],
        "human": [0.0, 2250.0, 17.0],
        "speed": 900.0,
        "target": (-350.0, 900.0),
        "pressure": [900.0, 3650.0, 17.0],
    },
    "bouncing-side-pass": {
        "title": "Bouncing side pass",
        "description": (
            "A repeatable ball launches from the left side with a bounce. Beginner "
            "deliveries settle before the receiving lane; Gold and above may arrive "
            "as a bounce or low volley."
        ),
        "origin": [-2100.0, 2925.0, 93.0],
        "lane": [250.0, 3850.0, 93.0],
        "human": [250.0, 2200.0, 17.0],
        "speed": 860.0,
        "launch": "bounce",
        "target": (300.0, 850.0),
        "pressure": [-850.0, 3600.0, 17.0],
    },

}
_GOAL = {"center_x": 0.0, "half_width": 750.0, "min_z": 93.0, "max_z": 550.0}


def _validate(lesson_id, scenario_id, difficulty):
    if lesson_id != LESSON_ID:
        raise ValueError("Scenario definitions exist only for the power-shots lesson.")
    if not isinstance(scenario_id, str) or scenario_id not in _SCENARIOS:
        raise ValueError(
            "Unknown Power Shot scenario. Implemented scenarios: "
            + ", ".join(IMPLEMENTED_SCENARIOS) + "."
        )
    if not isinstance(difficulty, str) or difficulty not in _PRESSURE:
        raise ValueError(
            "Unknown Power Shot difficulty rank. Choose one of: " + ", ".join(RANKS) + "."
        )


def _launch(scenario_id, difficulty, speed):
    data = _SCENARIOS[scenario_id]
    origin, lane = data["origin"], data["lane"]
    dx, dy = lane[0] - origin[0], lane[1] - origin[1]
    length = math.hypot(dx, dy)
    velocity = [speed * dx / length, speed * dy / length, 0.0]
    position = list(origin)
    execution = "grounded-receive"
    launch = data.get("launch")
    if launch == "wall":
        mirrored_lane = [2 * _SIDE_WALL_X - lane[0], lane[1]]
        dx, dy = mirrored_lane[0] - origin[0], mirrored_lane[1] - origin[1]
        length = math.hypot(dx, dy)
        velocity = [speed * dx / length, speed * dy / length, 0.0]
        execution = "grounded-wall-read" if difficulty in {"bronze", "silver"} else "wall-rebound-strike"
    elif launch == "backboard":
        mirrored_lane = [lane[0], 2 * _BACK_WALL_Y - lane[1]]
        dx, dy = mirrored_lane[0] - origin[0], mirrored_lane[1] - origin[1]
        length = math.hypot(dx, dy)
        impact_x = origin[0] + dx * (_BACK_WALL_Y - origin[1]) / dy
        if abs(impact_x) <= _GOAL_MOUTH_HALF_WIDTH + _BALL_RADIUS:
            raise ValueError("Back-wall launches must aim outside the goal mouth plus one ball radius.")
        velocity = [speed * dx / length, speed * dy / length, 0.0]
        execution = "grounded-rebound" if difficulty in {"bronze", "silver"} else "rebound-recovery"
    elif launch in {"bounce", "drop"}:
        if difficulty in {"bronze", "silver"}:
            position[2], velocity[2] = 125.0, -260.0
            execution = "settled-bounce"
        else:
            position[2] = 260.0 if launch == "bounce" else 520.0
            velocity[2] = -80.0 if launch == "bounce" else -140.0
            execution = "low-volley"
    return {
        "position": position,
        "velocity": velocity,
        "angular_velocity": [0.0, 0.0, 0.0],
    }, execution, length / speed


def _opponents(difficulty, scenario_id, data):
    profile = _PRESSURE[difficulty]
    if "keeper" not in profile:
        return {}, {}, {}
    level, skill, speed_limit, reaction_delay, lane_limit, depth = profile["keeper"]
    later_situation = IMPLEMENTED_SCENARIOS.index(scenario_id) >= 6
    if later_situation:
        depth -= 220.0
        lane_limit -= 180.0
        reaction_delay += .4
    cover_x = data.get("keeper_x", -620.0 + 95.0 * RANKS.index(difficulty))
    pose = {
        "position": [cover_x, depth, 17.0],
        "velocity": [0.0, 0.0, 0.0],
        "rotation": [0.0, -math.pi / 2, 0.0],
        "angular_velocity": [0.0, 0.0, 0.0],
        "boost": 100.0,
    }
    bots, roles = {0: pose}, {"keeper": 0}
    pressure = {
        "keeper_level": level,
        "keeper_difficulty": skill,
        "keeper_speed_limit": speed_limit,
        "keeper_reaction_delay": reaction_delay,
        "keeper_lane_limit_y": lane_limit,
    }
    if "defender" in profile:
        dlevel, dskill, dspeed, ddelay = profile["defender"]
        defender = deepcopy(_HUMAN)
        defender["position"] = list(data["pressure"])
        if later_situation:
            dx = defender["position"][0] - data["lane"][0]
            dy = defender["position"][1] - data["lane"][1]
            distance = math.hypot(dx, dy)
            if distance < 1400.0:
                scale = 1400.0 / distance
                defender["position"][:2] = [data["lane"][0] + dx * scale,
                                             data["lane"][1] + dy * scale]
            ddelay += .4
        defender["rotation"] = [0.0, -math.pi / 2, 0.0]
        bots[1] = defender
        roles["defender"] = 1
        pressure.update(defender_level=dlevel, defender_difficulty=dskill,
                        defender_speed_limit=dspeed, defender_reaction_delay=ddelay)
    return bots, roles, pressure


def scenario_definition(lesson_id, scenario_id, difficulty="gold"):
    """Return one validated SDK-independent launch situation."""
    _validate(lesson_id, scenario_id, difficulty)
    data = _SCENARIOS[scenario_id]
    profile = _PRESSURE[difficulty]
    speed = data["speed"] * profile["speed"]
    timeout = profile["timeout"]
    launch, execution, arrival_seconds = _launch(scenario_id, difficulty, speed)
    bots, bot_roles, keeper_pressure = _opponents(difficulty, scenario_id, data)
    human_index = len(bots)
    human = deepcopy(_HUMAN)
    human["position"] = list(data["human"])
    parked_ball = {
        "position": [launch["position"][0], launch["position"][1], 93.0],
        "velocity": [0.0, 0.0, 0.0],
        "angular_velocity": [0.0, 0.0, 0.0],
    }
    pressure = {
        "rank": difficulty,
        "rank_title": _RANK_TITLES[difficulty],
        "launch_speed": speed,
        "timeout": timeout,
        **keeper_pressure,
        "note": "Intended difficulty only; not a certified bot rank.",
    }
    return {
        "version": SCENARIO_VERSION,
        "lesson_id": LESSON_ID,
        "id": scenario_id,
        "scenario_id": scenario_id,
        "title": _SCENARIOS[scenario_id]["title"],
        "description": _SCENARIOS[scenario_id]["description"],
        "steps": [
            "Read the launched ball into the central lane.",
            "Meet it and shoot toward the marked goal target.",
            "Score after your own fresh contact; retry resets the whole situation.",
        ],
        "planned_total": PLANNED_TOTAL,
        "implemented_total": len(IMPLEMENTED_SCENARIOS),
        "implemented_scenarios": list(IMPLEMENTED_SCENARIOS),
        "difficulty": difficulty,
        "rank_title": _RANK_TITLES[difficulty],
        "execution": execution,
        "roles": {**bot_roles, "human": human_index},
        "teams": {**{role: 1 for role in bot_roles}, "human": 0},
        "starting_state": {"car": human, "ball": launch, "bots": bots},
        "settle_state": {"car": deepcopy(human), "ball": parked_ball, "bots": deepcopy(bots)},
        "receiving_lane": list(_SCENARIOS[scenario_id]["lane"]),
        "arrival_seconds": arrival_seconds,
        "shot_window_seconds": timeout - arrival_seconds,
        "targets": [{"type": "goal", **deepcopy(_GOAL),
                     "center_x": data["target"][0], "half_width": data["target"][1]}],
        "success_events": ["launch_observed", "human_touch", "goal_target"],
        "timeout": timeout,
        "pressure": pressure,
        "reference_status": "No validated teaching demonstration is bundled.",
        "provenance": "unapproved functional prototype; owner playtesting required",
    }


def _role_descriptor(definition, role):
    pressure = definition["pressure"]
    return {
        "name": "Scenario Keeper" if role == "keeper" else "Scenario Defender",
        "team": 1, "role": role,
        "level": pressure[f"{role}_level"],
        "difficulty": pressure[f"{role}_difficulty"], "seed": 23 if role == "keeper" else 29,
        "loadout": {"car_id": 23, "primary_color": 12, "secondary_color": 0},
    }


def scenario_descriptors(request):
    if not isinstance(request, dict):
        raise ValueError("A scenario request mapping is required.")
    if request.get("capture") is not None or request.get("capture_profile") is not None:
        raise ValueError("Reference capture cannot run a ball-launch scenario.")
    definition = scenario_definition(
        request.get("lesson_id"), request.get("scenario_id"), request.get("difficulty", "gold")
    )
    return {
        index: _role_descriptor(definition, role)
        for role, index in definition["roles"].items() if role != "human"
    }


def scenario_actor_controllers(definition):
    if not isinstance(definition, dict) or definition.get("lesson_id") != LESSON_ID:
        raise ValueError("A validated scenario definition is required.")
    result = {}
    if "keeper" in definition["roles"]:
        result[definition["roles"]["keeper"]] = ScenarioKeeperController(definition)
    if "defender" in definition["roles"]:
        result[definition["roles"]["defender"]] = ScenarioDefenderController(definition)
    return result


class ScenarioKeeperController:
    """Bias the scenario keeper toward goal and actively guard the receiving lane."""

    def __init__(self, definition):
        pressure = definition["pressure"]
        self.level = pressure["keeper_level"]
        self.difficulty = pressure["keeper_difficulty"]
        self.ground_only = definition["difficulty"] in {"gold", "platinum"}
        self.parameters = {
            "speed_limit": pressure["keeper_speed_limit"],
            "reaction_interval": pressure["keeper_reaction_delay"],
        }
        self.reaction_delay = pressure["keeper_reaction_delay"]
        self.lane_limit_y = pressure["keeper_lane_limit_y"]
        self.home = tuple(definition["starting_state"]["bots"][0]["position"])
        self.delegate = SpecialistController("keeper", self.level, self.difficulty, seed=23)
        self.delegate.parameters.update(self.parameters)
        self.started_at = None
        self.intent = None
        self.last_decision = None

    def reset(self):
        self.delegate.reset()
        self.started_at = None
        self.intent = None
        self.last_decision = None

    def step(self, frame, player_index, intents=None):
        now = frame.get("time", 0.0)
        if self.started_at is None:
            self.started_at = now
        car = next((
            item for item in frame.get("cars", [])
            if isinstance(item, dict) and item.get("index") == player_index
        ), None)
        if not car:
            return _neutral()
        if not all(_finite3(car.get(field)) for field in ("position", "velocity", "rotation")):
            self.intent = {
                "player_index": player_index,
                "team": car.get("team", 1),
                "time": now,
                "kind": "unavailable",
                "reason": "keeper pose telemetry unavailable",
            }
            self.last_decision = dict(self.intent)
            return _neutral()
        if now - self.started_at < self.reaction_delay:
            return _neutral()
        controls = self.delegate.step(frame, player_index, intents)
        outward_speed = max(0.0, -car["velocity"][1])
        stopping_margin = max(120.0, min(650.0, outward_speed * 0.5))
        if car["position"][1] - self.lane_limit_y <= stopping_margin:
            perception = perceive(frame, player_index, self.delegate.parameters)
            decision = Decision(
                "support", self.home, self.home, 0.0, 0.0,
                "Scenario boundary guard returns the keeper toward goal",
            )
            controls = execute(perception, decision, self.delegate.parameters)
            controls.update(boost=False, jump=False)
            self.last_decision = {**decision.as_dict(), "boundary_override": "return_to_goal"}
            self.intent = {
                **(self.delegate.intent or {}),
                **self.last_decision,
                "player_index": player_index,
                "team": car.get("team", 1),
                "time": now,
            }
        else:
            self.intent = self.delegate.intent
            self.last_decision = self.delegate.last_decision
        if self.ground_only:
            controls.update(boost=False, jump=False)
        return controls


class ScenarioDefenderController:
    """Wait behind the keeper-first ranks, then close the shooting lane."""

    def __init__(self, definition):
        pressure = definition["pressure"]
        self.level = pressure["defender_level"]
        self.difficulty = pressure["defender_difficulty"]
        self.reaction_delay = pressure["defender_reaction_delay"]
        self.delegate = SpecialistController("defender", self.level, self.difficulty, seed=29)
        self.delegate.parameters["speed_limit"] = pressure["defender_speed_limit"]
        self.started_at = None
        self.intent = None
        self.last_decision = None

    def reset(self):
        self.delegate.reset()
        self.started_at = None
        self.intent = None
        self.last_decision = None

    def step(self, frame, player_index, intents=None):
        now = frame.get("time", 0.0)
        if self.started_at is None:
            self.started_at = now
        car = next((
            item for item in frame.get("cars", [])
            if isinstance(item, dict) and item.get("index") == player_index
        ), None)
        if not car:
            return _neutral()
        if not all(_finite3(car.get(field)) for field in ("position", "velocity", "rotation")):
            self.intent = {
                "player_index": player_index,
                "team": car.get("team", 1),
                "time": now,
                "kind": "unavailable",
                "reason": "defender pose telemetry unavailable",
            }
            self.last_decision = dict(self.intent)
            return _neutral()
        if now - self.started_at < self.reaction_delay:
            return _neutral()
        controls = self.delegate.step(frame, player_index, intents)
        self.intent = self.delegate.intent
        self.last_decision = self.delegate.last_decision
        return controls


def _finite3(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(item)
            for item in value
        )
    )


def _neutral():
    return {
        "throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
        "jump": False, "boost": False, "handbrake": False,
    }
