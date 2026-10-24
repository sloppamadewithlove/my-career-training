"""Native startup composition with fake asset preparation and no launched process."""
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from my_career_training import native_menu_assets, native_offline
from my_career_training.platforms import ProcessIdentity


SESSION = "45234854-6e9c-4af5-9c50-e9347f375140"


def layout(tmp_path, monkeypatch, *, enabled=True):
    data = tmp_path / "data"
    (data / "bridge").mkdir(parents=True)
    executable = tmp_path / "game/Binaries/Win64/RocketLeague.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"game-sentinel")
    plugin = tmp_path / "MyCareerTraining.dll"
    plugin.write_bytes(b"candidate-plugin")
    receipt = {"native_movie_trial": enabled, "native_host_probe": False, "gameplay_verified": False,
               "sha256": hashlib.sha256(plugin.read_bytes()).hexdigest()}
    plugin.with_name("plugin-build-receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(native_offline, "data_dir", lambda: data)
    monkeypatch.setattr(native_offline, "runtime_directory", lambda component: tmp_path / "runtime" / component)
    calls = []
    prepared = SimpleNamespace(private_package=str(data / "native-menu-sessions" / SESSION / "GFX_MainMenu_SF.upk"),
                               private_package_sha256="f" * 64)
    monkeypatch.setattr(native_menu_assets, "prepare_native_menu",
                        lambda *args, **kwargs: calls.append((args, kwargs)) or prepared)
    return data, executable, plugin, prepared, calls


def test_prepare_uses_the_bridge_nonce_and_matching_private_paths(tmp_path, monkeypatch):
    data, executable, plugin, prepared, calls = layout(tmp_path, monkeypatch)
    session = native_offline.NativeOfflineSession(data, SESSION)
    assert calls == []
    session.prepare(executable, plugin)
    assert session.prepared is prepared
    assert calls == [((executable.parent.parent.parent, SESSION, data / "bridge", data / "native-menu-sessions"),
                      {"runtime_directory": tmp_path / "runtime/native-menu"})]
    assert executable.read_bytes() == b"game-sentinel"
    with pytest.raises(RuntimeError, match="already prepared"):
        session.prepare(executable, plugin)


def test_custom_data_folder_is_refused_before_private_preparation(tmp_path, monkeypatch):
    data, executable, plugin, _, calls = layout(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="normal My Career data"):
        native_offline.NativeOfflineSession(data / "different", SESSION).prepare(executable, plugin)
    assert calls == []


@pytest.mark.parametrize("change", ["off", "hash", "probe", "verified"])
def test_nonmatching_candidate_is_refused(tmp_path, monkeypatch, change):
    data, executable, plugin, _, calls = layout(tmp_path, monkeypatch)
    path = plugin.with_name("plugin-build-receipt.json")
    receipt = json.loads(path.read_text())
    field, value = {"off": ("native_movie_trial", False), "hash": ("sha256", "0" * 64),
                    "probe": ("native_host_probe", True), "verified": ("gameplay_verified", True)}[change]
    receipt[field] = value
    path.write_text(json.dumps(receipt))
    with pytest.raises(RuntimeError, match="matching native menu candidate"):
        native_offline.NativeOfflineSession(data, SESSION).prepare(executable, plugin)
    assert calls == []
    assert not (data / "native-menu-sessions").exists()


def test_launch_retains_helper_and_returns_the_game_identity(tmp_path, monkeypatch):
    data, executable, plugin, prepared, _ = layout(tmp_path, monkeypatch)
    identity = ProcessIdentity(739, 100.5, str(executable))
    owner = SimpleNamespace(identity=identity, helper=SimpleNamespace(pid=111), poll=lambda: "ready",
                            release=lambda: True)
    calls = []
    fake = SimpleNamespace(launch_native_offline=lambda *args, **kwargs: calls.append((args, kwargs)) or owner,
                           NativeLaunchUncertain=type("Uncertain", (RuntimeError,), {}))
    monkeypatch.setitem(sys.modules, "my_career_training.native_launch", fake)
    session = native_offline.NativeOfflineSession(data, SESSION)
    with pytest.raises(RuntimeError, match="Prepare"):
        session.launch(executable)
    session.prepare(executable, plugin)
    assert session.launch(executable) is identity
    assert session.owner is owner
    assert calls == [((executable.parent.parent.parent, prepared.private_package, "f" * 64, SESSION),
                      {"runtime_directory": tmp_path / "runtime/native"})]
    with pytest.raises(RuntimeError, match="Prepare"):
        session.launch(executable)
    assert session.warning() == ""
    assert session.finished() is False
    owner.poll = lambda: "degraded"
    assert "helper stopped" in session.warning()
    owner.poll = lambda: "reaping"
    assert session.warning() == ""
    assert session.finished() is False
    owner.poll = lambda: "exited"
    assert session.finished() is True


def test_native_cli_flag_cannot_change_worker_or_test_modes(monkeypatch):
    from my_career_training import __main__ as entry

    for mode in ("--worker", "--self-test", "--smoke-test", "--manage"):
        monkeypatch.setattr(sys, "argv", ["mct", "--native-menu-trial", mode])
        with pytest.raises(SystemExit) as error:
            entry.main()
        assert error.value.code == 2


def test_uncertain_launch_is_retained_and_cannot_start_another_helper(tmp_path, monkeypatch):
    data, executable, plugin, _, _ = layout(tmp_path, monkeypatch)
    stopped = [False]
    games = [object()]
    monkeypatch.setattr(native_offline, "game_processes", lambda: games)
    monkeypatch.setattr(native_offline, "native_launcher_pending", lambda: False)
    released = []

    class Uncertain(RuntimeError):
        def helper_exited(self):
            return stopped[0]

        def release(self):
            released.append(True)
            return True

    error = Uncertain("still starting")
    def launch(*_args, **_kwargs):
        raise error
    fake = SimpleNamespace(launch_native_offline=launch, NativeLaunchUncertain=Uncertain)
    monkeypatch.setitem(sys.modules, "my_career_training.native_launch", fake)
    session = native_offline.NativeOfflineSession(data, SESSION)
    session.prepare(executable, plugin)
    with pytest.raises(Uncertain):
        session.launch(executable)
    assert session.uncertain is error
    assert not session.finished() and released == []
    with pytest.raises(RuntimeError, match="Prepare"):
        session.launch(executable)
    stopped[0] = True
    assert not session.finished() and released == []
    games.clear()
    assert session.finished() and released == [True]
