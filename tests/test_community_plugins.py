import hashlib
import io
import json
import ssl
import stat
import zipfile
from pathlib import Path

import pytest

from my_career_training import community_plugins as plugins
from my_career_training.community_plugins import (
    CommunityPluginError, DownloadCancelled, cached_plugins, curated_catalog,
    download_plugin, lookup_plugin,
)


METADATA = "https://bakkesplugins.com/api/v1/plugins/get/short?pluginids=223"
METADATA_BASE = "https://bakkesplugins.com/api/v1/plugins/get/short?pluginids="
DOWNLOAD = (
    "https://cdn.bakkesplugins.com/uploads/"
    "cad81d4f4ba54a77a76b6fec36385b20-WorkshopMapLoader_v1.16.1.zip"
)
OFFICIAL = {
    "success": True,
    "response": {
        "plugins": {
            "223": {
                "version": 21,
                "download_url": DOWNLOAD,
                "verified": True,
            },
        },
    },
}


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self._body = body
        self._offset = 0
        self.reads = 0

    def read(self, size=-1):
        self.reads += 1
        if size is None or size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self):
        return None


def metadata_body(payload=None):
    return json.dumps(OFFICIAL if payload is None else payload).encode()


def metadata_body_for(plugin_id):
    item = OFFICIAL["response"]["plugins"]["223"]
    return json.dumps({
        "success": True,
        "response": {"plugins": {plugin_id: item}},
    }).encode()


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, payload in files:
            bundle.writestr(name, payload)
    return buffer.getvalue()


def valid_archive():
    return zip_bytes([
        ("plugins/", b""),
        ("plugins/WorkshopMapLoader.dll", b"MZ-fixture-plugin"),
        ("plugin.json", b'{"name":"WorkshopMapLoader"}'),
    ])


def response(status, body, content_type, extra=None):
    headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
    if extra:
        headers.update(extra)
    return Response(status, headers, body)


def service(archive=None, metadata=None, routes=None):
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        if routes is not None:
            return routes(request, seen)
        if request.full_url == METADATA:
            return response(200, metadata if metadata is not None else metadata_body(),
                            "application/json; charset=utf-8")
        if request.full_url == DOWNLOAD:
            body = valid_archive() if archive is None else archive
            return response(200, body, "application/zip")
        raise AssertionError(request.full_url)

    return opener, seen


def patch_central_uncompressed(data, size):
    patched = bytearray(data)
    index = patched.rfind(b"PK\x01\x02")
    patched[index + 24:index + 28] = size.to_bytes(4, "little")
    return bytes(patched)


def patch_local_uncompressed(data, size):
    patched = bytearray(data)
    index = patched.find(b"PK\x03\x04")
    patched[index + 22:index + 26] = size.to_bytes(4, "little")
    return bytes(patched)


def mark_encrypted(data):
    patched = bytearray(data)
    local = patched.find(b"PK\x03\x04")
    patched[local + 6:local + 8] = (int.from_bytes(patched[local + 6:local + 8], "little") | 1).to_bytes(2, "little")
    central = patched.find(b"PK\x01\x02")
    patched[central + 8:central + 10] = (
        int.from_bytes(patched[central + 8:central + 10], "little") | 1
    ).to_bytes(2, "little")
    return bytes(patched)


def corrupt_first_crc(data):
    patched = bytearray(data)
    local = patched.find(b"PK\x03\x04")
    central = patched.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    wrong_crc = (int.from_bytes(patched[central + 16:central + 20], "little") ^ 1).to_bytes(4, "little")
    patched[local + 14:local + 18] = wrong_crc
    patched[central + 16:central + 20] = wrong_crc
    return bytes(patched)


def special_zip(name, payload, mutate):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as bundle:
        info = zipfile.ZipInfo(name)
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        mutate(info)
        bundle.writestr(info, payload)
    return buffer.getvalue()


def assert_no_personal_path(exc, tmp_path):
    text = str(exc)
    assert str(tmp_path) not in text
    assert str(Path.home()) not in text
    assert "evil.example" not in text


