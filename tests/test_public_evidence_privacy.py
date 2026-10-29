from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_public_evidence_privacy.py"


@pytest.mark.parametrize(
    ("content", "rule", "sensitive_value"),
    [
        (r"source: C:\Users\synthetic-person\Documents\save", "home-path", "synthetic-person"),
        ("source: /Users/synthetic-person/Documents/save", "home-path", "synthetic-person"),
        ("source: /home/synthetic-person/save", "home-path", "synthetic-person"),
        (
            "contact: synthetic-lint-fixture-0001@private.co",
            "private-email",
            "synthetic-lint-fixture-0001@private.co",
        ),
        ("SteamID: fixture-account-123456", "platform-id", "fixture-account-123456"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----", "private-key", "OPENSSH PRIVATE KEY"),
        ("ghp_syntheticFixtureToken000000000", "github-token", "ghp_syntheticFixtureToken000000000"),
        ("AKIASYNTHETIC000001X", "aws-access-key", "AKIASYNTHETIC000001X"),
        ("password = syntheticSensitiveValue123!", "credential-assignment", "syntheticSensitiveValue123!"),
    ],
)
def test_sensitive_values_fail_without_echoing_them(tmp_path, content, rule, sensitive_value):
    evidence = tmp_path / "docs" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "sample.md").write_text(content, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "docs/evidence"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert f"docs/evidence/sample.md:1:{rule}" in result.stdout
    assert sensitive_value not in result.stdout + result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


def test_example_and_redaction_placeholders_pass(tmp_path):
    evidence = tmp_path / "docs" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "sample.md").write_text(
        """Examples: user@example.com, user@example.invalid, /home/<user>, C:\\Users\\username\\save

"""
        """Redacted fields: token=<redacted>; password=YOUR_PASSWORD; key=placeholder; SteamID=<id>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "docs/evidence"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_recursive_scan_is_sorted_and_reports_read_errors_safely(tmp_path):
    evidence = tmp_path / "docs" / "evidence"
    (evidence / "nested").mkdir(parents=True)
    (evidence / "z.md").write_text("password=oneSyntheticValue123\n", encoding="utf-8")
    (evidence / "nested" / "a.md").write_text("secret=anotherSyntheticValue456\n", encoding="utf-8")
    (evidence / "bad.md").write_bytes(b"\xff\xfe")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "docs/evidence"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines == [
        "docs/evidence/bad.md:0:read-error",
        "docs/evidence/nested/a.md:1:credential-assignment",
        "docs/evidence/z.md:1:credential-assignment",
    ]
    assert "SyntheticValue" not in result.stdout + result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr

