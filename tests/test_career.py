"""Career contracts use synthetic final packets, never claim a real game run."""
from copy import deepcopy
import json

import pytest

from my_career_training import career as rules
from my_career_training.bots import PROVIDER_ID, PROVIDER_VERSION, SpecialistController, provider_manifest


def play(career, home_score=3, away_score=1, sid=None):
    f = rules.next_fixture(career)
    sid = sid or f"session-{f['id']}"
    started = rules.start_fixture(career, sid)
    return rules.complete_fixture(started, f["id"], sid, home_score, away_score)


@pytest.mark.parametrize("format", [1, 2, 3, 4])
def test_schedule_and_roster_have_one_human_and_correct_bench(format):
    career = rules.new_career("Night Shift", format=format, seed=402)
    assert len(rules.squad_members(career)) == 5
    assert len(career["lineup"]) == format - 1
    assert len(career["squad"]) - len(career["lineup"]) == 5 - format
    fixtures = career["seasons"][0]["fixtures"]
    assert len(fixtures) == 12
    assert len([f for f in fixtures if "human" in (f["home"], f["away"])]) == 6
    assert {(f["home"], f["away"]) for f in fixtures} == {
        (home, away) for home in rules.CLUB_IDS for away in rules.CLUB_IDS if home != away
    }
    assert all(f["format"] == format and f["status"] == "scheduled" for f in fixtures)
    assert rules.validate_career(json.loads(json.dumps(career)))


def test_failure_never_changes_input_and_active_squad_changes_are_blocked():
    career = rules.new_career("Night Shift", seed=402)
    started = rules.start_fixture(career, "real-session")
    original = deepcopy(started)
    for change in (lambda: rules.set_lineup(started, ["relay", "comet"]),
                   lambda: rules.replace_recruit(started, "anchor", "orbit"),
                   lambda: rules.set_format(started, 4),
                   lambda: rules.set_difficulty(started, 0.8, "steep")):
        with pytest.raises(ValueError, match="pending"):
            change()
        assert started == original
    assert career["pending_session"] is None
    assert rules.start_fixture(started, "real-session") == started


def test_session_binding_abandonment_and_exactly_once_result_rewards():
    initial = rules.new_career("Night Shift", seed=402)
    fixture = rules.next_fixture(initial)
    started = rules.start_fixture(initial, "attempt-one")
    with pytest.raises(ValueError, match="session"):
        rules.complete_fixture(started, fixture["id"], "wrong", 3, 2)
    with pytest.raises(ValueError, match="overtime"):
        rules.complete_fixture(started, fixture["id"], "attempt-one", 2, 2)
    abandoned = rules.abandon_fixture(started)
    assert abandoned["rewards"] == []
    assert abandoned["record"]["played"] == 0
    assert rules.next_fixture(abandoned)["result"] is None
    with pytest.raises(ValueError, match="already been used"):
        rules.start_fixture(abandoned, "attempt-one")
    retry = rules.start_fixture(abandoned, "attempt-two")
    with pytest.raises(ValueError, match="session"):
        rules.complete_fixture(retry, fixture["id"], "attempt-one", 3, 2)
    complete = rules.complete_fixture(retry, fixture["id"], "attempt-two", 3, 2)
    assert complete["record"]["played"] == 1
    assert len(complete["rewards"]) == 1
    assert rules.complete_fixture(complete, fixture["id"], "attempt-two", 3, 2) == complete
    with pytest.raises(ValueError, match="different final"):
        rules.complete_fixture(complete, fixture["id"], "attempt-two", 4, 2)
    reopened = json.loads(json.dumps(complete))
    assert rules.complete_fixture(reopened, fixture["id"], "attempt-two", 3, 2) == complete
    assert len([f for f in complete["seasons"][0]["fixtures"] if f["status"] == "completed"]) == 2


