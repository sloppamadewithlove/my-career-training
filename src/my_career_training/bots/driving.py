"""Ordinary bounded car controls for the experimental ground specialist."""
import math
from .physics import clamp, distance, vec


def neutral():
    return {"throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0,
            "roll": 0.0, "jump": False, "boost": False, "handbrake": False}


def execute(perception, decision, parameters, aim_error=0.0, jump_started=None):
    p = perception
    controls = neutral()
    position = vec(p.car.get("position"))
    pitch, yaw, roll = vec(p.car.get("rotation"))
    if decision.kind == "recovery":
        gain = parameters["recovery_gain"]
        controls.update(throttle=1.0, pitch=clamp(-pitch * gain), roll=clamp(-roll * gain))
        # Wheel contact is false while turtling too. Use low height and low
        # vertical velocity to distinguish a resting upside-down car from an
        # airborne car, and release jump between attempts via the shared guard.
        turtling = position[2] < 90 and abs(vec(p.car.get("velocity"))[2]) < 120 and abs(roll) > 1.35
        controls["jump"] = bool(jump_started is not None and 0 <= p.time - jump_started < .12
                                or turtling and jump_started is None)
        return controls

    target = decision.target
    if decision.kind in {"shot", "pass", "clear"}:
        dx, dy = decision.aim[0] - target[0], decision.aim[1] - target[1]
        magnitude = max(1.0, math.hypot(dx, dy))
        approach = (target[0] - dx / magnitude * 260, target[1] - dy / magnitude * 260, target[2])
        alignment = ((target[0] - position[0]) * dx + (target[1] - position[1]) * dy) / magnitude
        lateral = abs((target[0] - position[0]) * dy - (target[1] - position[1]) * dx) / magnitude
        if alignment < 0 or lateral > 190:
            target = approach
        else:
            target = (target[0] + dx / magnitude * 110, target[1] + dy / magnitude * 110, target[2])
    target = (target[0] + aim_error, target[1], target[2])
    heading = math.atan2(target[1] - position[1], target[0] - position[0])
    angle = math.atan2(math.sin(heading - yaw), math.cos(heading - yaw))
    speed = math.hypot(*vec(p.car.get("velocity"))[:2])
    remaining = distance(position, target)
    desired_speed = parameters["speed_limit"] * (1 - min(.75, abs(angle) / 3.3))
    if decision.kind in {"support", "boost"}:
        desired_speed = min(desired_speed, max(0, remaining * 2.3))
    throttle = clamp((desired_speed - speed) / 450)
    if abs(angle) > 2.45 and remaining < 650:
        throttle = -.6
        angle = math.atan2(math.sin(angle + math.pi), math.cos(angle + math.pi))
        controls["steer"] = clamp(-angle * parameters["steer_gain"])
    else:
        controls["steer"] = clamp(angle * parameters["steer_gain"])
    controls["throttle"] = throttle
    controls["handbrake"] = bool(abs(angle) > 1.45 and speed > 650)
    controls["boost"] = bool(throttle > .9 and abs(angle) < .17 and speed < parameters["speed_limit"] - 80
                             and remaining > 900 and p.car.get("boost", 0) > 0)
    # A short single-jump intercept. No aerial ability or flip reset is claimed.
    ball_distance = distance(position, decision.target)
    jump_window = jump_started is not None and 0 <= p.time - jump_started < .12
    trigger_jump = (decision.kind in {"save", "shot", "pass", "clear"} and ball_distance < 320
                    and 145 < decision.target[2] < 330 and abs(angle) < .35
                    and p.car.get("wheel_contact", True))
    controls["jump"] = bool(jump_window or trigger_jump and jump_started is None)
    return controls
