"""RLBot v5 b56/flatbuffers 0.19 contract; imported only in the Windows worker."""
from __future__ import annotations

from pathlib import Path

CORE_VERSION = "v5.0.0-rc18"
CORE_SHA256 = "454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1"
SDK_VERSION = "2.0.0b56"
ARENAS = {"DFHStadium", "DFHStadium_P", "Mannfield", "EuroStadium_P", "ChampionsField", "CS_P",
          "UtopiaColiseum", "UtopiaStadium_P", "BeckwithPark", "Park_P"}
MAPS = {"DFHStadium": "Stadium_P", "DFHStadium_P": "Stadium_P", "Mannfield": "EuroStadium_P",
        "ChampionsField": "CS_P", "UtopiaColiseum": "UtopiaStadium_P", "BeckwithPark": "Park_P"}


def flat_module():
    from rlbot import flat
    return flat


def capture_descriptor(capture):
    """Descriptor for the single known development capture bot.

    The existing controller construction and team mapping read exactly these
    fields, so the capture bot reuses the ordinary bot path instead of a
    bot-only configuration. The Human stays present and uncontrolled.
    """
    return {
        "name": "Development Capture Bot",
        "team": 0,
        "role": "all-rounder",
        "level": 1,
        "difficulty": .5,
        "seed": 0,
        "loadout": {"car_id": 23, "primary_color": 27, "secondary_color": 0},
        "capture_profile": capture["profile"],
        "capture_trial_id": capture["trial_id"],
    }


