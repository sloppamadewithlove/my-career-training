"""Immutable, local career rules. Only other clubs' games are simulated.

League fixtures are resolved one round at a time. A human result must match an
explicit pending session; duplicate final packets return the same awarded state.
All dictionaries returned by this module can be serialized as ordinary JSON.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import random
import uuid

from .bots import PROVIDER_ID, PROVIDER_VERSION, capability_parameters

SCHEMA_VERSION = 1
MAX_LEVEL = 5
ROLES = ("keeper", "defender", "passer", "attacker", "all-rounder")
DEFAULT_RECRUITS = {
    "anchor": {"id": "anchor", "name": "Anchor", "role": "keeper"},
    "shield": {"id": "shield", "name": "Shield", "role": "defender"},
    "relay": {"id": "relay", "name": "Relay", "role": "passer"},
    "comet": {"id": "comet", "name": "Comet", "role": "attacker"},
    "orbit": {"id": "orbit", "name": "Orbit", "role": "all-rounder"},
}
MAPS = ("DFHStadium", "Mannfield", "ChampionsField", "UtopiaColiseum")
CLUB_IDS = ("human", "aurora", "cinder", "tidal")
PROVIDER = {
    "id": PROVIDER_ID, "version": PROVIDER_VERSION,
    "capability": "Experimental specialist controller; no rank certification",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, low=0, high=2**63 - 1):
    return type(value) is int and low <= value <= high


def _name(value, label="Name"):
    _require(isinstance(value, str) and 1 <= len(value.strip()) <= 48,
             f"{label} must contain 1 to 48 characters.")
    _require(all(ord(c) >= 32 for c in value), f"{label} cannot contain control characters.")
    return value.strip()


def _ids(value, length, label):
    _require(isinstance(value, list) and len(value) == length,
             f"{label} must contain exactly {length} recruit(s).")
    _require(all(isinstance(i, str) and i in DEFAULT_RECRUITS for i in value),
             f"{label} contains an unknown recruit.")
    _require(len(set(value)) == length, f"{label} cannot contain duplicates.")


def _format(value):
    _require(_integer(value, 1, 4), "Match format must be 1, 2, 3, or 4.")


def _difficulty(baseline, curve):
    _require(type(baseline) in (int, float) and math.isfinite(baseline) and 0 <= baseline <= 1,
             "Difficulty must be a number from 0 to 1.")
    _require(isinstance(curve, str) and curve.lower() in ("flat", "gentle", "steep"),
             "Season curve must be Flat, Gentle, or Steep.")
    return {"baseline": float(baseline), "curve": curve.lower()}


def _season(career):
    return career["seasons"][career["current_season"]]


def _fixtures(season):
    return season["fixtures"] + season["playoffs"]


def _all_fixtures(career):
    return [f for season in career["seasons"] for f in _fixtures(season)]


def _assert_editable(career):
    _require(career["pending_session"] is None,
             "Finish or abandon the pending match before changing the squad or settings.")


def _copy(career, editable=False):
    validate_career(career)
    if editable:
        _assert_editable(career)
    return deepcopy(career)


def _finish(career):
    career["updated_at"] = _now()
    validate_career(career)
    return career


def _decisions(career, round_number):
    setting = career["difficulty"]
    stage = min(1.0, max(0, round_number - 1) / 5)
    increment = {"flat": 0, "gentle": 0.12, "steep": 0.25}[setting["curve"]]
    return {**setting, "stage": stage, "value": round(min(1, setting["baseline"] + increment * stage), 4)}


def _snapshot(career, lineup):
    return {key: {"id": key, "name": career["recruits"][key]["name"],
                  "role": career["recruits"][key]["role"],
                  "level": career["recruits"][key]["level"],
                  "loadout": deepcopy(career["recruits"][key]["loadout"])} for key in lineup}


def policy_manifest(provider_id):
    """Immutable policy identity without importing the inference runtime."""
    if provider_id == PROVIDER_ID:
        return deepcopy(PROVIDER)
    from .bots.providers import MODELS, SOURCE_REVISION
    _require(provider_id in MODELS, "Unknown bot policy.")
    return {"id": provider_id, "version": SOURCE_REVISION,
            "model_sha256": MODELS[provider_id]["sha256"]}


def set_policy(career, provider_id):
    career = _copy(career)
    _assert_editable(career)
    manifest = policy_manifest(provider_id)
    _require(provider_id == PROVIDER_ID or career["format"] <= 3,
             "Necto and Nexto support 1v1, 2v2 and 3v3; select Ground Specialists for 4v4.")
    career["bot_policy"] = manifest["id"]
    return _finish(career)


def bot_runtime_snapshot(fixture):
    """Record the exact pure-controller configuration in RLBot's player order.

    Custom bots occupy team 0 then team 1; the human is always the last player.
    Other-club score simulations have no instantiated game controllers.
    """
    if "human" not in (fixture["home"], fixture["away"]):
        return []
    human_team = 0 if fixture["home"] == "human" else 1
    difficulty = fixture["difficulty"]["value"]
    bots = []
    for team in (0, 1):
        count = fixture["format"] - int(team == human_team)
        for position in range(count):
            recruit_id = fixture["lineup"][position] if team == human_team else None
            if recruit_id is not None:
                descriptor = fixture["recruit_snapshots"][recruit_id]
            else:
                descriptor = {
                    "name": f"Rival {position + 1}",
                    "role": ("keeper", "attacker", "defender", "passer")[position],
                    "level": fixture["opponent_starting_level"],
                    "loadout": {"car_id": 23, "primary_color": 30, "secondary_color": 0},
                }
            bots.append({
                "index": len(bots), "team": team, "recruit_id": recruit_id,
                "name": descriptor["name"], "role": descriptor["role"], "level": descriptor["level"],
                "loadout": deepcopy(descriptor["loadout"]),
                "difficulty": difficulty, "seed": fixture["seed"] + len(bots),
                "parameters": (capability_parameters(descriptor["level"], difficulty)
                    if fixture["provider"]["id"] == PROVIDER_ID else {}),
                "provider_id": fixture["provider"]["id"], "provider_version": fixture["provider"]["version"],
            })
    return bots


def _fixture(career, season, home, away, round_number, index, phase="league"):
    rng = random.Random(f"{season['seed']}:{phase}:{round_number}:{index}")
    lineup = list(career["lineup"]) if "human" in (home, away) else []
    fixture = {
        "id": f"{season['id']}:{phase}:{round_number}:{index}",
        "home": home, "away": away, "round": round_number, "phase": phase,
        "format": career["format"], "map": rng.choice(MAPS),
        "seed": rng.randrange(2**63), "difficulty": _decisions(career, round_number),
        "lineup": lineup, "squad": list(career["squad"]) if lineup or "human" in (home, away) else [],
        "recruit_snapshots": _snapshot(career, lineup), "provider": deepcopy(PROVIDER),
        "opponent_starting_level": max(1, min(MAX_LEVEL, 1 + int(_decisions(career, round_number)["value"] * 4))),
        "duration_seconds": 300, "overtime": True,
        "status": "scheduled", "result": None, "session_id": None, "attempts": [],
    }
    fixture["bot_runtime"] = bot_runtime_snapshot(fixture)
    return fixture


def _new_season(career, number, seed):
    season = {
        "id": f"{career['id']}:s{number}", "number": number, "seed": seed,
        "clubs": [{"id": "human", "name": career["team_name"], "strength": 0.5},
                  {"id": "aurora", "name": "Aurora Athletic", "strength": 0.46},
                  {"id": "cinder", "name": "Cinder City", "strength": 0.52},
                  {"id": "tidal", "name": "Tidal Rovers", "strength": 0.58}],
        "fixtures": [], "playoffs": [], "champion": None,
        "playoff_draw": list(CLUB_IDS), "title_contenders": [],
        "settings_history": [], "completed_at": None,
    }
    random.Random(seed).shuffle(season["playoff_draw"])
    first_half = [(("human", "tidal"), ("aurora", "cinder")),
                  (("human", "cinder"), ("tidal", "aurora")),
                  (("human", "aurora"), ("cinder", "tidal"))]
    rounds = first_half + [tuple((away, home) for home, away in pairs) for pairs in first_half]
    for round_number, pairs in enumerate(rounds, 1):
        for index, (home, away) in enumerate(pairs, 1):
            season["fixtures"].append(_fixture(career, season, home, away, round_number, index))
    season["settings_history"].append({"after_round": 0, "format": career["format"],
                                         "difficulty": deepcopy(career["difficulty"]), "time": _now()})
    return season


def new_career(team_name, format=3, seed=None, recruits=None):
    """Create one human plus four persistent recruits; the fifth remains available."""
    team_name = _name(team_name, "Team name")
    _format(format)
    chosen = list(DEFAULT_RECRUITS)[:4] if recruits is None else deepcopy(recruits)
    _ids(chosen, 4, "Squad")
    if seed is None:
        seed = random.SystemRandom().randrange(2**63)
    _require(_integer(seed), "Career seed must be a non-negative 63-bit integer.")
    now = _now()
    career = {
        "id": str(uuid.uuid4()), "schema_version": SCHEMA_VERSION,
        "team_name": team_name, "format": format, "seed": seed,
        "created_at": now, "updated_at": now,
        "team_colors": {"primary": "#368cff", "secondary": "#f29447"},
        "difficulty": _difficulty(0.5, "gentle"),
        "recruits": {key: {**value, "xp": 0, "level": 1,
                             "loadout": {"car_id": 23, "primary_color": 27, "secondary_color": 0},
                             "stats": {"appearances": 0, "bench_appearances": 0, "wins": 0}}
                     for key, value in deepcopy(DEFAULT_RECRUITS).items()},
        "squad": chosen, "lineup": chosen[:format - 1],
        "seasons": [], "current_season": 0, "pending_session": None, "rewards": [],
        "record": {"played": 0, "wins": 0, "losses": 0, "goals_for": 0, "goals_against": 0},
    }
    career["seasons"].append(_new_season(career, 1, seed))
    return _finish(career)


def standings(career):
    """League-only table. Playoffs never rewrite the league points or goals."""
    season = _season(career)
    rows = {club["id"]: {"id": club["id"], "club_id": club["id"], "name": club["name"],
                             "played": 0, "wins": 0, "losses": 0, "points": 0,
                             "goals_for": 0, "goals_against": 0, "goal_difference": 0,
                             "head_to_head_points": 0} for club in season["clubs"]}
    completed = [f for f in season["fixtures"] if f["status"] == "completed"]
    for f in completed:
        result = f["result"]
        for own, other, score, against in ((f["home"], f["away"], result["home_score"], result["away_score"]),
                                           (f["away"], f["home"], result["away_score"], result["home_score"])):
            row = rows[own]
            row["played"] += 1
            row["wins"] += score > against
            row["losses"] += score < against
            row["points"] += 3 if score > against else 0
            row["goals_for"] += score
            row["goals_against"] += against
            row["goal_difference"] = row["goals_for"] - row["goals_against"]
    def primary(row):
        return row["points"], row["goal_difference"], row["goals_for"]
    for row in rows.values():
        tied = {other["id"] for other in rows.values() if primary(other) == primary(row)}
        row["head_to_head_points"] = sum(
            3 for f in completed if f["home"] in tied and f["away"] in tied
            and f["result"]["winner"] == row["id"]
        )
    draw = season["playoff_draw"]
    ordered = sorted(rows.values(), key=lambda row: (*(-n for n in primary(row)),
                                                     -row["head_to_head_points"], draw.index(row["id"])))
    last_key = None
    rank = 0
    for index, row in enumerate(ordered, 1):
        key = (*primary(row), row["head_to_head_points"])
        if key != last_key:
            rank = index
        row["position"] = rank
        last_key = key
    return ordered


def next_fixture(career):
    """Return a detached human fixture, including a pending fixture after restart."""
    pending = career["pending_session"]
    if pending:
        return deepcopy(next(f for f in _fixtures(_season(career)) if f["id"] == pending["fixture_id"]))
    for f in _fixtures(_season(career)):
        if "human" in (f["home"], f["away"]) and f["status"] != "completed":
            return deepcopy(f)
    return None


def start_fixture(career, session_id):
    career = _copy(career)
    _require(isinstance(session_id, str) and 1 <= len(session_id) <= 128
             and all(ord(c) >= 32 for c in session_id), "A valid match session ID is required.")
    pending = career["pending_session"]
    if pending:
        _require(pending["session_id"] == session_id,
                 "A match is already pending. Resume it or abandon it before starting another.")
        return career
    _require(not any(f["session_id"] == session_id or any(a["session_id"] == session_id for a in f["attempts"])
                     for f in _all_fixtures(career)),
             "This session ID has already been used. Start a fresh match session.")
    selected = next_fixture(career)
    _require(selected is not None, "This season is complete. Start the next season to play again.")
    fixture = next(f for f in _fixtures(_season(career)) if f["id"] == selected["id"])
    fixture["status"] = "pending"
    fixture["provider"] = policy_manifest(career.get("bot_policy", PROVIDER_ID))
    fixture["session_id"] = session_id
    fixture["lineup"] = list(career["lineup"])
    fixture["squad"] = list(career["squad"])
    fixture["recruit_snapshots"] = _snapshot(career, fixture["lineup"])
    fixture["bot_runtime"] = bot_runtime_snapshot(fixture)
    fixture["attempts"].append({"session_id": session_id, "status": "pending", "started_at": _now()})
    career["pending_session"] = {"fixture_id": fixture["id"], "session_id": session_id,
                                   "started_at": fixture["attempts"][-1]["started_at"]}
    return _finish(career)


def _result(fixture, session_id, home_score, away_score, provenance):
    return {"id": f"result:{fixture['id']}:{session_id}", "fixture_id": fixture["id"],
            "session_id": session_id, "home_score": home_score, "away_score": away_score,
            "winner": fixture["home"] if home_score > away_score else fixture["away"],
            "provenance": provenance, "simulated": provenance == "simulated", "completed_at": _now(),
            "format": fixture["format"], "map": fixture["map"], "lineup": list(fixture["lineup"]),
            "difficulty": deepcopy(fixture["difficulty"]), "seed": fixture["seed"],
            "bot_runtime": deepcopy(fixture["bot_runtime"])}


def _simulate(season, fixture):
    """Bounded bookkeeping from the recorded seed/club strength, never human play."""
    _require("human" not in (fixture["home"], fixture["away"]), "Human matches cannot be simulated.")
    strength = {club["id"]: club["strength"] for club in season["clubs"]}
    rng = random.Random(fixture["seed"])
    home_score = max(0, min(8, round(2 + strength[fixture["home"]] * 3 + rng.gauss(0, 1.5))))
    away_score = max(0, min(8, round(2 + strength[fixture["away"]] * 3 + rng.gauss(0, 1.5))))
    if home_score == away_score:
        advantage = 0.5 + (strength[fixture["home"]] - strength[fixture["away"]]) / 2
        if rng.random() < advantage:
            home_score += 1
        else:
            away_score += 1
    session_id = f"sim:{fixture['seed']}"
    fixture["session_id"] = session_id
    fixture["result"] = _result(fixture, session_id, home_score, away_score, "simulated")
    fixture["status"] = "completed"


def _award_match(career, fixture):
    result = fixture["result"]
    human_home = fixture["home"] == "human"
    won = result["winner"] == "human"
    record = career["record"]
    record["played"] += 1
    record["wins"] += int(won)
    record["losses"] += int(not won)
    record["goals_for"] += result["home_score"] if human_home else result["away_score"]
    record["goals_against"] += result["away_score"] if human_home else result["home_score"]
    awarded = {}
    for recruit_id in fixture["squad"]:
        recruit = career["recruits"][recruit_id]
        active = recruit_id in fixture["lineup"]
        gain = (35 if active else 12) + ((10 if active else 4) if won else 0)
        previous = recruit["xp"]
        recruit["xp"] = min((MAX_LEVEL - 1) * 100, previous + gain)
        recruit["level"] = 1 + recruit["xp"] // 100
        recruit["stats"]["appearances" if active else "bench_appearances"] += 1
        recruit["stats"]["wins"] += int(won)
        awarded[recruit_id] = recruit["xp"] - previous
    career["rewards"].append({"id": f"xp:{fixture['id']}", "type": "match_experience",
                               "fixture_id": fixture["id"], "xp": awarded,
                               "local_only": True})


def _conclude(career, champion):
    season = _season(career)
    if season["champion"] is not None:
        return
    season["champion"] = champion
    season["completed_at"] = _now()
    career["rewards"].append({"id": f"season:{season['id']}", "type": "season_trophy" if champion == "human"
                               else "season_badge", "season_id": season["id"], "local_only": True,
                               "name": "League Champion" if champion == "human" else "Season Complete"})


def _advance(career):
    season = _season(career)
    for round_number in range(1, 7):
        fixtures = [f for f in season["fixtures"] if f["round"] == round_number]
        human = next(f for f in fixtures if "human" in (f["home"], f["away"]))
        if human["status"] == "completed":
            for f in fixtures:
                if f["status"] == "scheduled":
                    _simulate(season, f)
    if any(f["status"] != "completed" for f in season["fixtures"]):
        return
    if season["champion"]:
        return
    if not season["title_contenders"]:
        table = standings(career)
        top = table[0]
        keys = ("points", "goal_difference", "goals_for", "head_to_head_points")
        tied = [row["id"] for row in table if all(row[k] == top[k] for k in keys)]
        if len(tied) == 1:
            _conclude(career, tied[0])
            return
        season["title_contenders"] = [club for club in season["playoff_draw"] if club in tied]
        draw = season["title_contenders"]
        if len(draw) == 2:
            season["playoffs"].append(_fixture(career, season, draw[0], draw[1], 7, 1, "final"))
        elif len(draw) == 3:
            season["playoffs"].append(_fixture(career, season, draw[1], draw[2], 7, 1, "semifinal"))
        else:
            for index, (home, away) in enumerate(((draw[0], draw[3]), (draw[1], draw[2])), 1):
                season["playoffs"].append(_fixture(career, season, home, away, 7, index, "semifinal"))
    while True:
        for f in season["playoffs"]:
            if f["status"] == "scheduled" and "human" not in (f["home"], f["away"]):
                _simulate(season, f)
        final = next((f for f in season["playoffs"] if f["phase"] == "final"), None)
        if final:
            if final["status"] == "completed":
                _conclude(career, final["result"]["winner"])
            return
        semis = season["playoffs"]
        if any(f["status"] != "completed" for f in semis):
            return
        winners = [f["result"]["winner"] for f in semis]
        if len(season["title_contenders"]) == 3:
            winners.insert(0, season["title_contenders"][0])
        season["playoffs"].append(_fixture(career, season, winners[0], winners[1], 8, 1, "final"))


def complete_fixture(career, fixture_id, session_id, home_score, away_score, provenance="game"):
    """Commit an authoritative final score once; ties and stale attempts are rejected."""
    career = _copy(career)
    _require(_integer(home_score, 0, 999) and _integer(away_score, 0, 999),
             "Final scores must be whole numbers from 0 to 999.")
    _require(home_score != away_score, "A completed Soccar match needs an overtime winner.")
    _require(provenance in ("game", "manual_recovery", "manual"),
             "Human results require game capture or explicitly labeled manual recovery.")
    fixture = next((f for f in _all_fixtures(career) if f["id"] == fixture_id), None)
    _require(fixture is not None and "human" in (fixture["home"], fixture["away"]),
             "This is not a human career fixture.")
    if fixture["status"] == "completed":
        r = fixture["result"]
        _require((r["session_id"], r["home_score"], r["away_score"], r["provenance"]) ==
                 (session_id, home_score, away_score, provenance),
                 "This fixture already has a different final result; it cannot be awarded twice.")
        return career
    _require(career["pending_session"] is not None and fixture["status"] == "pending"
             and career["pending_session"]["fixture_id"] == fixture_id
             and fixture["session_id"] == session_id, "Result does not match the active fixture/session.")
    fixture["result"] = _result(fixture, session_id, home_score, away_score, provenance)
    fixture["status"] = "completed"
    fixture["attempts"][-1]["status"] = "completed"
    fixture["attempts"][-1]["ended_at"] = _now()
    career["pending_session"] = None
    _award_match(career, fixture)
    _advance(career)
    return _finish(career)


def abandon_fixture(career):
    career = _copy(career)
    pending = career["pending_session"]
    if pending is None:
        return career
    fixture = next(f for f in _fixtures(_season(career)) if f["id"] == pending["fixture_id"])
    fixture["status"] = "scheduled"
    fixture["session_id"] = None
    fixture["attempts"][-1]["status"] = "abandoned"
    fixture["attempts"][-1]["ended_at"] = _now()
    career["pending_session"] = None
    return _finish(career)


def _refresh_future(career, update_format=False, update_difficulty=False):
    season = _season(career)
    completed_rounds = {f["round"] for f in season["fixtures"] if f["status"] == "completed"}
    for fixture in _fixtures(season):
        if fixture["status"] != "scheduled":
            continue
        if update_format and fixture["round"] not in completed_rounds:
            fixture["format"] = career["format"]
        if update_difficulty:
            fixture["difficulty"] = _decisions(career, fixture["round"])
            fixture["opponent_starting_level"] = max(1, min(MAX_LEVEL, 1 + int(fixture["difficulty"]["value"] * 4)))
        if "human" in (fixture["home"], fixture["away"]):
            fixture["lineup"] = list(career["lineup"])
            fixture["squad"] = list(career["squad"])
            fixture["recruit_snapshots"] = _snapshot(career, fixture["lineup"])
        fixture["bot_runtime"] = bot_runtime_snapshot(fixture)


def set_lineup(career, recruit_ids):
    career = _copy(career, editable=True)
    _ids(recruit_ids, career["format"] - 1, "Starting lineup")
    _require(set(recruit_ids) <= set(career["squad"]), "Choose starters from your four recruited bots.")
    career["lineup"] = list(recruit_ids)
    _refresh_future(career)
    return _finish(career)


def replace_recruit(career, outgoing_id, incoming_id):
    career = _copy(career, editable=True)
    _require(outgoing_id in career["squad"], "The outgoing recruit is not in this squad.")
    _require(isinstance(incoming_id, str) and incoming_id in career["recruits"]
             and incoming_id not in career["squad"], "Choose an available recruit outside the squad.")
    career["squad"] = [incoming_id if i == outgoing_id else i for i in career["squad"]]
    career["lineup"] = [incoming_id if i == outgoing_id else i for i in career["lineup"]]
    _refresh_future(career)
    return _finish(career)


def rename_recruit(career, recruit_id, name):
    career = _copy(career, editable=True)
    _require(isinstance(recruit_id, str) and recruit_id in career["recruits"], "Unknown recruit.")
    career["recruits"][recruit_id]["name"] = _name(name, "Recruit name")
    _refresh_future(career)
    return _finish(career)


def set_loadout(career, recruit_id, loadout):
    """Store an adapter-validated bot loadout; catalog ownership stays in cosmetics."""
    career = _copy(career, editable=True)
    _require(isinstance(recruit_id, str) and recruit_id in career["recruits"], "Unknown recruit.")
    _validate_loadout(loadout)
    career["recruits"][recruit_id]["loadout"] = deepcopy(loadout)
    _refresh_future(career)
    return _finish(career)


def set_format(career, format):
    career = _copy(career, editable=True)
    _format(format)
    season = _season(career)
    for round_number in range(1, 7):
        statuses = {f["status"] for f in season["fixtures"] if f["round"] == round_number}
        _require(not ("completed" in statuses and "scheduled" in statuses),
                 "Change match format between completed rounds.")
    career["format"] = format
    selected = career["lineup"] + [i for i in career["squad"] if i not in career["lineup"]]
    career["lineup"] = selected[:format - 1]
    _refresh_future(career, update_format=True)
    _settings_change(career)
    return _finish(career)


def _settings_change(career):
    season = _season(career)
    completed = [f["round"] for f in season["fixtures"] if f["status"] == "completed"]
    season["settings_history"].append({"after_round": max(completed, default=0),
                                         "format": career["format"],
                                         "difficulty": deepcopy(career["difficulty"]), "time": _now()})


def set_difficulty(career, baseline, curve):
    career = _copy(career, editable=True)
    career["difficulty"] = _difficulty(baseline, curve)
    _refresh_future(career, update_difficulty=True)
    _settings_change(career)
    return _finish(career)


def start_next_season(career):
    career = _copy(career, editable=True)
    _require(_season(career)["champion"] is not None, "Finish this season and its title playoffs first.")
    number = len(career["seasons"]) + 1
    seed = random.Random(f"{career['seed']}:season:{number}").randrange(2**63)
    career["seasons"].append(_new_season(career, number, seed))
    career["current_season"] += 1
    return _finish(career)


def squad_members(career):
    """Detached UI records, with starter and bench labels including the human."""
    return [{"id": "human", "name": "You", "human": True, "starter": True, "role": "captain"}] + [
        {**deepcopy(career["recruits"][i]), "human": False, "starter": i in career["lineup"]}
        for i in career["squad"]]


def _validate_loadout(loadout):
    _require(isinstance(loadout, dict) and set(loadout) == {"car_id", "primary_color", "secondary_color"},
             "Bot appearance must contain a car and two colors.")
    _require(_integer(loadout["car_id"], 0, 99999)
             and _integer(loadout["primary_color"], 0, 104) and _integer(loadout["secondary_color"], 0, 104),
             "Bot appearance IDs are outside the supported numeric range.")


def validate_career(career):
    """Reject malformed/unsupported imported careers before they replace a valid save.

    Historical lineups are checked against persistent recruit records, not today's
    format/squad. This permits genuine substitutions and format changes over time.
    """
    try:
        # Reject non-JSON extensions and non-finite values even in optional fields.
        json.dumps(career, allow_nan=False)
        _validate(career)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError, RecursionError) as exc:
        raise ValueError("The career save is incomplete or has malformed fields.") from exc
    return True


def _validate(career):
    _require(isinstance(career, dict), "Career save must be an object.")
    _require(type(career["schema_version"]) is int and career["schema_version"] == SCHEMA_VERSION,
             "Unsupported career save version. Keep the original and use a compatible app.")
    _require(isinstance(career["id"], str) and 1 <= len(career["id"]) <= 128, "Missing career identity.")
    _name(career["team_name"], "Team name")
    _format(career["format"])
    _require(_integer(career["seed"]), "Invalid career seed.")
    _difficulty(career["difficulty"]["baseline"], career["difficulty"]["curve"])
    _require(isinstance(career["created_at"], str) and isinstance(career["updated_at"], str),
             "Missing career timestamps.")
    _require(isinstance(career["recruits"], dict) and set(career["recruits"]) == set(DEFAULT_RECRUITS),
             "Career must preserve all five original recruit identities.")
    for key, recruit in career["recruits"].items():
        _require(isinstance(recruit, dict) and recruit["id"] == key
                 and recruit["role"] == DEFAULT_RECRUITS[key]["role"], "Recruit identity or role is invalid.")
        _name(recruit["name"], "Recruit name")
        _require(_integer(recruit["xp"], 0, (MAX_LEVEL - 1) * 100)
                 and _integer(recruit["level"], 1, MAX_LEVEL)
                 and recruit["level"] == 1 + recruit["xp"] // 100, "Recruit level does not match earned experience.")
        _validate_loadout(recruit["loadout"])
        _require(isinstance(recruit["stats"], dict) and all(
            _integer(recruit["stats"][k]) for k in ("appearances", "bench_appearances", "wins")),
            "Recruit statistics are malformed.")
    _ids(career["squad"], 4, "Squad")
    _ids(career["lineup"], career["format"] - 1, "Starting lineup")
    _require(set(career["lineup"]) <= set(career["squad"]), "A starter is not recruited.")
    seasons = career["seasons"]
    _require(isinstance(seasons, list) and 1 <= len(seasons) <= 10000, "Career needs a season history.")
    _require(_integer(career["current_season"], 0, len(seasons) - 1)
             and career["current_season"] == len(seasons) - 1, "The current season index is invalid.")
    fixture_ids, result_ids, session_ids, pending_fixtures = set(), set(), set(), []
    completed_human = []
    champions = []
    for index, season in enumerate(seasons):
        _require(isinstance(season, dict) and season["id"] == f"{career['id']}:s{index + 1}"
                 and season["number"] == index + 1 and _integer(season["seed"]), "Invalid season identity or seed.")
        _require(isinstance(season["clubs"], list) and len(season["clubs"]) == 4
                 and {c["id"] for c in season["clubs"]} == set(CLUB_IDS), "A league needs all four clubs.")
        for club in season["clubs"]:
            _name(club["name"], "Club name")
            _require(type(club["strength"]) in (int, float) and math.isfinite(club["strength"])
                     and 0 <= club["strength"] <= 1, "Invalid recorded club strength.")
        _require(isinstance(season["playoff_draw"], list) and len(season["playoff_draw"]) == 4
                 and set(season["playoff_draw"]) == set(CLUB_IDS), "The persisted title draw is invalid.")
        _require(isinstance(season["fixtures"], list) and len(season["fixtures"]) == 12
                 and isinstance(season["playoffs"], list) and len(season["playoffs"]) <= 3,
                 "The double round-robin schedule or playoff bracket is incomplete.")
        pairings = [(f["home"], f["away"]) for f in season["fixtures"]]
        _require(len(set(pairings)) == 12 and all(h in CLUB_IDS and a in CLUB_IDS and h != a
                                                for h, a in pairings), "League opponents must meet once each way.")
        for r in range(1, 7):
            scheduled = [f for f in season["fixtures"] if f["round"] == r]
            _require(len(scheduled) == 2 and {c for f in scheduled for c in (f["home"], f["away"])}
                     == set(CLUB_IDS), "Each league round needs exactly two distinct matches.")
            _require(len({f["format"] for f in scheduled}) == 1, "Fixtures in one round must share a format.")
            _require(len({f["status"] == "completed" for f in scheduled}) == 1,
                     "A resolved round must preserve its companion simulation.")
            if r > 1 and any(f["status"] != "scheduled" for f in scheduled):
                _require(all(f["status"] == "completed" for f in season["fixtures"] if f["round"] < r),
                         "Later rounds cannot start before earlier rounds finish.")
        contenders = season["title_contenders"]
        _require(isinstance(contenders, list) and len(set(contenders)) == len(contenders)
                 and len(contenders) in (0, 2, 3, 4) and set(contenders) <= set(CLUB_IDS),
                 "Title playoff participants are invalid.")
        if season["playoffs"]:
            _require(all(f["status"] == "completed" for f in season["fixtures"])
                     and len(contenders) >= 2, "Title playoffs require a completed tied league.")
        for fixture in _fixtures(season):
            _validate_fixture(fixture, fixture_ids, result_ids, session_ids)
            if index == career["current_season"] and fixture["status"] != "completed":
                _require(fixture["format"] == career["format"],
                         "Unstarted or pending fixtures must match the current career format.")
            if fixture["status"] == "pending":
                pending_fixtures.append(fixture)
                _require(index == career["current_season"], "An old season cannot have a pending match.")
            if fixture["status"] == "completed" and "human" in (fixture["home"], fixture["away"]):
                completed_human.append(fixture)
        for f in season["fixtures"]:
            _require(f["phase"] == "league" and f["round"] <= 6,
                     "A league fixture has an invalid round or phase.")
        _validate_bracket(career, season, index)
        _require(isinstance(season["settings_history"], list) and season["settings_history"],
                 "The season must preserve its starting settings.")
        for change in season["settings_history"]:
            _require(_integer(change["after_round"], 0, 6) and isinstance(change["time"], str),
                     "Malformed settings history.")
            _format(change["format"])
            _difficulty(change["difficulty"]["baseline"], change["difficulty"]["curve"])
        champion = season["champion"]
        _require(champion is None or champion in CLUB_IDS, "Invalid champion.")
        if champion is not None:
            _require(all(f["status"] == "completed" for f in _fixtures(season)),
                     "A season cannot award its title before every required game is finished.")
            if season["playoffs"]:
                finals = [f for f in season["playoffs"] if f["phase"] == "final"]
                _require(len(finals) == 1 and finals[0]["result"]["winner"] == champion,
                         "The champion must win the title final.")
            else:
                # Use a detached view so historical seasons are ranked independently.
                view = {**career, "current_season": index}
                table = standings(view)
                _require(table[0]["id"] == champion and table[1]["position"] != 1,
                         "A tied league title requires a played playoff.")
            champions.append(season["id"])
        _require(index == len(seasons) - 1 or champion is not None, "Finish previous seasons before continuing.")
    pending = career["pending_session"]
    if pending is None:
        _require(not pending_fixtures, "A pending fixture is missing its recovery session.")
    else:
        _require(isinstance(pending, dict) and len(pending_fixtures) == 1,
                 "A career may have only one pending session.")
        fixture = pending_fixtures[0]
        _require(pending["fixture_id"] == fixture["id"] and pending["session_id"] == fixture["session_id"],
                 "The saved session does not match the pending fixture.")
    rewards = career["rewards"]
    _require(isinstance(rewards, list) and all(isinstance(r, dict) and isinstance(r["id"], str) for r in rewards),
             "Career rewards are malformed.")
    _require(len({r["id"] for r in rewards}) == len(rewards), "A result reward was duplicated.")
    expected_rewards = {f"xp:{f['id']}" for f in completed_human} | {f"season:{s}" for s in champions}
    _require({r["id"] for r in rewards} == expected_rewards, "A completed result has missing or unearned rewards.")
    _validate_progression(career, completed_human, rewards)
    record = career["record"]
    wins = sum(f["result"]["winner"] == "human" for f in completed_human)
    expected_record = {"played": len(completed_human), "wins": wins, "losses": len(completed_human) - wins,
                       "goals_for": sum(f["result"]["home_score"] if f["home"] == "human"
                                        else f["result"]["away_score"] for f in completed_human),
                       "goals_against": sum(f["result"]["away_score"] if f["home"] == "human"
                                            else f["result"]["home_score"] for f in completed_human)}
    _require(isinstance(record, dict) and record == expected_record, "Career record does not match completed games.")


def _validate_bracket(career, season, index):
    """Validate persisted byes, semifinal winners, and final entrants on import."""
    league_finished = all(f["status"] == "completed" for f in season["fixtures"])
    contenders = season["title_contenders"]
    playoffs = season["playoffs"]
    if not league_finished:
        _require(not contenders and not playoffs and season["champion"] is None,
                 "A title playoff cannot precede the completed league.")
        return
    rows = standings({**career, "current_season": index})
    keys = ("points", "goal_difference", "goals_for", "head_to_head_points")
    tied = {row["id"] for row in rows if all(row[k] == rows[0][k] for k in keys)}
    if len(tied) == 1:
        _require(not contenders and not playoffs and season["champion"] == rows[0]["id"],
                 "An untied league must award its earned title directly.")
        return
    expected = [club for club in season["playoff_draw"] if club in tied]
    _require(contenders == expected, "Playoff entrants must match the unresolved league title tie.")
    count = len(contenders)
    if count == 2:
        _require(len(playoffs) == 1 and playoffs[0]["phase"] == "final"
                 and (playoffs[0]["home"], playoffs[0]["away"]) == tuple(contenders),
                 "The two-club title final has invalid entrants.")
    else:
        pairings = ([(contenders[1], contenders[2])] if count == 3 else
                    [(contenders[0], contenders[3]), (contenders[1], contenders[2])])
        semis = [f for f in playoffs if f["phase"] == "semifinal"]
        _require(len(semis) == len(pairings) and
                 [(f["home"], f["away"]) for f in semis] == pairings,
                 "The title semifinal draw is invalid.")
        finals = [f for f in playoffs if f["phase"] == "final"]
        semis_done = all(f["status"] == "completed" for f in semis)
        _require(len(playoffs) == len(semis) + len(finals) and len(finals) == int(semis_done),
                 "The final must follow every completed semifinal.")
        if semis_done:
            winners = [f["result"]["winner"] for f in semis]
            if count == 3:
                winners.insert(0, contenders[0])
            _require((finals[0]["home"], finals[0]["away"]) == tuple(winners),
                     "The title final must contain the semifinal winners and persisted bye.")
    _require(all("human" in (f["home"], f["away"]) or f["status"] == "completed" for f in playoffs),
             "Other-club playoff simulations must be durably resolved.")
    finals = [f for f in playoffs if f["phase"] == "final"]
    if finals and finals[0]["status"] == "completed":
        _require(season["champion"] == finals[0]["result"]["winner"],
                 "A finished title final must award its winner.")


def _validate_progression(career, fixtures, rewards):
    records = {i: {"xp": 0, "appearances": 0, "bench_appearances": 0, "wins": 0}
               for i in DEFAULT_RECRUITS}
    by_id = {reward["id"]: reward for reward in rewards}
    for f in fixtures:
        won = f["result"]["winner"] == "human"
        expected = {}
        for recruit_id in f["squad"]:
            row = records[recruit_id]
            active = recruit_id in f["lineup"]
            if active:
                _require(f["recruit_snapshots"][recruit_id]["level"] == 1 + row["xp"] // 100,
                         "Recorded starting bot level does not match its earned progress.")
            gain = (35 if active else 12) + ((10 if active else 4) if won else 0)
            actual = min(gain, (MAX_LEVEL - 1) * 100 - row["xp"])
            row["xp"] += actual
            row["appearances" if active else "bench_appearances"] += 1
            row["wins"] += int(won)
            expected[recruit_id] = actual
        reward = by_id[f"xp:{f['id']}"]
        _require(reward["type"] == "match_experience" and reward["fixture_id"] == f["id"]
                 and reward["xp"] == expected and reward["local_only"] is True,
                 "Experience reward does not match its completed fixture.")
    for recruit_id, row in records.items():
        recruit = career["recruits"][recruit_id]
        _require(recruit["xp"] == row["xp"] and recruit["stats"] == {
            key: row[key] for key in ("appearances", "bench_appearances", "wins")},
            "Recruit progress does not match earned match and bench experience.")


def _validate_fixture(f, fixture_ids, result_ids, session_ids):
    _require(isinstance(f, dict) and isinstance(f["id"], str) and f["id"] not in fixture_ids,
             "Duplicate or invalid fixture identity.")
    fixture_ids.add(f["id"])
    _require(f["home"] in CLUB_IDS and f["away"] in CLUB_IDS and f["home"] != f["away"],
             "A fixture has invalid clubs.")
    _format(f["format"])
    _require(f["map"] in MAPS and _integer(f["round"], 1, 8) and _integer(f["seed"]),
             "A fixture has invalid map, round, or seed.")
    _require(f["phase"] in ("league", "semifinal", "final"), "Unknown fixture phase.")
    _difficulty(f["difficulty"]["baseline"], f["difficulty"]["curve"])
    stage = min(1.0, (f["round"] - 1) / 5)
    increment = {"flat": 0, "gentle": 0.12, "steep": 0.25}[f["difficulty"]["curve"].lower()]
    _require(f["difficulty"]["stage"] == stage and f["difficulty"]["value"] == round(
        min(1, f["difficulty"]["baseline"] + increment * stage), 4),
        "The fixture difficulty does not match its recorded baseline and season curve.")
    _require(type(f["difficulty"]["value"]) in (int, float) and math.isfinite(f["difficulty"]["value"])
             and 0 <= f["difficulty"]["value"] <= 1, "Invalid recorded fixture difficulty.")
    human = "human" in (f["home"], f["away"])
    _ids(f["lineup"], f["format"] - 1 if human else 0, "Historical starting lineup")
    _ids(f["squad"], 4 if human else 0, "Historical squad")
    _require(set(f["lineup"]) <= set(f["squad"]), "Historical starter was not in that fixture's squad.")
    _require(isinstance(f["recruit_snapshots"], dict) and set(f["recruit_snapshots"]) == set(f["lineup"]),
             "Missing starting capability snapshot.")
    for key, snapshot in f["recruit_snapshots"].items():
        _require(snapshot["id"] == key and snapshot["role"] == DEFAULT_RECRUITS[key]["role"]
                 and _integer(snapshot["level"], 1, MAX_LEVEL), "Invalid historical bot capability.")
        _name(snapshot["name"])
        _validate_loadout(snapshot["loadout"])
    _require(isinstance(f["provider"], dict) and f["provider"] == policy_manifest(f["provider"].get("id")),
             "Unknown bot provider/version in the saved fixture.")
    _require(f["provider"]["id"] == PROVIDER_ID or f["format"] <= 3,
             "Learned bot policies do not support 4v4.")
    _require(_integer(f["opponent_starting_level"], 1, MAX_LEVEL)
             and f["duration_seconds"] == 300 and f["overtime"] is True, "Invalid match rules or bot level.")
    _require(f["bot_runtime"] == bot_runtime_snapshot(f),
             "Recorded bot runtime settings do not match this fixture's controllers.")
    _require(f["status"] in ("scheduled", "pending", "completed"), "Unknown fixture status.")
    _require(isinstance(f["attempts"], list), "Fixture attempts are malformed.")
    for attempt in f["attempts"]:
        sid = attempt["session_id"]
        _require(isinstance(sid, str) and 1 <= len(sid) <= 128 and sid not in session_ids,
                 "Duplicate match session ID.")
        session_ids.add(sid)
        _require(attempt["status"] in ("abandoned", "pending", "completed"), "Unknown match attempt status.")
    if f["status"] == "scheduled":
        _require(f["result"] is None and f["session_id"] is None
                 and all(a["status"] == "abandoned" for a in f["attempts"]),
                 "An unplayed fixture cannot have a result, active attempt, or rewards.")
    elif f["status"] == "pending":
        _require(human and f["result"] is None and f["attempts"]
                 and f["attempts"][-1]["status"] == "pending"
                 and f["attempts"][-1]["session_id"] == f["session_id"]
                 and all(a["status"] == "abandoned" for a in f["attempts"][:-1]),
                 "Pending fixture recovery data is inconsistent.")
    else:
        r = f["result"]
        _require(isinstance(r, dict) and r["id"] == f"result:{f['id']}:{f['session_id']}"
                 and r["id"] not in result_ids and r["fixture_id"] == f["id"]
                 and r["session_id"] == f["session_id"], "Completed result identity is inconsistent.")
        result_ids.add(r["id"])
        _require(_integer(r["home_score"], 0, 999) and _integer(r["away_score"], 0, 999)
                 and r["home_score"] != r["away_score"], "Completed games need an untied final score.")
        _require(r["winner"] == (f["home"] if r["home_score"] > r["away_score"] else f["away"]),
                 "Result winner does not match the final score.")
        _require(all(r[k] == f[k] for k in ("format", "map", "lineup", "difficulty", "seed", "bot_runtime")),
                 "Result settings do not match the played fixture.")
        _require((human and r["provenance"] in ("game", "manual", "manual_recovery")
                  and r["simulated"] is False) or
                 (not human and r["provenance"] == "simulated" and r["simulated"] is True),
                 "Simulated games cannot be represented as real human matches.")
        if human:
            _require(f["attempts"] and f["attempts"][-1]["status"] == "completed"
                     and f["attempts"][-1]["session_id"] == f["session_id"]
                     and all(a["status"] == "abandoned" for a in f["attempts"][:-1]),
                     "A completed human match needs its original session.")
        else:
            _require(not f["attempts"] and f["session_id"] == f"sim:{f['seed']}",
                     "Simulations must preserve their recorded seed and provenance.")
            _require(f["session_id"] not in session_ids, "Duplicate simulated match session ID.")
            session_ids.add(f["session_id"])