def test_catalog_is_only_the_checked_plugin():
    catalog = curated_catalog()
    assert [item["id"] for item in catalog] == ["223"]
    entry = catalog[0]
    assert entry["title"] == "Workshop Map Loader & Downloader"
    assert entry["creator"] == "Vync_"
    assert entry["page_version"] == "1.16.1"
    assert entry["details_url"] == "https://bakkesplugins.com/plugin/223"
    assert entry["metadata_url"] == METADATA
    assert entry["observed_api_version"] == 21
    assert entry["observed_site_verified"] is True
    assert entry["can_activate"] is False
    assert entry["capabilities"] == []
    assert "signature" not in entry["activation_reason"].lower()
    entry["title"] = "changed"
    entry["capabilities"].append("load")
    assert curated_catalog()[0]["title"] == "Workshop Map Loader & Downloader"
    assert curated_catalog()[0]["capabilities"] == []


def test_lookup_reads_official_metadata_shape():
    opener, seen = service()
    record = lookup_plugin("223", opener=opener)
    assert seen == [METADATA]
    assert record["id"] == "223"
    assert record["title"] == "Workshop Map Loader & Downloader"
    assert record["version"] == 21
    assert record["download_url"] == DOWNLOAD
    assert record["site_verified"] is True
    assert "not a cryptographic signature" in record["site_verified_meaning"]
    assert "signature" not in record
    assert record["details_url"] == "https://bakkesplugins.com/plugin/223"
    assert record["status"] == "listed_not_enabled"
    assert record["can_activate"] is False
    assert lookup_plugin(223, opener=opener)["version"] == 21


@pytest.mark.parametrize("plugin_id", [
    "0", "0223", "223 ", "", 0, True, None, "223\n1", "１２３", "١٢٣",
    "10000000000", -1,
])
def test_noncanonical_plugin_id_does_not_use_the_network(plugin_id):
    def opener(request, timeout=None):
        raise AssertionError(request.full_url)

    with pytest.raises(CommunityPluginError) as caught:
        lookup_plugin(plugin_id, opener=opener)
    assert "plugin" in str(caught.value).lower()


def test_non_curated_positive_plugin_id_can_be_looked_up_and_cached(tmp_path):
    plugin_id = "9876543210"
    expected_metadata = METADATA_BASE + plugin_id
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        if request.full_url == expected_metadata:
            return response(200, metadata_body_for(plugin_id), "application/json")
        if request.full_url == DOWNLOAD:
            return response(200, valid_archive(), "application/zip")
        raise AssertionError(request.full_url)

    listed = lookup_plugin(plugin_id, opener=opener)
    assert listed["id"] == plugin_id
    assert listed["title"] == f"Community plugin {plugin_id}"
    assert listed["creator"] == "See creator page"
    receipt = download_plugin(listed, tmp_path / "cache", opener=opener)
    assert receipt["id"] == plugin_id
    assert receipt["title"] == f"Community plugin {plugin_id}"
    assert receipt["creator"] == "See creator page"
    assert cached_plugins(tmp_path / "cache") == [receipt]
    assert seen.count(expected_metadata) == 2
    assert seen.count(DOWNLOAD) == 1


def test_metadata_rejects_plugin_object_key_mismatch():
    requested_id = "9876543210"
    wrong_key = metadata_body()
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return response(200, wrong_key, "application/json")

    with pytest.raises(CommunityPluginError):
        lookup_plugin(requested_id, opener=opener)
    assert seen == [METADATA_BASE + requested_id]


@pytest.mark.parametrize("payload", [
    b"not-json",
    b"[]",
    b'{"success": false}',
    b'{"success": true}',
    b'{"success": true, "response": {"plugins": {}}}',
    b'{"success": true, "response": {"plugins": {"1": {"version": 1, "download_url": "%s", "verified": true}}}}' % DOWNLOAD.encode(),
    b'{"success": true, "success": true}',
    json.dumps({"success": True, "response": {"plugins": {"223": {
        "version": "21", "download_url": DOWNLOAD, "verified": True,
    }}}}).encode(),
    json.dumps({"success": True, "response": {"plugins": {"223": {
        "version": 21, "download_url": DOWNLOAD, "verified": "true",
    }}}}).encode(),
    json.dumps({"success": True, "response": {"plugins": {"223": {
        "version": True, "download_url": DOWNLOAD, "verified": True,
    }}}}).encode(),
    json.dumps({"success": True, "response": {"plugins": {
        "223": {"version": 21, "download_url": DOWNLOAD, "verified": True},
        "224": {"version": 1, "download_url": DOWNLOAD, "verified": True},
    }}}).encode(),
])
def test_malformed_metadata_is_rejected(payload, tmp_path):
    def opener(request, timeout=None):
        assert request.full_url == METADATA
        return response(200, payload, "application/json")

    with pytest.raises(CommunityPluginError) as caught:
        lookup_plugin("223", opener=opener)
    assert_no_personal_path(caught.value, tmp_path)


