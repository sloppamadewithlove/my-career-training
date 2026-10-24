"""Offline launch owns a temporary BakkesMod plugin session and checks process identity."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from my_career_training import bootstrap
from my_career_training.platforms import ProcessIdentity
from my_career_training.plugin_session import PluginSession


class _ProcInfo:
    def __init__(self, name):
        self.info = {"name": name}


class _Started:
    def __init__(self, pid=4242, created=10.0):
        self.pid = pid
        self._created = created

    def create_time(self):
        return self._created


def _bakkes(tmp_path, cfg=b"plugin load alpha\n", dll=b"old-dll"):
    root = tmp_path / "bakkes"
    (root / "plugins").mkdir(parents=True)
    (root / "cfg").mkdir()
    config = root / "cfg" / "plugins.cfg"
    plugin = root / "plugins" / "MyCareerTraining.dll"
    if cfg is not None:
        config.write_bytes(cfg)
    if dll is not None:
        plugin.write_bytes(dll)
    source = tmp_path / "MyCareerTraining.dll"
    source.write_bytes(b"career-plugin-v1")
    executable = tmp_path / "game" / "Binaries" / "Win64" / "RocketLeague.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"rocket-league")
    steam_sentinel = tmp_path / "steam" / "userdata" / "localconfig.vdf"
    steam_sentinel.parent.mkdir(parents=True)
    steam_sentinel.write_bytes(b"steam-sentinel")
    return SimpleNamespace(
        root=root, source=source, cfg=config, dll=plugin, executable=executable,
        data=tmp_path / "MyCareerTraining", steam_sentinel=steam_sentinel,
        journal=tmp_path / "MyCareerTraining" / "plugin-session" / "active.json")


def _patch_launch(monkeypatch, layout, popen, *, created=10.0, game_running=None):
    running = game_running if game_running is not None else (lambda: False)
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    monkeypatch.setattr(bootstrap, "game_processes", running)
    monkeypatch.setattr(bootstrap, "detect_installations", lambda: [
        {"launcher": "steam", "path": str(layout.executable), "available": True}])
    monkeypatch.setattr(bootstrap, "bakkes_directory", lambda: layout.root)
    monkeypatch.setattr(bootstrap, "plugin_binary", lambda: layout.source)
    monkeypatch.setattr(bootstrap, "_injector_running", lambda: True)
    monkeypatch.setattr(bootstrap, "ensure_injector_running", lambda: None)

    import psutil
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: [_ProcInfo("steam.exe")])
    monkeypatch.setattr(psutil, "Process", lambda pid: _Started(pid, created))

    def _popen(args, **kwargs):
        return popen(args, **kwargs)

    monkeypatch.setattr(bootstrap.subprocess, "Popen", _popen)


def test_injector_installed_on_another_drive_is_found_and_started_directly(tmp_path, monkeypatch):
    from my_career_training import bakkes_installation

    layout = _bakkes(tmp_path)
    injector = tmp_path / "custom-install" / "BakkesMod.exe"
    injector.parent.mkdir()
    injector.write_bytes(b"injector-fixture")
    monkeypatch.setattr(bootstrap, "bakkes_directory", lambda: layout.root)
    monkeypatch.setattr(bootstrap, "_injector_running", lambda: False)
    monkeypatch.setattr(bakkes_installation, "discover_bakkesmod_injectors", lambda: [injector])
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        monkeypatch.setenv(variable, str(tmp_path / "unused-default"))
    started = []
    monkeypatch.setattr(bootstrap.subprocess, "Popen", lambda args, **kw: started.append((args, kw)))

    assert bootstrap.bakkes_ready() == layout.root
    assert started == []
    bootstrap.ensure_injector_running()
    assert started == [([str(injector)], {"shell": False})]
    assert layout.cfg.read_bytes() == b"plugin load alpha\n"
    assert not layout.journal.exists()


def test_verify_owned_offline_uses_shared_launch_tokens_and_rejects_bad_clocks(monkeypatch):
    expected = r"C:\Games\RocketLeague.exe"
    seen = {}

    class FakeProcess:
        def create_time(self):
            return seen["live"]

        def exe(self):
            return expected

        def cmdline(self):
            return seen["args"]

    import psutil
    monkeypatch.setattr(psutil, "Process", lambda _pid: FakeProcess())
    identity = ProcessIdentity(pid=73, created=123.0, executable=expected)

    seen.update(live=123.0, args=["RocketLeague.exe", "-noeac", "-rlbot", "RLBot_ControllerURL=127.0.0.1:23233"])
    assert bootstrap.verify_owned_offline(identity) is True

    seen["args"] = ["RocketLeague.exe", "-noeac", "-rlbot", "-eac"]
    assert bootstrap.verify_owned_offline(identity) is False

    for created, live in ((math.nan, 123.0), (math.inf, 123.0), (0, 123.0), (-5, 123.0),
                          (True, 123.0), (123.0, math.nan), (123.0, 0), (123.0, -1)):
        identity = ProcessIdentity(pid=73, created=created, executable=expected)
        seen.update(live=live, args=["RocketLeague.exe", "-noeac", "-rlbot"])
        assert bootstrap.verify_owned_offline(identity) is False


def test_failed_launch_restores_the_journal_and_does_not_touch_steam(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    original_cfg = layout.cfg.read_bytes()
    original_dll = layout.dll.read_bytes()
    observed = []

    def popen(args, **kwargs):
        observed.append((args, kwargs))
        assert layout.cfg.read_bytes() != original_cfg
        raise OSError("Rocket League did not start")

    _patch_launch(monkeypatch, layout, popen)
    with pytest.raises(OSError, match="did not start"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)

    assert layout.cfg.read_bytes() == original_cfg
    assert layout.dll.read_bytes() == original_dll
    assert not layout.journal.exists()
    assert layout.steam_sentinel.read_bytes() == b"steam-sentinel"
    args, kwargs = observed[0]
    assert args[0] == str(layout.executable)
    assert "-noeac" in args and "-rlbot" in args
    assert kwargs["shell"] is False
    assert all("localconfig" not in str(part).lower() for part in args)
    assert not (layout.root / "cfg" / "plugins.cfg.mct-backup").exists()


def test_unrecorded_executable_is_rejected_before_plugin_setup(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    _patch_launch(monkeypatch, layout, lambda *_a, **_kw: pytest.fail("unverified game launched"))
    monkeypatch.setattr(bootstrap, "detect_installations", lambda: [])
    with pytest.raises(RuntimeError, match="Steam's recorded"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)
    assert layout.cfg.read_bytes() == b"plugin load alpha\n"
    assert layout.dll.read_bytes() == b"old-dll"
    assert not layout.journal.exists()


def test_normal_game_started_during_setup_prevents_second_launch(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    state = {"running": False}
    _patch_launch(monkeypatch, layout, lambda *_a, **_kw: pytest.fail("second game launched"),
                  game_running=lambda: [object()] if state["running"] else [])
    monkeypatch.setattr(bootstrap, "ensure_injector_running", lambda: state.update(running=True))
    with pytest.raises(RuntimeError, match="Close the existing Rocket League"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)
    assert layout.journal.is_file()
    state["running"] = False
    bootstrap.recover_plugin_session(layout.data)
    assert layout.cfg.read_bytes() == b"plugin load alpha\n"
    assert layout.dll.read_bytes() == b"old-dll"


def test_launch_recovers_a_crashed_session_before_staging_the_new_one(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    original_cfg = layout.cfg.read_bytes()
    original_dll = layout.dll.read_bytes()
    PluginSession(layout.data, root=layout.root, game_running=lambda: False).begin(layout.source)
    assert b"plugin load MyCareerTraining" in layout.cfg.read_bytes()
    during_launch = []

    def popen(args, **kwargs):
        during_launch.append(layout.cfg.read_bytes())
        raise OSError("stopped")

    _patch_launch(monkeypatch, layout, popen)
    with pytest.raises(OSError):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)

    assert b"plugin load MyCareerTraining" in during_launch[0]
    assert layout.cfg.read_bytes() == original_cfg
    assert layout.dll.read_bytes() == original_dll


def test_invalid_process_clock_cleans_the_plugin_session(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    original_cfg = layout.cfg.read_bytes()

    def popen(args, **kwargs):
        return _Started()

    _patch_launch(monkeypatch, layout, popen, created=math.nan)
    with pytest.raises(RuntimeError, match="valid process start time"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)
    assert layout.cfg.read_bytes() == original_cfg
    assert not layout.journal.exists()


def test_outstanding_session_refuses_launch_while_rocket_league_is_open(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    staged = PluginSession(layout.data, root=layout.root, game_running=lambda: False)
    staged.begin(layout.source)
    staged_cfg = layout.cfg.read_bytes()
    calls = []

    def popen(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("game launch")

    _patch_launch(monkeypatch, layout, popen, game_running=lambda: [object()])
    with pytest.raises(RuntimeError, match="Close the existing Rocket League"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)
    assert calls == []
    assert layout.cfg.read_bytes() == staged_cfg
    assert layout.journal.is_file()


def test_injector_failure_rolls_the_plugin_session_back(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path, cfg=None, dll=None)
    _patch_launch(monkeypatch, layout, lambda *_args, **_kwargs: pytest.fail("game started"))
    monkeypatch.setattr(bootstrap, "ensure_injector_running", lambda: (_ for _ in ()).throw(RuntimeError("no injector")))
    with pytest.raises(RuntimeError, match="no injector"):
        bootstrap.launch_offline({"launcher": "steam", "install_path": str(layout.executable)}, layout.data)
    assert not layout.dll.exists()
    assert not layout.cfg.exists()
    assert not layout.journal.exists()


def _service_fakes(monkeypatch, layout, popen, game_running):
    _patch_launch(monkeypatch, layout, popen, game_running=game_running)
    monkeypatch.setattr(bootstrap, "bakkes_ready", lambda: layout.root)

    class FakeSignal:
        def connect(self, *_args):
            return None

    class FakeBackend:
        def __init__(self, directory):
            self.document = {"settings": {
                "launcher": "steam", "install_path": str(layout.executable),
                "binding_profile": "playstation", "setup_complete": True}, "career": None}
            self.setup_required = False
            self.installations = []
            self.store = SimpleNamespace(close=lambda: None)
            self.exitRequested = FakeSignal()
            self.in_game = False
            self.plugin_status = {}
            self.error = ""
            self.owned_game = None
            self.dispatch = lambda *_args, **_kwargs: None
            self.state = {}
            self.lifecycle = SimpleNamespace(frozen=False, state="Idle", last_error="")

        def _refresh_workshop(self):
            return None

        def _save_current(self):
            return None

        def close(self):
            return None

    class FakeBridge:
        def __init__(self, *_args, **_kwargs):
            return None

        def poll(self):
            return None

        def close(self):
            return None

        def plugin_status(self):
            return {}

    class FakeGuard:
        def __init__(self, _directory):
            return None

        def recover(self):
            return None

    class FakeTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = FakeSignal()

        def start(self, *_args):
            return None

    class FakeApp:
        def __init__(self, *_args, **_kwargs):
            return None

        @staticmethod
        def instance():
            return None

        def setQuitOnLastWindowClosed(self, _value):
            return None

        def quit(self):
            return None

        def exec(self):
            return 0

    class FakeMessageBox:
        warnings = []
        criticals = []

        @staticmethod
        def warning(_parent, title, text):
            FakeMessageBox.warnings.append((title, text))

        @staticmethod
        def critical(_parent, title, text):
            FakeMessageBox.criticals.append((title, text))

    from my_career_training import bridge as bridge_mod
    from my_career_training import ingame, map_guard
    import PySide6.QtCore as qt_core
    import PySide6.QtWidgets as qt_widgets
    monkeypatch.setattr(bridge_mod, "Backend", FakeBackend)
    monkeypatch.setattr(ingame, "FileBridge", FakeBridge)
    monkeypatch.setattr(map_guard, "MapGuard", FakeGuard)
    monkeypatch.setattr(qt_core, "QTimer", FakeTimer)
    monkeypatch.setattr(qt_widgets, "QApplication", FakeApp)
    monkeypatch.setattr(qt_widgets, "QMessageBox", FakeMessageBox)
    return FakeApp, FakeMessageBox


def test_service_restores_plugin_files_on_a_normal_exit(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    original_cfg = layout.cfg.read_bytes()
    original_dll = layout.dll.read_bytes()
    FakeApp, _box = _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: False)

    assert bootstrap.run_service(layout.data) == 0
    assert layout.cfg.read_bytes() == original_cfg
    assert layout.dll.read_bytes() == original_dll
    assert not layout.journal.exists()
    assert layout.steam_sentinel.read_bytes() == b"steam-sentinel"


def test_service_recovers_plugin_files_even_when_saving_on_exit_fails(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    before_cfg, before_dll = layout.cfg.read_bytes(), layout.dll.read_bytes()
    _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: False)
    from my_career_training import bridge, ingame
    closed = []
    def fail_save(self):
        raise OSError("save unavailable")
    monkeypatch.setattr(bridge.Backend, "close", fail_save)
    monkeypatch.setattr(ingame.FileBridge, "close", lambda self: closed.append(True))
    with pytest.raises(OSError, match="save unavailable"):
        bootstrap.run_service(layout.data)
    assert closed == [True]
    assert layout.cfg.read_bytes() == before_cfg
    assert layout.dll.read_bytes() == before_dll
    assert not layout.journal.exists()


def test_service_leaves_a_receipt_when_the_game_is_still_running(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    state = {"running": False}

    class App:
        def __init__(self, *_args, **_kwargs):
            return None

        @staticmethod
        def instance():
            return None

        def setQuitOnLastWindowClosed(self, _value):
            return None

        def quit(self):
            return None

        def exec(self):
            state["running"] = True
            return 0

    _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: [object()] if state["running"] else [])
    import PySide6.QtWidgets as qt_widgets
    monkeypatch.setattr(qt_widgets, "QApplication", App)

    assert bootstrap.run_service(layout.data) == 1
    assert "could not be restored" in qt_widgets.QMessageBox.criticals[-1][1]
    assert b"plugin load MyCareerTraining" in layout.cfg.read_bytes()
    assert layout.dll.read_bytes() == layout.source.read_bytes()
    assert layout.journal.is_file()

    state["running"] = False
    assert bootstrap.recover_plugin_session(layout.data)["status"] == "restored"
    assert layout.cfg.read_bytes() == b"plugin load alpha\n"
    assert layout.dll.read_bytes() == b"old-dll"


def test_service_waits_for_online_handoff_before_quitting(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    app_type, _box = _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: [])
    from my_career_training import bridge, platforms
    import PySide6.QtCore as qt_core
    lifecycle = SimpleNamespace(frozen=True, state="Waiting for Game Exit", last_error="")
    original_init = bridge.Backend.__init__

    def init(self, directory):
        original_init(self, directory)
        self.lifecycle = lifecycle

    monkeypatch.setattr(bridge.Backend, "__init__", init)
    monkeypatch.setattr(platforms, "is_alive", lambda _identity: False)
    now = [100.0]
    monkeypatch.setattr(bootstrap.time, "monotonic", lambda: now[0])
    callbacks = []

    class Timer:
        def __init__(self):
            self.timeout = SimpleNamespace(connect=callbacks.append)

        def start(self, _interval):
            pass

    monkeypatch.setattr(qt_core, "QTimer", Timer)
    quits = []
    monkeypatch.setattr(app_type, "quit", lambda self: quits.append(True))

    def run(self):
        now[0] = 106.0
        callbacks[0]()
        assert quits == []
        lifecycle.frozen = False
        lifecycle.state = "Online Launch Requested"
        callbacks[0]()
        assert quits == [True]
        return 0

    monkeypatch.setattr(app_type, "exec", run)
    assert bootstrap.run_service(layout.data) == 0
    assert not layout.journal.exists()


def test_service_refuses_an_outstanding_session_while_a_game_is_open(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    PluginSession(layout.data, root=layout.root, game_running=lambda: False).begin(layout.source)
    staged = layout.cfg.read_bytes()
    _box_holder = {}

    def popen(*_args, **_kwargs):
        raise AssertionError("must not launch over an open game")

    _service_fakes(monkeypatch, layout, popen, lambda: [object()])
    import PySide6.QtWidgets as qt_widgets
    _box_holder["box"] = qt_widgets.QMessageBox

    assert bootstrap.run_service(layout.data) == 1
    assert layout.cfg.read_bytes() == staged
    assert layout.journal.is_file()
    assert _box_holder["box"].criticals
    assert "will not start another session" in _box_holder["box"].criticals[-1][1]


def test_service_warns_and_preserves_a_legacy_autoload_line(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path, cfg=b"plugin load MyCareerTraining\nplugin load alpha\n")
    original = layout.cfg.read_bytes()
    _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: False)
    import PySide6.QtWidgets as qt_widgets

    assert bootstrap.run_service(layout.data) == 0
    assert layout.cfg.read_bytes() == original
    assert layout.dll.read_bytes() == b"old-dll"
    assert any("did not remove" in text for _title, text in qt_widgets.QMessageBox.warnings)


def test_service_reports_a_conflicting_restore_and_keeps_the_other_dll(tmp_path, monkeypatch):
    layout = _bakkes(tmp_path)
    state = {"running": False}

    class App:
        def __init__(self, *_args, **_kwargs):
            return None

        @staticmethod
        def instance():
            return None

        def setQuitOnLastWindowClosed(self, _value):
            return None

        def quit(self):
            return None

        def exec(self):
            layout.dll.write_bytes(b"replaced-while-playing")
            return 0

    _service_fakes(monkeypatch, layout, lambda *_args, **_kwargs: _Started(), lambda: [object()] if state["running"] else [])
    import PySide6.QtWidgets as qt_widgets
    monkeypatch.setattr(qt_widgets, "QApplication", App)

    assert bootstrap.run_service(layout.data) == 1
    assert layout.dll.read_bytes() == b"replaced-while-playing"
    assert layout.journal.is_file()
    assert (layout.data / "plugin-session" / "MyCareerTraining.dll.prior").read_bytes() == b"old-dll"
    assert "left that file in place" in qt_widgets.QMessageBox.criticals[-1][1]