def match_config(request):
    from .map_guard import refuse_custom_map_launch
    refuse_custom_map_launch(request)
    # The capture gate runs here as well as in the worker setup, so a caller
    # cannot obtain a capture match layout without passing every gate.
    from .reference_capture import validate_capture_request
    capture = validate_capture_request(request)
    # An explicit scenario is validated before any match layout is built. The
    # capture gate above already rejected capture+scenario combinations.
    scenario = None
    if request.get("scenario_id") is not None:
        from .training.scenarios import scenario_descriptors
        scenario = scenario_descriptors(request)
    f = flat_module()
    fixture = request.get("fixture") or {}
    training = bool(request.get("lesson_id"))
    size = 1 if training else fixture["format"]
    if type(size) is not int or size not in range(1, 5):
        raise ValueError("Only 1v1 through 4v4 Soccar is supported.")
    launcher = request["settings"]["launcher"]
    if launcher not in ("steam", "epic"):
        raise ValueError("Choose Steam or Epic.")
    human_team = 0 if training or fixture.get("home") == "human" else 1
    players, descriptors = [], {}
    if capture is not None:
        # Exactly one known CustomBot before the Human: bot index 0, Human
        # index 1, both on the known team 0. Ordinary training keeps one Human
        # and no bots; Career is unchanged.
        descriptor = capture_descriptor(capture)
        loadout = descriptor["loadout"]
        variety = f.CustomBot(name=descriptor["name"], root_dir=str(Path.cwd()), run_command="",
            agent_id="my-career-training/team-0", hivemind=True,
            loadout=f.PlayerLoadout(car_id=loadout.get("car_id", 23), wheels_id=376,
                team_color_id=loadout.get("primary_color", 27),
                custom_color_id=loadout.get("secondary_color", 0)))
        descriptors[0] = descriptor
        players.append(f.PlayerConfiguration(variety=variety, team=descriptor["team"]))
    elif scenario is not None:
        # Explicit ball-launch scenario: zero or one known keeper, then the
        # Human appended last. No caller-supplied actor data is used.
        for index in sorted(scenario):
            descriptor = scenario[index]
            loadout = descriptor["loadout"]
            variety = f.CustomBot(name=descriptor["name"], root_dir=str(Path.cwd()), run_command="",
                agent_id=f"my-career-training/team-{descriptor['team']}", hivemind=True,
                loadout=f.PlayerLoadout(car_id=loadout.get("car_id", 23), wheels_id=376,
                    team_color_id=loadout.get("primary_color", 27),
                    custom_color_id=loadout.get("secondary_color", 0)))
            descriptors[index] = descriptor
            players.append(f.PlayerConfiguration(variety=variety, team=descriptor["team"]))
    elif not training:
        from .career import bot_runtime_snapshot
        for bot in bot_runtime_snapshot(fixture):
            team, loadout = bot["team"], bot["loadout"]
            variety = f.CustomBot(name=bot["name"], root_dir=str(Path.cwd()), run_command="",
                agent_id=f"my-career-training/team-{team}", hivemind=True,
                loadout=f.PlayerLoadout(car_id=loadout.get("car_id", 23), wheels_id=376,
                    team_color_id=loadout.get("primary_color", 27),
                    custom_color_id=loadout.get("secondary_color", 0)))
            descriptors[len(players)] = bot
            players.append(f.PlayerConfiguration(variety=variety, team=team))
    # The core moves the human last. Build that layout explicitly to avoid remapping.
    players.append(f.PlayerConfiguration(variety=f.Human(), team=human_team))
    arena = fixture.get("map", "Stadium_P")
    arena = MAPS.get(arena, arena)
    if arena not in {"Stadium_P", "EuroStadium_P", "CS_P", "UtopiaStadium_P", "Park_P"}:
        raise ValueError(f"Unsupported built-in arena: {arena}")
    mutators = f.MutatorSettings(match_length=f.MatchLengthMutator.Unlimited if training else f.MatchLengthMutator.FiveMinutes,
        max_score=f.MaxScoreMutator.Unlimited, overtime=f.OvertimeMutator.Unlimited,
        multi_ball=f.MultiBallMutator.One, boost_amount=f.BoostAmountMutator.NormalBoost)
    if request.get("lesson_id") == "power-shots" and capture is None:
        # Use the RLBot match mutator, not the shipped SDK's no-op reset methods.
        # Exact native no-kickoff behavior still requires the owned game test.
        mutators.respawn_time = f.RespawnTimeMutator.DisableGoalReset
    config = f.MatchConfiguration(launcher=f.Launcher.NoLaunch if request.get("owned_game") else (f.Launcher.Steam if launcher == "steam" else f.Launcher.Epic),
        launcher_arg="", auto_start_agents=False, wait_for_agents=True, game_map_upk=arena,
        player_configurations=players, script_configurations=[], game_mode=f.GameMode.Soccar,
        skip_replays=training, instant_start=training, mutators=mutators,
        existing_match_behavior=f.ExistingMatchBehavior.Restart, enable_rendering=f.DebugRendering.OnByDefault,
        # Human drills use an unlimited offline match so shots can score. Keep
        # development capture's existing Free Play context unchanged.
        enable_state_setting=bool(request.get("lesson_id")), auto_save_replay=False,
        freeplay=training and capture is not None,
        performance_monitor=f.PerformanceMonitor.NeverShow)
    return config, descriptors, len(players) - 1


def vector(v):
    return [float(v.x), float(v.y), float(v.z)]


def physics(p):
    return {"position": vector(p.location), "velocity": vector(p.velocity),
            "rotation": [p.rotation.pitch, p.rotation.yaw, p.rotation.roll],
            "angular_velocity": vector(p.angular_velocity)}