def test_companion_simulation_is_seeded_bounded_and_labeled():
    first = rules.new_career("Night Shift", seed=991)
    second = rules.new_career("Other Team", seed=991)
    first, second = play(first), play(second)
    a = next(f for f in first["seasons"][0]["fixtures"] if f["result"] and f["result"]["simulated"])
    b = next(f for f in second["seasons"][0]["fixtures"] if f["result"] and f["result"]["simulated"])
    assert (a["seed"], a["result"]["home_score"], a["result"]["away_score"]) == (
        b["seed"], b["result"]["home_score"], b["result"]["away_score"])
    assert 0 <= a["result"]["home_score"] <= 9
    assert 0 <= a["result"]["away_score"] <= 9
    assert a["result"]["provenance"] == "simulated"
    assert a["home"] != "human" and a["away"] != "human"
    assert rules.next_fixture(first)["round"] == 2
    assert rules.standings(first)[0]["played"] == 1


def test_historical_lineups_settings_and_identity_survive_changes():
    career = play(rules.new_career("Night Shift", seed=90))
    completed = deepcopy([f for f in career["seasons"][0]["fixtures"] if f["status"] == "completed"])
    anchor = deepcopy(career["recruits"]["anchor"])
    career = rules.replace_recruit(career, "anchor", "orbit")
    assert career["recruits"]["anchor"] == anchor
    career = rules.rename_recruit(career, "anchor", "Captain Calm")
    career = rules.replace_recruit(career, "orbit", "anchor")
    assert career["recruits"]["anchor"]["xp"] == anchor["xp"]
    assert career["recruits"]["anchor"]["name"] == "Captain Calm"
    career = rules.set_format(career, 4)
    career = rules.set_difficulty(career, 0.8, "Flat")
    assert [f for f in career["seasons"][0]["fixtures"] if f["status"] == "completed"] == completed
    assert all(f["format"] == 4 and f["difficulty"]["value"] == 0.8
               for f in career["seasons"][0]["fixtures"] if f["status"] == "scheduled")
    assert rules.next_fixture(career)["recruit_snapshots"]["anchor"]["name"] == "Captain Calm"
    assert rules.validate_career(career)


def test_progression_includes_modest_bench_share_and_records_starting_level():
    career = rules.new_career("Night Shift", format=2, seed=201)
    for _ in range(3):
        career = play(career, 4, 0)
    assert career["recruits"]["anchor"]["level"] == 2
    assert career["recruits"]["shield"]["xp"] == 48
    assert career["recruits"]["shield"]["stats"]["bench_appearances"] == 3
    assert career["recruits"]["orbit"]["xp"] == 0
    pending = rules.start_fixture(career, "progressed")
    assert rules.next_fixture(pending)["recruit_snapshots"]["anchor"]["level"] == 2
    assert pending["record"]["played"] == 3


def install_scorebook(monkeypatch, contenders):
    """Controlled opponent outcomes exercise rare tie paths independently of RNG."""
    def score(fixture):
        home, away = fixture["home"], fixture["away"]
        if home in contenders and away not in contenders:
            return 1, 0
        if home not in contenders and away in contenders:
            return 0, 1
        return 1, 0

    def simulate(season, fixture):
        assert "human" not in (fixture["home"], fixture["away"])
        hs, aws = score(fixture)
        fixture["session_id"] = f"sim:{fixture['seed']}"
        fixture["result"] = rules._result(fixture, fixture["session_id"], hs, aws, "simulated")
        fixture["status"] = "completed"

    monkeypatch.setattr(rules, "_simulate", simulate)
    return score


@pytest.mark.parametrize("count", [2, 3, 4])
def test_title_playoff_brackets_require_real_human_games_and_preserve_table(monkeypatch, count):
    contenders = list(rules.CLUB_IDS)[:count]
    score = install_scorebook(monkeypatch, contenders)
    career = rules.new_career("Night Shift", seed=7)
    for _ in range(6):
        f = rules.next_fixture(career)
        hs, aws = score(f)
        career = play(career, hs, aws)
    season = career["seasons"][0]
    assert set(season["title_contenders"]) == set(contenders)
    assert season["champion"] is None
    table = deepcopy(rules.standings(career))
    while rules.next_fixture(career):
        fixture = rules.next_fixture(career)
        assert "human" in (fixture["home"], fixture["away"])
        assert fixture["phase"] in ("semifinal", "final")
        assert fixture["result"] is None
        # Human wins its playoff fixtures, so every human bracket round is exercised.
        career = play(career, *( (2, 1) if fixture["home"] == "human" else (1, 2)))
        assert rules.standings(career) == table
    season = career["seasons"][0]
    assert season["champion"] == "human"
    assert len(season["playoffs"]) == count - 1
    assert all(f["status"] == "completed" for f in season["playoffs"])
    assert all(f["result"]["simulated"] == ("human" not in (f["home"], f["away"]))
               for f in season["playoffs"])
    assert rules.validate_career(json.loads(json.dumps(career)))


