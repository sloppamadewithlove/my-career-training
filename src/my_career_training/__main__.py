"""The installed GUI and console worker have explicit, separate entry modes."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile


def self_test():
    from . import career
    from .storage import Store, default_state
    from .training import catalog
    from .bots import SpecialistController
    with tempfile.TemporaryDirectory(prefix="MCT self-test é ") as directory:
        with Store(directory) as store:
            state = default_state()
            state["career"] = career.new_career("Package check")
            store.save(state)
            assert store.load()["career"]["team_name"] == "Package check"
            assert len(state["career"]["seasons"][0]["fixtures"]) == 12
        assert len(catalog()) == 8
        assert SpecialistController("keeper").manifest()
        if sys.platform == "win32":
            from rlbot import flat
            from rlbot.interface import SocketRelay
            from rlbot.managers.match import MatchManager
            from rlbot.managers.rendering import Renderer
            from .adapter import match_config, desired_state
            from .training import configure_lesson
            assert all(callable(value) for value in (SocketRelay, MatchManager, Renderer))
            config, _, human = match_config({"fixture": career.next_fixture(state["career"]),
                                             "settings": {"launcher": "steam"}})
            assert len(flat.MatchConfiguration.unpack(config.pack()).player_configurations) == 6
            lesson = configure_lesson("speed-flip")
            assert desired_state(lesson["starting_state"], human).pack()
    return 0


def main():
    parser = argparse.ArgumentParser(description="My Career Training")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.worker:
        from .game_worker import main as worker_main
        return worker_main()
    from .storage import data_dir
    from .app import run
    return run(args.data_dir or data_dir(), args.smoke_test, args.screenshot)


if __name__ == "__main__":
    raise SystemExit(main())
