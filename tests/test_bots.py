import copy
import math
import random
import unittest

from my_career_training.bots import SpecialistController, capability_parameters, provider_manifest
from my_career_training.bots.physics import reachable_intercept


def car(index=0, team=0, position=(0, -1800, 17), yaw=math.pi / 2, **extra):
    return dict(index=index, team=team, position=list(position), velocity=[0, 1000, 0],
                rotation=[0, yaw, 0], boost=70, wheel_contact=True, **extra)


def frame(ball=(0, 0, 93), velocity=(0, 0, 0), cars=None):
    return {"time": 10., "cars": cars or [car()],
            "ball": {"position": list(ball), "velocity": list(velocity)}, "boosts": []}


class BotTests(unittest.TestCase):
    def controller(self, role="all-rounder", **kwargs):
        return SpecialistController(role, level=10, difficulty=1, seed=4, **kwargs)

    def test_roles_make_different_choices_and_passes_are_real(self):
        f = frame(ball=(0, -600, 93), cars=[car(position=(0, -1800, 17)), car(1, position=(1600, 800, 17))])
        f["prediction"] = [{"time": 11, "position": [0, -600, 93]}]
        decisions = {}
        for role in ("keeper", "defender", "passer", "attacker", "all-rounder"):
            bot = self.controller(role)
            bot.step(f, 0)
            decisions[role] = bot.last_decision
        self.assertEqual(decisions["keeper"]["kind"], "support")
        self.assertEqual(decisions["passer"]["kind"], "pass")
        self.assertEqual(decisions["attacker"]["kind"], "shot")
        self.assertGreater(decisions["passer"]["aim"][0], 1000)

    def test_every_role_defends_an_emergency(self):
        f = frame((300, -4200, 120), (0, -1400, 0), [car(position=(0, -4700, 17))])
        for role in provider_manifest()["roles"]:
            bot = self.controller(role)
            bot.step(f, 0)
            self.assertEqual(bot.last_decision["kind"], "save", role)

    def test_defender_clears_sideways_under_pressure(self):
        f = frame((1300, -1500, 93), cars=[car(position=(1200, -2200, 17))])
        f["prediction"] = [{"time": 10.8, "position": [1300, -1500, 93]}]
        bot = self.controller("defender")
        bot.step(f, 0)
        self.assertEqual(bot.last_decision["kind"], "clear")
        self.assertGreater(bot.last_decision["aim"][0], 2500)

    def test_coordination_yields_but_stale_or_opponent_intents_do_not(self):
        f = frame(cars=[car(), car(1, position=(1000, -1600, 17)), car(2, team=1)])
        bot = self.controller("attacker")
        bot.step(f, 0, {1: {"kind": "shot", "eta": .1, "time": 10}})
        self.assertEqual(bot.last_decision["kind"], "support")
        for intents in ({1: {"kind": "shot", "eta": .1, "time": 8}}, {2: {"kind": "shot", "eta": .1, "time": 10}}):
            other = self.controller("attacker")
            other.step(f, 0, intents)
            self.assertEqual(other.last_decision["kind"], "shot")

    def test_human_near_ball_triggers_rotation_without_intent(self):
        bot = self.controller("attacker")
        bot.step(frame(cars=[car(), car(1, position=(100, -100, 17))]), 0)
        self.assertEqual(bot.last_decision["kind"], "support")

    def test_prediction_requires_reachability_and_rejects_aerial(self):
        f = frame()
        f["prediction"] = [{"time": 10.1, "position": [0, 2000, 93]},
                           {"time": 11., "position": [0, -1000, 700]},
                           {"time": 11.4, "position": [0, -800, 93]}]
        intercept = reachable_intercept(f, f["cars"][0], 3, 2250)
        self.assertTrue(intercept.reachable)
        self.assertEqual(intercept.position, (0., -800., 93.))
        self.assertAlmostEqual(intercept.eta, 1.4)
        f["prediction"] = [{"time": 10.1, "position": [4000, 4000, 93]}]
        self.assertFalse(reachable_intercept(f, f["cars"][0], 3, 2250).reachable)

    def test_levels_change_prediction_and_execution(self):
        low = capability_parameters(1, .5)
        high = capability_parameters(10, .5)
        self.assertGreater(high["prediction_horizon"], low["prediction_horizon"])
        self.assertLess(high["reaction_interval"], low["reaction_interval"])
        self.assertLess(high["aim_error"], low["aim_error"])
        self.assertGreater(high["pass_options"], low["pass_options"])
        self.assertGreater(high["recovery_gain"], low["recovery_gain"])
        f = frame(ball=(0, 0, 93), cars=[car(position=(0, -3000, 17))])
        f["cars"][0]["velocity"] = [0, 0, 0]
        f["prediction"] = [{"time": 12.7, "position": [0, 0, 93]}]
        slow = reachable_intercept(f, f["cars"][0], low["prediction_horizon"], low["speed_limit"])
        fast = reachable_intercept(f, f["cars"][0], high["prediction_horizon"], high["speed_limit"])
        self.assertFalse(slow.reachable)
        self.assertTrue(fast.reachable)

    def test_recovery_and_boost_collection(self):
        f = frame()
        f["cars"][0].update(wheel_contact=False, rotation=[.6, 0, -.8])
        bot = self.controller()
        controls = bot.step(f, 0)
        self.assertEqual(bot.last_decision["kind"], "recovery")
        self.assertLess(controls["pitch"], 0)
        self.assertGreater(controls["roll"], 0)
        self.assertFalse(controls["boost"])
        f = frame(ball=(0, 2500, 93), cars=[car(), car(1, position=(0, 2300, 17))])
        f["cars"][0]["boost"] = 0
        f["boosts"] = [{"position": [100, -1500, 0], "active": True, "is_full": False}]
        bot.reset()
        bot.step(f, 0)
        self.assertEqual(bot.last_decision["kind"], "boost")

    def test_seed_is_repeatable_and_input_not_mutated(self):
        f = frame()
        original = copy.deepcopy(f)
        a, b = self.controller(), self.controller()
        for time in (10, 10.05, 10.5, 11):
            f["time"] = time
            self.assertEqual(a.step(f, 0), b.step(f, 0))
        f["time"] = original["time"]
        self.assertEqual(f, original)
        a.reset()
        self.assertEqual(a.step(f, 0), self.controller().step(f, 0))

    def test_turtle_recovery_releases_jump_between_attempts(self):
        bot = self.controller()
        f = frame()
        f["cars"][0].update(wheel_contact=False, rotation=[0, 0, 3.0])
        self.assertTrue(bot.step(f, 0)["jump"])
        f["time"] += .18
        self.assertFalse(bot.step(f, 0)["jump"])
        f["time"] += .5
        self.assertTrue(bot.step(f, 0)["jump"])

    def test_orange_team_rotates_in_the_right_direction(self):
        bot = self.controller("keeper")
        bot.step(frame((100, 0, 93), cars=[car(team=1, position=(0, 1800, 17), yaw=-math.pi/2)]), 0)
        self.assertEqual(bot.last_decision["kind"], "support")
        self.assertGreater(bot.last_decision["target"][1], 0)

    def test_controls_bounded_and_no_physics_mutation_across_varied_frames(self):
        rng = random.Random(9)
        bot = self.controller()
        for n in range(200):
            f = frame((rng.uniform(-4000, 4000), rng.uniform(-4900, 4900), rng.uniform(93, 1800)),
                      (rng.uniform(-2000, 2000), rng.uniform(-2000, 2000), rng.uniform(-500, 500)))
            f["time"] += n / 30
            f["cars"][0]["rotation"] = [rng.uniform(-3, 3) for _ in range(3)]
            f["cars"][0]["boost"] = rng.uniform(0, 100)
            original = copy.deepcopy(f)
            controls = bot.step(f, 0)
            self.assertEqual(set(controls), {"throttle", "steer", "pitch", "yaw", "roll", "jump", "boost", "handbrake"})
            for key in ("throttle", "steer", "pitch", "yaw", "roll"):
                self.assertTrue(math.isfinite(controls[key]))
                self.assertLessEqual(abs(controls[key]), 1)
            for key in ("jump", "boost", "handbrake"):
                self.assertIsInstance(controls[key], bool)
            self.assertEqual(f, original)

    def test_manifest_is_honest_and_parameters_recorded(self):
        manifest = self.controller("passer").manifest()
        self.assertEqual(manifest["status"], "experimental")
        self.assertIsNone(manifest["rank_certification"])
        self.assertFalse(any(t["available"] for t in manifest["rank_targets"]))
        self.assertEqual(manifest["seed"], 4)
        self.assertEqual(manifest["level"], 10)
        self.assertEqual(manifest["parameters"], capability_parameters(10, 1))


if __name__ == "__main__":
    unittest.main()
