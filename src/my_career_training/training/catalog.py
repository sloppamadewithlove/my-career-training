"""Original built-in arena drills. Targets are training choices, not universal technique limits."""

from copy import deepcopy

ASSISTANCE_DEFAULTS = {
    "ghost": True,
    "explanations": True,
    "actions": True,
    "timing": True,
    "auto_reset": True,
    "playback_speed": 1.0,
}


def assistance_preferences(values=None):
    result = deepcopy(ASSISTANCE_DEFAULTS)
    for key, value in (values or {}).items():
        if key not in result:
            raise ValueError(f"Unknown lesson help setting: {key}")
        if key == "playback_speed":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value not in (0.25, 0.5, 0.75, 1.0)
            ):
                raise ValueError("Demonstration speed must be ¼, ½, ¾, or normal speed.")
        elif not isinstance(value, bool):
            raise ValueError(f"{key} must be on or off.")
        result[key] = value
    return result


def _state(car=(0, -2500, 17.01), ball=(0, 0, 93.15), ball_velocity=(0, 0, 0)):
    return {
        "car": {
            "position": list(car),
            "rotation": [0, 1.5707963267948966, 0],
            "velocity": [0, 0, 0],
            "angular_velocity": [0, 0, 0],
            "boost": 100,
        },
        "ball": {
            "position": list(ball),
            "rotation": [0, 0, 0],
            "velocity": list(ball_velocity),
            "angular_velocity": [0, 0, 0],
        },
        "game_speed": 1.0,
    }


def _lesson(id, title, description, steps, starting_state, targets, success_events, timeout=15):
    settle = _state(car=starting_state["car"]["position"], ball=(3000, 0, 93.15))
    return {
        "id": id,
        "version": 1,
        "title": title,
        "description": description,
        "map": "DFHStadium",
        "required_capabilities": ["state_setting", "human_actions", "telemetry"],
        "starting_state": starting_state,
        "settle_state": settle,
        "reset_conditions": {"grounded_seconds": 0.25, "position_tolerance": 60, "max_speed": 25},
        "steps": steps,
        "targets": targets,
        "success_events": success_events,
        "feedback_rules": {
            "precision": "Observed packet brackets; gaps reduce confidence.",
            "technique": "Outcome and technique evidence are assessed separately.",
        },
        "timeout": timeout,
        "reference_recordings": [],
        "reference_status": "Real successful demonstration required; none bundled.",
        "assistance_defaults": deepcopy(ASSISTANCE_DEFAULTS),
    }