def normalized_packet(packet, prediction=None, field_info=None):
    f = flat_module()
    cars = []
    for index, player in enumerate(packet.players):
        car = dict(physics(player.physics), index=index, player_index=index, team=player.team,
                   boost=player.boost, wheel_contact=player.air_state == f.AirState.OnGround,
                   air_state=str(player.air_state).split(".")[-1], has_jumped=player.has_jumped,
                   has_double_jumped=player.has_double_jumped, has_dodged=player.has_dodged,
                   dodge_timeout=player.dodge_timeout, is_bot=player.is_bot,
                   is_demolished=getattr(player, "demolished_timeout", 0) > 0)
        car["dodge_dir"] = [player.dodge_dir.x, player.dodge_dir.y]
        touch = player.latest_touch
        if touch is not None:
            car["latest_touch"] = {"game_seconds": touch.game_seconds, "position": vector(touch.location),
                                   "normal": vector(touch.normal), "ball_index": touch.ball_index}
        car["actions"] = {key: getattr(player.last_input, key) for key in
                           ("throttle", "steer", "pitch", "yaw", "roll", "jump", "boost", "handbrake")}
        cars.append(car)
    boosts = []
    if field_info is not None:
        for index, pad in enumerate(field_info.boost_pads):
            if index < len(packet.boost_pads):
                boosts.append({"position": vector(pad.location), "active": packet.boost_pads[index].is_active,
                               "is_full": pad.is_full_boost})
    predictions = []
    if prediction is not None:
        predictions = [{"time": s.game_seconds, "position": vector(s.physics.location)}
                       for s in prediction.slices[::6]]
    return {"time": packet.match_info.seconds_elapsed, "frame_num": packet.match_info.frame_num,
            "is_kickoff": packet.match_info.match_phase == f.MatchPhase.Kickoff,
            "game_speed": packet.match_info.game_speed, "cars": cars, "boosts": boosts,
            "ball": physics(packet.balls[0].physics) if packet.balls else {}, "prediction": predictions}


def desired_state(state, human_index, bot_states=None):
    """Whole-actor desired state in one write.

    ``bot_states`` is an optional bounded mapping of bot index -> actor state.
    Indexes must be non-negative integers that do not overlap the Human, and
    every actor is written together so a reset cannot half-apply.
    """
    f = flat_module()
    from rlbot.utils import fill_desired_game_state
    if type(human_index) is not int or human_index < 0:
        raise ValueError("A non-negative integer Human index is required.")
    if bot_states is None:
        bot_states = {}
    if not isinstance(bot_states, dict):
        raise ValueError("Bot states must be a mapping of bot index to actor state.")
    cars = {}
    for index, actor in bot_states.items():
        if type(index) is not int or index < 0 or index == human_index:
            raise ValueError("Bot indexes must be non-negative integers that do not overlap the Human.")
        if not isinstance(actor, dict) or not isinstance(actor.get("position"), (list, tuple)):
            raise ValueError("Every bot state needs an observed position.")
        cars[index] = actor
    def body(data):
        return f.DesiredPhysics(location=f.Vector3Partial(*data["position"]),
            velocity=f.Vector3Partial(*data.get("velocity", [0, 0, 0])),
            rotation=f.RotatorPartial(*data.get("rotation", [0, 0, 0])),
            angular_velocity=f.Vector3Partial(*data.get("angular_velocity", [0, 0, 0])))
    # b56's convenience set_game_state passes an obsolete fourth argument. The
    # public relay and three-argument builder match the current schema.
    desired = {index: f.DesiredCarState(physics=body(actor), boost_amount=actor.get("boost", 100))
               for index, actor in cars.items()}
    desired[human_index] = f.DesiredCarState(physics=body(state["car"]),
                                             boost_amount=state["car"].get("boost", 100))
    return fill_desired_game_state(
        balls={0: f.DesiredBallState(physics=body(state["ball"]))},
        cars=desired,
        match_info=None)


def observed_score(packet):
    """Return home/away goals by explicit team index, never array position."""
    teams = getattr(packet, "teams", None)
    if not isinstance(teams, (list, tuple)) or len(teams) != 2:
        return None
    scores = {}
    for team in teams:
        index, score = getattr(team, "team_index", None), getattr(team, "score", None)
        if (type(index) is not int or index not in (0, 1) or index in scores
                or type(score) is not int or not 0 <= score <= 999):
            return None
        scores[index] = score
    return scores[0], scores[1]


def final_score(packet, seen_active):
    f = flat_module()
    if not seen_active or packet.match_info.match_phase != f.MatchPhase.Ended:
        return None
    scores = observed_score(packet)
    if scores is None or scores[0] == scores[1]:
        return None
    return scores
