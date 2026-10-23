"""Ordered online handoff. Call tick from the event loop, never block the UI."""
from __future__ import annotations

import time

CONFIRMATION = "Are you sure you want to close this and play online?"


class Lifecycle:
    def __init__(self, save, stop_worker, close_game, game_alive, launch, clock=time.monotonic):
        self.save, self.stop_worker, self.close_game = save, stop_worker, close_game
        self.game_alive, self.launch, self.clock = game_alive, launch, clock
        self.state = "Idle"
        self.message = ""
        self.deadline = 0
        self.frozen = False
        self.confirming = False
        self.last_error = ""

    def request_online(self):
        if self.frozen:
            raise ValueError("Wait for the current transition to finish.")
        self.confirming = True

    def confirm_online(self, yes: bool):
        if not self.confirming:
            return
        self.confirming = False
        if not yes:
            return
        self.frozen = True
        try:
            self.save()  # Must be durable before any shutdown side effect.
            self.state = "Stopping Career"
            self.message = "Saving complete. Stopping the career connection…"
            self.deadline = self.clock() + 20
            self.stop_worker()
        except Exception as exc:
            self.fail(str(exc))

    def worker_stopped(self):
        if self.state != "Stopping Career":
            return
        try:
            # Drain/commit all prior worker results before the stopped acknowledgment.
            self.save()
            self.close_game()
            self.state = "Waiting for Game Exit"
            self.message = "Waiting for the career game window to close…"
            self.deadline = self.clock() + 30
            self.tick()
        except Exception as exc:
            self.fail(str(exc))

    def tick(self):
        if self.state == "Waiting for Game Exit":
            try:
                if not self.game_alive():
                    self.state = "Starting Online"
                    self.message = self.launch()
                    self.state = "Online Launch Requested"
                    self.frozen = False
                elif self.clock() >= self.deadline:
                    self.fail("The game is still open. Close its window, then choose Play Online to retry.")
            except Exception as exc:
                self.fail(str(exc))
        elif self.state == "Stopping Career" and self.clock() >= self.deadline:
            self.fail("The career connection has not stopped. Wait or close the game, then retry.")

    def fail(self, message):
        self.state = "Error/Recovery"
        self.message = self.last_error = message
        self.frozen = False