def test_head_to_head_breaks_primary_tie_before_title_playoff():
    career = rules.new_career("Night Shift", seed=17)
    scores = [(4, 1), (1, 0), (3, 2), (1, 3), (2, 3), (4, 3),
              (1, 2), (4, 3), (1, 2), (1, 3), (4, 2), (2, 0)]
    for f, (home_score, away_score) in zip(career["seasons"][0]["fixtures"], scores):
        f["status"] = "completed"
        f["result"] = {"home_score": home_score, "away_score": away_score,
                       "winner": f["home"] if home_score > away_score else f["away"]}
    table = rules.standings(career)
    assert table[0]["id"] == "aurora" and table[1]["id"] == "human"
    assert all(table[0][k] == table[1][k] for k in ("points", "goal_difference", "goals_for"))
    assert table[0]["head_to_head_points"] == 6
    assert table[1]["head_to_head_points"] == 0
    assert table[0]["position"] == 1 and table[1]["position"] == 2


def test_three_club_bye_is_persisted_and_simulated_semi_does_not_fake_human_game(monkeypatch):
    score = install_scorebook(monkeypatch, ["human", "aurora", "cinder"])
    career = rules.new_career("Night Shift", seed=5)
    for _ in range(6):
        career = play(career, *score(rules.next_fixture(career)))
    season = career["seasons"][0]
    assert season["title_contenders"][0] == "human"
    assert season["playoffs"][0]["phase"] == "semifinal"
    assert season["playoffs"][0]["result"]["simulated"] is True
    assert rules.next_fixture(career)["phase"] == "final"
    assert career["record"]["played"] == 6
    assert rules.next_fixture(json.loads(json.dumps(career))) == rules.next_fixture(career)


def test_human_semifinal_loss_resolves_other_club_final_without_awarding_human_xp(monkeypatch):
    score = install_scorebook(monkeypatch, list(rules.CLUB_IDS))
    career = rules.new_career("Night Shift", seed=7)
    for _ in range(6):
        career = play(career, *score(rules.next_fixture(career)))
    f = rules.next_fixture(career)
    career = play(career, *((0, 1) if f["home"] == "human" else (1, 0)))
    assert rules.next_fixture(career) is None
    assert career["record"]["played"] == 7
    assert career["seasons"][0]["champion"] != "human"
    assert career["seasons"][0]["playoffs"][-1]["result"]["simulated"] is True
    assert len([r for r in career["rewards"] if r["type"] == "match_experience"]) == 7


def test_seasons_continue_without_resetting_roster_or_historical_rewards(monkeypatch):
    install_scorebook(monkeypatch, ["human"])
    career = rules.new_career("Night Shift", seed=71)
    for _ in range(6):
        f = rules.next_fixture(career)
        career = play(career, *((3, 0) if f["home"] == "human" else (0, 3)))
    assert career["seasons"][0]["champion"] == "human"
    old = deepcopy(career)
    career = rules.start_next_season(career)
    assert career["current_season"] == 1
    assert career["seasons"][0] == old["seasons"][0]
    assert career["recruits"] == old["recruits"]
    assert career["rewards"] == old["rewards"]
    assert career["seasons"][1]["seed"] != old["seasons"][0]["seed"]
    assert rules.next_fixture(career)["round"] == 1
    with pytest.raises(ValueError, match="Finish this season"):
        rules.start_next_season(career)


