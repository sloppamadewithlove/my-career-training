from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from my_career_training import bridge, community_discovery
from my_career_training.ingame import ALLOWED_ACTIONS


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(["community-discovery-tests"])


@pytest.fixture
def backend(tmp_path, monkeypatch, qt_app):
    game_running = {"value": False}
    monkeypatch.setattr(bridge, "native_launcher_pending", lambda: False)
    monkeypatch.setattr("my_career_training.platforms.native_launcher_pending", lambda: False)
    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    monkeypatch.setattr(
        bridge, "game_processes", lambda: ["mock-rocket-league"] if game_running["value"] else []
    )
    monkeypatch.setattr(bridge, "is_alive", lambda identity: identity is not None and game_running["value"])
    monkeypatch.setattr(bridge, "graceful_close", lambda _identity: None)
    monkeypatch.setattr(bridge, "launch_online", lambda _launcher: "online opened")
    instance = bridge.Backend(tmp_path)
    yield instance
    instance.timer.stop()
    instance.close()


def catalog_result(source: str, title: str, *, page: int = 1, query: str = "") -> dict:
    if source == "steam_maps":
        body = (
            '<a href="/sharedfiles/filedetails/?id=12345"><img alt="Map"></a>'
            f'<a href="/sharedfiles/filedetails/?id=12345">{title}</a>'
        )
    else:
        path = "plugin" if source == "bakkes_plugins" else "maps"
        body = f'<a href="/{path}/12345"><h2>{title}</h2></a>'
    result = community_discovery.parse_catalog(body, source, query=query, page=page)
    result["source_url"] = community_discovery.catalog_page_url(source, page)
    result["fetched"] = True
    return result


def wait_until(instance, predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        instance._poll_catalog()
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("Catalog worker did not reach the expected state")


def test_browse_runs_async_and_publishes_only_the_requested_page(backend, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def fetch(source, *, query, page, cancel):
        calls.append((source, query, page))
        entered.set()
        assert release.wait(2)
        return catalog_result(source, "Ice Rings", page=page, query=query)

    monkeypatch.setattr(community_discovery, "fetch_catalog", fetch)
    backend.dispatch("community_browse", {"source": "bakkes_maps", "page": 2, "query": "rings"})
    try:
        assert entered.wait(1)
        state = backend.state["community_catalog"]
        assert state["source"] == "bakkes_maps"
        assert state["page"] == 2
        assert state["query"] == "rings"
        assert state["busy"] is True
        assert state["loading"] is True
        assert state["items"] == []
        assert calls == [("bakkes_maps", "rings", 2)]
        assert backend.error == ""
    finally:
        release.set()

    wait_until(backend, lambda: not backend.catalog_state["busy"])
    state = backend.state["community_catalog"]
    assert [item["title"] for item in state["items"]] == ["Ice Rings"]
    assert state["source_url"] == "https://bakkesplugins.com/maps?page=2"
    assert state["fetched"] is True
    assert state["remote_query"] is False
    assert state["can_download"] is False
    assert state["can_activate"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "unknown", "page": 1},
        {"source": "steam_maps", "page": 0},
        {"source": "bakkes_maps", "page": 1, "query": "x" * 81},
        {"source": "bakkes_maps", "page": 1, "url": "https://evil.example/"},
        {"source": "bakkes_maps", "page": True},
    ],
)
def test_invalid_browse_payload_does_not_start_worker(backend, monkeypatch, payload):
    monkeypatch.setattr(
        community_discovery, "fetch_catalog", lambda *_args, **_kwargs: pytest.fail("invalid browse")
    )

    backend.dispatch("community_browse", payload)

    assert backend.error
    assert backend.catalog_state["busy"] is False
    assert backend.catalog_state["items"] == []


def test_cancel_invalidates_generation_allows_switch_and_discards_late_result(backend, monkeypatch):
    stale_entered, stale_release = threading.Event(), threading.Event()
    calls = []

    def fetch(source, *, query, page, cancel):
        calls.append((source, query, page))
        if query == "stale":
            stale_entered.set()
            assert stale_release.wait(2)
            # Simulate a read implementation that finishes despite cancellation.
            return catalog_result(source, "Stale result", page=page, query=query)
        return catalog_result(source, "Current result", page=page, query=query)

    monkeypatch.setattr(community_discovery, "fetch_catalog", fetch)
    backend.dispatch("community_browse", {"source": "bakkes_plugins", "query": "stale"})
    assert stale_entered.wait(1)
    old_generation = backend._catalog_generation

    backend.dispatch("community_browse_cancel", {})
    assert backend.error == ""
    assert backend.catalog_state["busy"] is False
    assert backend.catalog_state["status"] == "cancelled"
    assert backend._catalog_generation > old_generation

    backend.dispatch("community_browse", {"source": "bakkes_maps", "query": "current"})
    try:
        wait_until(backend, lambda: backend.catalog_state["status"] == "ok")
        assert [item["title"] for item in backend.catalog_state["items"]] == ["Current result"]
        assert backend.catalog_state["source"] == "bakkes_maps"
    finally:
        stale_release.set()

    wait_until(backend, lambda: backend._catalog_outstanding == 0)
    assert [item["title"] for item in backend.catalog_state["items"]] == ["Current result"]
    assert backend.catalog_state["source"] == "bakkes_maps"
    assert calls == [("bakkes_plugins", "stale", 1), ("bakkes_maps", "current", 1)]