@pytest.mark.parametrize("download_url", [
    "http://cdn.bakkesplugins.com/uploads/plugin.zip",
    "https://user:pass@cdn.bakkesplugins.com/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com:8443/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com:443/uploads/plugin.zip",
    "https://evil.example/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com.evil.example/uploads/plugin.zip",
    "https://bakkesplugins.com/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com/other/plugin.zip",
    "https://cdn.bakkesplugins.com/uploads/../plugin.zip",
    "https://cdn.bakkesplugins.com/uploads/plugin.zip?token=secret",
    "file:///tmp/plugin.zip",
    "https://cdn.bakkesplugins.com/uploads/plugin.zip#frag",
    DOWNLOAD + " ",
])
def test_hostile_download_url_is_rejected_before_fetch(download_url, tmp_path):
    payload = json.dumps({"success": True, "response": {"plugins": {"223": {
        "version": 21, "download_url": download_url, "verified": True,
    }}}}).encode()
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return response(200, payload, "application/json")

    with pytest.raises(CommunityPluginError) as caught:
        lookup_plugin("223", opener=opener)
    assert seen == [METADATA]
    assert_no_personal_path(caught.value, tmp_path)


@pytest.mark.parametrize("location", [
    "https://evil.example/uploads/plugin.zip",
    "http://cdn.bakkesplugins.com/uploads/plugin.zip",
    "https://user:pass@cdn.bakkesplugins.com/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com:443/uploads/plugin.zip",
    "https://cdn.bakkesplugins.com/uploads/plugin.zip?x=1",
    "file:///etc/passwd",
    "//evil.example/uploads/plugin.zip",
    "https://bakkesplugins.com/api/v1/plugins/get/short?pluginids=223&next=1",
])
def test_each_redirect_is_checked_before_the_next_fetch(location):
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return Response(302, {"Location": location, "Content-Type": "text/plain"}, b"")

    with pytest.raises(CommunityPluginError):
        lookup_plugin("223", opener=opener)
    assert seen == [METADATA]


def test_metadata_redirect_to_the_cdn_is_not_fetched():
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return Response(302, {"Location": DOWNLOAD, "Content-Type": "text/html"}, b"")

    with pytest.raises(CommunityPluginError):
        lookup_plugin("223", opener=opener)
    assert seen == [METADATA]


def test_allowed_download_redirect_is_followed_only_after_validation(tmp_path):
    second = "https://cdn.bakkesplugins.com/uploads/WorkshopMapLoader.zip"
    seen = []

    def routes(request, urls):
        if request.full_url == METADATA:
            return response(200, metadata_body(), "application/json")
        if request.full_url == DOWNLOAD:
            return Response(302, {"Location": second}, b"")
        if request.full_url == second:
            body = valid_archive()
            return response(200, body, "application/zip")
        raise AssertionError(request.full_url)

    opener, seen = service(routes=routes)
    record = lookup_plugin("223", opener=opener)
    receipt = download_plugin(record, tmp_path / "cache", opener=opener, progress=lambda done, total: None)
    assert DOWNLOAD in seen and second in seen
    assert "evil.example" not in seen
    assert receipt["status"] == "downloaded_not_enabled"
    assert receipt["can_activate"] is False


def test_oversized_metadata_is_not_read_when_length_is_declared():
    def opener(request, timeout=None):
        body = Response(200, {
            "Content-Type": "application/json",
            "Content-Length": str(plugins._MAX_METADATA_BYTES + 1),
        }, b"{}")
        body.read = lambda size=-1: (_ for _ in ()).throw(AssertionError("read"))
        return body

    with pytest.raises(CommunityPluginError, match="too large"):
        lookup_plugin("223", opener=opener)


def test_html_and_truncated_metadata_are_rejected():
    def html(request, timeout=None):
        return response(200, b"<html></html>", "text/html")

    with pytest.raises(CommunityPluginError):
        lookup_plugin("223", opener=html)

    def truncated(request, timeout=None):
        return Response(200, {"Content-Type": "application/json", "Content-Length": "40"}, b"{")

    with pytest.raises(CommunityPluginError, match="truncated"):
        lookup_plugin("223", opener=truncated)


