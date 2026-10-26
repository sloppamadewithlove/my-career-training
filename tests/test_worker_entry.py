"""The private helper cannot accidentally become a second player app."""
import json
import os
from pathlib import Path
import queue
import runpy
import subprocess
import sys
import threading
import uuid

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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native-import and redirected-stdin regression")
@pytest.mark.parametrize("interpreter_name", ["python.exe", "pythonw.exe"])
def test_background_numpy_import_with_real_worker_stdin_open(tmp_path, interpreter_name):
    interpreter = Path(sys.executable).with_name(interpreter_name)
    assert interpreter.is_file()
    # Use the real packaged entry/JSON reader, replacing only the game session:
    # no core/game starts. Delay the import until the main reader is waiting
    # for its next command, reproducing numpy/numpy#24290 without closing stdin.
    harness = """
import runpy, sys, time
from my_career_training import game_worker
def session(self):
    time.sleep(.2)
    import numpy
    self.event("numpy_ready", version=numpy.__version__)
game_worker.GameSession.run = session
entry = sys.argv[1]
sys.argv = [entry, "--worker"]
runpy.run_path(entry, run_name="__main__")
"""
    process = subprocess.Popen(
        [str(interpreter), "-u", "-c", harness, str(ENTRY)],
        cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    messages = queue.Queue()
    reader = threading.Thread(
        target=lambda: [messages.put(json.loads(line)) for line in process.stdout],
        daemon=True,
    )
    reader.start()
    try:
        assert messages.get(timeout=15)["type"] == "ready"
        sid = str(uuid.uuid4())
        process.stdin.write(json.dumps({"type": "start", "session_id": sid, "data_dir": str(tmp_path)}) + "\n")
        process.stdin.flush()
        imported = messages.get(timeout=10)
        assert imported["type"] == "numpy_ready"
        assert imported["session_id"] == sid
        assert process.poll() is None  # The stdin pipe remained open throughout.
        process.stdin.write('{"type":"shutdown","id":"done"}\n')
        process.stdin.flush()
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()  # Only this synthetic worker subprocess.
            process.wait(timeout=5)
        reader.join(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