_LESSONS = [
    _lesson(
        "speed-flip",
        "Speed flip",
        "Speed flip through the green FINISH rectangle, then recover on your wheels. The rectangle is the target, not a ghost.",
        [
            "Accelerate and boost toward the green FINISH rectangle.",
            "Jump, release Jump, then jump again with diagonal direction to dodge.",
            "Reverse pitch after the dodge; cross FINISH and recover on your wheels.",
        ],
        _state(),
        [{"type": "plane", "axis": 1, "value": 0, "width": 1000, "height": 300,
          "label": "FINISH", "purpose": "Cross this green rectangle, then land on your wheels."}],
        ["target_crossed", "landed"],
        10,
    ),
    _lesson(
        "flip-reset",
        "Flip reset",
        "Meet the raised ball with your underside and observe a newly gained flip.",
        [
            "Jump and approach the raised ball.",
            "Use your initial flip before attempting acquisition.",
            "Turn your wheels toward the ball; use the gained flip if you can.",
        ],
        _state(car=(0, -650, 17.01), ball=(0, 250, 950), ball_velocity=(0, -40, 150)),
        [{"type": "ball_reset", "minimum_height": 300, "central_space": 2800}],
        ["reset_acquired"],
        12,
    ),
    _lesson(
        "dribble-flick",
        "Ground dribble & flick",
        "Carry the ball through a controlled zone, then flick toward goal.",
        ["Catch the ball on the roof.", "Keep it in the carry zone.", "Flick toward the target."],
        _state(car=(0, -1800, 17.01), ball=(0, -1690, 160)),
        [
            {"type": "carry", "seconds": 2.0, "forward": 160, "side": 110, "height": [80, 220]},
            {"type": "goal", "center_x": 0, "half_width": 700, "min_z": 93, "max_z": 550},
        ],
        ["carry_sustained", "flick", "goal_target"],
        20,
    ),
    _lesson(
        "power-shots",
        "Power shots",
        "Meet a repeatable incoming ball and measure its outgoing speed.",
        ["Approach the incoming ball.", "Time your contact.", "Send it through the marked goal target."],
        _state(car=(0, -2200, 17.01), ball=(0, -200, 200), ball_velocity=(0, -700, 120)),
        [{"type": "goal", "center_x": 0, "half_width": 750, "min_z": 93, "max_z": 550}],
        ["ball_contact", "goal_target"],
        12,
    ),
    _lesson(
        "shot-placement",
        "Shot placement",
        "Choose a goal zone and place a shot inside it.",
        ["Aim for the marked zone.", "Strike the ball.", "Review where the ball crossed the goal plane."],
        _state(car=(-650, -2100, 17.01), ball=(-400, -900, 93.15)),
        [{"type": "goal", "center_x": 480, "half_width": 300, "min_z": 93, "max_z": 500}],
        ["ball_contact", "goal_target"],
        15,
    ),
    _lesson(
        "fast-aerial",
        "Fast aerial",
        "Reach the high target with two jumps and controlled boost.",
        [
            "Jump and pitch upward with boost.",
            "Release jump, then jump again without a backward dodge.",
            "Reach the aerial gate.",
        ],
        _state(car=(0, -1800, 17.01)),
        [{"type": "gate", "position": [0, -600, 850], "radius": 250}],
        ["gate_0"],
        12,
    ),
    _lesson(
        "aerial-air-roll",
        "Aerial & air-roll control",
        "Fly through ordered gates and recover; mirror the route for either side.",
        [
            "Take off toward the first gate.",
            "Use air roll to steer your orientation through each gate.",
            "Return to the floor on your wheels.",
        ],
        _state(car=(0, -2200, 17.01)),
        [
            {"type": "gate", "position": [0, -1000, 500], "radius": 300},
            {"type": "gate", "position": [700, 0, 850], "radius": 300},
            {"type": "gate", "position": [0, 1000, 500], "radius": 350},
        ],
        ["gate_0", "gate_1", "gate_2", "landed"],
        25,
    ),
    _lesson(
        "flight-recovery",
        "Fast flight & recovery",
        "Complete an airborne route and land with useful forward momentum.",
        [
            "Boost through the gates in order.",
            "Aim your wheels toward the floor.",
            "Land and continue driving in the recovery corridor.",
        ],
        _state(car=(0, -2500, 17.01)),
        [
            {"type": "gate", "position": [0, -1200, 500], "radius": 350},
            {"type": "gate", "position": [0, 1000, 800], "radius": 400},
            {"type": "recovery", "center_x": 0, "min_y": 1000, "max_y": 4200, "half_width": 1100},
        ],
        ["gate_0", "gate_1", "recovered"],
        25,
    ),
]


def catalog():
    return deepcopy(_LESSONS)


def lesson(lesson_id):
    for value in _LESSONS:
        if value["id"] == lesson_id:
            return deepcopy(value)
    raise ValueError(f"Unknown lesson: {lesson_id}")


def configure_lesson(lesson_id, *, side="right", target_zone=None, angle="center", simplified=False):
    """Select target/approach variations without changing physics or hiding the setup difference."""
    value = lesson(lesson_id)
    if side not in ("left", "right") or angle not in ("center", "left", "right"):
        raise ValueError("Choose a supported side and starting angle.")
    if side == "left":
        for target in value["targets"]:
            if "position" in target:
                target["position"][0] *= -1
    if angle != "center":
        value["starting_state"]["car"]["position"][0] = -900 if angle == "left" else 900
    if target_zone is not None:
        zones = {"left": (-480, 300), "center": (0, 300), "right": (480, 300), "whole": (0, 750)}
        if target_zone not in zones:
            raise ValueError("Choose left, center, right, or whole goal.")
        for target in value["targets"]:
            if target["type"] == "goal":
                target["center_x"], target["half_width"] = zones[target_zone]
    if simplified and lesson_id == "flip-reset":
        value["starting_state"]["car"]["position"][1] = -250
        value["starting_state"]["ball"]["position"] = [0, 150, 600]
        value["description"] += " Shortened approach setup; records are compared only with the same setup."
    value["settle_state"]["car"]["position"] = deepcopy(value["starting_state"]["car"]["position"])
    value["variant"] = {"side": side, "angle": angle, "target_zone": target_zone, "simplified": simplified}
    return value
