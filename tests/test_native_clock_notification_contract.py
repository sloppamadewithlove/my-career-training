"""Source-level guard for the native clock writer consumed by the game HUD."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugin" / "src" / "MyCareerTraining.cpp"
SIGNATURE = "void MyCareerTraining::updateTrainingClock(const Json& state, bool cleanup)"


def _without_comments_and_literals(source: str) -> str:
    """Mask C++ comments and quoted literals while keeping braces/positions."""
    chars = list(source)
    cursor = 0
    while cursor < len(source):
        if source.startswith("//", cursor):
            end = source.find("\n", cursor)
            if end < 0:
                end = len(source)
        elif source.startswith("/*", cursor):
            found = source.find("*/", cursor + 2)
            end = len(source) if found < 0 else found + 2
        elif source[cursor] in ("\"", "'"):
            quote = source[cursor]
            end = cursor + 1
            while end < len(source):
                if source[end] == "\\":
                    end += 2
                elif source[end] == quote:
                    end += 1
                    break
                else:
                    end += 1
        else:
            cursor += 1
            continue
        for index in range(cursor, end):
            if chars[index] not in "\r\n":
                chars[index] = " "
        cursor = end
    return "".join(chars)


def _function_body(code: str, signature: str) -> str:
    start = code.find(signature)
    assert start >= 0, f"missing production clock method: {signature}"
    opening = code.find("{", start)
    assert opening >= 0, "production clock method has no body"
    depth = 0
    for offset in range(opening, len(code)):
        if code[offset] == "{":
            depth += 1
        elif code[offset] == "}":
            depth -= 1
            if depth == 0:
                return code[opening + 1 : offset]
    raise AssertionError("production clock method body is not closed")


def _assert_order(source: str, *tokens: str) -> None:
    positions = []
    for token in tokens:
        assert token in source, f"missing native clock contract token: {token}"
        positions.append(source.index(token))
    assert positions == sorted(positions), (
        "native clock writer must snapshot before writes, store both time fields "
        "before notifying the HUD, then verify readback"
    )


def test_native_clock_writer_notifies_after_integer_write_before_readback():
    source = _without_comments_and_literals(SOURCE.read_text(encoding="utf-8"))
    body = _function_body(source, SIGNATURE)
    read_start = body.index("auto read = [&]")
    write_start = body.index("auto write = [&]")
    update_start = body.index("trainingClock_.update(server.memory_address")
    read_lambda = body[read_start:write_start]
    write_lambda = body[write_start:update_start]

    for getter in (
        "server.GetGameTimeRemaining()",
        "server.GetbUnlimitedTime() != 0",
        "server.GetSecondsRemaining()",
    ):
        assert getter in read_lambda, f"native clock snapshot misses {getter}"

    notification_guard = re.compile(
        r"if\s*\(\s*before\.seconds\s*!=\s*value\.seconds\s*\|\|\s*"
        r"before\.unlimited\s*!=\s*value\.unlimited\s*\)\s*"
        r"(?:\{\s*server\.OnGameTimeUpdated\(\);\s*\}|"
        r"server\.OnGameTimeUpdated\(\);)",
        re.DOTALL,
    )
    assert notification_guard.search(write_lambda), (
        "HUD notification must be controlled by integer-seconds or unlimited-time changes"
    )
    _assert_order(
        write_lambda,
        "const auto before = read();",
        "server.SetbUnlimitedTime(value.unlimited ? 1UL : 0UL);",
        "server.SetGameTimeRemaining(value.remaining);",
        "server.SetSecondsRemaining(value.seconds);",
        "server.OnGameTimeUpdated();",
        "const auto observed = read();",
        "if (observed.seconds != value.seconds",
    )