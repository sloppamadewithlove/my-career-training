"""The native-host trial harness stays inside its prepared temporary fixture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "native_host_trial.py"
SPEC = importlib.util.spec_from_file_location("native_host_trial", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
trial = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(SCRIPT.parent))
try:
    SPEC.loader.exec_module(trial)
finally:
    sys.path.remove(str(SCRIPT.parent))


def _world(tmp_path: Path, *, create_trial: bool = True) -> SimpleNamespace:
    root = tmp_path / "project"
    build = root / "build" / "plugin"
    source = build / "Release" / "MCTNativeHostProbe.dll"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"diagnostic dll bytes")

    game = tmp_path / "game"
    executable = game / "Binaries" / "Win64" / "RocketLeague.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"fixture executable bytes")

    bakkes = tmp_path / "bakkes-host"
    (bakkes / "plugins").mkdir(parents=True)
    (bakkes / "cfg").mkdir()
    (bakkes / "version.txt").write_text("229\n", encoding="utf-8")
    cfg = bakkes / "cfg" / "plugins.cfg"
    cfg.write_bytes(b"plugin load existing\n")

    trial.ROOT = root
    trial.OBSERVED_SHA256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    executable_relative = "Binaries/Win64/RocketLeague.exe"
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({
        "format": "mct-game-files-v1",
        "root": str(game.resolve()),
        "complete": True,
        "errors": [],
        "files": {executable_relative: {
            "size": executable.stat().st_size,
            "sha256": trial.OBSERVED_SHA256,
        }},
    }), encoding="utf-8")

    probe_root = build / "mct-host-probes"
    directory = probe_root / str(uuid.uuid4()) if create_trial else probe_root
    if create_trial:
        directory.mkdir(parents=True)
    name = "MCTHostProbe_" + directory.name.replace("-", "")
    destination = bakkes / "plugins" / (name + ".dll")
    record = {
        "schema_version": 1,
        "kind": "native_host_trial_plan",
        "nonce": directory.name,
        "game": str(game),
        "executable": str(executable),
        "baseline": str(baseline.resolve()),
        "bakkes": str(bakkes),
        "source_dll": str(source),
        "dll_sha256": trial.digest(source),
        "destination": str(destination),
        "plugin_name": name,
        "configuration_before": trial.configuration_hashes(bakkes),
        "autoload_modified": False,
        "menu_rewrite_verified": False,
    }
    if create_trial:
        (directory / "plan.json").write_text(json.dumps(record), encoding="utf-8")
    return SimpleNamespace(
        root=root,
        build=build,
        source=source,
        game=game,
        executable=executable,
        bakkes=bakkes,
        cfg=cfg,
        baseline=baseline,
        directory=directory,
        destination=destination,
        plan=record,
    )


def _mock_host(monkeypatch, world, *, running=False):
    monkeypatch.setattr(trial.bootstrap, "preflight_offline", lambda _settings: world.executable)
    monkeypatch.setattr(trial.bootstrap, "bakkes_ready", lambda: world.bakkes)
    monkeypatch.setattr(trial.bootstrap, "ensure_injector_running", lambda: None)
    monkeypatch.setattr(trial, "game_processes", lambda: [object()] if running else [])


@pytest.mark.parametrize("baseline_state", ["missing", "incomplete"])
def test_prepare_rejects_missing_or_incomplete_baseline_without_staging(
    tmp_path, monkeypatch, baseline_state
):
    world = _world(tmp_path, create_trial=False)
    if baseline_state == "missing":
        world.baseline.unlink()
    else:
        world.baseline.write_text(json.dumps({
            "format": "mct-game-files-v1",
            "root": str(world.game.resolve()),
            "complete": False,
            "errors": ["incomplete"],
            "files": {},
        }), encoding="utf-8")
    _mock_host(monkeypatch, world)
    bakkes_calls = []
    monkeypatch.setattr(trial.bootstrap, "bakkes_ready", lambda: bakkes_calls.append(True))

    expected = FileNotFoundError if baseline_state == "missing" else ValueError
    with pytest.raises(expected):
        trial.prepare(world.game, world.baseline)

    assert not (world.build / "mct-host-probes").exists()
    assert not bakkes_calls
    assert not world.destination.exists()


@pytest.mark.parametrize("hash_mismatch", ["baseline", "executable"])
def test_prepare_rejects_a_different_executable_hash_without_trial_output(
    tmp_path, monkeypatch, hash_mismatch
):
    world = _world(tmp_path, create_trial=False)
    _mock_host(monkeypatch, world)
    if hash_mismatch == "baseline":
        baseline = json.loads(world.baseline.read_text(encoding="utf-8"))
        baseline["files"]["Binaries/Win64/RocketLeague.exe"]["sha256"] = "0" * 64
        world.baseline.write_text(json.dumps(baseline), encoding="utf-8")
    else:
        baseline = json.loads(world.baseline.read_text(encoding="utf-8"))
        baseline["files"]["Binaries/Win64/RocketLeague.exe"]["sha256"] = trial.OBSERVED_SHA256
        world.baseline.write_text(json.dumps(baseline), encoding="utf-8")
        world.executable.write_bytes(b"different executable bytes")

    with pytest.raises(RuntimeError, match="differs from this diagnostic"):
        trial.prepare(world.game, world.baseline)

    assert not (world.build / "mct-host-probes").exists()
    assert not world.destination.exists()


@pytest.mark.parametrize("changed", ["configuration", "dll"])
def test_launch_rejects_stale_configuration_or_modified_dll_before_popen(
    tmp_path, monkeypatch, changed
):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    if changed == "configuration":
        world.cfg.write_bytes(b"plugin load existing\nplugin load changed\n")
    else:
        world.source.write_bytes(b"modified diagnostic dll")
    popen_calls = []
    injector_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    monkeypatch.setattr(trial.bootstrap, "ensure_injector_running", lambda: injector_calls.append(True))

    with pytest.raises(RuntimeError, match="changed after trial preparation"):
        trial.launch(world.directory)

    assert not popen_calls
    assert not injector_calls
    assert not world.destination.exists()
    assert not (world.directory / "launch-attempt.json").exists()
    assert not (world.directory / "session.json").exists()


def test_launch_refuses_an_existing_launch_attempt_before_popen(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    (world.directory / "launch-attempt.json").write_text('{"at": 1}\n', encoding="utf-8")
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))

    with pytest.raises(RuntimeError, match="already attempted"):
        trial.launch(world.directory)

    assert not popen_calls
    assert not world.destination.exists()


def test_launch_refuses_a_preexisting_session_before_popen(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    (world.directory / "session.json").write_text('{"old": true}\n', encoding="utf-8")
    popen_calls = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (popen_calls.append((args, kwargs)) or SimpleNamespace(pid=4321)),
    )
    monkeypatch.setattr(trial.psutil, "Process", lambda _pid: SimpleNamespace(create_time=lambda: 10.0))

    with pytest.raises(RuntimeError, match="already attempted"):
        trial.launch(world.directory)

    assert not popen_calls
    assert not world.destination.exists()
    assert not (world.directory / "launch-attempt.json").exists()


def test_finish_refuses_running_game_without_removing_trial_dll(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world, running=True)
    world.destination.write_bytes(world.source.read_bytes())
    original = world.destination.read_bytes()

    with pytest.raises(RuntimeError, match="Close Rocket League"):
        trial.finish(world.directory)

    assert world.destination.read_bytes() == original
    assert not (world.directory / "finished.json").exists()


def test_finish_refuses_changed_dll_without_removing_it(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    world.destination.write_bytes(b"different DLL owned by someone else")
    original = world.destination.read_bytes()

    with pytest.raises(RuntimeError, match="Trial DLL changed"):
        trial.finish(world.directory)

    assert world.destination.read_bytes() == original
    assert not (world.directory / "finished.json").exists()


def test_finish_removes_only_the_unchanged_trial_dll(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    world.destination.write_bytes(world.source.read_bytes())
    unrelated = world.bakkes / "plugins" / "UserPlugin.dll"
    unrelated.write_bytes(b"leave this plugin alone")
    original_config = world.cfg.read_bytes()

    result = trial.finish(world.directory)

    assert not world.destination.exists()
    assert unrelated.read_bytes() == b"leave this plugin alone"
    assert world.cfg.read_bytes() == original_config
    assert result["trial_dll_removed"] is True
    assert result["configuration_unchanged"] is True
    assert json.loads((world.directory / "finished.json").read_text(encoding="utf-8")) == result


def test_finish_reports_configuration_changes_without_overwriting_them(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    world.destination.write_bytes(world.source.read_bytes())
    changed_config = b"plugin load existing\nmanual user change\n"
    world.cfg.write_bytes(changed_config)

    result = trial.finish(world.directory)

    assert not world.destination.exists()
    assert world.cfg.read_bytes() == changed_config
    assert result["configuration_unchanged"] is False
    assert result["changed_configuration_files"] == ["plugins.cfg"]


def _write_command_session(world, *, nonce=None, issued_at=100.0, expires_at=200.0):
    session = {
        "protocol": 1,
        "kind": "mct_native_host_probe",
        "nonce": world.plan["nonce"] if nonce is None else nonce,
        "pid": 4321,
        "created": 50.0,
        "executable_sha256": trial.OBSERVED_SHA256,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    (world.directory / "session.json").write_text(json.dumps(session), encoding="utf-8")
    return session


def _listener(ip, port, status=None):
    return SimpleNamespace(
        status=status or trial.psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip=ip, port=port),
    )


def _mock_command_context(monkeypatch, *, owned=True, listeners=()):
    monkeypatch.setattr(trial.time, "time", lambda: 150.0)
    identities = []
    monkeypatch.setattr(
        trial.bootstrap,
        "verify_owned_offline",
        lambda identity: identities.append(identity) or owned,
    )
    inspected_pids = []
    monkeypatch.setattr(
        trial.psutil,
        "Process",
        lambda pid: inspected_pids.append(pid) or SimpleNamespace(net_connections=lambda kind: list(listeners)),
    )
    return identities, inspected_pids


def test_command_context_rejects_expired_session_without_checking_process(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _write_command_session(world, issued_at=50.0, expires_at=149.0)
    identities, inspected_pids = _mock_command_context(monkeypatch)

    with pytest.raises(RuntimeError, match="missing or expired"):
        trial.command_context(world.directory, 9001)

    assert not identities
    assert not inspected_pids


def test_command_context_rejects_mismatched_nonce_without_checking_process(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _write_command_session(world, nonce=str(uuid.uuid4()))
    identities, inspected_pids = _mock_command_context(monkeypatch)

    with pytest.raises(RuntimeError, match="missing or expired"):
        trial.command_context(world.directory, 9001)

    assert not identities
    assert not inspected_pids


def test_command_context_rejects_unowned_pid_without_inspecting_listener(tmp_path, monkeypatch):
    world = _world(tmp_path)
    session = _write_command_session(world)
    identities, inspected_pids = _mock_command_context(monkeypatch, owned=False)

    with pytest.raises(RuntimeError, match="owned offline game is not running"):
        trial.command_context(world.directory, 9001)

    assert len(identities) == 1
    assert identities[0].pid == session["pid"]
    assert identities[0].created == session["created"]
    assert identities[0].executable == world.plan["executable"]
    assert not inspected_pids


def test_command_context_rejects_listener_on_different_port(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _write_command_session(world)
    identities, inspected_pids = _mock_command_context(
        monkeypatch, listeners=[_listener("127.0.0.1", 9002)]
    )

    with pytest.raises(RuntimeError, match="listener does not belong"):
        trial.command_context(world.directory, 9001)

    assert len(identities) == 1
    assert inspected_pids == [4321]


@pytest.mark.parametrize("listener_ip", ["127.0.0.1", "0.0.0.0"])
def test_command_context_accepts_owned_local_listener_without_network_access(
    tmp_path, monkeypatch, listener_ip
):
    world = _world(tmp_path)
    _write_command_session(world)
    identities, inspected_pids = _mock_command_context(
        monkeypatch, listeners=[_listener(listener_ip, 9001)]
    )

    context = trial.command_context(world.directory, 9001)

    assert context == {"owned_listener": True, "plugin_name": world.plan["plugin_name"]}
    assert len(identities) == 1
    assert inspected_pids == [4321]


def test_menu_event_trace_cli_implies_object_header_without_enabling_menu_graph(
    tmp_path, monkeypatch, capsys
):
    world = _world(tmp_path, create_trial=False)
    _mock_host(monkeypatch, world)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "prepare",
            "--game-dir",
            str(world.game),
            "--baseline",
            str(world.baseline),
            "--menu-event-trace",
        ],
    )

    trial.main()

    output = json.loads(capsys.readouterr().out)
    directory = Path(output["directory"])
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    assert plan["menu_event_trace"] is True
    assert plan["object_header_trial"] is True
    assert plan["menu_graph_trial"] is False
    assert plan["menu_remap_trial"] is False
    assert output["game_launched"] is False
    assert not world.destination.exists()
    assert not (directory / "launch-attempt.json").exists()


def test_menu_event_trace_optins_propagate_to_launched_session(tmp_path, monkeypatch):
    world = _world(tmp_path, create_trial=False)
    _mock_host(monkeypatch, world)
    directory, plan = trial.prepare(world.game, world.baseline, menu_event_trace=True)
    assert plan["menu_event_trace"] is True
    assert plan["object_header_trial"] is True
    assert plan["menu_graph_trial"] is False
    assert plan["menu_remap_trial"] is False

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: SimpleNamespace(pid=4321),
    )
    monkeypatch.setattr(
        trial.psutil,
        "Process",
        lambda _pid: SimpleNamespace(create_time=lambda: 50.0),
    )
    monkeypatch.setattr(trial.time, "time", lambda: 150.0)

    trial.launch(directory)

    session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert session["menu_event_trace"] is True
    assert session["object_header_trial"] is True
    assert session["menu_graph_trial"] is False
    assert session["menu_remap_trial"] is False


def test_menu_remap_cli_implies_header_and_event_trace_and_reaches_session(
    tmp_path, monkeypatch, capsys
):
    world = _world(tmp_path, create_trial=False)
    _mock_host(monkeypatch, world)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "prepare",
            "--game-dir",
            str(world.game),
            "--baseline",
            str(world.baseline),
            "--menu-remap-trial",
        ],
    )

    trial.main()

    output = json.loads(capsys.readouterr().out)
    directory = Path(output["directory"])
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    assert plan["menu_remap_trial"] is True
    assert plan["menu_event_trace"] is True
    assert plan["object_header_trial"] is True
    assert plan["menu_graph_trial"] is False
    assert output["game_launched"] is False

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: SimpleNamespace(pid=4321),
    )
    monkeypatch.setattr(
        trial.psutil,
        "Process",
        lambda _pid: SimpleNamespace(create_time=lambda: 50.0),
    )
    monkeypatch.setattr(trial.time, "time", lambda: 150.0)

    trial.launch(directory)

    session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert session["menu_remap_trial"] is True
    assert session["menu_event_trace"] is True
    assert session["object_header_trial"] is True
    assert session["menu_graph_trial"] is False


def test_menu_remap_optins_are_disabled_by_default_in_plan_and_session(tmp_path, monkeypatch):
    world = _world(tmp_path, create_trial=False)
    _mock_host(monkeypatch, world)
    directory, plan = trial.prepare(world.game, world.baseline)

    assert plan["menu_remap_trial"] is False
    assert plan["menu_event_trace"] is False
    assert plan["object_header_trial"] is False
    assert plan["menu_graph_trial"] is False

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: SimpleNamespace(pid=4321),
    )
    monkeypatch.setattr(
        trial.psutil,
        "Process",
        lambda _pid: SimpleNamespace(create_time=lambda: 50.0),
    )
    monkeypatch.setattr(trial.time, "time", lambda: 150.0)
    trial.launch(directory)

    session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert session["menu_remap_trial"] is False
    assert session["menu_event_trace"] is False
    assert session["object_header_trial"] is False
    assert session["menu_graph_trial"] is False


def test_command_context_is_repeatable_and_read_only_for_live_session(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _write_command_session(world)
    _mock_command_context(
        monkeypatch,
        listeners=[_listener("127.0.0.1", 9001)],
    )
    before = {path.name: path.read_bytes() for path in world.directory.iterdir() if path.is_file()}

    first = trial.command_context(world.directory, 9001)
    second = trial.command_context(world.directory, 9001)

    after = {path.name: path.read_bytes() for path in world.directory.iterdir() if path.is_file()}
    assert first == second == {
        "owned_listener": True,
        "plugin_name": world.plan["plugin_name"],
    }
    assert after == before


def test_finish_allows_safe_cleanup_after_session_expiry_when_game_is_closed(
    tmp_path, monkeypatch
):
    world = _world(tmp_path)
    _mock_host(monkeypatch, world)
    _write_command_session(world, issued_at=50.0, expires_at=149.0)
    world.destination.write_bytes(world.source.read_bytes())

    result = trial.finish(world.directory)

    assert not world.destination.exists()
    assert result["trial_dll_removed"] is True
    assert result["configuration_unchanged"] is True
    assert (world.directory / "finished.json").is_file()
