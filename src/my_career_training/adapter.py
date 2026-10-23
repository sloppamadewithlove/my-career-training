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


def match_config(request):
    from .map_guard import refuse_custom_map_launch
    refuse_custom_map_launch(request)
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
    if not training:
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
    config = f.MatchConfiguration(launcher=f.Launcher.NoLaunch if request.get("owned_game") else (f.Launcher.Steam if launcher == "steam" else f.Launcher.Epic),
        launcher_arg="", auto_start_agents=False, wait_for_agents=True, game_map_upk=arena,
        player_configurations=players, script_configurations=[], game_mode=f.GameMode.Soccar,
        skip_replays=training, instant_start=training, mutators=mutators,
        existing_match_behavior=f.ExistingMatchBehavior.Restart, enable_rendering=f.DebugRendering.OnByDefault,
        enable_state_setting=bool(request.get("lesson_id")), auto_save_replay=False, freeplay=training,
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


def desired_state(state, human_index):
    f = flat_module()
    from rlbot.utils import fill_desired_game_state
    def body(data):
        return f.DesiredPhysics(location=f.Vector3Partial(*data["position"]),
            velocity=f.Vector3Partial(*data.get("velocity", [0, 0, 0])),
            rotation=f.RotatorPartial(*data.get("rotation", [0, 0, 0])),
            angular_velocity=f.Vector3Partial(*data.get("angular_velocity", [0, 0, 0])))
    # b56's convenience set_game_state passes an obsolete fourth argument. The
    # public relay and three-argument builder match the current schema.
    return fill_desired_game_state(
        balls={0: f.DesiredBallState(physics=body(state["ball"]))},
        cars={human_index: f.DesiredCarState(physics=body(state["car"]), boost_amount=state["car"].get("boost", 100))},
        match_info=None)


def final_score(packet, seen_active):
    f = flat_module()
    if not seen_active or packet.match_info.match_phase != f.MatchPhase.Ended:
        return None
    scores = {t.team_index: t.score for t in packet.teams}
    if set(scores) != {0, 1} or scores[0] == scores[1]:
        return None
    return scores[0], scores[1]
