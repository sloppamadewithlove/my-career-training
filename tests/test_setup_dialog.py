"""First-run prerequisite prompts never start an unapproved installer or game."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from my_career_training import bootstrap
from my_career_training.prerequisites import DownloadCancelled
from my_career_training import prerequisites
from my_career_training.setup_dialog import PrerequisiteDialog, ensure_bakkes_available


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(["my-career-training-tests"])


def _pump_until(app, condition, seconds=2):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert condition()


def test_setup_requires_separate_download_and_install_clicks(tmp_path, qt_app):
    installed = [False]
    launches = []
    fake_installer = tmp_path / "BakkesModSetup.exe"
    fake_installer.write_bytes(b"verified by fake downloader")
    dialog = PrerequisiteDialog(
        tmp_path,
        finder=lambda: tmp_path if installed[0] else None,
        downloader=lambda _cache, **kwargs: fake_installer,
        launcher=lambda path: launches.append(path),
    )
    assert not launches
    assert not dialog.install_button.isEnabled()
    dialog.download_button.click()
    _pump_until(qt_app, lambda: dialog.install_button.isEnabled())
    assert not launches
    dialog.install_button.click()
    assert launches == [fake_installer]
    assert not dialog.install_button.isEnabled()
    dialog._allow_install_retry()
    assert dialog.install_button.text() == "Open installer again"
    dialog.install_button.click()
    assert launches == [fake_installer, fake_installer]
    assert dialog.isVisible() is False  # created without exec(); detection is timer driven
    installed[0] = True
    dialog._check_installation()
    _pump_until(qt_app, lambda: dialog.result() == QDialog.DialogCode.Accepted)


@pytest.mark.parametrize("close_window", [False, True])
def test_cancelled_download_closes_without_install(tmp_path, qt_app, close_window):
    started = []
    launches = []

    def downloader(_cache, *, cancelled, progress):
        started.append(True)
        progress(1, 10)
        while not cancelled():
            time.sleep(0.005)
        raise DownloadCancelled("cancelled")

    dialog = PrerequisiteDialog(tmp_path, finder=lambda: None, downloader=downloader,
                                launcher=lambda path: launches.append(path))
    dialog.show()
    dialog.download_button.click()
    _pump_until(qt_app, lambda: started)
    if close_window:
        dialog.close()
    else:
        dialog.reject()
    _pump_until(qt_app, lambda: not dialog.download_thread or not dialog.download_thread.isRunning())
    _pump_until(qt_app, lambda: dialog.result() == QDialog.DialogCode.Rejected)
    assert launches == []
    assert list(tmp_path.iterdir()) == []


def test_existing_install_skips_dialog(tmp_path, qt_app):
    assert ensure_bakkes_available(tmp_path, finder=lambda: tmp_path,
        downloader=lambda *_args, **_kwargs: pytest.fail("should not download"),
        launcher=lambda _path: pytest.fail("should not install"))


def test_existing_game_precedes_prerequisite_setup(monkeypatch):
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    monkeypatch.setattr(bootstrap, "game_processes", lambda: ["RocketLeague.exe"])
    with pytest.raises(RuntimeError, match="Close the existing Rocket League"):
        bootstrap.preflight_offline({"launcher": "steam", "install_path": "unused"})


def test_interactive_installer_rechecks_bytes_and_uses_windows_uac(tmp_path, monkeypatch):
    installer = tmp_path / "BakkesModSetup.exe"
    installer.write_bytes(b"fake")
    calls = []
    monkeypatch.setattr(prerequisites.sys, "platform", "win32")
    monkeypatch.setattr(prerequisites, "_valid_exe", lambda path, spec: False)
    monkeypatch.setattr(prerequisites.os, "startfile", lambda *args: calls.append(args), raising=False)
    with pytest.raises(prerequisites.PrerequisiteError, match="verification"):
        prerequisites.launch_verified_bakkes_setup(installer)
    assert calls == []
    monkeypatch.setattr(prerequisites, "_valid_exe", lambda path, spec: True)
    prerequisites.launch_verified_bakkes_setup(installer)
    assert calls == [(str(installer), "runas")]


def test_cancel_beats_automatic_install_detection(tmp_path, qt_app):
    installed = [False]
    started = []

    def downloader(_cache, *, cancelled, progress):
        started.append(True)
        while not cancelled():
            time.sleep(0.005)
        raise DownloadCancelled("cancelled")

    dialog = PrerequisiteDialog(tmp_path, finder=lambda: tmp_path if installed[0] else None,
                                downloader=downloader, launcher=lambda path: pytest.fail("must not launch"))
    dialog.download_button.click()
    _pump_until(qt_app, lambda: started)
    installed[0] = True
    dialog._check_installation()
    dialog.reject()
    _pump_until(qt_app, lambda: dialog.download_thread is None)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_bakkes_readiness_waits_for_injector(tmp_path, monkeypatch):
    executable = tmp_path / "BakkesMod.exe"
    monkeypatch.setattr(bootstrap, "bakkes_directory", lambda: tmp_path)
    monkeypatch.setattr(bootstrap, "_injector_running", lambda: False)
    monkeypatch.setattr(bootstrap, "_injector_candidates", lambda root: [executable])
    assert bootstrap.bakkes_ready() is None
    executable.write_bytes(b"present")
    assert bootstrap.bakkes_ready() == tmp_path
