"""Receipts distinguish unchanged bytes, changed files and incomplete inspection."""
import importlib.util
import json
from pathlib import Path

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
    assert verify.main(["baseline", "--game-dir", str(root), "--output", str(baseline)]) == 0
    record = json.loads(baseline.read_text())
    assert record["files"]["asset.upk"]["size"] == 5
    assert len(record["files"]["asset.upk"]["sha256"]) == 64
    before = baseline.read_bytes()
    assert verify.main(["baseline", "--game-dir", str(root), "--output", str(baseline)]) == 2
    assert baseline.read_bytes() == before
    clean = tmp_path / "clean.json"
    assert verify.main(["compare", "--game-dir", str(root), "--baseline", str(baseline),
                        "--output", str(clean)]) == 0
    assert json.loads(clean.read_text())["unchanged"] is True
    (root / "asset.upk").unlink()
    (root / "Binaries" / "Win64" / "RocketLeague.exe").write_bytes(b"changed")
    (root / "new.dll").write_bytes(b"new")
    report = tmp_path / "after.json"
    assert verify.main(["compare", "--game-dir", str(root), "--baseline", str(baseline),
                        "--output", str(report)]) == 2
    result = json.loads(report.read_text())
    assert result["changed"] == ["Binaries/Win64/RocketLeague.exe"]
    assert result["missing"] == ["asset.upk"]
    assert result["added"] == ["new.dll"]
    assert result["complete"] is True and result["unchanged"] is False


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
    manifest.write_text(json.dumps(verify.snapshot(root)))
    with pytest.raises(ValueError, match="different"):
        verify.load_baseline(manifest, tmp_path)
    monkeypatch.setattr(verify, "MAX_MANIFEST_BYTES", 2)
    with pytest.raises(ValueError, match="size limit"):
        verify.load_baseline(manifest, root)
