from __future__ import annotations

import pytest

from my_career_training import community_discovery as discovery


def bakkes_card(source: str, item_id: int, title: str, *, image: str | None = None) -> str:
    path = "plugin" if source == "bakkes_plugins" else "maps"
    thumbnail = f'<img src="{image}">' if image else ""
    return (
        f'<a href="/{path}/{item_id}"><div>{thumbnail}'
        '<span title="5 out of 5">5.0</span><span>v1.16.1</span>'
        f'<h2>{title}</h2><span>Maker</span><p>Useful catalog description.</p>'
        '<span>View Details</span></div></a>'
    )


def steam_card(item_id: int, title: str) -> str:
    href = f"/sharedfiles/filedetails/?id={item_id}"
    return f'<a href="{href}"><img alt="Larger map"></a><a href="{href}">{title}</a>'


class Response:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        final_url: str | None = None,
    ):
        self.status = status
        self.headers = headers or {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body)),
        }
        self.body = body
        self.offset = 0
        self.final_url = final_url
        self.closed = False
        self.read_calls = 0

    def geturl(self):
        return self.final_url

    def read(self, size=-1):
        self.read_calls += 1
        if size is None or size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self):
        self.closed = True


def html_response(body: str, **kwargs) -> Response:
    return Response(body.encode("utf-8"), **kwargs)


@pytest.mark.parametrize(
    ("source", "item_id", "title"),
    [
        ("bakkes_maps", 138, "Ice Rings"),
        ("bakkes_plugins", 223, "[New Update!] Workshop Map Loader &amp; Downloader"),
    ],
)
def test_bakkes_h2_card_uses_title_heading_not_rating_version_or_cta(source, item_id, title):
    result = discovery.parse_catalog(
        '<input name="search">' + bakkes_card(source, item_id, title), source
    )

    assert len(result["items"]) == 1
    item = result["items"][0]
    expected_title = title.replace("&amp;", "&")
    assert item["title"] == expected_title
    assert "5.0" not in item["title"]
    assert "v1.16.1" not in item["title"]
    assert "View Details" not in item["title"]
    assert item["creator"] == "Maker"
    assert item["description"] == "Useful catalog description."


def test_steam_duplicate_anchors_merge_and_script_content_is_ignored():
    html = (
        '<script>"<a href="/sharedfiles/filedetails/?id=999">Fake Workshop Item</a>"</script>'
        '<input name="search">'
        + steam_card(1520915243, "Larger map")
        + '<a href="/profiles/123456789/myworkshopfiles/?appid=252950">By Salade</a>'
        + steam_card(246810, "Dribble Challenge")
    )

    result = discovery.parse_catalog(html, "steam_maps")

    assert [item["source_id"] for item in result["items"]] == [1520915243, 246810]
    assert [item["title"] for item in result["items"]] == ["Larger map", "Dribble Challenge"]
    assert result["items"][0]["creator"] == "Salade"
    assert all("Fake Workshop Item" not in item["title"] for item in result["items"])


def test_bakkes_creator_uses_full_title_attribute_instead_of_avatar_initial():
    html = (
        '<a href="/maps/138"><div><h2>Ice Rings</h2>'
        '<span class="avatar">L</span><span title="Lethamyr">Lethamyr</span>'
        '<p>Learn aerial control through rings.</p><span>View Details</span></div></a>'
    )

    result = discovery.parse_catalog(html, "bakkes_maps")
    item = result["items"][0]

    assert item["title"] == "Ice Rings"
    assert item["creator"] == "Lethamyr"
    assert item["description"] == "Learn aerial control through rings."


@pytest.mark.parametrize(
    ("source", "url", "body"),
    [
        (
            "steam_maps",
            "https://steamcommunity.com/workshop/browse/?appid=252950&browsesort=trend&section=readytouseitems",
            '<input name="search">' + steam_card(1520915243, "Larger map"),
        ),
        (
            "bakkes_maps",
            "https://bakkesplugins.com/maps",
            '<input name="search">' + bakkes_card("bakkes_maps", 138, "Ice Rings"),
        ),
        (
            "bakkes_plugins",
            "https://bakkesplugins.com/plugins",
            '<input name="search">' + bakkes_card("bakkes_plugins", 223, "Map Loader"),
        ),
    ],
)
def test_fetch_uses_only_approved_html_page_without_credentials_or_media_requests(source, url, body):
    seen = []

    def opener(request, timeout):
        seen.append(request)
        headers = {name.casefold(): value for name, value in request.header_items()}
        assert request.get_method() == "GET"
        assert timeout == discovery._TIMEOUT
        assert "cookie" not in headers
        assert "authorization" not in headers
        assert set(headers) == {"user-agent", "accept"}
        return html_response(body, final_url=request.full_url)

    result = discovery.fetch_catalog(source, opener=opener)

    assert [request.full_url for request in seen] == [url]
    assert result["fetched"] is True
    assert result["source_url"] == url
    assert result["items"]
    assert all(item["catalog_only"] for item in result["items"])
    assert not any("cdn." in request.full_url or ".dll" in request.full_url for request in seen)


