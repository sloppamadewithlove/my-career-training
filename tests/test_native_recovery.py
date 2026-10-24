"""A helper can outlive the app and create a child after a receipt timeout."""
from types import SimpleNamespace

import psutil
import pytest

from my_career_training import platforms
from my_career_training.plugin_session import PluginSession, PluginSessionError


@pytest.mark.parametrize("names, expected", [
    (["steam.exe", "MctNativeLauncher.exe"], True),
    (["steam.exe", "mctnativelauncher.EXE"], True),
    (["steam.exe", "OtherLauncher.exe"], False),
    (["steam.exe", None], True),
    (["steam.exe", ""], True),
])
def test_helper_presence_is_a_conservative_restore_blocker(monkeypatch, names, expected):
    monkeypatch.setattr(psutil, "process_iter", lambda *_: [SimpleNamespace(info={"name": n}) for n in names])
    assert platforms.native_launcher_pending() is expected


def test_interrupted_enumeration_cannot_authorize_restore(monkeypatch):
    def interrupted(*_):
        yield SimpleNamespace(info={"name": "steam.exe"})
        raise psutil.AccessDenied(123)
    monkeypatch.setattr(psutil, "process_iter", interrupted)
    assert platforms.native_launcher_pending() is True


def test_restarted_app_keeps_journal_until_helper_exits_even_without_game(tmp_path, monkeypatch):
    root = tmp_path / "bakkes"
    (root / "plugins").mkdir(parents=True)
    (root / "cfg").mkdir()
    config = root / "cfg/plugins.cfg"
    config.write_bytes(b"plugin load existing\r\n")
    original = config.read_bytes()
    source = tmp_path / "MyCareerTraining.dll"
    source.write_bytes(b"synthetic-plugin")
    pending = [False]
    monkeypatch.setattr(platforms, "native_launcher_pending", lambda: pending[0])
    # A custom game probe must not bypass the helper check.
    session = PluginSession(tmp_path / "data", root=root, game_running=lambda: False)
    session.begin(source)
    prepared = config.read_bytes()
    pending[0] = True
    restarted = PluginSession(tmp_path / "data", root=root, game_running=lambda: False)
    assert restarted.finish()["status"] == "deferred"
    with pytest.raises(PluginSessionError, match="offline menu helper"):
        restarted.recover()
    assert restarted.outstanding() and config.read_bytes() == prepared
    pending[0] = False
    assert restarted.recover()["status"] == "restored"
    assert config.read_bytes() == original
    assert not restarted.outstanding()