@pytest.mark.parametrize("corrupt", [
    lambda c: c.update(schema_version=99),
    lambda c: c.update(format=True),
    lambda c: c["recruits"]["anchor"].update(level=5),
    lambda c: c["seasons"][0]["fixtures"][0].update(lineup=["anchor", "anchor"]),
    lambda c: c["seasons"][0]["fixtures"].pop(),
    lambda c: c["seasons"][0].update(champion="human"),
    lambda c: c.update(pending_session={"fixture_id": "not-real", "session_id": "not-real"}),
    lambda c: c["seasons"][0]["fixtures"][0].update(result={"home_score": 3, "away_score": 1}),
    lambda c: c["rewards"].append({"id": "xp:unplayed"}),
])
def test_malformed_imports_are_rejected(corrupt):
    career = rules.new_career("Night Shift", seed=402)
    corrupt(career)
    with pytest.raises(ValueError):
        rules.validate_career(career)


@pytest.mark.parametrize("bad", [-1, True, 1.2, float("nan"), "3"])
def test_invalid_scores_cannot_award_progress(bad):
    career = rules.start_fixture(rules.new_career("Night Shift", seed=402), "packet")
    with pytest.raises(ValueError):
        rules.complete_fixture(career, rules.next_fixture(career)["id"], "packet", bad, 0)
    assert career["rewards"] == []


def test_import_rejects_tampered_awards_stats_and_recorded_capability():
    valid = play(rules.new_career("Night Shift", seed=402))
    for corrupt in (
        lambda c: c["rewards"][0]["xp"].update(anchor=100),
        lambda c: c["recruits"]["anchor"]["stats"].update(appearances=900),
        lambda c: c["seasons"][0]["fixtures"][0]["recruit_snapshots"]["anchor"].update(level=4),
        lambda c: c["seasons"][0]["fixtures"][0]["difficulty"].update(value=0.9),
    ):
        malformed = deepcopy(valid)
        corrupt(malformed)
        with pytest.raises(ValueError):
            rules.validate_career(malformed)
    assert rules.validate_career(valid)


def test_import_rejects_current_format_inconsistent_with_unplayed_schedule():
    forged = rules.new_career("Night Shift", format=3, seed=402)
    forged["format"] = 4
    forged["lineup"] = forged["squad"][:3]
    with pytest.raises(ValueError, match="current career format"):
        rules.validate_career(forged)


def test_repeated_format_changes_validate_against_future_rounds_and_not_old_snapshots():
    career = play(rules.new_career("Night Shift", format=3, seed=402))
    career = rules.set_format(career, 1)
    career = play(career)
    career = rules.set_format(career, 4)
    rounds = {f["round"]: f["format"] for f in career["seasons"][0]["fixtures"]}
    assert rounds == {1: 3, 2: 1, 3: 4, 4: 4, 5: 4, 6: 4}
    assert rules.validate_career(json.loads(json.dumps(career)))
    assert rules.validate_career(rules.start_fixture(career, "current-four-v-four"))


@pytest.mark.parametrize("format", [1, 2, 3, 4])
@pytest.mark.parametrize("human_team", [0, 1])
def test_recorded_runtime_matches_controller_parameters_for_every_player_mapping(format, human_team):
    career = rules.new_career("Runtime Metadata", format=format, seed=775)
    if human_team == 1:
        for _ in range(3):
            career = play(career)
    career = rules.set_difficulty(career, 0.7, "steep")
    career = rules.start_fixture(career, "runtime-inspection")
    fixture = rules.next_fixture(career)
    manifest = provider_manifest()
    assert fixture["provider"]["id"] == manifest["id"] == PROVIDER_ID
    assert fixture["provider"]["version"] == manifest["version"] == PROVIDER_VERSION
    runtime = fixture["bot_runtime"]
    assert len(runtime) == format * 2 - 1
    assert [bot["index"] for bot in runtime] == list(range(format * 2 - 1))
    assert [bot["team"] for bot in runtime] == sorted(bot["team"] for bot in runtime)
    teammates = [bot for bot in runtime if bot["team"] == human_team]
    rivals = [bot for bot in runtime if bot["team"] != human_team]
    assert [bot["recruit_id"] for bot in teammates] == fixture["lineup"]
    assert [bot["role"] for bot in rivals] == ["keeper", "attacker", "defender", "passer"][:format]
    assert all(bot["level"] == fixture["opponent_starting_level"] for bot in rivals)
    for bot in runtime:
        controller = SpecialistController(bot["role"], bot["level"], fixture["difficulty"]["value"],
                                          fixture["seed"] + bot["index"])
        actual = controller.manifest()
        assert bot["provider_id"] == actual["id"]
        assert bot["provider_version"] == actual["version"]
        for key in ("role", "level", "difficulty", "seed", "parameters"):
            assert bot[key] == actual[key]
    done = rules.complete_fixture(career, fixture["id"], "runtime-inspection", 2, 1)
    result = next(f for f in done["seasons"][0]["fixtures"] if f["id"] == fixture["id"])["result"]
    assert result["bot_runtime"] == runtime
    assert rules.validate_career(json.loads(json.dumps(done)))