def test_thumbnail_is_metadata_only_and_rows_do_not_claim_install_or_compatibility():
    image_url = "https://cdn.bakkesplugins.com/uploads/cover.jpg"
    requests = []

    def opener(request, timeout):
        requests.append(request.full_url)
        return html_response(
            '<input name="search">' + bakkes_card("bakkes_maps", 138, "Ice Rings", image=image_url),
            final_url=request.full_url,
        )

    result = discovery.fetch_catalog("bakkes_maps", opener=opener)
    item = result["items"][0]

    assert requests == ["https://bakkesplugins.com/maps"]
    assert item["thumbnail_url"] == image_url
    assert item["installed"] is None
    assert item["installed_state"] == "unknown"
    assert item["can_launch"] is False
    assert item["can_activate"] is False
    assert item["career_allowed"] is False
    assert item["catalog_only"] is True
    assert "compatibility" not in item
    assert "compatibility is unverified" in result["message"]


@pytest.mark.parametrize(
    ("source", "page_two_url", "body"),
    [
        (
            "steam_maps",
            "https://steamcommunity.com/workshop/browse/?appid=252950&browsesort=trend&section=readytouseitems&p=2",
            '<input name="search">' + steam_card(20, "Speed Flip Trainer") + steam_card(21, "Aerial Control"),
        ),
        (
            "bakkes_maps",
            "https://bakkesplugins.com/maps?page=2",
            '<input name="search">'
            + bakkes_card("bakkes_maps", 20, "Speed Flip Trainer")
            + bakkes_card("bakkes_maps", 21, "Aerial Control"),
        ),
        (
            "bakkes_plugins",
            "https://bakkesplugins.com/plugins?page=2",
            '<input name="search">'
            + bakkes_card("bakkes_plugins", 20, "Speed Flip Trainer")
            + bakkes_card("bakkes_plugins", 21, "Aerial Control"),
        ),
    ],
)
def test_query_is_local_and_page_is_bounded_in_canonical_url(source, page_two_url, body):
    seen = []

    def opener(request, timeout):
        seen.append(request.full_url)
        return html_response(body, final_url=request.full_url)

    result = discovery.fetch_catalog(source, query="speed flip", page=2, opener=opener)

    assert seen == [page_two_url]
    assert [item["title"] for item in result["items"]] == ["Speed Flip Trainer"]
    assert result["query"] == "speed flip"
    assert result["query_scope"] == "local_page_filter"
    assert result["remote_query"] is False
    assert result["page"] == 2


@pytest.mark.parametrize("bad_page", [0, -1, 51, True, 1.0, "2"])
def test_invalid_page_is_rejected_before_request(bad_page):
    with pytest.raises(discovery.CommunityCatalogError):
        discovery.fetch_catalog("bakkes_maps", page=bad_page, opener=lambda *_args, **_kwargs: pytest.fail())


@pytest.mark.parametrize("bad_query", ["x" * 81, "bad\nquery", None, 7])
def test_invalid_query_is_rejected_before_request(bad_query):
    with pytest.raises(discovery.CommunityCatalogError):
        discovery.fetch_catalog("bakkes_maps", query=bad_query, opener=lambda *_args, **_kwargs: pytest.fail())


def test_page_body_and_item_count_are_bounded():
    with pytest.raises(discovery.CatalogUnavailable, match="too large"):
        discovery.parse_catalog("x" * (discovery._MAX_BODY + 1), "bakkes_maps")

    cards = "".join(
        bakkes_card("bakkes_maps", index, f"Map {index}")
        for index in range(1, discovery._MAX_ITEMS + 3)
    )
    result = discovery.parse_catalog('<input name="search">' + cards, "bakkes_maps")

    assert len(result["items"]) == discovery._MAX_ITEMS
    assert result["page_item_count"] == discovery._MAX_ITEMS
    assert result["truncated"] is True


