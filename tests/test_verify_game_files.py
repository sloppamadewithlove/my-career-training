"""Receipts distinguish unchanged bytes, changed files and incomplete inspection."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "verify_game_files", Path(__file__).resolve().parents[1] / "scripts/verify_game_files.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def installation(tmp_path):
    root = tmp_path / "Rocket League"
    (root / "Binaries" / "Win64").mkdir(parents=True)
    (root / "Binaries" / "Win64" / "RocketLeague.exe").write_bytes(b"game executable")
    (root / "asset.upk").write_bytes(b"asset")
    return root


def test_receipts_compare_bytes_and_never_overwrite(tmp_path):
    root = installation(tmp_path)
    baseline = tmp_path / "before.json"
    status = verify.main(["baseline", "--game-dir", str(root), "--output", str(baseline)])
    record = json.loads(baseline.read_text())
    assert status == 0, record["errors"]
    assert record["files"]["asset.upk"]["size"] == 5
    assert len(record["files"]["asset.upk"]["sha256"]) == 64
    before = baseline.read_bytes()
    assert verify.main(["baseline", "--game-dir", str(root), "--output", str(baseline)]) == 2
    assert baseline.read_bytes() == before
    clean = tmp_path / "clean.json"
    status = verify.main(["compare", "--game-dir", str(root), "--baseline", str(baseline),
                          "--output", str(clean)])
    clean_result = json.loads(clean.read_text())
    assert status == 0, clean_result
    assert clean_result["unchanged"] is True, clean_result
    (root / "asset.upk").unlink()
    (root / "Binaries" / "Win64" / "RocketLeague.exe").write_bytes(b"changed")
    (root / "new.dll").write_bytes(b"new")
    report = tmp_path / "after.json"
    assert verify.main(["compare", "--game-dir", str(root), "--baseline", str(baseline),
                        "--output", str(report)]) == 2
    result = json.loads(report.read_text())
    assert result["complete"] is True, result
    assert result["changed"] == ["Binaries/Win64/RocketLeague.exe"], result
    assert result["missing"] == ["asset.upk"], result
    assert result["added"] == ["new.dll"], result
    assert result["unchanged"] is False, result


def test_outputs_inside_game_are_refused_before_snapshot(tmp_path, monkeypatch):
    root = installation(tmp_path)
    def unexpected(_root):
        pytest.fail("Must reject destination before inspecting game")
    monkeypatch.setattr(verify, "snapshot", unexpected)
    assert verify.main(["baseline", "--game-dir", str(root), "--output", str(root / "receipt.json")]) == 2
    assert not (root / "receipt.json").exists()


def test_unreadable_file_never_reports_clean_or_missing(tmp_path, monkeypatch):
    root = installation(tmp_path)
    baseline = verify.snapshot(root)
    original = verify._hash_file
    def unreadable(path, before):
        if path.name == "asset.upk":
            raise PermissionError("test access denied")
        return original(path, before)
    monkeypatch.setattr(verify, "_hash_file", unreadable)
    current = verify.snapshot(root)
    result = verify.compare(baseline, current)
    assert result["complete"] is False and result["unchanged"] is False
    assert result["errors"][0]["path"] == "asset.upk"
    assert result["missing"] == []
    broken = tmp_path / "incomplete.json"
    broken.write_text(json.dumps(current))
    with pytest.raises(ValueError, match="incomplete"):
        verify.load_baseline(broken, root)


def test_links_are_not_followed_and_invalidate_receipt(tmp_path):
    root = installation(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("not game data")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privilege")
    receipt = verify.snapshot(root)
    assert receipt["complete"] is False
    assert "linked/secret.txt" not in receipt["files"]
    assert any(error["path"] == "linked" for error in receipt["errors"])
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink or reparse"):
        verify.snapshot(alias)
    with pytest.raises(ValueError, match="outside"):
        verify._outside(alias / "report.json", root)


def test_file_replaced_during_hash_and_directory_change_are_errors(tmp_path, monkeypatch):
    root = installation(tmp_path)
    file = root / "asset.upk"
    original_open = verify._open_readonly
    def replace_file(path):
        stream = original_open(path)
        if path == file:
            path.unlink()
            path.write_bytes(b"other")
        return stream
    monkeypatch.setattr(verify, "_open_readonly", replace_file)
    current = verify.snapshot(root)
    assert current["complete"] is False
    assert "asset.upk" not in current["files"]
    assert any("changed" in error["error"].lower() for error in current["errors"])


def test_manifest_limits_and_wrong_install_are_refused(tmp_path, monkeypatch):
    root = installation(tmp_path)
    monkeypatch.setattr(verify, "MAX_ENTRIES", 1)
    receipt = verify.snapshot(root)
    assert receipt["complete"] is False
    assert any("limit" in error["error"] for error in receipt["errors"])
    monkeypatch.setattr(verify, "MAX_ENTRIES", 50_000)
    manifest = tmp_path / "before.json"
    complete = verify.snapshot(root)
    assert complete["complete"], complete["errors"]
    manifest.write_text(json.dumps(complete))
    with pytest.raises(ValueError, match="different"):
        verify.load_baseline(manifest, tmp_path)
    monkeypatch.setattr(verify, "MAX_MANIFEST_BYTES", 2)
    with pytest.raises(ValueError, match="size limit"):
        verify.load_baseline(manifest, root)


def test_directory_entry_identity_cache_is_not_used_for_hash_guard(tmp_path, monkeypatch):
    root = installation(tmp_path)
    real_scandir = verify.os.scandir

    def cached_entry(child):
        info = child.stat(follow_symlinks=False)
        # Windows DirEntry.stat omits these identities even for a stable file.
        cached = SimpleNamespace(st_ino=0, st_dev=0, st_size=info.st_size,
                                 st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns,
                                 st_mode=info.st_mode,
                                 st_file_attributes=getattr(info, "st_file_attributes", 0))
        return SimpleNamespace(path=child.path, stat=lambda **_kwargs: cached)

    @contextmanager
    def cached_scandir(directory):
        with real_scandir(directory) as children:
            yield (cached_entry(child) for child in children)

    monkeypatch.setattr(verify.os, "scandir", cached_scandir)
    receipt = verify.snapshot(root)
    assert receipt["complete"], receipt["errors"]
    assert set(receipt["files"]) == {"asset.upk", "Binaries/Win64/RocketLeague.exe"}


@pytest.mark.parametrize("change_during_read", [False, True])
def test_path_creation_time_and_handle_change_time_are_compared_separately(
        tmp_path, monkeypatch, change_during_read):
    root = installation(tmp_path)
    path = root / "asset.upk"
    before = path.lstat()
    real_fstat = verify.os.fstat
    calls = 0

    def windows_handle_stat(descriptor):
        nonlocal calls
        calls += 1
        info = real_fstat(descriptor)
        # CPython3.12 Windows path stat uses birthtime as ctime, but handle
        # fstat exposes ChangeTime. Stable values may differ after prior writes.
        ctime = info.st_ctime_ns + 1_000_000
        if change_during_read and calls == 2:
            ctime += 1
        return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
                               st_size=info.st_size, st_mtime_ns=info.st_mtime_ns,
                               st_ctime_ns=ctime, st_mode=info.st_mode)

    monkeypatch.setattr(verify.os, "fstat", windows_handle_stat)
    if change_during_read:
        with pytest.raises(ValueError, match="changed during hashing"):
            verify._hash_file(path, before)
    else:
        assert verify._hash_file(path, before)["size"] == len(b"asset")
