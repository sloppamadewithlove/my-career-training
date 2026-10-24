"""Per-launch BakkesMod plugin files are journaled and compared before restore."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from my_career_training.plugin_session import PluginSession, PluginSessionError


@pytest.fixture
def layout(tmp_path, monkeypatch):
    # Synthetic plugin files must not depend on a real developer test session.
    monkeypatch.setattr("my_career_training.platforms.native_launcher_pending", lambda: False)
    root = tmp_path / "bakkes"
    (root / "plugins").mkdir(parents=True)
    (root / "cfg").mkdir()
    source = tmp_path / "MyCareerTraining.dll"
    source.write_bytes(b"career-plugin-v1")
    return SimpleNamespace(
        root=root,
        source=source,
        data=tmp_path / "MyCareerTraining",
        dll=root / "plugins" / "MyCareerTraining.dll",
        cfg=root / "cfg" / "plugins.cfg",
        journal=tmp_path / "MyCareerTraining" / "plugin-session",
    )


def session(layout, *, running=False):
    return PluginSession(layout.data, root=layout.root, game_running=lambda: running)


def test_absent_files_are_created_for_the_session_and_removed_afterward(layout):
    report = session(layout).begin(layout.source)

    assert report["dll"] == "installed"
    assert report["config"] == "created"
    assert layout.dll.read_bytes() == b"career-plugin-v1"
    assert layout.cfg.read_bytes() == b"plugin load MyCareerTraining\n"
    assert (layout.journal / "active.json").is_file()
    assert not (layout.root / "plugins" / "MyCareerTraining.dll.previous").exists()
    assert not (layout.root / "cfg" / "plugins.cfg.mct-backup").exists()

    assert session(layout).finish()["status"] == "restored"
    assert not layout.dll.exists()
    assert not layout.cfg.exists()
    assert not (layout.journal / "active.json").exists()


def test_preexisting_files_restore_exact_bytes_including_line_endings(layout):
    original_cfg = b"plugin load alpha\r\nplugin load beta"
    original_dll = b"community-build-\x00\xff"
    layout.cfg.write_bytes(original_cfg)
    layout.dll.write_bytes(original_dll)
    legacy_backup = layout.root / "cfg" / "plugins.cfg.mct-backup"
    legacy_backup.write_bytes(b"do-not-use-this-legacy-backup")

    report = session(layout).begin(layout.source)

    assert report["config"] == "appended"
    assert report["dll"] == "replaced"
    assert layout.cfg.read_bytes() == original_cfg + b"\nplugin load MyCareerTraining\n"
    assert layout.dll.read_bytes() == layout.source.read_bytes()
    assert legacy_backup.read_bytes() == b"do-not-use-this-legacy-backup"

    crashed = session(layout)
    assert crashed.recover()["status"] == "restored"
    assert layout.cfg.read_bytes() == original_cfg
    assert layout.dll.read_bytes() == original_dll
    assert legacy_backup.read_bytes() == b"do-not-use-this-legacy-backup"
    assert not (layout.journal / "active.json").exists()


def test_empty_existing_config_is_restored_rather_than_deleted(layout):
    layout.cfg.write_bytes(b"")

    session(layout).begin(layout.source)
    session(layout).finish()

    assert layout.cfg.read_bytes() == b""
    assert not layout.dll.exists()


def test_restore_removes_autoload_first_and_defers_if_another_game_starts(layout, monkeypatch):
    original = b"plugin load alpha\n"
    layout.cfg.write_bytes(original)
    alive = [False]
    current = PluginSession(layout.data, root=layout.root, game_running=lambda: alive[0])
    current.begin(layout.source)
    restored = []
    real_restore = current._restore_resource

    def restore(root, record):
        restored.append(record["kind"])
        real_restore(root, record)
        if record["kind"] == "config":
            alive[0] = True

    monkeypatch.setattr(current, "_restore_resource", restore)
    assert current.finish()["status"] == "deferred"
    assert restored == ["config"]
    assert layout.cfg.read_bytes() == original
    assert layout.dll.read_bytes() == layout.source.read_bytes()
    receipt = json.loads((layout.journal / "active.json").read_text())
    assert [item["kind"] for item in receipt["resources"]] == ["dll"]
    alive[0] = False
    assert current.recover()["status"] == "restored"
    assert not layout.dll.exists()
    assert layout.cfg.read_bytes() == original


def test_crash_receipt_is_recovered_before_a_new_session_can_treat_it_as_legacy(layout):
    original = b"plugin load alpha\n"
    layout.cfg.write_bytes(original)
    layout.dll.write_bytes(b"old-dll")
    session(layout).begin(layout.source)
    assert b"plugin load MyCareerTraining" in layout.cfg.read_bytes()

    restarted = session(layout)
    restarted.begin(layout.source)
    restarted.finish()

    assert layout.cfg.read_bytes() == original
    assert layout.dll.read_bytes() == b"old-dll"


def test_legacy_autoload_line_is_not_removed_without_ownership(layout):
    original = b"plugin load mycareertraining\nplugin load alpha\n"
    layout.cfg.write_bytes(original)
    layout.dll.write_bytes(b"someone-elses-dll")

    report = session(layout).begin(layout.source)

    assert report["config"] == "preexisting"
    assert report["remediation"]
    assert "did not remove" in report["remediation"][0]
    assert layout.cfg.read_bytes() == original
    session(layout).finish()
    assert layout.cfg.read_bytes() == original
    assert layout.dll.read_bytes() == b"someone-elses-dll"


def test_commented_or_compound_lines_do_not_count_as_an_owned_autoload(layout):
    commented = b"// plugin load MyCareerTraining\nplugin load alpha\n"
    layout.cfg.write_bytes(commented)
    session(layout).begin(layout.source)
    session(layout).finish()
    assert layout.cfg.read_bytes() == commented

    compound = b"plugin load alpha; plugin load MyCareerTraining\n"
    layout.cfg.write_bytes(compound)
    report = session(layout).begin(layout.source)
    assert report["config"] == "preexisting"
    session(layout).finish()
    assert layout.cfg.read_bytes() == compound


def test_subsequent_config_edits_survive_and_a_different_dll_is_not_overwritten(layout):
    original = b"plugin load alpha\n"
    layout.cfg.write_bytes(original)
    session(layout).begin(layout.source)
    layout.cfg.write_bytes(layout.cfg.read_bytes() + b"plugin load added-later\n")
    session(layout).finish()
    assert layout.cfg.read_bytes() == original + b"plugin load added-later\n"

    layout.dll.write_bytes(b"old-dll")
    session(layout).begin(layout.source)
    layout.dll.write_bytes(b"newer-community-build")
    with pytest.raises(PluginSessionError, match="left that file in place"):
        session(layout).finish()
    assert layout.dll.read_bytes() == b"newer-community-build"
    assert (layout.journal / "MyCareerTraining.dll.prior").read_bytes() == b"old-dll"
    with pytest.raises(PluginSessionError, match="left that file in place"):
        session(layout).begin(layout.source)
    assert layout.dll.read_bytes() == b"newer-community-build"


def test_deleted_owned_file_is_not_recreated_over_the_deletion(layout):
    layout.dll.write_bytes(b"old-dll")
    layout.cfg.write_bytes(b"plugin load alpha\n")
    session(layout).begin(layout.source)
    layout.dll.unlink()
    with pytest.raises(PluginSessionError, match="did not recreate"):
        session(layout).finish()
    assert not layout.dll.exists()
    assert (layout.journal / "active.json").is_file()
    assert (layout.journal / "MyCareerTraining.dll.prior").read_bytes() == b"old-dll"


def test_unreadable_config_refuses_setup_without_touching_plugin_files(layout):
    original = b"plugin load alpha\xff\n"
    layout.cfg.write_bytes(original)
    with pytest.raises(PluginSessionError, match="not UTF-8"):
        session(layout).begin(layout.source)
    assert layout.cfg.read_bytes() == original
    assert not layout.dll.exists()
    assert not (layout.journal / "active.json").exists()


def test_user_edit_to_the_autoload_line_is_not_deleted(layout):
    session(layout).begin(layout.source)
    edited = b"plugin load MyCareerTraining // keep my choice\n"
    layout.cfg.write_bytes(edited)
    with pytest.raises(PluginSessionError, match="does not own"):
        session(layout).finish()
    assert layout.cfg.read_bytes() == edited
    assert (layout.journal / "active.json").is_file()


def _symlink_or_skip(link, target):
    try:
        link.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows denied symlink creation because this account lacks the required privilege")
        raise


def test_symlinked_plugin_config_is_refused(layout, tmp_path):
    outside = tmp_path / "outside.cfg"
    outside.write_bytes(b"plugin load alpha\n")
    _symlink_or_skip(layout.cfg, outside)
    with pytest.raises(PluginSessionError, match="link"):
        session(layout).begin(layout.source)
    assert outside.read_bytes() == b"plugin load alpha\n"
    assert not (layout.journal / "active.json").exists()


def test_outside_receipt_paths_are_refused(layout, tmp_path):
    outside = tmp_path / "outside.cfg"
    outside.write_bytes(b"plugin load alpha\n")
    layout.cfg.write_bytes(b"plugin load alpha\n")
    receipt = {
        "schema": 1,
        "bakkes_root": str(layout.root.resolve()),
        "resources": [{
            "kind": "dll",
            "path": str(outside),
            "existed": True,
            "prior_sha256": "a" * 64,
            "session_sha256": "b" * 64,
            "backup": "MyCareerTraining.dll.prior",
        }],
        "remediation": [],
        "created_dirs": [],
    }
    layout.journal.mkdir(parents=True)
    (layout.journal / "active.json").write_text(json.dumps(receipt))
    with pytest.raises(PluginSessionError, match="outside"):
        session(layout).recover()
    assert outside.read_bytes() == b"plugin load alpha\n"


def test_concurrent_game_refuses_setup_and_defers_an_outstanding_receipt(layout):
    with pytest.raises(PluginSessionError, match="Close the existing Rocket League"):
        session(layout, running=True).begin(layout.source)
    assert not layout.dll.exists()
    assert not layout.cfg.exists()

    quiet = session(layout, running=False)
    quiet.begin(layout.source)
    staged_cfg = layout.cfg.read_bytes()
    staged_dll = layout.dll.read_bytes()
    with pytest.raises(PluginSessionError, match="will not start another session"):
        session(layout, running=True).recover()
    with pytest.raises(PluginSessionError, match="will not start another session"):
        session(layout, running=True).begin(layout.source)
    assert session(layout, running=True).finish()["status"] == "deferred"
    assert layout.cfg.read_bytes() == staged_cfg
    assert layout.dll.read_bytes() == staged_dll
    assert (layout.journal / "active.json").is_file()

    assert session(layout, running=False).recover()["status"] == "restored"
    assert not layout.dll.exists()
    assert not layout.cfg.exists()


def test_pending_native_helper_blocks_setup_and_defers_recovery(layout, monkeypatch):
    pending = [True]
    monkeypatch.setattr("my_career_training.platforms.native_launcher_pending", lambda: pending[0])
    current = session(layout, running=False)
    with pytest.raises(PluginSessionError, match="offline menu helper"):
        current.begin(layout.source)
    assert not layout.cfg.exists() and not layout.dll.exists()
    pending[0] = False
    current.begin(layout.source)
    before = (layout.cfg.read_bytes(), layout.dll.read_bytes())
    pending[0] = True
    with pytest.raises(PluginSessionError, match="will not start another session"):
        current.recover()
    assert current.finish()["status"] == "deferred"
    assert (layout.cfg.read_bytes(), layout.dll.read_bytes()) == before
    pending[0] = False
    assert current.finish()["status"] == "restored"


def test_corrupt_receipt_blocks_a_new_session_without_writing_bakkes_files(layout):
    layout.dll.write_bytes(b"keep-me")
    layout.journal.mkdir(parents=True)
    (layout.journal / "active.json").write_text("{")
    with pytest.raises(PluginSessionError, match="unreadable"):
        session(layout).begin(layout.source)
    assert layout.dll.read_bytes() == b"keep-me"
    assert (layout.journal / "active.json").read_text() == "{"


@pytest.mark.parametrize("failed_step", ["_write_receipt", "_replace_if_unchanged"])
def test_setup_failure_preserves_absent_config_directory(layout, monkeypatch, failed_step):
    (layout.root / "cfg").rmdir()
    current = session(layout)
    def fail(*_args, **_kwargs):
        raise OSError("test disk failure")
    monkeypatch.setattr(current, failed_step, fail)
    with pytest.raises(PluginSessionError, match="disk failure"):
        current.begin(layout.source)
    assert not (layout.root / "cfg").exists()
    assert not layout.dll.exists()
    assert not (layout.journal / "active.json").exists()
