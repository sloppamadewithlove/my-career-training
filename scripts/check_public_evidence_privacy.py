"""Heuristic checks for private data in public Markdown evidence."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HOME_PATHS = (
    re.compile(
        r"(?i)(?<![A-Z0-9_])[A-Z]:[\\/]+Users[\\/]+"
        r"(?!(?:Public|Default|All Users|user|username|<[^>]+>|%[^%]+%|\$\{[^}]+\})[\\/])[^\\/\s<>]+"
    ),
    re.compile(
        r"(?i)(?<![A-Z0-9_])(?:\\\\\?\\UNC\\|\\\\|//)[^\\/\s]+[\\/]+(?:Users|home)[\\/]+"
        r"(?!(?:Public|Default|All Users|Shared|Guest|user|username|<[^>]+>|%[^%]+%|\$\{[^}]+\})[\\/])[^\\/\s<>]+"
    ),
    re.compile(
        r"(?i)(?<![\w/])/(?:Users|home)/"
        r"(?!(?:Shared|Guest|user|username|<[^>]+>|%[^%]+%|\$\{[^}]+\})/)[^/\s<>]+"
    ),
)
EMAIL = re.compile(
    r"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?)+\b"
)
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net", "example.invalid", "example.test"}
PLATFORM_ID = re.compile(
    r"(?i)\b(?:steam(?:\s*(?:account\s*)?id(?:64)?)?|"
    r"epic\s*(?:account\s*)?id|psn(?:\s*id)?|playstation\s*(?:network\s*)?id|"
    r"xbox\s*(?:live\s*)?(?:id|gamertag)|discord\s*(?:user\s*)?id|"
    r"platform\s*(?:account\s*)?id)\s*[:=]\s*"
    r"(?P<value>[A-Z0-9][A-Z0-9_.-]{5,})"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.IGNORECASE)
GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
AUTHORIZATION_BEARER = re.compile(
    r"(?i)\b(?:proxy-)?authorization\s*[:=]\s*Bearer\s+"
    r"(?P<value>[A-Z0-9._~+/=\-]{8,})"
)
CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[ _-]?key|access[ _-]?key|private[ _-]?key|"
    r"set[ _-]?cookies?|cookies?|session(?:[ _-]?id)?|secret|token|password|passwd|key)\b\s*[:=]\s*"
    r"['\"]?(?P<value>[^\s,;'\"`]+)"
)
PLACEHOLDERS = {
    "...", "example", "example-key", "example-token", "n/a", "none", "null",
    "placeholder", "redacted", "<redacted>", "[redacted]", "<secret>", "[secret]",
    "<placeholder>", "[placeholder]", "<example>", "[example]", "value", "string",
    "your_key", "your-key", "your_password", "your-password", "your_secret", "your-secret",
    "your_token", "your-token",
}


def _is_placeholder(value: str) -> bool:
    value = value.strip().lower()
    return (
        value in PLACEHOLDERS
        or value.startswith(("redacted", "placeholder", "example-", "example_", "your-", "your_"))
        or re.fullmatch(r"(?:x{3,}|0{4,}|\*{3,}|\.{3,})", value) is not None
    )


def rules_for_line(line: str) -> tuple[str, ...]:
    rules: list[str] = []
    if any(pattern.search(line) for pattern in HOME_PATHS):
        rules.append("home-path")
    for match in EMAIL.finditer(line):
        domain = match.group(0).rsplit("@", 1)[1].rstrip(".,;:").lower()
        if not any(domain == item or domain.endswith("." + item) for item in EXAMPLE_DOMAINS):
            rules.append("private-email")
            break
    for match in PLATFORM_ID.finditer(line):
        if not _is_placeholder(match.group("value")):
            rules.append("platform-id")
            break
    if PRIVATE_KEY.search(line):
        rules.append("private-key")
    if GITHUB_TOKEN.search(line):
        rules.append("github-token")
    if AWS_ACCESS_KEY.search(line):
        rules.append("aws-access-key")
    if any(not _is_placeholder(match.group("value")) for match in AUTHORIZATION_BEARER.finditer(line)):
        rules.append("credential-assignment")
    if any(not _is_placeholder(match.group("value")) for match in CREDENTIAL_ASSIGNMENT.finditer(line)):
        rules.append("credential-assignment")
    return tuple(rules)


def _path_sort_key(path: str) -> tuple[str, str]:
    return path.casefold(), path


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "<outside-repository>"


def scan_paths(inputs: list[str], root: Path) -> list[tuple[str, int, str]]:
    root = root.resolve()
    files: dict[Path, str] = {}
    findings: list[tuple[str, int, str]] = []

    for raw_path in inputs:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            candidate = candidate.resolve()
        except (OSError, RuntimeError, ValueError):
            findings.append(("<path-resolution>", 0, "read-error"))
            continue
        if not candidate.is_relative_to(root):
            findings.append(("<outside-repository>", 0, "outside-path"))
            continue
        if candidate.is_dir():
            try:
                children = sorted(candidate.rglob("*"), key=lambda item: _path_sort_key(item.as_posix()))
            except (OSError, RuntimeError, ValueError):
                findings.append((_display_path(candidate, root), 0, "read-error"))
                continue
            for child in children:
                if child.suffix.lower() != ".md":
                    continue
                try:
                    resolved = child.resolve()
                except (OSError, RuntimeError, ValueError):
                    findings.append(("<path-resolution>", 0, "read-error"))
                    continue
                if not resolved.is_relative_to(root):
                    findings.append(("<outside-repository>", 0, "outside-path"))
                elif resolved.is_file():
                    files[resolved] = _display_path(resolved, root)
        elif candidate.is_file() and candidate.suffix.lower() == ".md":
            files[candidate] = _display_path(candidate, root)
        else:
            findings.append((_display_path(candidate, root), 0, "read-error"))

    for path, display in sorted(files.items(), key=lambda item: _path_sort_key(item[1])):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append((display, 0, "read-error"))
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in rules_for_line(line):
                findings.append((display, line_number, rule))

    return sorted(findings, key=lambda item: (*_path_sort_key(item[0]), item[1], item[2]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_public_evidence_privacy.py",
        description="Check explicitly named Markdown evidence from the repository root.",
    )
    parser.add_argument("paths", nargs="+", help="Markdown files or directories to scan")
    args = parser.parse_args(argv)
    findings = scan_paths(args.paths, Path.cwd())
    for path, line_number, rule in findings:
        print(f"{path}:{line_number}:{rule}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