def _human_result(career):
    return next(f for f in career["seasons"][0]["fixtures"]
                if f["result"] and "human" in (f["home"], f["away"]))


def test_forfeit_keeps_observed_scores_home_and_away():
    career = rules.new_career("Night Shift", seed=402)
    observed = [(2, 2), (4, 1), (0, 3), (1, 1), (0, 5), (3, 1)]
    sides = []
    for home_score, away_score in observed:
        fixture = rules.next_fixture(career)
        session = f"forfeit-round-{fixture['round']}"
        career = rules.forfeit_fixture(rules.start_fixture(career, session), fixture["id"], session,
                                       home_score, away_score)
        stored = next(f for f in career["seasons"][0]["fixtures"] if f["id"] == fixture["id"])
        result = stored["result"]
        opponent = stored["away"] if stored["home"] == "human" else stored["home"]
        assert (result["home_score"], result["away_score"]) == (home_score, away_score)
        assert result["winner"] == opponent and result["winner"] != "human"
        assert result["provenance"] == "forfeit" and result["outcome"] == "forfeited"
        assert result["forfeited_by"] == "human" and result["simulated"] is False
        sides.append(stored["home"] == "human")
    assert sides == [True, True, True, False, False, False]
    assert career["record"] == {"played": 6, "wins": 0, "losses": 6, "goals_for": 13, "goals_against": 10}
    round_one = [f for f in career["seasons"][0]["fixtures"] if f["round"] == 1]
    assert sum(f["result"]["provenance"] == "forfeit" for f in round_one) == 1
    assert sum(f["result"]["provenance"] == "simulated" for f in round_one) == 1
    assert len([r for r in career["rewards"] if r["type"] == "match_experience"]) == 6
    assert rules.validate_career(json.loads(json.dumps(career)))


def test_forfeit_duplicate_is_idempotent_and_conflicts_are_rejected():
    career = rules.new_career("Night Shift", seed=402)
    fixture = rules.next_fixture(career)
    companion = next(f for f in career["seasons"][0]["fixtures"] if "human" not in (f["home"], f["away"]))
    future = next(f for f in career["seasons"][0]["fixtures"]
                  if "human" in (f["home"], f["away"]) and f["id"] != fixture["id"])
    started = rules.start_fixture(career, "keep")
    untouched = deepcopy(started)
    for call in (lambda: rules.forfeit_fixture(started, companion["id"], "keep", 1, 1),
                 lambda: rules.forfeit_fixture(started, "missing-fixture", "keep", 1, 1),
                 lambda: rules.forfeit_fixture(started, future["id"], "keep", 1, 0),
                 lambda: rules.forfeit_fixture(started, fixture["id"], "other-session", 1, 1),
                 lambda: rules.forfeit_fixture(started, fixture["id"], "keep", 1000, 0)):
        with pytest.raises(ValueError):
            call()
        assert started == untouched
    done = rules.forfeit_fixture(started, fixture["id"], "keep", 4, 2)
    assert started == untouched
    assert rules.forfeit_fixture(done, fixture["id"], "keep", 4, 2) == done
    reopened = json.loads(json.dumps(done))
    assert rules.forfeit_fixture(reopened, fixture["id"], "keep", 4, 2) == done
    for call in (lambda: rules.forfeit_fixture(done, fixture["id"], "keep", 4, 1),
                 lambda: rules.forfeit_fixture(done, fixture["id"], "other-session", 4, 2),
                 lambda: rules.complete_fixture(done, fixture["id"], "keep", 4, 2)):
        with pytest.raises(ValueError):
            call()
    assert done["record"]["played"] == 1 and len([r for r in done["rewards"] if r["type"] == "match_experience"]) == 1
    idle = rules.new_career("Night Shift", seed=402)
    with pytest.raises(ValueError, match="pending human fixture"):
        rules.forfeit_fixture(idle, rules.next_fixture(idle)["id"], "never-started", 0, 0)
    played = play(rules.new_career("Night Shift", seed=88), 2, 0)
    finished = _human_result(played)
    with pytest.raises(ValueError, match="played result"):
        rules.forfeit_fixture(played, finished["id"], finished["session_id"], 2, 0)
    assert played["record"]["wins"] == 1


