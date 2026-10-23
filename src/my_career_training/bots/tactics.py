"""Role preferences select real, inspectable intents; safety overrides the role."""
from dataclasses import dataclass
from .physics import Vec, clamp, distance, vec

# Scores multiply tactical opportunities, rather than changing car physics.
ROLE_WEIGHTS = {
    "keeper": {"save": 1.4, "clear": 1.1, "pass": .65, "shot": .45, "support": 1.3},
    "defender": {"save": 1.2, "clear": 1.4, "pass": .9, "shot": .7, "support": 1.15},
    "passer": {"save": 1., "clear": .9, "pass": 1.65, "shot": .95, "support": 1.1},
    "attacker": {"save": .9, "clear": .8, "pass": .85, "shot": 1.55, "support": .9},
    "all-rounder": {"save": 1.05, "clear": 1., "pass": 1., "shot": 1.05, "support": 1.},
}
COMMIT_KINDS = {"save", "clear", "pass", "shot"}


@dataclass(frozen=True)
class Decision:
    kind: str
    target: Vec
    aim: Vec
    eta: float
    score: float
    reason: str

    def as_dict(self):
        return {"kind": self.kind, "target": list(self.target), "aim": list(self.aim),
                "eta": self.eta, "score": round(self.score, 4), "reason": self.reason}


def _intent_items(intents):
    if isinstance(intents, dict):
        return intents.items()
    return ((i.get("player_index", i.get("index", -1)), i) for i in (intents or ()))


