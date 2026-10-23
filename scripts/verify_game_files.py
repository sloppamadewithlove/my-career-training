"""Read-only Steam install integrity receipts; Python 3.12, no project dependencies.

These hashes compare bytes. They do not verify native menus, compatibility or EAC.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

MAX_ENTRIES = 50_000
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
REPARSE_POINT = 0x400


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE_POINT)


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _root(path: Path) -> Path:
    path = path.absolute()
    for component in (path, *path.parents):
        if _linked(component.lstat()):
            raise ValueError("Game install path must not contain a symlink or reparse point")
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Game install must be a directory")
    return path


def _outside(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    if resolved == root or root in resolved.parents:
        raise ValueError("Receipt paths must be outside the game installation")
    return resolved


def _open_readonly(path: Path):
    if os.name != "nt":
        return os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)), "rb")
    # OPEN_REPARSE_POINT opens the link itself instead of following a substituted link.
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   wintypes.LPVOID, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x00200000 | 0x08000000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    transferred = False
    try:
        class AttributeTag(ctypes.Structure):
            _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]
        attributes = AttributeTag()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes.attributes & REPARSE_POINT:
            raise ValueError("File became a reparse point")
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        transferred = True
        return os.fdopen(descriptor, "rb")
    finally:
        if not transferred:
            kernel.CloseHandle(handle)


def _hash_file(path: Path, before: os.stat_result) -> dict:
    digest = hashlib.sha256()
    with _open_readonly(path) as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise ValueError("File changed before hashing")
        remaining = before.st_size
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError("File shrank during hashing")
            digest.update(block)
            remaining -= len(block)
        if stream.read(1):
            raise ValueError("File grew during hashing")
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if _linked(current) or _identity(before) != _identity(after) or _identity(before) != _identity(current):
        raise ValueError("File changed during hashing")
    return {"size": after.st_size, "sha256": digest.hexdigest()}


def snapshot(root: Path) -> dict:
    """Every skipped/unreadable/unstable entry makes this receipt incomplete."""
    root = _root(root)
    files: dict[str, dict] = {}
    errors: list[dict] = []
    entries = 0

    def visit(directory: Path):
        nonlocal entries
        before = directory.lstat()
        if _linked(before) or not stat.S_ISDIR(before.st_mode):
            raise ValueError("Directory became a link or non-directory")
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError(f"Entry limit exceeded ({MAX_ENTRIES}); snapshot incomplete")
                path = Path(child.path)
                relative = path.relative_to(root).as_posix()
                try:
                    # DirEntry.stat() on Windows caches zero st_ino/st_dev values;
                    # use fresh no-follow metadata for comparison with the opened handle.
                    # https://docs.python.org/3.12/library/os.html#os.DirEntry.stat
                    info = path.lstat()
                    if _linked(info):
                        raise ValueError("Symlink/reparse point skipped")
                    if stat.S_ISDIR(info.st_mode):
                        visit(path)
                    elif stat.S_ISREG(info.st_mode):
                        files[relative] = _hash_file(path, info)
                    else:
                        raise ValueError("Non-ordinary file skipped")
                except (OSError, ValueError) as error:
                    errors.append({"path": relative, "error": str(error)})
                    if entries > MAX_ENTRIES:
                        raise
        after = directory.lstat()
        if _linked(after) or _identity(before) != _identity(after):
            raise ValueError("Directory contents changed during snapshot")

    try:
        visit(root)
    except (OSError, ValueError) as error:
        errors.append({"path": ".", "error": str(error)})
    return {"format": "mct-game-files-v1", "root": str(root),
            "created_utc": datetime.now(timezone.utc).isoformat(), "complete": not errors,
            "files": files, "errors": errors}


def load_baseline(path: Path, root: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Baseline exceeds size limit")
    baseline = json.loads(data)
    if not isinstance(baseline, dict) or baseline.get("format") != "mct-game-files-v1":
        raise ValueError("Invalid baseline format")
    if baseline.get("complete") is not True or baseline.get("errors") != []:
        raise ValueError("Baseline is incomplete; create a clean baseline first")
    if os.path.normcase(baseline.get("root", "")) != os.path.normcase(str(root)):
        raise ValueError("Baseline belongs to a different game installation")
    records = baseline.get("files")
    if not isinstance(records, dict) or len(records) > MAX_ENTRIES:
        raise ValueError("Invalid baseline file count")
    for name, record in records.items():
        parts = PurePosixPath(name)
        if not name or parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
            raise ValueError("Invalid relative path in baseline")
        if (not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0
                or not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in record["sha256"])):
            raise ValueError("Invalid file record in baseline")
    return baseline


def compare(baseline: dict, current: dict) -> dict:
    old, new = baseline["files"], current["files"]
    # A path we could not inspect is unknown, not a confirmed missing file.
    failed = [item["path"] for item in current["errors"]]
    missing = [name for name in old.keys() - new.keys()
               if not any(p == "." or name == p or name.startswith(p + "/") for p in failed)]
    changed = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])
    added = sorted(new.keys() - old.keys())
    return {"format": "mct-game-compare-v1", "root": current["root"],
            "created_utc": current["created_utc"], "complete": current["complete"],
            "unchanged": current["complete"] and not (changed or missing or added),
            "changed": changed, "missing": sorted(missing), "added": added, "errors": current["errors"]}


def _write_receipt(path: Path, document: dict):
    # Exclusive creation prevents accidentally replacing an earlier baseline.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "compare"))
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New receipt outside the game folder")
    parser.add_argument("--baseline", type=Path, help="Required for compare")
    args = parser.parse_args(argv)
    try:
        root = _root(args.game_dir)
        output = _outside(args.output, root)
        if output.exists():
            raise ValueError("Output already exists; choose a new receipt filename")
        if args.mode == "compare":
            if args.baseline is None:
                raise ValueError("compare requires --baseline")
            baseline = load_baseline(_outside(args.baseline, root), root)
        elif args.baseline is not None:
            raise ValueError("--baseline is only used with compare")
        current = snapshot(root)
        result = compare(baseline, current) if args.mode == "compare" else current
        _write_receipt(output, result)
        if args.mode == "baseline":
            print(f"Baseline: {len(current['files'])} files; {len(current['errors'])} errors. Receipt: {output}")
            return 0 if result["complete"] else 2
        print(f"Compare: {len(result['changed'])} changed, {len(result['missing'])} missing, "
              f"{len(result['added'])} added, {len(result['errors'])} errors. Receipt: {output}")
        return 0 if result["unchanged"] else 2
    except (OSError, ValueError, TypeError) as error:
        print(f"Cannot verify: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