def test_forfeit_restart_roundtrip_rejects_tampered_identity():
    career = rules.new_career("Night Shift", seed=402)
    fixture = rules.next_fixture(career)
    restarted = rules.abandon_fixture(rules.start_fixture(career, "abandoned-session"))
    with pytest.raises(ValueError, match="pending human fixture"):
        rules.forfeit_fixture(restarted, fixture["id"], "abandoned-session", 1, 0)
    done = rules.forfeit_fixture(rules.start_fixture(restarted, "fresh-session"), fixture["id"],
                                 "fresh-session", 1, 0)
    reopened = json.loads(json.dumps(done))
    assert rules.validate_career(reopened)
    assert rules.forfeit_fixture(reopened, fixture["id"], "fresh-session", 1, 0) == done
    stored = _human_result(done)
    assert stored["attempts"][0]["status"] == "abandoned"
    assert stored["attempts"][1]["status"] == "completed"

    def result_of(value):
        return _human_result(value)["result"]

    for corrupt in (
        lambda c: result_of(c).update(winner="human"),
        lambda c: result_of(c).update(outcome="played"),
        lambda c: result_of(c).pop("forfeited_by"),
        lambda c: result_of(c).pop("outcome"),
        lambda c: result_of(c).update(simulated=True),
        lambda c: result_of(c).update(provenance="game"),
        lambda c: result_of(c).update(forfeited_by="opponent"),
    ):
        forged = deepcopy(done)
        corrupt(forged)
        with pytest.raises(ValueError):
            rules.validate_career(forged)
    natural = play(rules.new_career("Night Shift", seed=402), 3, 2)
    for corrupt in (
        lambda c: _human_result(c)["result"].update(outcome="forfeited"),
        lambda c: _human_result(c)["result"].update(forfeited_by="human"),
        lambda c: _human_result(c)["result"].update(home_score=_human_result(c)["result"]["away_score"]),
    ):
        forged = deepcopy(natural)
        corrupt(forged)
        with pytest.raises(ValueError):
            rules.validate_career(forged)
    assert rules.validate_career(natural)
    assert rules.validate_career(done)


