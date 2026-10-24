"""The private helper cannot accidentally become a second player app."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "packaging" / "worker_entry.py"


def test_explicit_worker_round_trip_exits_without_opening_game():
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run(
        [sys.executable, str(ENTRY), "--worker"],
        input='{"type":"ping","id":"entry"}\n{"type":"shutdown","id":"exit"}\n',
        text=True, capture_output=True, timeout=15, env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr
    messages = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [message["type"] for message in messages] == ["ready", "pong", "stopped"]
    assert messages[1]["id"] == "entry"
    assert messages[2]["id"] == "exit"


def test_manual_helper_start_explains_correct_entry_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(ENTRY)])
    monkeypatch.setattr(sys, "platform", "linux")
    from my_career_training import __main__
    monkeypatch.setattr(__main__, "main", lambda: pytest.fail("Manual helper started the app"))
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ENTRY), run_name="__main__")
    assert stopped.value.code == 2
    assert "Open My Career Training from its shortcut" in capsys.readouterr().err
