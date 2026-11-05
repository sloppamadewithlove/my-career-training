"""Source-level guard for the native clock writer consumed by the game HUD."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugin" / "src" / "MyCareerTraining.cpp"
SIGNATURE = "void MyCareerTraining::updateTrainingClock(const Json& state, bool cleanup)"


def _function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    assert start >= 0, f"missing production clock method: {signature}"
    opening = source.find("{", start)
    assert opening >= 0, "production clock method has no body"
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : offset]
    raise AssertionError("production clock method body is not closed")


def _assert_order(source: str, *tokens: str) -> None:
    positions = []
    for token in tokens:
        assert token in source, f"missing native clock contract token: {token}"
        positions.append(source.index(token))
    assert positions == sorted(positions), (
        "native clock writer must store both time fields before notifying "
        "the HUD and verifying readback"
    )


def test_native_clock_writer_notifies_after_integer_write_before_readback():
    source = SOURCE.read_text(encoding="utf-8")
    body = _function_body(source, SIGNATURE)
    read_start = body.index("auto read = [&]")
    write_start = body.index("auto write = [&]")
    update_start = body.index("trainingClock_.update(")
    read_lambda = body[read_start:write_start]
    write_lambda = body[write_start:update_start]

    for getter in (
        "server.GetGameTimeRemaining()",
        "server.GetbUnlimitedTime() != 0",
        "server.GetSecondsRemaining()",
    ):
        assert getter in read_lambda, f"native clock snapshot misses {getter}"

    guard = "if (before.seconds != value.seconds || before.unlimited != value.unlimited)"
    assert guard in write_lambda, (
        "HUD notification must be gated by integer-seconds or unlimited-time changes"
    )
    _assert_order(
        write_lambda,
        "server.SetbUnlimitedTime(value.unlimited ? 1UL : 0UL);",
        "server.SetGameTimeRemaining(value.remaining);",
        "server.SetSecondsRemaining(value.seconds);",
        guard,
        "server.OnGameTimeUpdated();",
        "const auto observed = read();",
        "if (observed.seconds != value.seconds",
    )