def choose(perception, role, parameters, intents=None):
    p, w = perception, ROLE_WEIGHTS[role]
    car, ball, sign = p.car, p.ball, p.attack_sign
    position = vec(car.get("position"))
    intercept = p.intercept
    if not car.get("wheel_contact", True) or abs(vec(car.get("rotation"))[2]) > 1.35:
        return Decision("recovery", position, ball, 0, 100, "Restore wheel contact and upright orientation")

    teammates = [c for c in p.cars if c.get("team") == car.get("team") and c.get("index") != car.get("index")]
    other_committer = False
    for index, intent in _intent_items(intents):
        try:
            teammate = next((c for c in teammates if c.get("index") == int(index)), None)
        except (TypeError, ValueError):
            continue
        if teammate and isinstance(intent, dict) and intent.get("kind") in COMMIT_KINDS:
            if p.time - float(intent.get("time", p.time)) > .65:
                continue
            eta = float(intent.get("eta", 99))
            # Index breaks ties so two equal bots do not yield simultaneously.
            if eta + .12 < intercept.eta or (abs(eta - intercept.eta) < .12 and int(index) < car["index"]):
                other_committer = True

    # Includes the human: observed motion/proximity matters, no cooperation assumed.
    closer_teammate = any(distance(vec(c.get("position")), ball) + 550 < distance(position, ball)
                           and distance(vec(c.get("position")), ball) < 1800 for c in teammates)
    yield_commit = other_committer or closer_teammate
    commitment = .24 if yield_commit else 1.
    behind_ball = position[1] * sign < ball[1] * sign + 200
    forward_ball = ball[1] * sign
    reachable = 1. if intercept.reachable else .42

    # Support lies on the goal side of the ball and away from the active lane.
    depth = {"keeper": 2150, "defender": 1600, "passer": 1100, "attacker": 700, "all-rounder": 1300}[role]
    support_y = clamp(ball[1] - sign * depth, -4550, 4550)
    lane = (-1 if ball[0] > 0 else 1) if abs(ball[0]) > 1400 else (-1 if car["index"] % 2 else 1)
    support = (clamp(ball[0] * .28 + lane * 850, -2900, 2900), support_y, 17)
    choices = [Decision("support", support, ball, 0,
                        w["support"] * (.52 + p.danger * .34 + (.8 if yield_commit else 0)),
                        "Rotate goal-side and leave the active teammate a clear lane")]

    # Aim through the ball from a point behind it. Driving later switches from
    # approach to contact when aligned, avoiding continuous ball orbiting.
    if not yield_commit or p.danger > .86:
        shot_open = 1.0
        for opponent in p.cars:
            op = vec(opponent.get("position"))
            if opponent.get("team") != car.get("team") and abs(op[0]) < 1000 and op[1] * sign > forward_ball + 300:
                shot_open = .60
        choices.append(Decision("shot", intercept.position, p.enemy_goal, intercept.eta,
                                w["shot"] * (.72 + .24 * shot_open + max(0, forward_ball) / 12000)
                                * reachable * commitment * (1 if behind_ball else .42),
                                "Approach behind the predicted ball and shoot at goal"))
        if forward_ball < 1200:
            clear_side = 1 if ball[0] >= 0 else -1
            clear_aim = (clear_side * 3200, clamp(ball[1] + sign * 3000, -4000, 4000), 100)
            choices.append(Decision("clear", intercept.position, clear_aim, intercept.eta,
                                    w["clear"] * (.46 + .90 * p.danger) * reachable * commitment,
                                    "Clear pressure toward the side rather than across our goal"))
        if p.danger > .32:
            # Ball moving toward goal: target a reachable prediction, otherwise
            # cover its projected goal-mouth x rather than chasing behind it.
            save_target = intercept.position if intercept.reachable else (
                clamp(ball[0] + p.ball_velocity[0] * .5, -850, 850), -sign * 4850, 17)
            choices.append(Decision("save", save_target, (ball[0] * 1.5, 0, 100), intercept.eta,
                                    w["save"] * (1.0 + 2.5 * p.danger) * (1 if p.danger > .86 else commitment),
                                    "Protect the goal mouth from a goalward ball"))

        # A useful pass needs a forward teammate, enough separation and a
        # reasonably open lane. Higher levels inspect more passing options.
        options = sorted(teammates, key=lambda c: vec(c.get("position"))[1] * sign, reverse=True)
        for mate in options[:parameters["pass_options"]]:
            mate_pos = vec(mate.get("position"))
            separation = distance(mate_pos, ball)
            if not (650 < separation < parameters["pass_range"] and mate_pos[1] * sign > forward_ball + 150):
                continue
            aim = (clamp(mate_pos[0] + vec(mate.get("velocity"))[0] * .35, -3500, 3500),
                   clamp(mate_pos[1] + vec(mate.get("velocity"))[1] * .35, -4700, 4700), 100)
            lane_blocked = False
            for opponent in p.cars:
                if opponent.get("team") == car.get("team"):
                    continue
                op = vec(opponent.get("position"))
                dx, dy = aim[0] - ball[0], aim[1] - ball[1]
                u = clamp(((op[0]-ball[0])*dx + (op[1]-ball[1])*dy) / max(1, dx*dx+dy*dy), 0, 1)
                if .1 < u < .9 and distance(op, (ball[0]+u*dx, ball[1]+u*dy, 0)) < 500:
                    lane_blocked = True
            if not lane_blocked:
                choices.append(Decision("pass", intercept.position, aim, intercept.eta,
                                        w["pass"] * .95 * reachable * commitment * (1 if behind_ball else .5),
                                        "Lead a forward teammate through an open passing lane"))

    # Pads only when leaving the ball will not expose the goal or steal an
    # active commitment; actual boost always comes from the game's pickup.
    if car.get("boost", 0) < parameters["boost_threshold"] and p.danger < .25:
        for pad in p.boosts:
            pos = vec(pad.get("position"))
            if pad.get("active", False) and distance(position, pos) < 2300 and pos[1] * sign < forward_ball + 400:
                score = .85 + (parameters["boost_threshold"] - car.get("boost", 0)) / 100
                score -= distance(position, pos) / 9000
                if yield_commit:
                    score += .6
                choices.append(Decision("boost", pos, ball, 0, score, "Collect an active pad on the rotation route"))
    return max(choices, key=lambda c: c.score)