@pytest.mark.parametrize(
    "final_url",
    [
        "https://evil.example/plugins",
        "http://bakkesplugins.com/plugins",
        "https://bakkesplugins.com.evil.example/plugins",
        "https://bakkesplugins.com:443/plugins",
        "https://bakkesplugins.com@evil.example/plugins",
        "https://bakkesplugins.com/plugin/223",
    ],
)
def test_opener_cannot_return_an_unapproved_final_url(final_url):
    def opener(request, timeout):
        return html_response(
            '<input name="search">' + bakkes_card("bakkes_plugins", 223, "Map Loader"),
            final_url=final_url,
        )

    with pytest.raises(discovery.CatalogUnavailable, match="URL is not allowed"):
        discovery.fetch_catalog("bakkes_plugins", opener=opener)


def test_redirect_is_followed_only_to_an_approved_catalog_page():
    requested = []
    first = Response(
        status=302,
        headers={"Location": "/plugins?page=2"},
        final_url="https://bakkesplugins.com/plugins",
    )
    html = '<input name="search">' + bakkes_card("bakkes_plugins", 223, "Map Loader")

    def opener(request, timeout):
        requested.append(request.full_url)
        if len(requested) == 1:
            return first
        return html_response(html, final_url=request.full_url)

    result = discovery.fetch_catalog("bakkes_plugins", opener=opener)

    assert requested == [
        "https://bakkesplugins.com/plugins",
        "https://bakkesplugins.com/plugins?page=2",
    ]
    assert first.closed is True
    assert result["source_url"] == requested[-1]


def test_redirect_to_unapproved_host_is_not_requested():
    requested = []

    def opener(request, timeout):
        requested.append(request.full_url)
        return Response(
            status=302,
            headers={"Location": "https://evil.example/plugins"},
            final_url=request.full_url,
        )

    with pytest.raises(discovery.CatalogUnavailable, match="URL is not allowed"):
        discovery.fetch_catalog("bakkes_plugins", opener=opener)

    assert requested == ["https://bakkesplugins.com/plugins"]


def test_cancellation_before_request_and_during_body_read_closes_response():
    body = '<input name="search">' + bakkes_card("bakkes_maps", 138, "Ice Rings")
    response = html_response(body, final_url="https://bakkesplugins.com/maps")

    def cancel_after_first_chunk():
        return response.read_calls > 0

    with pytest.raises(discovery.CatalogCancelled):
        discovery.fetch_catalog("bakkes_maps", cancel=lambda: True, opener=lambda *_args, **_kwargs: pytest.fail())
    with pytest.raises(discovery.CatalogCancelled):
        discovery.fetch_catalog(
            "bakkes_maps", cancel=cancel_after_first_chunk,
            opener=lambda *_args, **_kwargs: response,
        )
    assert response.closed is True


def test_read_deadline_times_out_and_closes_response(monkeypatch):
    response = html_response(
        '<input name="search">' + bakkes_card("bakkes_maps", 138, "Ice Rings"),
        final_url="https://bakkesplugins.com/maps",
    )
    ticks = iter([100.0, 100.0, 121.0])
    monkeypatch.setattr(discovery.time, "monotonic", lambda: next(ticks))

    with pytest.raises(discovery.CatalogUnavailable, match="timed out"):
        discovery.fetch_catalog("bakkes_maps", opener=lambda *_args, **_kwargs: response)

    assert response.closed is True


@pytest.mark.parametrize(
    "html",
    [
        "<html><title>Just a moment...</title><body>Verify you are human</body></html>",
        "<html><body>unexpected layout</body></html>",
        '<input name="search"><a href="/maps/138"><span>5.0</span><span>v1.0.0</span></a>',
    ],
)
def test_challenge_and_unreadable_catalog_pages_fail_closed(html):
    with pytest.raises(discovery.CatalogUnavailable):
        discovery.parse_catalog(html, "bakkes_maps")


def test_page_parser_marks_empty_recognized_catalog_without_fabricating_items():
    result = discovery.parse_catalog('<input name="search">', "bakkes_plugins")

    assert result["status"] == "empty_page"
    assert result["items"] == []
    assert result["catalog_only"] is True
    assert result["fetched"] is False
