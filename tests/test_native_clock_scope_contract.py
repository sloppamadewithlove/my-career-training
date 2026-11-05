"""Source guard for the production native-clock offline-session boundary."""
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parents[1] / "plugin" / "src" / "MyCareerTraining.cpp"
SIGNATURE = "void MyCareerTraining::updateTrainingClock(const Json& state, bool cleanup)"
_NON_CODE = re.compile(
    r"//[^\r\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
    re.S,
)


def _mask_cpp(text):
    return _NON_CODE.sub(lambda m: re.sub(r"[^\r\n]", " ", m.group()), text)


def _block(code, opening):
    depth = 0
    for i in range(opening, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[opening + 1 : i], i
    raise AssertionError("unclosed C++ block")


def _function_body(code):
    match = re.search(re.escape(SIGNATURE) + r"\s*\{", code)
    assert match, f"missing production clock function: {SIGNATURE}"
    return _block(code, match.end() - 1)[0]


def test_native_clock_requires_offline_session_before_server_access():
    body = _function_body(_mask_cpp(SOURCE.read_text(encoding="utf-8")))
    offline = re.search(r"const\s+bool\s+offline\s*=\s*(.*?);", body, re.S)
    assert offline, "offline-session expression missing"
    expr = offline.group(1)
    assert re.search(
        r"\bgameWrapper\s*&&\s*gameWrapper\s*->\s*IsInGame\s*\(\s*\)",
        expr,
    ), "clock must require an active game wrapper"
    assert re.search(
        r"!\s*gameWrapper\s*->\s*IsInOnlineGame\s*\(\s*\)", expr
    ), "online exclusion removed"
    assert re.search(
        r"!\s*gameWrapper\s*->\s*IsInReplay\s*\(\s*\)", expr
    ), "replay exclusion removed"
    gate = re.search(r"if\s*\(\s*!\s*offline\s*\)\s*\{", body)
    assert gate, "early offline-session gate missing"
    rejected, gate_end = _block(body, gate.end() - 1)
    assert re.search(
        r"trainingClock_\s*\.\s*update\s*\(\s*0\s*,\s*false\s*,",
        rejected,
    ), "rejected session must clear the clock lease without writing"
    assert re.search(
        r"trainingClockStatus_\s*=\s*Json::object\s*\(\s*\)", rejected
    ), "rejected session must clear clock status"
    assert re.search(r"\breturn\s*;", rejected), "offline-session gate must return"
    event = body.find("GetGameEventAsServer")
    assert event > gate_end, "native event wrapper must be acquired after the offline gate"
