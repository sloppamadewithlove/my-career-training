"""A controller drawing model from observed game actions, never a hardware input hook.

Rocket League exposes logical actions after the player's bindings. Mapping those
actions to a PlayStation drawing is a configurable explanation, not physical
button capture. Missing telemetry must remain visibly unavailable.
"""

from copy import deepcopy
import math

from .recordings import ACTION_KEYS

PLAYSTATION_BINDINGS = {
    "throttle": "r2", "reverse": "l2", "steer": "left_stick_x",
    "pitch": "left_stick_y", "yaw": "left_stick_x", "roll": "left_stick_x",
    "jump": "cross", "boost": "circle", "handbrake": "square",
}
BUTTONS = ("cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "l3", "r3")
AXES = ("left_stick_x", "left_stick_y", "right_stick_x", "right_stick_y")
BUTTON_LABELS = {
    "cross": "Cross", "circle": "Circle", "square": "Square", "triangle": "Triangle",
    "l1": "L1", "r1": "R1", "l2": "L2", "r2": "R2", "l3": "L3", "r3": "R3",
}
ACTION_LABELS = {
    "throttle": "Accelerate", "reverse": "Reverse", "steer": "Steer", "pitch": "Pitch",
    "yaw": "Yaw", "roll": "Air roll", "jump": "Jump", "boost": "Boost", "handbrake": "Powerslide",
}


def controller_bindings(values=None):
    """Merge the player's display mappings; gameplay bindings remain in the game."""
    if values is not None and not isinstance(values, dict):
        raise ValueError("Controller display bindings must be an action-to-control object.")
    result = deepcopy(PLAYSTATION_BINDINGS)
    for action, control in (values or {}).items():
        if action not in result or control not in BUTTONS + AXES:
            raise ValueError("Choose a supported logical action and PlayStation control.")
        result[action] = control
    return result


def controller_display(actions=None, bindings=None, *, observed=True, source="live"):
    """Serializable drawing state. It never provides PlayerInput or set-state events."""
    if source not in ("live", "ghost"):
        raise ValueError("Controller source must be live or ghost.")
    bindings = controller_bindings(bindings)
    observed = observed is True and isinstance(actions, dict)
    if observed:
        for key in ACTION_KEYS:
            value = actions.get(key)
            if key in ("jump", "boost", "handbrake"):
                valid = isinstance(value, bool)
            else:
                valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
                         and math.isfinite(value) and -1 <= value <= 1)
            if not valid:
                observed = False
                break
    logical = {key: actions[key] for key in ACTION_KEYS} if observed else None
    controls = {key: 0.0 if observed else None for key in BUTTONS + AXES}
    labels = []
    if observed:
        values = {**logical, "throttle": max(0.0, logical["throttle"]),
                  "reverse": max(0.0, -logical["throttle"])}
        for action, control in bindings.items():
            value = float(values[action])
            if control in BUTTONS:
                controls[control] = max(controls[control], abs(value))
            elif abs(value) > abs(controls[control]):
                # Several logical axes may share a physical display axis. Avoid
                # summing them into a fictional stick position.
                controls[control] = value
            if abs(value) > 0.05:
                labels.append({"action": action, "label": ACTION_LABELS[action],
                               "control": control, "value": value})
    return {
        "layout": "playstation", "source": source, "observed": observed,
        "capture": "logical_game_actions", "physical_button_capture": False,
        "label": ("Recorded coach actions" if source == "ghost" else "Your game actions")
                 if observed else "Controller actions unavailable",
        "binding_note": "Display mappings are configurable; these are observed game actions, not raw button capture.",
        "bindings": bindings, "actions": logical, "controls": controls,
        "buttons": [{"id": key, "label": BUTTON_LABELS[key], "value": controls[key]}
                    for key in BUTTONS],
        "sticks": {"left": {"x": controls["left_stick_x"], "y": controls["left_stick_y"]},
                   "right": {"x": controls["right_stick_x"], "y": controls["right_stick_y"]}},
        "active_actions": labels,
    }
