"""Optional, bounded review of observed offline match telemetry.

Score observations are authoritative scoreboard changes, not inferred scorers or
causes. The two positioning checks are explicitly coaching heuristics. No skill
rating, perfect move, outcome attribution, or progress gate is produced here.
"""
from copy import deepcopy
import math


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _position(car, key="position"):
    value = car.get(key) if isinstance(car, dict) else None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    result = [_number(v) for v in value]
    return tuple(result) if all(v is not None for v in result) else None


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _approach(car, ball):
    position, velocity = _position(car), _position(car, "velocity")
    if position is None or velocity is None:
        return None
    distance = _distance(position, ball)
    if distance < 1:
        return 0
    return ((ball[0] - position[0]) * velocity[0] + (ball[1] - position[1]) * velocity[1]) / distance


def _xyz(position):
    return "(" + ", ".join(str(round(v)) for v in position) + ")"


def _scores(scores):
    if isinstance(scores, dict):
        values = [scores.get(i, scores.get(str(i))) for i in (0, 1)]
    elif isinstance(scores, (list, tuple)) and len(scores) == 2:
        values = scores
    else:
        return None
    result = [_number(v) for v in values]
    if any(v is None or v < 0 or not v.is_integer() for v in result):
        return None
    return tuple(int(v) for v in result)


def bounded_summary(value):
    """Keep optional display data bounded; absent/bad notes never lose a score."""
    if not isinstance(value, list):
        return []
    result = []
    for moment in value[:12]:
        if not isinstance(moment, dict):
            continue
        stamp = _number(moment.get("time"))
        if stamp is None or stamp < 0 or any(not isinstance(moment.get(key), str)
                for key in ("title", "evidence", "suggestion", "kind")):
            continue
        result.append({"time": stamp, "title": moment["title"][:160],
                       "evidence": moment["evidence"][:1500], "suggestion": moment["suggestion"][:600],
                       "kind": moment["kind"][:40]})
    return result


