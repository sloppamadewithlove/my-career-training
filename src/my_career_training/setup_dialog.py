"""Visible, opt-in first-run setup for the official BakkesMod prerequisite."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from .prerequisites import PrerequisiteError, launch_verified_bakkes_setup, prepare_bakkes_setup


class _Downloader(QObject):
    progress = Signal(int, int)
    ready = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, cache: Path, download: Callable, cancelled: threading.Event):
        super().__init__()
        self.cache = cache
        self.download = download
        self.cancelled = cancelled

    @Slot()
    def run(self) -> None:
        try:
            path = self.download(self.cache, progress=self.progress.emit, cancelled=self.cancelled.is_set)
            self.ready.emit(str(path))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PrerequisiteDialog(QDialog):
    def __init__(
        self,
        cache: Path,
        *,
        finder: Callable,
        downloader: Callable = prepare_bakkes_setup,
        launcher: Callable[[Path], None] = launch_verified_bakkes_setup,
    ):
        super().__init__()
        self.cache = Path(cache)
        self.finder = finder
        self.downloader = downloader
        self.launcher = launcher
        self.installer: Path | None = None
        self.download_thread: QThread | None = None
        self._worker: _Downloader | None = None
        self._cancel_download = threading.Event()
        self._close_after_worker = False
        self._accept_after_worker = False

        self.setWindowTitle("My Career setup")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "My Career needs BakkesMod to open its menu inside Rocket League. "
            "You can download the official setup here. Windows may ask for administrator approval "
            "when you choose Install. Complete the BakkesMod installer yourself, then open BakkesMod once. "
            "Rocket League will start only after setup is detected."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status = QLabel("BakkesMod is not installed yet.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.download_button = QPushButton("Download official setup")
        self.download_button.clicked.connect(self._begin_download)
        buttons.addWidget(self.download_button)
        self.install_button = QPushButton("Install BakkesMod")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._install_clicked)
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)

        bottom = QHBoxLayout()
        self.check_button = QPushButton("Check installation")
        self.check_button.clicked.connect(self._check_installation)
        bottom.addWidget(self.check_button)
        self.cancel_button = QPushButton("Not now")
        self.cancel_button.clicked.connect(self.reject)
        bottom.addWidget(self.cancel_button)
        layout.addLayout(bottom)

        self._poll = QTimer(self)
        self._poll.timeout.connect(self._check_installation)
        self._poll.start(1_000)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self._allow_install_retry)

    @Slot()
    def _begin_download(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            return
        self._cancel_download.clear()
        self._close_after_worker = False
        self._accept_after_worker = False
        self.installer = None
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status.setText("Downloading the verified official BakkesMod setup…")
        self.cancel_button.setText("Cancel download")
        self.download_thread = QThread(self)
        self._worker = _Downloader(self.cache, self.downloader, self._cancel_download)
        self._worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._set_progress)
        self._worker.ready.connect(self._download_ready)
        self._worker.error.connect(self._download_error)
        self._worker.finished.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self._worker.deleteLater)
        self.download_thread.finished.connect(self._download_stopped)
        self.download_thread.start()

    @Slot(int, int)
    def _set_progress(self, downloaded: int, total: int) -> None:
        self.progress.setValue(round(downloaded * 100 / total) if total else 0)

    @Slot(str)
    def _download_ready(self, path: str) -> None:
        self.installer = Path(path)
        self.progress.setValue(100)
        self.install_button.setEnabled(True)
        self.status.setText("Download verified. Choose Install to open the official BakkesMod installer.")

    @Slot(str)
    def _download_error(self, message: str) -> None:
        if not self._close_after_worker:
            self.status.setText(f"Download did not finish: {message} You can retry.")
            self.download_button.setEnabled(True)

    @Slot()
    def _download_stopped(self) -> None:
        if self.download_thread is not None:
            self.download_thread.deleteLater()
            self.download_thread = None
        self._worker = None
        self.cancel_button.setText("Not now")
        if self._close_after_worker:
            self._poll.stop()
            self._retry.stop()
            super().reject()
        elif self._accept_after_worker:
            self._poll.stop()
            self._retry.stop()
            super().accept()

    @Slot()
    def _install_clicked(self) -> None:
        if self.installer is None:
            return
        try:
            self.launcher(self.installer)
        except PrerequisiteError as exc:
            self.status.setText(str(exc))
            self.installer = None
            self.install_button.setEnabled(False)
            self.download_button.setEnabled(True)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1223:
                self.status.setText("Windows installation approval was cancelled. Choose Install when ready.")
            else:
                self.status.setText(f"Could not open the BakkesMod installer: {exc}")
            return
        self.status.setText("Complete the official installer and open BakkesMod once. Waiting for its files…")
        self.install_button.setEnabled(False)
        self._retry.start(5_000)

    @Slot()
    def _allow_install_retry(self) -> None:
        if self.finder() is None and self.installer is not None:
            self.install_button.setText("Open installer again")
            self.install_button.setEnabled(True)
            self.status.setText("If the official installer was closed, choose Open installer again. "
                                "Open BakkesMod once after setup finishes.")

    @Slot()
    def _check_installation(self) -> None:
        if self._close_after_worker:
            return
        if self.finder() is None:
            return
        if self.download_thread and self.download_thread.isRunning():
            self._accept_after_worker = True
            self._cancel_download.set()
            return
        self._poll.stop()
        self._retry.stop()
        super().accept()

    def reject(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            self._close_after_worker = True
            self._accept_after_worker = False
            self._cancel_download.set()
            self.status.setText("Stopping download…")
            self.cancel_button.setEnabled(False)
            return
        self._poll.stop()
        self._retry.stop()
        super().reject()

    def closeEvent(self, event) -> None:
        if self.download_thread and self.download_thread.isRunning():
            self.reject()
            event.ignore()
            return
        super().closeEvent(event)


def ensure_bakkes_available(
    cache: Path,
    *,
    finder: Callable,
    downloader: Callable = prepare_bakkes_setup,
    launcher: Callable[[Path], None] = launch_verified_bakkes_setup,
) -> bool:
    """Wait for BakkesMod's plugin directory, or return False when deferred."""
    if finder() is not None:
        return True
    dialog = PrerequisiteDialog(cache, finder=finder, downloader=downloader, launcher=launcher)
    return dialog.exec() == QDialog.DialogCode.Accepted and finder() is not None
