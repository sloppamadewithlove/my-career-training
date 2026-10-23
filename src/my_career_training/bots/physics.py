"""Conservative baseline perception in Rocket League's ordinary game units.

Predictions supplied by the game take precedence. The fallback is deliberately a
short ground-ball estimate, not an assertion of accurate arena collision physics.
"""
from dataclasses import dataclass
import math

Vec = tuple[float, float, float]


def clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


def vec(value, default=(0.0, 0.0, 0.0)) -> Vec:
    try:
        result = tuple(float(value[i]) for i in range(3))
        return result if all(math.isfinite(v) for v in result) else default
    except (TypeError, ValueError, IndexError, KeyError):
        return default


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass(frozen=True)
class Intercept:
    position: Vec
    eta: float
    reachable: bool


@dataclass(frozen=True)
class Perception:
    time: float
    car: dict
    cars: tuple
    ball: Vec
    ball_velocity: Vec
    attack_sign: int
    intercept: Intercept
    danger: float
    own_goal: Vec
    enemy_goal: Vec
    boosts: tuple


def travel_distance(car, seconds, speed_limit):
    """Estimate ordinary acceleration with a turn penalty; never grant boost."""
    speed = min(math.hypot(*vec(car.get("velocity"))[:2]), speed_limit)
    acceleration = 900.0 if float(car.get("boost", 0)) > 10 else 550.0
    to_limit = max(0.0, (speed_limit - speed) / acceleration)
    accelerating = min(seconds, to_limit)
    return (speed * accelerating + .5 * acceleration * accelerating**2
            + speed_limit * max(0.0, seconds - accelerating))


def reachable_intercept(frame, car, horizon, speed_limit, precision=0.1):
    now = float(frame.get("time", 0))
    ball = vec(frame.get("ball", {}).get("position"))
    velocity = vec(frame.get("ball", {}).get("velocity"))
    position = vec(car.get("position"))
    yaw = vec(car.get("rotation"))[1]
    samples = []
    for sample in frame.get("prediction", ()):
        eta = float(sample.get("time", now)) - now
        if 0.06 <= eta <= horizon:
            samples.append((eta, vec(sample.get("position"))))
    if not samples:
        # A floor bounce is enough for a safe fallback. Full game predictions are
        # necessary for reliable wall/aerial reads and remain clearly preferred.
        for n in range(1, int(horizon / precision) + 1):
            eta = n * precision
            z = ball[2] + velocity[2] * eta - 325.0 * eta * eta
            samples.append((eta, (clamp(ball[0] + velocity[0] * eta, -4000, 4000),
                                  clamp(ball[1] + velocity[1] * eta, -5100, 5100),
                                  max(93.0, z))))
    samples.sort(key=lambda s: s[0])
    for eta, point in samples:
        if point[2] > 330:  # No fictitious aerial reach in this baseline.
            continue
        heading = math.atan2(point[1] - position[1], point[0] - position[0])
        angle = abs(math.atan2(math.sin(heading - yaw), math.cos(heading - yaw)))
        travel_time = max(0.0, eta - angle * .19)
        if distance(position, point) <= travel_distance(car, travel_time, speed_limit) + 130:
            return Intercept(point, eta, True)
    # Last estimate is a positioning target, never falsely called reachable.
    low = [(t, p) for t, p in samples if p[2] <= 330]
    eta, point = (low or samples or [(0, ball)])[-1]
    return Intercept(point, eta, False)


def perceive(frame, player_index, parameters):
    cars = tuple(frame.get("cars", ()))
    car = next((c for c in cars if c.get("index") == player_index), None)
    if car is None:
        raise ValueError(f"No car with index {player_index} in the frame")
    sign = 1 if car.get("team", 0) == 0 else -1
    ball = vec(frame.get("ball", {}).get("position"))
    velocity = vec(frame.get("ball", {}).get("velocity"))
    relative_y = ball[1] * sign
    goalward_speed = max(0.0, -velocity[1] * sign)
    danger = clamp((-relative_y - 1200) / 3500, 0, 1)
    if abs(ball[0]) < 1300 and relative_y < -1900:
        danger = max(danger, clamp(goalward_speed / 1500, 0, 1))
    return Perception(float(frame.get("time", 0)), car, cars, ball, velocity, sign,
                      reachable_intercept(frame, car, parameters["prediction_horizon"],
                                          parameters["speed_limit"], parameters["prediction_step"]),
                      danger, (0, -sign * 5050, 17), (0, sign * 5120, 100),
                      tuple(frame.get("boosts", ())))
