"""The installed GUI and console worker have explicit, separate entry modes."""
from __future__ import annotations

import argparse
from pathlib import Path
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
    return 0


def main():
    parser = argparse.ArgumentParser(description="My Career Training")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if args.worker:
        from .game_worker import main as worker_main
        return worker_main()
    if args.self_test:
        return self_test()
    from .storage import data_dir
    from .app import run
    return run(args.data_dir or data_dir(), args.smoke_test, args.screenshot)


if __name__ == "__main__":
    raise SystemExit(main())