@pytest.mark.parametrize("archive", [
    zip_bytes([("../outside.dll", b"MZ")]),
    zip_bytes([("/tmp/outside.dll", b"MZ")]),
    zip_bytes([(r"plugins\..\outside.dll", b"MZ")]),
    zip_bytes([(r"\\server\share\outside.dll", b"MZ")]),
    zip_bytes([("C:/Windows/outside.dll", b"MZ")]),
    zip_bytes([("plugins/foo.dll:Zone.Identifier", b"MZ")]),
    zip_bytes([("plugins/CON.dll", b"MZ")]),
    zip_bytes([("plugins/nul.txt", b"MZ")]),
    zip_bytes([("COM1", b"MZ")]),
    zip_bytes([("plugins/foo.dll", b"MZ"), ("plugins/Foo.DLL", b"MZ")]),
    zip_bytes([("plugins/../outside.dll", b"MZ")]),
    special_zip("plugins/link", b"../outside.dll", lambda info: setattr(
        info, "external_attr", (stat.S_IFLNK | 0o777) << 16)),
    special_zip("plugins/reparse.dll", b"MZ", lambda info: (
        setattr(info, "create_system", 0), setattr(info, "external_attr", 0x400))),
], ids=[
    "parent-traversal", "absolute", "backslash", "unc", "drive", "ads",
    "device-con", "device-nul", "device-com1", "case-alias", "nested-traversal",
    "symlink", "reparse",
])
def test_hostile_archive_paths_and_links_are_not_cached(archive, tmp_path):
    opener, _seen = service(archive=archive)
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(CommunityPluginError) as caught:
        download_plugin(record, cache, opener=opener)
    assert list(cache.iterdir()) == []
    assert cached_plugins(cache) == []
    assert_no_personal_path(caught.value, tmp_path)


def test_encrypted_entry_is_rejected(tmp_path):
    archive = mark_encrypted(zip_bytes([("plugins/WorkshopMapLoader.dll", b"MZ-secret")]))
    opener, _seen = service(archive=archive)
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(CommunityPluginError, match="encrypted"):
        download_plugin(record, cache, opener=opener)
    assert cached_plugins(cache) == []


