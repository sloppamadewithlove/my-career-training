import copy
import unittest

from my_career_training.review import MatchReview


def sample(time=10., boost=40):
    human = {"index": 0, "team": 0, "is_bot": False, "position": [-100, -2400, 17],
             "velocity": [0, 800, 0], "boost": boost}
    teammate = {"index": 1, "team": 0, "is_bot": True, "position": [100, -2400, 17],
                "velocity": [0, 800, 0]}
    opponent = {"index": 2, "team": 1, "is_bot": True, "position": [0, -1300, 17],
                "velocity": [0, -800, 0]}
    return {"time": time, "car": human, "cars": [human, teammate, opponent],
            "ball": {"position": [0, -1900, 93]}, "packet_gap": False}


class ReviewTests(unittest.TestCase):
    def test_score_change_uses_observed_scores_and_does_not_name_scorer(self):
        review = MatchReview()
        review.update({"time": 0}, [0, 0])
        review.update({"time": 5}, {0: 1, 1: 0})
        review.update({"time": 6}, [1, 0])
        moments = review.summary()
        self.assertEqual(len(moments), 1)
        self.assertEqual(moments[0]["kind"], "score")
        self.assertEqual(moments[0]["time"], 5)
        self.assertIn("0–0 to 1–0", moments[0]["evidence"])
        self.assertEqual(moments[0]["suggestion"], "")
        review.update({"time": 9}, [0, 0])  # Reset is not a negative goal.
        self.assertEqual(len(review.summary()), 1)

    def test_initial_score_or_invalid_score_is_not_a_fabricated_goal(self):
        review = MatchReview()
        for value in ([3, 1], [float("nan"), 1], [True, 1], [-1, 1], [3.5, 1], None):
            review.update({"time": 10}, value)
        self.assertEqual(review.summary(), [])

    def test_actual_touch_deduplicates_and_ignores_old_history(self):
        review = MatchReview()
        f = sample()
        f["car"]["latest_touch"] = {"game_seconds": 2, "position": [0, 0, 93]}
        review.update(f)
        self.assertEqual(review.summary(), [])
        f["car"]["latest_touch"]["game_seconds"] = 10
        review.update(f)
        f["time"] = 10.1
        review.update(f)
        self.assertEqual([m["kind"] for m in review.summary()], ["touch"])
        self.assertEqual(review.summary()[0]["suggestion"], "")

    def test_two_approaching_teammates_without_cover_are_labeled_heuristic(self):
        review = MatchReview()
        for n in range(8):
            review.update(sample(10 + n * .1))
        moments = review.summary()
        self.assertEqual(len(moments), 1)
        moment = moments[0]
        self.assertEqual(moment["kind"], "double_commit")
        self.assertIn("coaching suggestion", moment["title"])
        self.assertIn("player 0 at (-100, -2400, 17)", moment["evidence"])
        self.assertIn("not a cause", moment["evidence"])
        self.assertTrue(moment["suggestion"])

    def test_cover_or_missing_velocities_or_attack_half_suppresses_flag(self):
        for mode in ("cover", "velocity", "offense", "missing_roster"):
            review = MatchReview()
            for n in range(8):
                f = sample(10 + n * .1)
                if mode == "cover":
                    f["cars"].append({"index": 3, "team": 0, "position": [0, -4000, 17], "velocity": [0, 0, 0]})
                elif mode == "velocity":
                    f["cars"][1].pop("velocity")
                elif mode == "offense":
                    for c in f["cars"]:
                        c["position"][1] += 4000
                    f["ball"]["position"][1] += 4000
                else:
                    f.pop("cars")
                review.update(f)
            self.assertEqual(review.summary(), [], mode)

    def test_packet_gaps_and_sparse_frames_do_not_establish_sustained_risk(self):
        for sparse in (False, True):
            review = MatchReview()
            for n in range(10):
                f = sample(10 + n * (1 if sparse else .1))
                f["packet_gap"] = not sparse
                review.update(f)
            self.assertEqual(review.summary(), [])

    def test_empty_boost_requires_real_contest_and_approach(self):
        review = MatchReview()
        for n in range(6):
            f = sample(10 + n * .1, boost=0)
            f["cars"][1]["position"] = [2000, -4000, 17]
            review.update(f)
        self.assertEqual([m["kind"] for m in review.summary()], ["empty_boost"])
        self.assertIn("reported boost 0", review.summary()[0]["evidence"])
        for invalid in ("boost", "opponent", "velocity"):
            review = MatchReview()
            for n in range(6):
                f = sample(10 + n * .1, boost=0)
                f["cars"][1]["position"] = [2000, -4000, 17]
                if invalid == "boost":
                    f["car"].pop("boost")
                elif invalid == "opponent":
                    f["cars"].pop()
                else:
                    f["car"]["velocity"] = [0, -800, 0]
                review.update(f)
            self.assertEqual(review.summary(), [], invalid)

    def test_bounded_output_and_score_retention(self):
        review = MatchReview(max_moments=12)
        review.update({"time": 0}, [0, 0])
        review.update({"time": 1}, [1, 0])
        for n in range(100):
            f = sample(10 + n * 10)
            f["car"]["latest_touch"] = {"game_seconds": f["time"]}
            review.update(f, [1, 0])
        result = review.summary()
        self.assertEqual(len(result), 12)
        self.assertIn("score", [m["kind"] for m in result])
        self.assertEqual(len(review._moments), 12)
        self.assertEqual(result, sorted(result, key=lambda m: m["time"]))

    def test_human_identification_and_summary_are_independent(self):
        review = MatchReview(human_index=0)
        f = sample()
        f.pop("car")
        f["cars"][0]["latest_touch"] = {"game_seconds": 10}
        original = copy.deepcopy(f)
        review.update(f)
        self.assertEqual(f, original)
        result = review.summary()
        result[0]["title"] = "Changed externally"
        self.assertEqual(review.summary()[0]["title"], "Your ball contact")

    def test_missing_evidence_generates_no_coaching(self):
        review = MatchReview()
        for n in range(10):
            review.update({"time": n * .1, "car": {"boost": 0}, "cars": [{}], "ball": {}}, None)
        review.update({"time": float("nan")}, [0, 1])
        review.update(None)
        self.assertEqual(review.summary(), [])


if __name__ == "__main__":
    unittest.main()