def test_only_two_cancelled_catalog_workers_can_remain_outstanding(backend, monkeypatch):
    entered = [threading.Event(), threading.Event()]
    releases = [threading.Event(), threading.Event()]
    calls = []

    def fetch(source, *, query, page, cancel):
        slot = len(calls)
        calls.append((source, query, page))
        entered[slot].set()
        assert releases[slot].wait(2)
        return catalog_result(source, f"Late {slot}", page=page, query=query)

    monkeypatch.setattr(community_discovery, "fetch_catalog", fetch)
    try:
        backend.dispatch("community_browse", {"source": "steam_maps", "query": "one"})
        assert entered[0].wait(1)
        backend.dispatch("community_browse_cancel", {})
        backend.dispatch("community_browse", {"source": "bakkes_maps", "query": "two"})
        assert entered[1].wait(1)
        backend.dispatch("community_browse_cancel", {})
        assert backend._catalog_outstanding == 2

        backend.dispatch("community_browse", {"source": "bakkes_plugins", "query": "three"})
        assert "Two catalog reads" in backend.error
        assert calls == [("steam_maps", "one", 1), ("bakkes_maps", "two", 1)]
        assert backend._catalog_outstanding == 2
    finally:
        for release in releases:
            release.set()

    wait_until(backend, lambda: backend._catalog_outstanding == 0)
    assert backend.catalog_state["status"] == "cancelled"
    assert backend.catalog_state["items"] == []


def test_open_item_uses_only_id_and_source_from_current_page(backend, monkeypatch):
    opened = []
    monkeypatch.setattr(bridge.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    backend.catalog_state["items"] = catalog_result("bakkes_maps", "Ice Rings")["items"]

    backend.dispatch("community_open_item", {"source": "bakkes_maps", "id": 12345})

    assert opened == ["https://bakkesplugins.com/maps/12345"]
    assert backend.error == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "bakkes_maps", "id": 12345, "url": "https://evil.example/"},
        {"source": "bakkes_plugins", "id": 12345},
        {"source": "bakkes_maps", "id": "12345"},
        {"source": "bakkes_maps", "id": True},
        {"source": "bakkes_maps", "id": 9},
    ],
)
def test_open_item_rejects_unlisted_or_untrusted_payload(backend, monkeypatch, payload):
    opened = []
    monkeypatch.setattr(bridge.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    backend.catalog_state["items"] = catalog_result("bakkes_maps", "Ice Rings")["items"]

    backend.dispatch("community_open_item", payload)

    assert backend.error
    assert opened == []


def test_open_item_rechecks_displayed_details_url(backend, monkeypatch):
    opened = []
    monkeypatch.setattr(bridge.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    item = catalog_result("bakkes_maps", "Ice Rings")["items"][0]
    item["details_url"] = "https://evil.example/"
    backend.catalog_state["items"] = [item]

    backend.dispatch("community_open_item", {"source": "bakkes_maps", "id": 12345})

    assert "not allowed" in backend.error
    assert opened == []


def test_select_plugin_routes_only_current_plugin_id_to_existing_lookup(backend, monkeypatch):
    calls = []
    monkeypatch.setattr(backend, "_community_job", lambda *args: calls.append(args))
    backend.catalog_state["items"] = catalog_result("bakkes_plugins", "Map Loader")["items"]

    backend.dispatch("community_select_plugin", {"source": "bakkes_plugins", "id": 12345})

    assert calls == [("lookup", "12345")]
    assert backend.error == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "bakkes_maps", "id": 12345},
        {"source": "bakkes_plugins", "id": 9},
        {"source": "bakkes_plugins", "id": 12345, "url": "https://evil.example/"},
    ],
)
def test_select_plugin_rejects_non_plugin_or_unlisted_rows(backend, monkeypatch, payload):
    monkeypatch.setattr(backend, "_community_job", lambda *_args: pytest.fail("invalid selection"))
    backend.catalog_state["items"] = catalog_result("bakkes_plugins", "Map Loader")["items"]

    backend.dispatch("community_select_plugin", payload)

    assert backend.error


@pytest.mark.parametrize("source", community_discovery.SOURCES)
def test_open_source_uses_fixed_canonical_url_only(backend, monkeypatch, source):
    opened = []
    monkeypatch.setattr(bridge.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))

    backend.dispatch("community_open_source", {"source": source})

    assert opened == [community_discovery.catalog_page_url(source, 1)]
    assert backend.error == ""


def test_open_source_rejects_caller_supplied_urls(backend, monkeypatch):
    opened = []
    monkeypatch.setattr(bridge.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))

    backend.dispatch(
        "community_open_source", {"source": "bakkes_maps", "url": "https://evil.example/"}
    )

    assert backend.error
    assert opened == []


def test_ingame_allowlist_contains_catalog_actions_but_no_activation_action():
    assert {
        "community_browse",
        "community_browse_cancel",
        "community_open_item",
        "community_open_source",
        "community_select_plugin",
    } <= ALLOWED_ACTIONS
    assert "community_activate" not in ALLOWED_ACTIONS