def test_compression_bomb_and_expansion_cap_are_rejected(tmp_path):
    bomb = zip_bytes([("plugins/bomb.dll", b"\0" * (256 * 1024))])
    stored = io.BytesIO()
    with zipfile.ZipFile(stored, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr("plugins/Big.dll", b"A" * (400 * 1024))
    expanded = patch_local_uncompressed(patch_central_uncompressed(stored.getvalue(), 20_000_000), 20_000_000)
    mismatch = patch_central_uncompressed(stored.getvalue(), 20_000_000)
    crowded = zip_bytes([(f"plugins/part{index}.dll", b"MZ") for index in range(plugins._MAX_ENTRIES + 1)])
    cache = tmp_path / "cache"
    cache.mkdir()
    expectations = {
        id(bomb): "too compressed",
        id(expanded): "expands too far",
        id(mismatch): "not a valid zip",
        id(crowded): "too many entries",
    }
    for archive, message in (
        (bomb, expectations[id(bomb)]),
        (expanded, expectations[id(expanded)]),
        (mismatch, expectations[id(mismatch)]),
        (crowded, expectations[id(crowded)]),
    ):
        opener, _seen = service(archive=archive)
        record = lookup_plugin("223", opener=opener)
        with pytest.raises(CommunityPluginError, match=message):
            download_plugin(record, cache, opener=opener)
        assert list(cache.iterdir()) == []


def test_zip_with_bad_member_crc_is_rejected_before_cache_publish(tmp_path):
    archive = corrupt_first_crc(valid_archive())
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert bundle.testzip() is not None

    opener, _seen = service(archive=archive)
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(CommunityPluginError):
        download_plugin(record, cache, opener=opener)
    assert list(cache.iterdir()) == []
    assert cached_plugins(cache) == []


def test_cancel_and_truncation_do_not_publish(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()

    def immediate(request, timeout=None):
        raise AssertionError("network used after cancel")

    record = {"id": "223", "version": 21, "download_url": DOWNLOAD, "can_activate": False}
    with pytest.raises(DownloadCancelled):
        download_plugin(record, cache, opener=immediate, cancelled=lambda: True)
    assert list(cache.iterdir()) == []

    reads = {"count": 0}

    def routes(request, urls):
        if request.full_url == METADATA:
            return response(200, metadata_body(), "application/json")
        body = valid_archive()
        upstream = response(200, body, "application/zip")

        def read(size=-1):
            reads["count"] += 1
            if reads["count"] > 1:
                return b""
            return body[:32]
        upstream.read = read
        return upstream

    opener, seen = service(routes=routes)
    listed = lookup_plugin("223", opener=opener)
    with pytest.raises(DownloadCancelled) as caught:
        download_plugin(listed, cache, opener=opener, cancelled=lambda: reads["count"] > 0)
    assert_no_personal_path(caught.value, tmp_path)
    assert DOWNLOAD not in seen or seen.count(DOWNLOAD) == 1
    assert list(cache.iterdir()) == []

    def truncated(request, timeout=None):
        if request.full_url == METADATA:
            return response(200, metadata_body(), "application/json")
        return Response(200, {"Content-Type": "application/zip", "Content-Length": "5000"}, b"PK\x03\x04short")

    with pytest.raises(CommunityPluginError, match="truncated") as caught:
        download_plugin(listed, cache, opener=truncated)
    assert_no_personal_path(caught.value, tmp_path)
    assert cached_plugins(cache) == []

    def reset(request, timeout=None):
        if request.full_url == METADATA:
            return response(200, metadata_body(), "application/json")
        upstream = response(200, b"PK", "application/zip")

        def read(size=-1):
            raise ConnectionResetError("reset")
        upstream.read = read
        return upstream

    with pytest.raises(CommunityPluginError, match="interrupted") as caught:
        download_plugin(listed, cache, opener=reset)
    assert caught.value.__cause__ is None
    assert_no_personal_path(caught.value, tmp_path)
    assert list(cache.rglob(".mct-*")) == []


def test_cancel_during_archive_inspection_does_not_publish(tmp_path, monkeypatch):
    opener, _seen = service()
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    cache.mkdir()
    cancelled = {"value": False}
    inspect = plugins._inspect_zip

    def inspect_then_cancel(archive):
        package = inspect(archive)
        cancelled["value"] = True
        return package

    monkeypatch.setattr(plugins, "_inspect_zip", inspect_then_cancel)
    with pytest.raises(DownloadCancelled):
        download_plugin(record, cache, opener=opener,
                        cancelled=lambda: cancelled["value"])
    assert list(cache.iterdir()) == []
    assert cached_plugins(cache) == []


def test_cancel_during_staging_removes_unpublished_files(tmp_path, monkeypatch):
    opener, _seen = service()
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    cache.mkdir()
    cancelled = {"value": False}
    write = plugins._atomic_write

    def write_then_cancel(folder, name, data):
        write(folder, name, data)
        if name == "archive.zip" and folder.name.startswith(".staging-"):
            cancelled["value"] = True

    monkeypatch.setattr(plugins, "_atomic_write", write_then_cancel)
    with pytest.raises(DownloadCancelled):
        download_plugin(record, cache, opener=opener,
                        cancelled=lambda: cancelled["value"])
    objects = cache / "objects"
    assert not objects.exists() or list(objects.iterdir()) == []
    assert cached_plugins(cache) == []


def test_record_identity_must_match_metadata(tmp_path):
    opener, seen = service()
    record = lookup_plugin("223", opener=opener)
    tampered = dict(record)
    tampered["download_url"] = "https://cdn.bakkesplugins.com/uploads/other-plugin.zip"
    seen.clear()
    cache = tmp_path / "cache"
    with pytest.raises(CommunityPluginError, match="does not match"):
        download_plugin(tampered, cache, opener=opener)
    assert seen == [METADATA]
    assert not cache.exists()

    activated = dict(record)
    activated["can_activate"] = True
    with pytest.raises(CommunityPluginError, match="cannot be activated"):
        download_plugin(activated, cache, opener=opener)
    assert record["can_activate"] is False


def test_valid_archive_is_cached_privately_and_not_enabled(tmp_path):
    archive = valid_archive()
    progress_calls = []
    opener, _seen = service(archive=archive)
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    receipt = download_plugin(
        record, cache, opener=opener,
        progress=lambda done, total: progress_calls.append((done, total)),
    )
    encoded = json.dumps(receipt, allow_nan=False)
    assert json.loads(encoded)["can_activate"] is False
    assert receipt["status"] == "downloaded_not_enabled"
    assert receipt["version"] == 21
    assert receipt["id"] == "223"
    assert receipt["artifact_sha256"] == hashlib.sha256(archive).hexdigest()
    assert receipt["archive"] == f"objects/{receipt['artifact_sha256']}/archive.zip"
    assert receipt["package"]["file_count"] == 2
    assert receipt["package"]["directory_count"] == 1
    assert {item["name"] for item in receipt["package"]["entries"]} == {
        "plugins", "plugins/WorkshopMapLoader.dll", "plugin.json",
    }
    assert "not a cryptographic signature" in receipt["site_verified_meaning"]
    stored = cache / receipt["archive"]
    assert stored.read_bytes() == archive
    assert not stored.is_symlink()
    assert cached_plugins(cache) == [receipt]
    assert progress_calls[-1] == (len(archive), len(archive))
    assert list(cache.rglob("*.dll")) == []
    assert not (cache / "plugins.cfg").exists()
    names = sorted(path.name for path in cache.rglob("*") if path.is_file())
    assert names == ["archive.zip", "receipt.json"]

    again = download_plugin(record, cache, opener=opener)
    assert again == receipt
    assert cached_plugins(cache) == [receipt]


def test_cached_listing_rejects_identity_mismatch_and_links(tmp_path):
    opener, _seen = service()
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    receipt = download_plugin(record, cache, opener=opener)
    archive = cache / receipt["archive"]
    original = archive.read_bytes()
    archive.write_bytes(original + b"x")
    assert cached_plugins(cache) == []

    archive.write_bytes(original)
    receipt_path = archive.with_name("receipt.json")
    receipt_path.write_text(receipt_path.read_text().replace("false", "true", 1))
    assert cached_plugins(cache) == []

    receipt_path.write_text(json.dumps(receipt))
    outside = tmp_path / "outside.zip"
    outside.write_bytes(original)
    archive.unlink()
    archive.symlink_to(outside)
    assert cached_plugins(cache) == []
    assert outside.read_bytes() == original

    partial = cache / "objects" / ("ab" * 32)
    partial.mkdir()
    (partial / "archive.zip").write_bytes(original)
    assert all(item["artifact_sha256"] != partial.name for item in cached_plugins(cache))
    assert cached_plugins(cache) == []


@pytest.mark.parametrize(("field", "value"), [
    ("id", []),
    ("download_url", []),
    ("version", "21"),
    ("package", []),
])
def test_malformed_cached_receipt_types_are_skipped(tmp_path, field, value):
    opener, _seen = service()
    record = lookup_plugin("223", opener=opener)
    cache = tmp_path / "cache"
    receipt = download_plugin(record, cache, opener=opener)
    damaged = dict(receipt)
    damaged[field] = value
    receipt_path = cache / receipt["archive"]
    receipt_path.with_name("receipt.json").write_text(json.dumps(damaged), encoding="utf-8")
    assert cached_plugins(cache) == []


def test_linked_parents_and_relative_directories_are_not_written(tmp_path, monkeypatch):
    opener, _seen = service()
    record = lookup_plugin("223", opener=opener)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(outside, target_is_directory=True)
    cache = linked_parent / "cache"
    cache.mkdir()
    with pytest.raises(CommunityPluginError, match="link") as caught:
        download_plugin(record, cache, opener=opener)
    assert_no_personal_path(caught.value, tmp_path)
    assert list((outside / "cache").iterdir()) == []
    with pytest.raises(CommunityPluginError, match="link"):
        cached_plugins(cache)

    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(CommunityPluginError, match="link"):
        download_plugin(record, alias, opener=opener)
    assert list(real.iterdir()) == []

    holder = tmp_path / "holder"
    holder.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (holder / "objects").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(CommunityPluginError, match="link"):
        download_plugin(record, holder, opener=opener)
    assert list(elsewhere.iterdir()) == []
    assert list((outside / "cache").iterdir()) == []

    monkeypatch.chdir(tmp_path)
    with pytest.raises(CommunityPluginError):
        download_plugin(record, Path("relative-cache"), opener=opener)
    assert not (tmp_path / "relative-cache").exists()


def test_default_transport_verifies_tls_and_does_not_follow_redirects(monkeypatch):
    captured = {}

    class Connection:
        def __init__(self, host, timeout=None, context=None):
            captured["host"] = host
            captured["context"] = context
            raise OSError("stop before the network")

        def close(self):
            return None

    monkeypatch.setattr(plugins.http.client, "HTTPSConnection", Connection)
    with pytest.raises(CommunityPluginError, match="Could not reach"):
        lookup_plugin("223")
    assert captured["host"] == "bakkesplugins.com"
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True
    context = plugins._tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_module_does_not_stage_load_or_disable_tls():
    source = Path(plugins.__file__).read_text(encoding="utf-8").lower()
    for banned in ("urlopen", "cert_none", "extractall", "plugins.cfg", "subprocess",
                   "plugin load", "check_hostname=false", "writeplugins"):
        assert banned not in source