def test_forfeit_standings_keep_goals_and_progression_matches_a_loss():
    career = rules.new_career("Night Shift", seed=402)
    fixture = rules.next_fixture(career)
    assert (fixture["home"], fixture["away"]) == ("human", "tidal")
    done = rules.forfeit_fixture(rules.start_fixture(career, "lead"), fixture["id"], "lead", 5, 1)
    rows = {row["id"]: row for row in rules.standings(done)}
    assert (rows["human"]["wins"], rows["human"]["losses"], rows["human"]["points"]) == (0, 1, 0)
    assert (rows["human"]["goals_for"], rows["human"]["goals_against"]) == (5, 1)
    assert (rows["tidal"]["wins"], rows["tidal"]["losses"], rows["tidal"]["points"]) == (1, 0, 3)
    assert (rows["tidal"]["goals_for"], rows["tidal"]["goals_against"]) == (1, 5)
    assert rows["aurora"]["played"] == rows["cinder"]["played"] == 1
    played_loss = play(rules.new_career("Night Shift", seed=402), 0, 1)
    assert done["rewards"][0]["xp"] == played_loss["rewards"][0]["xp"]
    assert done["record"]["wins"] == played_loss["record"]["wins"] == 0
    assert (done["record"]["goals_for"], done["record"]["goals_against"]) == (5, 1)
    assert all(done["recruits"][i]["stats"]["wins"] == 0 for i in done["squad"])
    fresh = rules.new_career("Night Shift", seed=402)
    level = rules.next_fixture(fresh)
    tied = rules.forfeit_fixture(rules.start_fixture(fresh, "level"), level["id"], "level", 2, 2)
    tied_rows = {row["id"]: row for row in rules.standings(tied)}
    assert tied_rows["human"]["points"] == 0 and tied_rows["tidal"]["points"] == 3
    assert (tied_rows["human"]["goals_for"], tied_rows["human"]["goals_against"]) == (2, 2)
    assert rules.validate_career(json.loads(json.dumps(done)))
    assert rules.validate_career(json.loads(json.dumps(tied)))


def test_forfeit_title_semifinal_awards_opponent_and_preserves_table(monkeypatch):
    score = install_scorebook(monkeypatch, list(rules.CLUB_IDS))
    career = rules.new_career("Night Shift", seed=7)
    for _ in range(6):
        career = play(career, *score(rules.next_fixture(career)))
    table = deepcopy(rules.standings(career))
    wins = {key: recruit["stats"]["wins"] for key, recruit in career["recruits"].items()}
    fixture = rules.next_fixture(career)
    assert fixture["phase"] == "semifinal"
    home_score, away_score = (3, 0) if fixture["home"] == "human" else (0, 3)
    done = rules.forfeit_fixture(rules.start_fixture(career, "forfeit-semi"), fixture["id"],
                                 "forfeit-semi", home_score, away_score)
    stored = next(f for f in done["seasons"][0]["playoffs"] if f["id"] == fixture["id"])
    result = stored["result"]
    score_winner = stored["home"] if home_score > away_score else stored["away"]
    assert (result["home_score"], result["away_score"]) == (home_score, away_score)
    assert score_winner == "human" and result["winner"] != "human"
    assert result["provenance"] == "forfeit" and result["outcome"] == "forfeited"
    assert result["forfeited_by"] == "human" and result["simulated"] is False
    assert rules.standings(done) == table
    assert rules.next_fixture(done) is None
    assert done["seasons"][0]["champion"] not in (None, "human")
    assert done["seasons"][0]["playoffs"][-1]["phase"] == "final"
    assert done["seasons"][0]["playoffs"][-1]["result"]["simulated"] is True
    assert done["record"]["wins"] == career["record"]["wins"]
    assert done["record"]["losses"] == career["record"]["losses"] + 1
    reward = next(item for item in done["rewards"] if item["fixture_id"] == fixture["id"])
    assert reward["xp"] == {recruit_id: 35 if recruit_id in fixture["lineup"] else 12
                            for recruit_id in fixture["squad"]}
    assert {key: recruit["stats"]["wins"] for key, recruit in done["recruits"].items()} == wins
    assert len([item for item in done["rewards"] if item["type"] == "match_experience"]) == 7
    assert rules.validate_career(json.loads(json.dumps(done)))


def test_bot_runtime_rejects_tampered_parameters_and_preserves_completed_snapshot():
    career = play(rules.new_career("Runtime Metadata", seed=775))
    completed = deepcopy(career["seasons"][0]["fixtures"][0]["bot_runtime"])
    career = rules.replace_recruit(career, "anchor", "orbit")
    career = rules.set_difficulty(career, 0.2, "flat")
    assert career["seasons"][0]["fixtures"][0]["bot_runtime"] == completed
    malformed = deepcopy(career)
    rules.next_fixture(malformed)  # Selecting a fixture must not expose an alias.
    malformed["seasons"][0]["fixtures"][2]["bot_runtime"][0]["parameters"]["speed_limit"] += 100
    with pytest.raises(ValueError, match="runtime settings"):
        rules.validate_career(malformed)
