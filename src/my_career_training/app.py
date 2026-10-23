"""Qt application and foreground-only controller navigation."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox

from .bridge import Backend


class ControllerNavigation:
    """Read the user's controller only while our window is active; never hook game input."""
    def __init__(self, app):
        self.app = app
        self.previous = set()
        self.joysticks = {}
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        self.pygame = pygame
        pygame.display.init()
        pygame.joystick.init()
        pygame.display.set_mode((1, 1), pygame.HIDDEN)
        self.timer = QTimer(app)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)

    def poll(self):
        p = self.pygame
        for event in p.event.get():
            if event.type == p.JOYDEVICEADDED:
                stick = p.joystick.Joystick(event.device_index)
                self.joysticks[stick.get_instance_id()] = stick
            elif event.type == p.JOYDEVICEREMOVED:
                self.joysticks.pop(event.instance_id, None)
                self.previous.clear()
        if self.app.applicationState() != Qt.ApplicationActive:
            self.previous.clear()
            return
        keys = set()
        for stick in self.joysticks.values():
            if stick.get_numbuttons() > 1:
                if stick.get_button(0):
                    keys.add(Qt.Key_Return)
                if stick.get_button(1):
                    keys.add(Qt.Key_Escape)
            if stick.get_numhats():
                x, y = stick.get_hat(0)
                if y or x:
                    keys.add(Qt.Key_Backtab if y > 0 or x < 0 else Qt.Key_Tab)
            if stick.get_numaxes() > 1 and abs(stick.get_axis(1)) > 0.65:
                keys.add(Qt.Key_Backtab if stick.get_axis(1) < 0 else Qt.Key_Tab)
        target = self.app.focusObject()
        if target is not None:
            for key in keys - self.previous:
                modifiers = Qt.ShiftModifier if key == Qt.Key_Backtab else Qt.NoModifier
                QCoreApplication.postEvent(target, QKeyEvent(QEvent.KeyPress, key, modifiers))
                QCoreApplication.postEvent(target, QKeyEvent(QEvent.KeyRelease, key, modifiers))
        self.previous = keys


def run(directory, smoke_test=False, screenshot=None):
    QQuickStyle.setStyle("Basic")
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("MyCareerTraining")
    app.setApplicationName("My Career Training")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "ui/icon.ico")))
    try:
        backend = Backend(directory)
    except Exception as exc:
        if not smoke_test:
            QMessageBox.critical(None, "My Career Training", str(exc))
        return 1
    engine = QQmlApplicationEngine()
    backend.exitRequested.connect(app.quit)
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "ui/Main.qml")))
    if not engine.rootObjects():
        backend.store.close()
        return 1
    navigation = None
    if not smoke_test:
        try:
            navigation = ControllerNavigation(app)
        except Exception:
            backend.notice = "Controller navigation is unavailable here. Mouse and keyboard remain available."
            backend.stateChanged.emit()
    if smoke_test:
        def finish():
            if screenshot:
                engine.rootObjects()[0].grabWindow().save(str(screenshot))
            app.quit()
        QTimer.singleShot(600, finish)
    code = app.exec()
    try:
        backend.close()
    except Exception:
        backend.store.close()
        code = 1
    if navigation:
        navigation.pygame.quit()
    return code
