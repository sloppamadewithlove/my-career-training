"""Private cache for packages listed by the official BakkesPlugins service.

This module looks up metadata and stores the original ZIP. It does not extract,
load, install, or autoload a plugin, and it does not write BakkesMod or game files.
``site_verified`` is the site's review flag, not a cryptographic signature and not
an artifact attestation.

Provenance, read 2026-10-24 (artifact body not downloaded):

- Metadata ``GET https://bakkesplugins.com/api/v1/plugins/get/short?pluginids=223``
  returned ``success``, ``response.plugins["223"]`` with ``version`` 21,
  ``download_url``, and ``verified`` true. The plugin id is the object key.
  That payload has no title.
- Plugin page ``https://bakkesplugins.com/plugin/223`` names the plugin
  "Workshop Map Loader & Downloader" by Vync_. The HTML title and og:title also
  prepended "[New Update!] ". The page version label was 1.16.1. Description:
  "A plugin to load & download Workshop Maps For Epic Games".
- The metadata download URL was
  ``https://cdn.bakkesplugins.com/uploads/cad81d4f4ba54a77a76b6fec36385b20-WorkshopMapLoader_v1.16.1.zip``.
  A HEAD response reported ``content-type: application/zip`` and
  ``content-length: 870288``.
- Official client (not copied; it disables TLS peer verification):
  ``https://github.com/bakkesmodorg/PluginManager/blob/master/PluginManager/PluginManager.cpp``
- Review policy, which is a site review rather than a signature:
  ``https://bakkesplugins.com/wiki/bakkesmod-sdk/useful-info/submitting-to-bakkesplugins``
- Public browse page, not used as a catalog API:
  ``https://bakkesplugins.com/plugins?sortBy=release``

Allowed hosts are only those two observed HTTPS hosts: ``bakkesplugins.com`` for
the ID-based metadata URL and ``cdn.bakkesplugins.com`` for ``/uploads/<file>.zip``.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import re
import ssl
import stat
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
import zlib
from pathlib import Path
from typing import Callable


class CommunityPluginError(RuntimeError):
    """A community plugin could not be listed, downloaded, or read from cache."""


class DownloadCancelled(CommunityPluginError):
    """The caller cancelled the download before a cache entry was published."""


_ACTIVATION_REASON = (
    "Community plugins stay in this private cache. "
    "My Career Training does not install, load, or autoload them."
)
_SITE_VERIFIED_MEANING = (
    "The BakkesPlugins verified flag is a site review state, not a cryptographic "
    "signature, and it does not attest the downloaded bytes."
)
_METADATA_HOST = "bakkesplugins.com"
_DOWNLOAD_HOSTS = frozenset({"cdn.bakkesplugins.com"})
_USER_AGENT = "MyCareerTraining/0.3"
_METADATA_ACCEPT = "application/json"
_ARCHIVE_ACCEPT = "application/zip"
_MAX_METADATA_BYTES = 64 * 1024
_MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
_MAX_EXPANDED_BYTES = 32 * 1024 * 1024
_MAX_ENTRY_BYTES = 16 * 1024 * 1024
_MAX_ENTRIES = 64
_MAX_RATIO = 50
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_REDIRECTS = 3
_METADATA_TIMEOUT = 20
_ARCHIVE_TIMEOUT = 60
_CHUNK = 64 * 1024
_SHA = re.compile(r"^[a-f0-9]{64}$")
_ZIP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,180}\.zip")
_SAFE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._+- ")
_DEVICES = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_RECEIPT_KEYS = frozenset({
    "id", "title", "creator", "version", "download_url", "remote_filename",
    "artifact_sha256", "archive", "package", "site_verified", "site_verified_meaning",
    "details_url", "status", "can_activate", "activation_reason",
})
_PACKAGE_KEYS = frozenset({
    "entry_count", "file_count", "directory_count", "uncompressed_bytes",
    "compressed_bytes", "entries",
})

# Snapshots from the 2026-10-24 read. Live version and verified come from lookup.
_CURATED = {
    "223": {
        "id": "223",
        "title": "Workshop Map Loader & Downloader",
        "creator": "Vync_",
        "description": "A plugin to load & download Workshop Maps For Epic Games",
        "page_version": "1.16.1",
        "details_url": "https://bakkesplugins.com/plugin/223",
        "metadata_url": "https://bakkesplugins.com/api/v1/plugins/get/short?pluginids=223",
        "source_url": "https://bakkesplugins.com/plugin/223",
        "source_checked": "2026-10-24",
        "observed_api_version": 21,
        "observed_site_verified": True,
        "status": "not_enabled",
        "can_activate": False,
        "activation_reason": _ACTIVATION_REASON,
        "compatibility": "Unreviewed. Private cache only; this app does not load the plugin.",
        "capabilities": [],
    },
}


def curated_catalog() -> list[dict]:
    """Return listing snapshots; inclusion does not attest package compatibility."""
    return [json.loads(json.dumps(entry, allow_nan=False)) for entry in _CURATED.values()]


def lookup_plugin(plugin_id, *, opener: Callable[..., object] | None = None) -> dict:
    """Fetch official metadata for one canonical numeric plugin id."""
    identity = _coerce_id(plugin_id)
    payload = _request(
        _opener(opener),
        _metadata_url(identity),
        accept=_METADATA_ACCEPT,
        validate=lambda url: _validate_metadata_url(url, identity),
        limit=_MAX_METADATA_BYTES,
        cancelled=None,
        progress=None,
        timeout=_METADATA_TIMEOUT,
        media_type="application/json",
    )
    item = _parse_metadata(identity, payload)
    return _listed(identity, item["version"], item["download_url"], item["verified"])


def download_plugin(
    record,
    directory: Path,
    *,
    opener: Callable[..., object] | None = None,
    cancelled: Callable[[], bool] | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> dict:
    """Download one metadata-backed archive into ``directory`` and return its receipt.

    The archive bytes are stored as-is. The ZIP is inspected and is not extracted.
    """
    if not isinstance(record, dict):
        raise CommunityPluginError("Plugin record is not valid.")
    if cancelled is not None and not callable(cancelled):
        raise CommunityPluginError("Plugin download is not valid.")
    if progress is not None and not callable(progress):
        raise CommunityPluginError("Plugin download is not valid.")
    _check_cancelled(cancelled)
    identity = _coerce_id(record.get("id"))
    if record.get("can_activate") not in (False, None):
        raise CommunityPluginError("Community plugins cannot be activated.")
    client = _opener(opener)
    live = lookup_plugin(identity, opener=client)
    if record.get("version") != live["version"] or record.get("download_url") != live["download_url"]:
        raise CommunityPluginError("Plugin record does not match the official metadata.")
    _check_cancelled(cancelled)
    archive = _request(
        client,
        live["download_url"],
        accept=_ARCHIVE_ACCEPT,
        validate=_validate_download_url,
        limit=_MAX_ARCHIVE_BYTES,
        cancelled=cancelled,
        progress=progress,
        timeout=_ARCHIVE_TIMEOUT,
        media_type="application/zip",
    )
    _check_cancelled(cancelled)
    package = _inspect_zip(archive)
    _check_cancelled(cancelled)
    digest = hashlib.sha256(archive).hexdigest()
    receipt = {
        **live,
        "artifact_sha256": digest,
        "archive": f"objects/{digest}/archive.zip",
        "package": package,
        "status": "downloaded_not_enabled",
        "can_activate": False,
        "activation_reason": _ACTIVATION_REASON,
    }
    _check_cancelled(cancelled)
    return _publish(_cache_root(directory), archive, receipt, cancelled=cancelled)


def cached_plugins(directory: Path) -> list[dict]:
    """Return receipts whose stored bytes still match the receipt hash.

    Symlinks are not followed. Incomplete, tampered, and non-receipt files are omitted.
    """
    root = _cache_root(directory, create=False)
    if root is None:
        return []
    objects = root / "objects"
    if objects.is_symlink() or _is_junction(objects):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    if not objects.exists():
        return []
    if not _real_dir(objects):
        raise CommunityPluginError("Cache directory is not a real directory.")
    try:
        children = list(objects.iterdir())
    except OSError:
        raise CommunityPluginError("Cache directory is not available.") from None
    found = []
    for child in children:
        if child.is_symlink() or _is_junction(child) or not _SHA.fullmatch(child.name):
            continue
        if not _real_dir(child):
            continue
        loaded = _load_cached(root, child.name)
        if loaded is not None:
            found.append(loaded)
    found.sort(key=lambda item: (item["id"], item["version"], item["artifact_sha256"]))
    return found


def _listed(identity: str, version: int, download_url: str, verified: bool) -> dict:
    catalog = _listing_identity(identity)
    return {
        "id": identity,
        "title": catalog["title"],
        "creator": catalog["creator"],
        "version": version,
        "download_url": download_url,
        "remote_filename": download_url.rsplit("/", 1)[-1],
        "site_verified": verified,
        "site_verified_meaning": _SITE_VERIFIED_MEANING,
        "details_url": catalog["details_url"],
        "status": "listed_not_enabled",
        "can_activate": False,
        "activation_reason": _ACTIVATION_REASON,
    }


def _coerce_id(value) -> str:
    if type(value) is int and 1 <= value <= 9_999_999_999:
        text = str(value)
    elif type(value) is str and re.fullmatch(r"[1-9][0-9]{0,9}", value):
        text = value
    else:
        raise CommunityPluginError("Enter the numeric ID from a BakkesPlugins page.")
    return text


def _metadata_url(identity: str) -> str:
    return f"https://bakkesplugins.com/api/v1/plugins/get/short?pluginids={identity}"


def _listing_identity(identity: str) -> dict:
    # The short API returns no name or creator. Do not invent these from a URL.
    return _CURATED.get(identity, {
        "title": f"Community plugin {identity}",
        "creator": "See creator page",
        "details_url": f"https://bakkesplugins.com/plugin/{identity}",
    })


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise DownloadCancelled("Plugin download cancelled.")


def _pairs(message: str):
    def hook(pairs):
        obj = {}
        for key, value in pairs:
            if type(key) is not str or key in obj:
                raise CommunityPluginError(message)
            obj[key] = value
        return obj
    return hook


def _parse_metadata(identity: str, payload: bytes) -> dict:
    if len(payload) > _MAX_METADATA_BYTES:
        raise CommunityPluginError("Plugin metadata was too large.")
    try:
        text = payload.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_pairs("Plugin metadata was not valid."))
    except CommunityPluginError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise CommunityPluginError("Plugin metadata was not valid.") from None
    if type(parsed) is not dict or parsed.get("success") is not True:
        raise CommunityPluginError("Plugin metadata was not valid.")
    response = parsed.get("response")
    plugins = response.get("plugins") if type(response) is dict else None
    if type(plugins) is not dict or list(plugins) != [identity]:
        raise CommunityPluginError("Plugin metadata was not valid.")
    item = plugins[identity]
    if type(item) is not dict:
        raise CommunityPluginError("Plugin metadata was not valid.")
    version = item.get("version")
    download_url = item.get("download_url")
    verified = item.get("verified")
    if type(version) is not int or isinstance(version, bool) or not 0 <= version <= 1_000_000:
        raise CommunityPluginError("Plugin metadata was not valid.")
    if type(download_url) is not str or type(verified) is not bool:
        raise CommunityPluginError("Plugin metadata was not valid.")
    _validate_download_url(download_url)
    return {"version": version, "download_url": download_url, "verified": verified}


def _validate_metadata_url(url: str, identity: str) -> None:
    if url != _metadata_url(identity):
        raise CommunityPluginError("Plugin metadata URL is not allowed.")


def _validate_download_url(url: str) -> None:
    if type(url) is not str or not 12 <= len(url) <= 400:
        raise CommunityPluginError("Plugin download URL is not allowed.")
    if any(ord(char) < 33 or ord(char) > 126 or char in "@\\%#" for char in url):
        raise CommunityPluginError("Plugin download URL is not allowed.")
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    if (parts.scheme != "https" or host is None or parts.username or parts.password
            or parts.query or parts.fragment or host.casefold() not in _DOWNLOAD_HOSTS
            or parts.netloc.casefold() != host.casefold()):
        raise CommunityPluginError("Plugin download URL is not allowed.")
    pieces = parts.path.split("/")
    if (len(pieces) != 3 or pieces[0] != "" or pieces[1] != "uploads"
            or _ZIP_NAME.fullmatch(pieces[2]) is None or ".." in pieces[2]):
        raise CommunityPluginError("Plugin download URL is not allowed.")


def _opener(opener: Callable[..., object] | None) -> Callable[..., object]:
    if opener is None:
        return _default_open
    if not callable(opener):
        raise CommunityPluginError("Plugin download is not valid.")
    return opener


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise CommunityPluginError("TLS certificate verification is required.")
    return context


class _ConnResponse:
    def __init__(self, upstream, connection, url: str):
        self.status = upstream.status
        self.headers = upstream.headers
        self._upstream = upstream
        self._connection = connection
        self._url = url

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._upstream.read(size)

    def close(self) -> None:
        try:
            self._upstream.close()
        finally:
            self._connection.close()


def _default_open(request, timeout: float = _METADATA_TIMEOUT):
    """One HTTPS GET. Redirects are not followed here; the caller checks each hop."""
    parts = urllib.parse.urlsplit(getattr(request, "full_url", ""))
    host_allowed = parts.hostname == _METADATA_HOST or parts.hostname in _DOWNLOAD_HOSTS
    if parts.scheme != "https" or not host_allowed:
        raise CommunityPluginError("Plugin URL is not allowed.")
    context = _tls_context()
    connection = http.client.HTTPSConnection(parts.hostname, timeout=timeout, context=context)
    target = parts.path or "/"
    if parts.query:
        target = f"{target}?{parts.query}"
    headers = {name: value for name, value in request.header_items()}
    try:
        connection.request("GET", target, headers=headers)
        upstream = connection.getresponse()
    except Exception:
        connection.close()
        raise
    return _ConnResponse(upstream, connection, request.full_url)


def _request(
    opener: Callable[..., object],
    url: str,
    *,
    accept: str,
    validate: Callable[[str], None],
    limit: int,
    cancelled: Callable[[], bool] | None,
    progress: Callable[[int, int | None], None] | None,
    timeout: float,
    media_type: str,
) -> bytes:
    deadline = time.monotonic() + timeout
    current = url
    for _hop in range(_MAX_REDIRECTS + 1):
        _check_cancelled(cancelled)
        validate(current)
        response = _open_once(opener, current, accept, timeout)
        try:
            status = getattr(response, "status", None)
            if status in _REDIRECTS:
                current = _redirect_target(current, response)
                continue
            if status != 200:
                raise CommunityPluginError("Plugin server returned an error.")
            _require_media_type(response, media_type)
            return _read_body(response, limit, cancelled, progress, deadline)
        finally:
            closer = getattr(response, "close", None)
            if callable(closer):
                closer()
    raise CommunityPluginError("Plugin server redirected too many times.")


def _open_once(opener, url: str, accept: str, timeout: float):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": accept},
        method="GET",
    )
    try:
        return opener(request, timeout=timeout)
    except CommunityPluginError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError, http.client.HTTPException):
        raise CommunityPluginError("Could not reach the plugin service.") from None


def _redirect_target(current: str, response) -> str:
    location = _header(response, "Location")
    if location is None or not location or location != location.strip():
        raise CommunityPluginError("Plugin server returned an invalid redirect.")
    if any(ord(char) < 33 or ord(char) == 127 or char in "\\" for char in location):
        raise CommunityPluginError("Plugin server returned an invalid redirect.")
    return urllib.parse.urljoin(current, location)


def _header(response, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        raise CommunityPluginError("Plugin server returned an unexpected response.")
    value = getter(name)
    if value is None:
        return None
    if type(value) is not str or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise CommunityPluginError("Plugin server returned an unexpected response.")
    return value


def _require_media_type(response, expected: str) -> None:
    raw = _header(response, "Content-Type")
    if raw is None or "," in raw:
        raise CommunityPluginError("Plugin server returned an unexpected response.")
    if raw.split(";", 1)[0].strip().casefold() != expected:
        raise CommunityPluginError("Plugin server returned an unexpected response.")


def _content_length(response, limit: int) -> int | None:
    raw = _header(response, "Content-Length")
    if raw is None:
        return None
    if not raw.isdigit():
        raise CommunityPluginError("Plugin download is too large.")
    size = int(raw)
    if size > limit:
        raise CommunityPluginError("Plugin download is too large.")
    return size


def _read_body(response, limit: int, cancelled, progress, deadline: float) -> bytes:
    declared = _content_length(response, limit)
    chunks: list[bytes] = []
    count = 0
    while True:
        _check_cancelled(cancelled)
        if time.monotonic() >= deadline:
            raise CommunityPluginError("Plugin download timed out.")
        try:
            chunk = response.read(min(_CHUNK, limit - count + 1))
        except OSError:
            raise CommunityPluginError("Plugin download was interrupted.") from None
        if not isinstance(chunk, (bytes, bytearray)) or not chunk:
            break
        count += len(chunk)
        if count > limit:
            raise CommunityPluginError("Plugin download is too large.")
        chunks.append(bytes(chunk))
        if progress is not None:
            progress(count, declared)
    if declared is not None and count != declared:
        raise CommunityPluginError("Plugin download was truncated.")
    return b"".join(chunks)


def _inspect_zip(data: bytes) -> dict:
    """Bound and CRC-check member bytes in memory; never extract or execute."""
    if len(data) < 22 or data[:2] != b"PK":
        raise CommunityPluginError("Plugin archive is not a valid zip file.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            infos = bundle.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        raise CommunityPluginError("Plugin archive is not a valid zip file.") from None
    if not infos or len(infos) > _MAX_ENTRIES:
        raise CommunityPluginError(
            "Plugin archive has no files." if not infos else "Plugin archive has too many entries."
        )
    seen: dict[str, str] = {}
    entries = []
    files = directories = uncompressed = compressed = 0
    for info in infos:
        _reject_entry_mode(info)
        _sizes_agree(data, info)
        name, is_dir = _entry_name(info.filename)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if (kind == stat.S_IFDIR and not is_dir) or (kind == stat.S_IFREG and is_dir):
            raise CommunityPluginError("Plugin archive contains an unsafe path.")
        key = name.casefold()
        if key in seen:
            raise CommunityPluginError("Plugin archive contains colliding names.")
        seen[key] = name
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise CommunityPluginError("Plugin archive is not a valid zip file.")
        if info.file_size < 0 or info.compress_size < 0:
            raise CommunityPluginError("Plugin archive is not a valid zip file.")
        if is_dir:
            if info.file_size != 0 or info.compress_size > 64:
                raise CommunityPluginError("Plugin archive is not a valid zip file.")
            directories += 1
        else:
            if info.compress_size == 0 and info.file_size > 0:
                raise CommunityPluginError("Plugin archive is too compressed to inspect safely.")
            if info.compress_size and info.file_size > info.compress_size * _MAX_RATIO:
                raise CommunityPluginError("Plugin archive is too compressed to inspect safely.")
            if info.file_size > _MAX_ENTRY_BYTES or uncompressed + info.file_size > _MAX_EXPANDED_BYTES:
                raise CommunityPluginError("Plugin archive expands too far.")
            if compressed + info.compress_size > _MAX_ARCHIVE_BYTES:
                raise CommunityPluginError("Plugin archive is too large.")
            files += 1
            uncompressed += info.file_size
            compressed += info.compress_size
        entries.append({"name": name, "bytes": info.file_size, "directory": is_dir})
    if files < 1:
        raise CommunityPluginError("Plugin archive has no files.")
    # Header checks alone accept corrupt payloads. Stream through the bounded
    # members so ZipFile validates local names, overlapping entries and CRCs.
    # No member data is written to disk, interpreted, or retained.
    try:
        total_read = 0
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            for info in infos:
                entry_read = 0
                with bundle.open(info) as member:
                    while chunk := member.read(_CHUNK):
                        entry_read += len(chunk)
                        total_read += len(chunk)
                        if entry_read > _MAX_ENTRY_BYTES or total_read > _MAX_EXPANDED_BYTES:
                            raise CommunityPluginError("Plugin archive expands too far.")
                if entry_read != info.file_size:
                    raise CommunityPluginError("Plugin archive is truncated.")
    except CommunityPluginError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, zlib.error, RuntimeError, NotImplementedError):
        raise CommunityPluginError("Plugin archive failed its integrity check.") from None
    return {
        "entry_count": len(entries),
        "file_count": files,
        "directory_count": directories,
        "uncompressed_bytes": uncompressed,
        "compressed_bytes": compressed,
        "entries": entries,
    }


def _reject_entry_mode(info: zipfile.ZipInfo) -> None:
    if info.flag_bits & 0x1:
        raise CommunityPluginError("Plugin archive contains an encrypted entry.")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode) or _windows_reparse(info):
        raise CommunityPluginError("Plugin archive contains a link.")
    kind = stat.S_IFMT(mode)
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise CommunityPluginError("Plugin archive contains an unsafe path.")


def _windows_reparse(info: zipfile.ZipInfo) -> bool:
    return info.create_system in (0, 10) and bool(info.external_attr & 0x400)


def _sizes_agree(data: bytes, info: zipfile.ZipInfo) -> None:
    offset = info.header_offset
    if offset < 0 or offset + 30 > len(data):
        raise CommunityPluginError("Plugin archive is not a valid zip file.")
    header = data[offset:offset + 30]
    if header[:4] != b"PK\x03\x04":
        raise CommunityPluginError("Plugin archive is not a valid zip file.")
    flags, method = int.from_bytes(header[6:8], "little"), int.from_bytes(header[8:10], "little")
    if flags & 0x1:
        raise CommunityPluginError("Plugin archive contains an encrypted entry.")
    if method not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise CommunityPluginError("Plugin archive is not a valid zip file.")
    if flags & 0x8:
        return
    compressed = int.from_bytes(header[18:22], "little")
    uncompressed = int.from_bytes(header[22:26], "little")
    if compressed != info.compress_size or uncompressed != info.file_size:
        raise CommunityPluginError("Plugin archive is not a valid zip file.")


def _entry_name(name: str) -> tuple[str, bool]:
    if type(name) is not str or not name or len(name) > 240:
        raise CommunityPluginError("Plugin archive contains an unsafe path.")
    if any(ord(char) < 32 or ord(char) == 127 or char in '\\:<>"|?*' for char in name):
        raise CommunityPluginError("Plugin archive contains an unsafe path.")
    directory = name.endswith("/")
    trimmed = name[:-1] if directory else name
    if not trimmed or trimmed.endswith("/"):
        raise CommunityPluginError("Plugin archive contains an unsafe path.")
    parts = trimmed.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise CommunityPluginError("Plugin archive contains an unsafe path.")
    for part in parts:
        if part != part.strip() or part.endswith(".") or part.startswith(".") or len(part) > 128:
            raise CommunityPluginError("Plugin archive contains an unsafe path.")
        if any(char not in _SAFE_CHARS for char in part):
            raise CommunityPluginError("Plugin archive contains an unsafe path.")
        if part.split(".", 1)[0].casefold() in _DEVICES:
            raise CommunityPluginError("Plugin archive contains an unsafe path.")
    return "/".join(parts), directory


def _chain(path: Path) -> list[Path]:
    chain = []
    current = path
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    chain.reverse()
    return chain


def _real_dir(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.stat(follow_symlinks=False).st_mode)
    except OSError:
        return False


def _is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        raise CommunityPluginError("Cache directory is not available.") from None


def _reject_links(path: Path) -> None:
    for candidate in _chain(path):
        if candidate.is_symlink() or _is_junction(candidate):
            raise CommunityPluginError("Cache directory cannot follow a link.")


def _cache_root(directory: Path, create: bool = True) -> Path | None:
    if not isinstance(directory, (str, Path)):
        raise CommunityPluginError("Choose a private cache directory.")
    root = Path(directory)
    if not root.is_absolute():
        raise CommunityPluginError("Choose a private cache directory.")
    _reject_links(root)
    if root.is_symlink() or _is_junction(root):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    if root.exists():
        if not _real_dir(root):
            raise CommunityPluginError("Cache directory is not a real directory.")
        return root
    if not create:
        return None
    parent = root.parent
    _reject_links(parent)
    if parent.is_symlink() or not _real_dir(parent):
        raise CommunityPluginError("Cache directory is not available.")
    try:
        os.mkdir(root, 0o700)
    except OSError:
        raise CommunityPluginError("Could not store the plugin archive.") from None
    if root.is_symlink() or not _real_dir(root):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    return root


def _mkdir_real(path: Path) -> Path:
    if path.is_symlink() or _is_junction(path):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        if path.is_symlink() or _is_junction(path) or not _real_dir(path):
            raise CommunityPluginError("Cache directory cannot follow a link.") from None
    except OSError:
        raise CommunityPluginError("Could not store the plugin archive.") from None
    if path.is_symlink() or not _real_dir(path):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    return path


def _atomic_write(folder: Path, name: str, data: bytes) -> None:
    if not _SHA.fullmatch(folder.name) and not folder.name.startswith(".staging-"):
        raise CommunityPluginError("Plugin cache path is not valid.")
    if name not in {"archive.zip", "receipt.json"}:
        raise CommunityPluginError("Plugin cache path is not valid.")
    temporary = None
    try:
        descriptor, raw = tempfile.mkstemp(prefix=".mct-", dir=folder)
        temporary = Path(raw)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, folder / name)
        temporary = None
        if sys.platform != "win32":
            directory_fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError:
        raise CommunityPluginError("Could not store the plugin archive.") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _read_nofollow(path: Path, limit: int) -> bytes:
    if path.is_symlink() or _is_junction(path):
        raise CommunityPluginError("Cached plugin is not a regular file.")
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags | nofollow)
    except OSError:
        raise CommunityPluginError("Cached plugin could not be read.") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise CommunityPluginError("Cached plugin is not a regular file.")
        chunks = []
        remaining = info.st_size
        while remaining:
            blob = os.read(descriptor, min(_CHUNK, remaining))
            if not blob:
                raise CommunityPluginError("Cached plugin could not be read.")
            chunks.append(blob)
            remaining -= len(blob)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or _is_junction(path):
        try:
            path.unlink()
        except OSError:
            pass
        return
    if not path.exists() or not _real_dir(path):
        return
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        if _real_dir(child) and not child.is_symlink() and not _is_junction(child):
            _remove_tree(child)
        else:
            try:
                child.unlink()
            except OSError:
                pass
    try:
        path.rmdir()
    except OSError:
        pass


def _publish(root: Path, archive: bytes, receipt: dict, *, cancelled=None) -> dict:
    _check_cancelled(cancelled)
    digest = receipt["artifact_sha256"]
    if not _SHA.fullmatch(digest):
        raise CommunityPluginError("Plugin archive identity check failed.")
    objects = root / "objects"
    if not objects.exists():
        _mkdir_real(objects)
    elif objects.is_symlink() or _is_junction(objects) or not _real_dir(objects):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    try:
        leftovers = [child for child in objects.iterdir() if child.name.startswith(".staging-")]
    except OSError:
        raise CommunityPluginError("Could not store the plugin archive.") from None
    for leftover in leftovers:
        _remove_tree(leftover)
    staging = objects / f".staging-{digest}"
    final = objects / digest
    if staging.exists() or staging.is_symlink():
        _remove_tree(staging)
    if final.is_symlink() or _is_junction(final):
        raise CommunityPluginError("Cache directory cannot follow a link.")
    _mkdir_real(staging)
    try:
        _atomic_write(staging, "archive.zip", archive)
        encoded = json.dumps(receipt, ensure_ascii=True, allow_nan=False, indent=2).encode("ascii")
        if len(encoded) > _MAX_RECEIPT_BYTES:
            raise CommunityPluginError("Plugin receipt is too large.")
        _atomic_write(staging, "receipt.json", encoded)
        if _load_folder(staging, digest) is None:
            raise CommunityPluginError("Plugin archive identity check failed.")
        # Last cancellable point: after this point, report a committed receipt
        # even if Cancel races with the rename. The bridge preserves that result.
        _check_cancelled(cancelled)
        if not final.exists():
            os.rename(staging, final)
        elif _real_dir(final):
            os.replace(staging / "archive.zip", final / "archive.zip")
            os.replace(staging / "receipt.json", final / "receipt.json")
            _remove_tree(staging)
        else:
            raise CommunityPluginError("Cache directory cannot follow a link.")
    except CommunityPluginError:
        _remove_tree(staging)
        raise
    except OSError:
        _remove_tree(staging)
        raise CommunityPluginError("Could not store the plugin archive.") from None
    loaded = _load_cached(root, digest)
    if loaded is None:
        _remove_tree(final)
        raise CommunityPluginError("Plugin archive identity check failed.")
    return loaded


def _load_cached(root: Path, digest: str) -> dict | None:
    if not _SHA.fullmatch(digest):
        return None
    return _load_folder(root / "objects" / digest, digest)


def _load_folder(folder: Path, digest: str) -> dict | None:
    if folder.is_symlink() or _is_junction(folder) or not _real_dir(folder):
        return None
    archive_path = folder / "archive.zip"
    receipt_path = folder / "receipt.json"
    try:
        if archive_path.is_symlink() or receipt_path.is_symlink():
            return None
        blob = _read_nofollow(archive_path, _MAX_ARCHIVE_BYTES)
        raw = _read_nofollow(receipt_path, _MAX_RECEIPT_BYTES)
        receipt = _receipt_from_bytes(raw, digest, blob)
    except (CommunityPluginError, OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None
    return receipt


def _receipt_from_bytes(raw: bytes, digest: str, blob: bytes) -> dict:
    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs("Plugin receipt is damaged."))
    if type(parsed) is not dict or set(parsed) != _RECEIPT_KEYS:
        raise CommunityPluginError("Plugin receipt is damaged.")
    if type(parsed["id"]) is not str or type(parsed["download_url"]) is not str:
        raise CommunityPluginError("Plugin receipt is damaged.")
    catalog = _listing_identity(_coerce_id(parsed["id"]))
    package = parsed["package"]
    expected_archive = f"objects/{digest}/archive.zip"
    if (parsed["title"] != catalog["title"] or parsed["creator"] != catalog["creator"]
            or parsed["details_url"] != catalog["details_url"]
            or type(parsed["version"]) is not int or not 0 <= parsed["version"] <= 1_000_000
            or parsed["artifact_sha256"] != digest or hashlib.sha256(blob).hexdigest() != digest
            or parsed["archive"] != expected_archive or parsed["remote_filename"] != parsed["download_url"].rsplit("/", 1)[-1]
            or type(parsed["site_verified"]) is not bool or parsed["site_verified_meaning"] != _SITE_VERIFIED_MEANING
            or parsed["status"] != "downloaded_not_enabled" or parsed["can_activate"] is not False
            or parsed["activation_reason"] != _ACTIVATION_REASON):
        raise CommunityPluginError("Plugin receipt is damaged.")
    _validate_download_url(parsed["download_url"])
    if type(package) is not dict or set(package) != _PACKAGE_KEYS or package != _inspect_zip(blob):
        raise CommunityPluginError("Plugin receipt is damaged.")
    return parsed
