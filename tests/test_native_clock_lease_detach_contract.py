"""Source guards for TrainingClock lease detachment."""
from pathlib import Path
import re

import pytest

HEADER = Path(__file__).resolve().parent.parent / "plugin/include/TrainingClock.h"


def _mask(source):
    patterns = (
        r"/\*.*?\*/",
        r"//[^\n]*",
        r"\"(?:\\.|[^\"\\])*\"",
        r"'(?:\\.|[^'\\])*'",
    )
    for pattern in patterns:
        source = re.sub(
            pattern, lambda match: " " * len(match.group()), source, flags=re.S
        )
    return source


def _block(source, opening):
    assert source[opening] == "{"
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening : index + 1]
    raise AssertionError("unbalanced C++ block")


def _if_block(body, condition):
    match = re.search(condition, body)
    assert match, f"if block absent: {condition!r}"
    return _block(body, body.index("{", match.end()))


@pytest.fixture(scope="module")
def update_body():
    assert HEADER.is_file(), f"header not found: {HEADER}"
    source = _mask(HEADER.read_text(encoding="utf-8"))
    method = re.search(r"\bupdate\s*\(", source)
    assert method, "TrainingClock update method absent"
    return _block(source, source.index("{", method.end()))


def _assert_detach_without_write(body, label, condition):
    block = _if_block(body, r"if\s*\(\s*" + condition + r"\s*\)")
    clear = re.search(r"\bclear\s*\(\s*\)", block)
    returning = re.search(r"\breturn\b", block)
    assert clear, f"{label}: missing clear()"
    assert returning, f"{label}: missing return"
    assert clear.start() < returning.start(), f"{label}: return before clear()"
    assert not re.search(r"\bwrite\s*\(", block), f"{label}: unexpected write()"


def test_offline_detach_does_not_write():
    body = update_body.__wrapped__()
    _assert_detach_without_write(body, "!offline", r"!\s*offline")


def test_replaced_event_detach_does_not_write():
    body = update_body.__wrapped__()
    _assert_detach_without_write(
        body, "active_&&event!=event_", r"active_\s*&&\s*event\s*!=\s*event_"
    )
