"""Real directory fixtures exercise offline library discovery and ID-only launches."""
import hashlib
from pathlib import Path

import pytest

from my_career_training.content import community_catalog, import_map
from my_career_training.workshop import (
    discover_steam_maps, library_state, prepare_launch, steam_library_roots, toggle_favorite,
)

MAGIC = b"\xc1\x83\x2a\x9e"


def package(root, workshop_id="1906378036", name="Aim training.udk", payload=MAGIC + b"map fixture"):
    path = root / "steamapps/workshop/content/252950" / workshop_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_discovery_follows_real_library_manifest_and_preserves_source(tmp_path):
    main, second = tmp_path / "Steam", tmp_path / "Second Library"
    (main / "steamapps").mkdir(parents=True)
    (main / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders" { "1" { "path" "' + str(second) + '" } }', encoding="utf-8")
    source = package(second)
    payload = source.read_bytes()
    roots = steam_library_roots(roots=[main])
    assert second in roots
    found = discover_steam_maps(steam_roots=[main])
    assert len(found) == 1
    assert found[0]["workshop_id"] == "1906378036"
    assert found[0]["path"] == str(source)
    assert found[0]["game_tested"] is False
    assert "subscription" not in found[0]["provenance"]
    prepared = prepare_launch("coco-aim", tmp_path / "data", steam_roots=[main])
    assert prepared["sha256"] == hashlib.sha256(payload).hexdigest()
    assert Path(prepared["path"]).read_bytes() == source.read_bytes() == payload
    assert prepared["requires_game_map_recovery"] is True
    assert prepared["route"] == "rlbot_steam_local_map"
    assert prepared["creator_url"].endswith("id=1906378036")


def test_bad_packages_other_apps_links_and_traversal_are_excluded(tmp_path):
    root = tmp_path / "Steam"
    valid = package(root)
    package(root, "999", "loader.exe", b"MZprogram")
    package(root, "999", "fake.udk", b"MZprogram")
    package(root, "999", "archive.zip", b"PKarchive")
    package(root, "not-a-workshop-id", "skip.udk")
    other_app = root / "steamapps/workshop/content/730/123/other.udk"
    other_app.parent.mkdir(parents=True)
    other_app.write_bytes(MAGIC)
    outside = tmp_path / "outside.udk"
    outside.write_bytes(MAGIC + b"external package")
    linked = valid.parent / "escape.udk"
    try:
        linked.symlink_to(outside)
    except OSError:
        pass
    else:
        assert linked.is_symlink()
    entries = discover_steam_maps(steam_roots=[root])
    assert len(entries) == 1 and entries[0]["path"] == str(valid)
    for identity in ("../outside.udk", str(outside), "steam:1906378036:../outside", "unknown"):
        with pytest.raises(ValueError):
            prepare_launch(identity, tmp_path / "data", steam_roots=[root])
    assert not (tmp_path / "data").exists()


def test_linked_workshop_directory_is_not_trusted(tmp_path):
    root, actual = tmp_path / "Steam", tmp_path / "actual"
    package(actual)
    base = root / "steamapps"
    base.mkdir(parents=True)
    try:
        (base / "workshop").symlink_to(actual / "steamapps/workshop", target_is_directory=True)
    except OSError:
        pytest.skip("Directory links unavailable to this user")
    assert discover_steam_maps(steam_roots=[root]) == []


def test_tabs_filters_favorites_and_created_local_maps(tmp_path):
    root, data = tmp_path / "Steam", tmp_path / "data"
    package(root)
    original = tmp_path / "My created course.udk"
    original.write_bytes(MAGIC + b"personal course")
    imported = import_map(original, data, "steam")
    state = library_state(data, steam_roots=[root], imported_maps=[imported])
    assert len(community_catalog()) == 11
    assert len(state["items"]) == 13
    favorites = toggle_favorite([], "coco-aim", state["items"])
    favorite_state = library_state(data, steam_roots=[root], favorites=favorites, tab="favorites")
    assert [row["id"] for row in favorite_state["items"]] == ["coco-aim"]
    assert toggle_favorite(favorites, "coco-aim", state["items"]) == []
    assert favorites == ["coco-aim"]
    filtered = library_state(data, steam_roots=[root], query="COCO", category="Shooting")
    assert len(filtered["items"]) == 2
    created = library_state(data, steam_roots=[], imported_maps=[imported], tab="created")
    assert len(created["items"]) == 1
    assert created["items"][0]["title"] == original.name
    assert created["items"][0]["origin"] == "local_import"
    assert prepare_launch(created["items"][0]["id"], data, imported_maps=[imported], steam_roots=[])["sha256"]
    with pytest.raises(ValueError):
        toggle_favorite([], "unknown", state["items"])
    with pytest.raises(ValueError):
        library_state(data, steam_roots=[], tab="fake")


def test_multi_package_item_requires_exact_selection(tmp_path):
    root = tmp_path / "Steam"
    package(root)
    package(root, name="texture dependency.upk")
    state = library_state(tmp_path / "data", steam_roots=[root])
    catalog = next(row for row in state["items"] if row["id"] == "coco-aim")
    assert catalog["installed"] and not catalog["can_launch"]
    assert catalog["availability"] == "Choose an installed package"
    with pytest.raises(ValueError):
        prepare_launch("coco-aim", tmp_path / "data", steam_roots=[root])
    selected = next(row for row in state["items"] if row.get("original_name") == "Aim training.udk")
    assert prepare_launch(selected["id"], tmp_path / "data", steam_roots=[root])["sha256"]


def test_imported_records_cannot_authorize_arbitrary_paths_or_changed_bytes(tmp_path):
    data = tmp_path / "data"
    source = tmp_path / "source.udk"
    source.write_bytes(MAGIC + b"original")
    record = import_map(source, data, "steam")
    escaped = {**record, "path": str(source)}
    assert not library_state(data, steam_roots=[], imported_maps=[escaped], tab="created")["items"]
    Path(record["path"]).write_bytes(MAGIC + b"modified")
    with pytest.raises(ValueError, match="changed"):
        prepare_launch("imported:" + record["sha256"], data, imported_maps=[record], steam_roots=[])


def test_epic_does_not_claim_steam_maps_or_a_working_loader(tmp_path):
    root = tmp_path / "Steam"
    package(root)
    data = tmp_path / "data"
    source = tmp_path / "permitted.udk"
    source.write_bytes(MAGIC + b"fixture")
    imported = import_map(source, data, "steam")
    state = library_state(data, launcher="epic", steam_roots=[root], imported_maps=[imported])
    assert not any(row["can_launch"] for row in state["items"])
    assert not any(row["origin"] == "steam_workshop" for row in state["items"])
    assert any(row["origin"] == "local_import" for row in state["items"])
    with pytest.raises(ValueError, match="Epic"):
        prepare_launch("coco-aim", data, launcher="epic", steam_roots=[root])
