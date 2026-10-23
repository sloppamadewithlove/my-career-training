from copy import deepcopy
import hashlib

import pytest

from my_career_training.content import (
    community_catalog, garage_catalog, import_map, validate_loadout,
)


def test_supported_styles_validate_without_mutating_and_reject_unknown_items():
    style = {"car_id": 23, "primary_color": 27, "secondary_color": 0}
    result = validate_loadout(style)
    assert result == style and result is not style
    assert {entry["car_id"] for entry in garage_catalog()} == {23, 403, 30, 22}
    assert all(entry["wheels_id"] == 376 for entry in garage_catalog())
    for change in ({"car_id": 999999}, {"primary_color": 70}, {"secondary_color": -1},
                   {"car_id": True}, {"secondary_color": "0"}, {"run_command": "bad"}):
        invalid = deepcopy(style)
        invalid.update(change)
        with pytest.raises(ValueError):
            validate_loadout(invalid)
    assert style == {"car_id": 23, "primary_color": 27, "secondary_color": 0}


def test_catalog_keeps_creator_permission_and_launcher_status_visible():
    entries = community_catalog()
    assert entries
    for entry in entries:
        assert entry["creator"] and entry["license"] and entry["loading_route"]
        assert entry["url"].startswith("https://")
        assert "unavailable" in entry["epic"].lower()
    entries[0]["title"] = "changed"
    assert community_catalog()[0]["title"] != "changed"


def test_import_identity_spaces_unicode_and_source_preservation(tmp_path):
    source = tmp_path / "Créateur map with spaces.UDK"
    payload = b"\xc1\x83\x2a\x9e" + b"local package fixture" * 50
    source.write_bytes(payload)
    user_data = tmp_path / "User Data 日本語"
    imported = import_map(source, user_data, "steam")
    from pathlib import Path
    saved = Path(imported["path"])
    assert saved.parent == user_data / "maps"
    assert saved.name == hashlib.sha256(payload).hexdigest() + ".udk"
    assert saved.read_bytes() == source.read_bytes() == payload
    assert imported["sha256"] == hashlib.sha256(payload).hexdigest()
    assert imported["size"] == len(payload)
    assert imported["game_tested"] is False
    assert import_map(source, user_data, "Steam")["path"] == str(saved)


def test_invalid_inputs_do_not_create_data_or_run_loaders(tmp_path):
    data = tmp_path / "data"
    source = tmp_path / "level.udk"
    source.write_bytes(b"\xc1\x83\x2a\x9e" + b"test")
    with pytest.raises(ValueError, match="Epic"):
        import_map(source, data, "epic")
    assert not data.exists()

    for filename, payload in [("loader.exe", b"MZtest"), ("archive.zip", b"PKtest"),
                              ("fake.udk", b"MZthis is not a map"), ("empty.upk", b"")]:
        invalid = tmp_path / filename
        invalid.write_bytes(payload)
        with pytest.raises(ValueError):
            import_map(invalid, data, "steam")
    with pytest.raises(ValueError):
        import_map("relative.udk", data, "steam")
    with pytest.raises(ValueError):
        import_map("//server/maps/level.udk", data, "steam")
    linked = tmp_path / "link.udk"
    try:
        linked.symlink_to(source)
    except OSError:
        pass  # Windows may not permit symlinks for an unprivileged CI user.
    else:
        with pytest.raises(ValueError):
            import_map(linked, data, "steam")
    assert not data.exists()


def test_import_size_limit_and_linked_destination_do_not_escape_user_data(tmp_path, monkeypatch):
    import my_career_training.content as content
    source = tmp_path / "valid.udk"
    source.write_bytes(b"\xc1\x83\x2a\x9e" + b"x" * 40)
    data = tmp_path / "data"
    monkeypatch.setattr(content, "MAX_MAP_BYTES", 8)
    with pytest.raises(ValueError, match="1 GiB"):
        import_map(source, data, "steam")
    assert not data.exists()
    monkeypatch.setattr(content, "MAX_MAP_BYTES", 1024)
    data.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        (data / "maps").symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        return  # Symlink creation may require extra permissions on Windows.
    with pytest.raises(ValueError, match="symbolic link"):
        import_map(source, data, "steam")
    assert not list(elsewhere.iterdir())