class MatchReview:
    """Collect a maximum of twelve useful moments without retaining packets.

    ``frame.car`` is the human when present. Otherwise provide ``human_index`` or
    a roster containing exactly one explicit ``is_bot=False`` car. Coordinates
    are Rocket League units; team zero defends negative Y. ``scores`` is the
    observed [blue, orange] pair or a map keyed by team index.
    """

    def __init__(self, human_index=None, max_moments=12):
        self.human_index = human_index
        self.max_moments = max(1, min(12, int(max_moments)))
        self._moments = []
        self._score = None
        self._last_touch = None
        self._last_time = None
        self._last_events = {}
        self._sustained = {}

    def _add(self, time, title, evidence, suggestion, kind, priority):
        moment = {"time": round(time, 3), "title": title, "evidence": evidence,
                  "suggestion": suggestion, "kind": kind}
        self._moments.append((priority, moment))
        if len(self._moments) > self.max_moments:
            # Retain goals before low-priority touches; among equal priorities,
            # replace the oldest moment. Neither packets nor histories grow.
            remove = min(range(len(self._moments)), key=lambda i: (self._moments[i][0], i))
            self._moments.pop(remove)
        self._last_events[kind] = time

    def _human(self, frame):
        cars = frame.get("cars", [])
        if isinstance(frame.get("car"), dict):
            return frame["car"]
        if self.human_index is not None:
            return next((c for c in cars if c.get("index", c.get("player_index")) == self.human_index), None)
        humans = [c for c in cars if c.get("is_bot") is False]
        return humans[0] if len(humans) == 1 else None

    def _ready(self, kind, condition, time, continuous):
        if not condition or not continuous:
            self._sustained.pop(kind, None)
            return False
        since = self._sustained.setdefault(kind, time)
        return time - since >= .30 and time - self._last_events.get(kind, -math.inf) >= 15

    def update(self, frame, scores=None):
        """Observe one normalized frame; missing evidence never creates a flag."""
        if not isinstance(frame, dict):
            return
        time = _number(frame.get("time"))
        if time is None or time < 0:
            return
        if self._last_time is not None and time < self._last_time:
            # A game-clock reset invalidates temporal comparisons. Preserve
            # already observed moments but do not turn a reset into a goal.
            self._score = None
            self._last_touch = None
            self._sustained.clear()
            self._last_events.clear()
        continuous = (self._last_time is not None and 0 < time - self._last_time <= .25
                      and not frame.get("packet_gap", False))
        self._last_time = time
        observed = _scores(scores)
        if observed is not None:
            if self._score is not None and all(observed[i] >= self._score[i] for i in (0, 1)):
                changes = [(i, observed[i] - self._score[i]) for i in (0, 1) if observed[i] != self._score[i]]
                if changes:
                    label = "; ".join(f"{'Blue' if team == 0 else 'Orange'} +{delta}" for team, delta in changes)
                    self._add(time, f"Score changed: {label}",
                              f"Observed scoreboard changed from {self._score[0]}–{self._score[1]} "
                              f"to {observed[0]}–{observed[1]}. This establishes the score change, not its cause.",
                              "", "score", 3)
            self._score = observed

        human = self._human(frame)
        if not human:
            self._sustained.clear()
            return
        touch = human.get("latest_touch")
        if isinstance(touch, dict):
            touch_time = _number(touch.get("game_seconds", touch.get("time")))
            touch_position = _position(touch)
            if (touch_time is not None and 0 <= time - touch_time <= .35
                    and touch_time != self._last_touch):
                if time - self._last_events.get("touch", -math.inf) >= 8:
                    location = f" at {_xyz(touch_position)}" if touch_position is not None else ""
                    self._add(touch_time, "Your ball contact",
                              f"The human player's latest_touch reports ball contact at {touch_time:.2f}s{location}. "
                              "Contact alone does not establish the quality or outcome of the play.",
                              "", "touch", 1)
                self._last_touch = touch_time

        cars = frame.get("cars", [])
        ball = _position(frame.get("ball"))
        position = _position(human)
        team = human.get("team")
        if (ball is None or position is None or team not in (0, 1) or not isinstance(cars, list)
                or len(cars) < 2 or any(not isinstance(c, dict) or _position(c) is None
                                      or c.get("team") not in (0, 1) for c in cars)):
            self._sustained.clear()
            return
        team_cars = [c for c in cars if c.get("team") == team]
        opponents = [c for c in cars if c.get("team") in (0, 1) and c.get("team") != team]
        sign = 1 if team == 0 else -1
        near = [c for c in team_cars if _distance(_position(c), ball) < 650
                and (_approach(c, ball) or 0) > 250]
        cover = [c for c in team_cars if _position(c)[1] * sign < ball[1] * sign - 1000
                 and abs(_position(c)[0]) < 2500]
        double_commit = (len(near) >= 2 and not cover and ball[1] * sign < -600
                         and ball[2] < 350 and len(opponents) > 0)
        if self._ready("double_commit", double_commit, time, continuous):
            details = "; ".join(f"player {c.get('index', c.get('player_index', '?'))} at {_xyz(_position(c))}"
                                for c in near[:4])
            self._add(time, "Likely double commit · coaching suggestion",
                      f"For at least 0.30s, {len(near)} teammates approached within 650 units of the ball "
                      f"at {_xyz(ball)} in your defensive half; {details}. No observed teammate was at least "
                      "1,000 units goal-side in the central cover area. This is a positioning heuristic, not a cause of any goal.",
                      "Consider leaving one teammate to challenge while another rotates goal-side.",
                      "double_commit", 2)

        boost = _number(human.get("boost"))
        approach = _approach(human, ball)
        opponent_near = any(_distance(_position(c), ball) < 1000 for c in opponents)
        empty_challenge = (boost is not None and boost <= 0 and approach is not None and approach > 400
                           and 250 < _distance(position, ball) < 1050 and opponent_near and ball[2] < 350)
        if self._ready("empty_boost", empty_challenge, time, continuous):
            self._add(time, "Empty boost near a contested ball · coaching suggestion",
                      f"For at least 0.30s, your car at {_xyz(position)} approached the ball at {_xyz(ball)} "
                      f"with reported boost {boost:g} and closing speed {approach:.0f} units/s. "
                      "An opponent was within 1,000 units of the ball. This does not establish that challenging was wrong.",
                      "For the next approach, consider a pad on your route or rotating behind a teammate if you need boost.",
                      "empty_boost", 2)

    def summary(self):
        """Return independent JSON-compatible records, in game-time order."""
        return deepcopy(sorted((moment for _, moment in self._moments), key=lambda m: m["time"]))
