"""Development host trial; never adds a shared BakkesMod autoload entry.

prepare validates and describes the trial without changing BakkesMod. launch
stages one uniquely named diagnostic DLL and opens one owned offline game.
finish requires that game to be closed and removes only that unchanged DLL.
This does not certify menu rewriting, gameplay, isolation, or online behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from my_career_training import bootstrap  # noqa: E402
from my_career_training.platforms import ProcessIdentity, game_processes  # noqa: E402
from verify_game_files import _root, load_baseline  # noqa: E402

OBSERVED_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, indent=2)
        target.write("\n")


def configuration_hashes(root):
    """Record identities only. Never put passwords or config contents in reports."""
    cfg = root / "cfg"
    _root(cfg)
    result = {}
    pending, count = [cfg], 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1
                if count > 2048:
                    raise RuntimeError("BakkesMod configuration exceeds the trial's inspection limit")
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise RuntimeError("Linked BakkesMod configuration is not supported by this trial")
                path = Path(entry.path)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    if info.st_size > 8 * 1024 * 1024:
                        raise RuntimeError("A BakkesMod configuration file exceeds the trial limit")
                    result[path.relative_to(cfg).as_posix()] = digest(path)
                else:
                    raise RuntimeError("Non-ordinary BakkesMod configuration cannot be inspected")
    return result


def prepare(game, baseline):
    game = _root(game)
    settings = {"launcher": "steam", "install_path": str(game / "Binaries/Win64/RocketLeague.exe")}
    executable = bootstrap.preflight_offline(settings)
    receipt = load_baseline(baseline, game)
    relative = executable.relative_to(game).as_posix()
    if (receipt["files"].get(relative, {}).get("sha256") != OBSERVED_SHA256
            or digest(executable) != OBSERVED_SHA256):
        raise RuntimeError("The game differs from this diagnostic's observed executable")
    bakkes = bootstrap.bakkes_ready()
    if bakkes is None:
        raise RuntimeError("The installed BakkesMod host is not ready")
    bakkes = _root(bakkes)
    _root(bakkes / "plugins")
    if (bakkes / "version.txt").read_text(encoding="utf-8").strip() != "229":
        raise RuntimeError("This diagnostic requires the observed BakkesMod version 229")
    plugin = ROOT / "build/plugin/Release/MCTNativeHostProbe.dll"
    if not plugin.is_file():
        raise RuntimeError("Build the development host probe first")
    output_root = _root(ROOT / "build/plugin")
    nonce = str(uuid.uuid4())
    parent = output_root / "mct-host-probes"
    parent.mkdir(exist_ok=True)
    _root(parent)
    directory = parent / nonce
    directory.mkdir()
    name = "MCTHostProbe_" + nonce.replace("-", "")
    record = {"schema_version": 1, "kind": "native_host_trial_plan", "nonce": nonce,
              "game": str(game), "executable": str(executable), "baseline": str(baseline.resolve()),
              "bakkes": str(bakkes), "source_dll": str(plugin), "dll_sha256": digest(plugin),
              "destination": str(bakkes / "plugins" / (name + ".dll")), "plugin_name": name,
              "configuration_before": configuration_hashes(bakkes), "autoload_modified": False,
              "menu_rewrite_verified": False}
    write_new(directory / "plan.json", record)
    return directory, record


def read_plan(directory):
    directory = _root(directory)
    if directory.parent != (ROOT / "build/plugin/mct-host-probes").resolve():
        raise RuntimeError("Not a host trial directory")
    if str(uuid.UUID(directory.name)) != directory.name:
        raise RuntimeError("Invalid trial identity")
    path = directory / "plan.json"
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise RuntimeError("Invalid trial plan")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if (plan.get("kind") != "native_host_trial_plan" or plan.get("nonce") != directory.name
            or plan.get("schema_version") != 1):
        raise RuntimeError("Trial plan does not match its directory")
    bakkes = _root(Path(plan["bakkes"]))
    expected_name = "MCTHostProbe_" + directory.name.replace("-", "")
    expected_path = bakkes / "plugins" / (expected_name + ".dll")
    _root(expected_path.parent)
    if plan["destination"] != str(expected_path) or plan["plugin_name"] != expected_name:
        raise RuntimeError("Trial destination does not match its identity")
    return plan


def launch(directory):
    import subprocess
    plan = read_plan(directory)
    if (directory / "launch-attempt.json").exists() or (directory / "session.json").exists():
        raise RuntimeError("This trial already attempted a launch; prepare a new trial")
    settings = {"launcher": "steam", "install_path": plan["executable"]}
    executable = bootstrap.preflight_offline(settings)
    if digest(executable) != OBSERVED_SHA256:
        raise RuntimeError("Executable changed after trial preparation")
    source = Path(plan["source_dll"])
    if source != ROOT / "build/plugin/Release/MCTNativeHostProbe.dll" or digest(source) != plan["dll_sha256"]:
        raise RuntimeError("Diagnostic DLL changed after trial preparation")
    if configuration_hashes(Path(plan["bakkes"])) != plan["configuration_before"]:
        raise RuntimeError("BakkesMod configuration changed after trial preparation; prepare again")
    write_new(directory / "launch-attempt.json", {"at": time.time()})
    destination = Path(plan["destination"])
    with destination.open("xb") as target:
        target.write(source.read_bytes())
    bootstrap.ensure_injector_running()
    bootstrap.preflight_offline(settings)
    env = dict(os.environ, SteamAppId="252950", SteamGameId="252950",
               MCT_HOST_PROBE_DIRECTORY=str(directory))
    process = subprocess.Popen([str(executable), "-noeac", "-rlbot", "-nomovie"],
                               cwd=executable.parent, env=env, shell=False)
    created = psutil.Process(process.pid).create_time()
    issued = time.time()
    write_new(directory / "session.json", {"protocol": 1, "kind": "mct_native_host_probe",
              "nonce": plan["nonce"], "pid": process.pid, "created": created,
              "executable_sha256": OBSERVED_SHA256, "issued_at": issued, "expires_at": issued + 300})
    return {"pid": process.pid, "created": created, "load_command": "plugin load " + plan["plugin_name"],
            "unload_command": "plugin unload " + plan["plugin_name"], "expires_at": issued + 300}


def finish(directory):
    plan = read_plan(directory)
    if game_processes():
        raise RuntimeError("Close Rocket League normally before finishing this trial")
    destination = Path(plan["destination"])
    if destination.is_symlink() or destination.is_junction():
        raise RuntimeError("Trial DLL became a link; leave it for manual review")
    if destination.exists():
        if digest(destination) != plan["dll_sha256"]:
            raise RuntimeError("Trial DLL changed; leave it for manual review")
        destination.unlink()
    before = plan["configuration_before"]
    after = configuration_hashes(Path(plan["bakkes"]))
    result = {"schema_version": 1, "trial_dll_removed": True,
              "configuration_unchanged": before == after,
              "changed_configuration_files": sorted(k for k in before.keys() | after.keys()
                                                    if before.get(k) != after.get(k)),
              "game_files_verified_after": False, "menu_rewrite_verified": False}
    write_new(directory / "finished.json", result)
    return result


def command_context(directory, port):
    """Validate the owned game's existing local listener, without changing RCON."""
    plan = read_plan(directory)
    session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    now = time.time()
    if (session.get("kind") != "mct_native_host_probe" or session.get("nonce") != plan["nonce"]
            or not session.get("issued_at", float("inf")) <= now <= session.get("expires_at", 0)
            or session["expires_at"] - session["issued_at"] > 300):
        raise RuntimeError("The diagnostic session is missing or expired")
    identity = ProcessIdentity(session["pid"], session["created"], plan["executable"])
    if not bootstrap.verify_owned_offline(identity):
        raise RuntimeError("The diagnostic's owned offline game is not running")
    if not 1024 <= port <= 65535:
        raise RuntimeError("RCON port is outside the diagnostic's allowed range")
    sockets = psutil.Process(identity.pid).net_connections(kind="tcp")
    if not any(s.status == psutil.CONN_LISTEN and s.laddr.port == port
               and s.laddr.ip in ("127.0.0.1", "0.0.0.0") for s in sockets):
        raise RuntimeError("The local RCON listener does not belong to the diagnostic game")
    return {"owned_listener": True, "plugin_name": plan["plugin_name"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--game-dir", type=Path, required=True)
    prep.add_argument("--baseline", type=Path, required=True)
    for command in ("launch", "finish"):
        commands.add_parser(command).add_argument("directory", type=Path)
    command = commands.add_parser("command-context")
    command.add_argument("directory", type=Path)
    command.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        directory, plan = prepare(args.game_dir, args.baseline)
        print(json.dumps({"directory": str(directory), "plugin_name": plan["plugin_name"],
                          "dll_sha256": plan["dll_sha256"], "game_launched": False}, indent=2))
    elif args.command == "command-context":
        print(json.dumps(command_context(args.directory, args.port)))
    else:
        print(json.dumps(launch(args.directory) if args.command == "launch" else finish(args.directory), indent=2))


if __name__ == "__main__":
    main()
