"""Bounded, read-only discovery for public community map and plugin catalogs.

This module reads one public catalog page at a time and returns link-only rows.
It never downloads a package, never fetches a thumbnail, never writes a cache,
never enables a plugin, and never touches game files. Download and activation
remain the existing validated routes in ``community_plugins.py``.

Provenance, observed during development on 2026-10-26 from anonymous public
pages (no account, no cookie, no API key):

- ``https://bakkesplugins.com/plugins`` listed 16 card anchors shaped like
  ``<a href="/plugin/223" class="group flex h-full flex-col ...">`` containing an
  ``img``, a rating span, a version span, a title ``h2``, creator and description
  text, and a trailing ``View Details`` label. ``/maps`` used the same card shape
  with ``/maps/138`` item links. Both pages expose ``name="search"`` inputs and
  ``?page=2`` pagination links.
- ``https://steamcommunity.com/workshop/browse/?appid=252950&browsesort=trend&section=readytouseitems``
  listed 30 map items. Each item has an image anchor
  ``.../sharedfiles/filedetails/?id=1520915243`` with an ``img`` whose ``alt`` is
  ``Larger map``, then a second anchor with the *same* URL carrying the title
  text, then a creator anchor ``/profiles/<id>/myworkshopfiles/?appid=252950``
  whose text is ``By Salade``. Script hydration blobs are present and ignored.
- A direct Python request to ``/plugins?search=speedflip`` returned HTTP 403.
  Remote search is therefore **not** implemented and **not** verified. This
  module never sends a query to a server, never retries with different headers,
  and never attempts to bypass a refusal. ``query`` is a local filter over the
  rows of the single page that was read.

Only these HTTPS hosts are allowed: ``bakkesplugins.com`` and
``steamcommunity.com`` for pages, ``images.steamusercontent.com`` for Steam
thumbnails, and ``bakkesplugins.com`` / ``cdn.bakkesplugins.com`` for Bakkes
thumbnails. Thumbnail URLs are validated metadata only; they are never fetched.
"""

from __future__ import annotations

import http.client
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Callable

SOURCES = ("steam_maps", "bakkes_maps", "bakkes_plugins")

_MAX_BODY = 2 * 1024 * 1024
_MAX_ITEMS = 60
_MAX_TITLE = 200
_MAX_CREATOR = 80
_MAX_DESCRIPTION = 400
_MAX_QUERY = 80
_MAX_PAGE = 50
_MAX_REDIRECTS = 3
_TIMEOUT = 20.0
_CHUNK = 64 * 1024
_MAX_URL = 400
_MAX_THUMBNAIL_URL = 500

_USER_AGENT = "MyCareerTraining/0.3"
_ACCEPT = "text/html,application/xhtml+xml;q=0.9"
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_REDIRECTS = frozenset({301, 302, 303, 307, 308})

_PAGE_HOSTS = frozenset({"bakkesplugins.com", "steamcommunity.com"})
_STEAM_MEDIA_HOSTS = frozenset({"images.steamusercontent.com"})
_BAKKES_MEDIA_HOSTS = frozenset({"bakkesplugins.com", "cdn.bakkesplugins.com"})

_BASE = {
    "steam_maps": "https://steamcommunity.com/",
    "bakkes_maps": "https://bakkesplugins.com/",
    "bakkes_plugins": "https://bakkesplugins.com/",
}
_STEAM_BROWSE = (
    "https://steamcommunity.com/workshop/browse/"
    "?appid=252950&browsesort=trend&section=readytouseitems"
)
_BAKKES_BROWSE = {
    "bakkes_plugins": "https://bakkesplugins.com/plugins",
    "bakkes_maps": "https://bakkesplugins.com/maps",
}

_ID = re.compile(r"[1-9][0-9]{0,9}")
_PAGE_NUMBER = re.compile(r"[1-9][0-9]{0,3}")
_PROFILE_PATH = re.compile(r"/profiles/[0-9]{1,20}/myworkshopfiles/?")
_VIEW_DETAILS = frozenset({"view details", "view detail"})

_VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})
_SKIP = frozenset({"script", "style", "noscript", "template", "svg"})
_HEADINGS = frozenset({"h2", "h3"})

_CHALLENGE_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "cf_chl_opt",
    "captcha",
    "attention required",
    "verify you are human",
    "are you a robot",
    "enable javascript and cookies",
    "access denied",
    "request unsuccessful",
    "too many requests",
    "unusual traffic",
    "sign in to continue",
    "please log in to continue",
)

_STATUS_MESSAGES = {
    401: "The catalog site requires sign-in (HTTP 401). This app does not sign in.",
    403: (
        "The catalog site refused this request (HTTP 403). Open the official page in a "
        "browser instead; this app does not bypass site protection."
    ),
    404: "The catalog page was not found (HTTP 404).",
    407: "The catalog site requires proxy authentication (HTTP 407).",
    429: "The catalog site is rate limiting requests (HTTP 429). Try again later.",
}


class CommunityCatalogError(RuntimeError):
    """A public catalog page could not be read or understood."""


class CatalogUnavailable(CommunityCatalogError):
    """The catalog page was refused, unreachable, or not a recognizable catalog."""


class CatalogCancelled(CommunityCatalogError):
    """The caller cancelled the catalog read before it finished."""


def fetch_catalog(
    source,
    *,
    query: str = "",
    page: int = 1,
    opener: Callable[..., object] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> dict:
    """Read one public catalog page and return link-only rows.

    ``query`` filters only the rows of this page locally; it is never sent to the
    server. ``opener`` is an injectable test/integration boundary and its actual
    final URL is validated against the same allowlist as the requested URL.
    """
    name = _source(source)
    text = _query(query)
    number = _page(page)
    _cancel_check(cancel)
    client = _opener(opener)
    body, final_url = _request(client, name, _page_url(name, number), cancel)
    result = parse_catalog(body, name, query=text, page=number)
    result["source_url"] = final_url
    result["fetched"] = True
    return result


def parse_catalog(html, source, *, query: str = "", page: int = 1) -> dict:
    """Parse already-fetched public HTML. Performs no network access."""
    name = _source(source)
    text = _query(query)
    number = _page(page)
    body = _body(html)
    parser = _CatalogParser(name)
    try:
        parser.feed(body)
        parser.close()
    except CommunityCatalogError:
        raise
    except Exception:
        raise CatalogUnavailable("The catalog page could not be read.") from None
    parser.flush()
    rows = _merge(parser.cards, name)
    truncated = len(rows) > _MAX_ITEMS
    if truncated:
        rows = rows[:_MAX_ITEMS]
    page_item_count = len(rows)
    if not rows:
        if _challenge(body):
            raise CatalogUnavailable(
                "The catalog site returned a sign-in or browser-challenge page instead of "
                "the catalog. Open the official page in a browser; this app does not bypass it."
            )
        if not parser.marker:
            raise CatalogUnavailable(
                "The page did not look like a recognized catalog page. The site layout may "
                "have changed; open the official page in a browser to check."
            )
        if parser.cards:
            raise CatalogUnavailable(
                "Catalog items were found but their titles could not be read. The site layout "
                "may have changed; open the official page in a browser to check."
            )
        status = "empty_page"
        message = "This catalog page listed no items."
    else:
        status = "ok"
        message = (
            "Catalog links only. Nothing was downloaded, installed, or enabled, and "
            "compatibility is unverified."
        )
    if text:
        needle = text.casefold()
        rows = [
            row for row in rows
            if needle in " ".join(
                str(row.get(key, "")) for key in ("title", "creator", "description", "source_id")
            ).casefold()
        ]
    return {
        "source": name,
        "query": text,
        "page": number,
        "items": rows,
        "has_next": (number + 1) in parser.pages,
        "source_url": _page_url(name, number),
        "status": status,
        "message": message,
        "query_scope": "local_page_filter" if text else "none",
        "remote_query": False,
        "page_item_count": page_item_count,
        "truncated": truncated,
        "catalog_only": True,
        "fetched": False,
    }


def validate_request(source, *, query: str = "", page: int = 1) -> dict:
    """Validate one browse request without any network access.

    Callers use this to reject a bad command before starting a background read.
    """
    return {"source": _source(source), "query": _query(query), "page": _page(page)}


def catalog_page_url(source, page: int = 1) -> str:
    """Return the canonical public catalog page URL for one source."""
    return _page_url(_source(source), _page(page))


def item_details_url(source, source_id) -> str:
    """Return the canonical public details URL for one numeric catalog item."""
    name = _source(source)
    if type(source_id) is not int or isinstance(source_id, bool) or _ID.fullmatch(str(source_id)) is None:
        raise CommunityCatalogError("Catalog item is not valid.")
    return _details_url(name, source_id)


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


def _source(value) -> str:
    if type(value) is not str or value not in SOURCES:
        raise CommunityCatalogError(
            "Choose one catalog source: steam_maps, bakkes_maps, or bakkes_plugins."
        )
    return value


def _query(value) -> str:
    if type(value) is not str:
        raise CommunityCatalogError("Catalog search text is not valid.")
    text = value.strip()
    if len(text) > _MAX_QUERY:
        raise CommunityCatalogError(f"Catalog search text must be {_MAX_QUERY} characters or fewer.")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise CommunityCatalogError("Catalog search text is not valid.")
    return text


def _page(value) -> int:
    if type(value) is not int or isinstance(value, bool) or not 1 <= value <= _MAX_PAGE:
        raise CommunityCatalogError(f"Catalog page must be a whole number from 1 to {_MAX_PAGE}.")
    return value


def _body(html) -> str:
    if isinstance(html, (bytes, bytearray)):
        if len(html) > _MAX_BODY:
            raise CatalogUnavailable("The catalog page was too large.")
        return bytes(html).decode("utf-8", "replace")
    if isinstance(html, str):
        if len(html) > _MAX_BODY:
            raise CatalogUnavailable("The catalog page was too large.")
        try:
            encoded = html.encode("utf-8")
        except UnicodeError:
            raise CommunityCatalogError("Catalog page content is not valid.") from None
        if len(encoded) > _MAX_BODY:
            raise CatalogUnavailable("The catalog page was too large.")
        return html
    raise CommunityCatalogError("Catalog page content is not valid.")


def _page_url(source: str, page: int) -> str:
    if source == "steam_maps":
        return _STEAM_BROWSE if page == 1 else f"{_STEAM_BROWSE}&p={page}"
    base = _BAKKES_BROWSE[source]
    return base if page == 1 else f"{base}?page={page}"


def _validate_page_url(source: str, url) -> None:
    if type(url) is not str or not 20 <= len(url) <= _MAX_URL:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    if any(ord(char) < 33 or ord(char) > 126 for char in url):
        raise CatalogUnavailable("Catalog URL is not allowed.")
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        raise CatalogUnavailable("Catalog URL is not allowed.") from None
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.fragment or port is not None):
        raise CatalogUnavailable("Catalog URL is not allowed.")
    host = (parts.hostname or "").casefold()
    if host not in _PAGE_HOSTS:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    keys: dict[str, str] = {}
    for key, value in pairs:
        if key in keys:
            raise CatalogUnavailable("Catalog URL is not allowed.")
        keys[key] = value
    if source == "steam_maps":
        if host != "steamcommunity.com" or parts.path.rstrip("/") != "/workshop/browse":
            raise CatalogUnavailable("Catalog URL is not allowed.")
        if (keys.get("appid") != "252950" or keys.get("browsesort") != "trend"
                or keys.get("section") != "readytouseitems"):
            raise CatalogUnavailable("Catalog URL is not allowed.")
        if set(keys) - {"appid", "browsesort", "section", "p"}:
            raise CatalogUnavailable("Catalog URL is not allowed.")
        if "p" in keys and _PAGE_NUMBER.fullmatch(keys["p"]) is None:
            raise CatalogUnavailable("Catalog URL is not allowed.")
        return
    if host != "bakkesplugins.com":
        raise CatalogUnavailable("Catalog URL is not allowed.")
    expected = "/plugins" if source == "bakkes_plugins" else "/maps"
    if parts.path.rstrip("/") != expected:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    if set(keys) - {"page"}:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    if "page" in keys and _PAGE_NUMBER.fullmatch(keys["page"]) is None:
        raise CatalogUnavailable("Catalog URL is not allowed.")


def _validate_final_url(source: str, url) -> None:
    """Validate the URL an opener actually landed on.

    Stricter than "any URL": the host and catalog path must match the source, and
    a Steam ``appid`` must still be Rocket League. Extra tracking parameters that
    a site may append on redirect are tolerated here, but the next request hop is
    still built only from a strictly validated URL.
    """
    if type(url) is not str or not 20 <= len(url) <= _MAX_URL:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    if any(ord(char) < 33 or ord(char) > 126 for char in url):
        raise CatalogUnavailable("Catalog URL is not allowed.")
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        raise CatalogUnavailable("Catalog URL is not allowed.") from None
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.fragment or port is not None):
        raise CatalogUnavailable("Catalog URL is not allowed.")
    host = (parts.hostname or "").casefold()
    if host not in _PAGE_HOSTS:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    if source == "steam_maps":
        if host != "steamcommunity.com" or parts.path.rstrip("/") != "/workshop/browse":
            raise CatalogUnavailable("Catalog URL is not allowed.")
        pairs = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        if pairs.get("appid", "252950") != "252950":
            raise CatalogUnavailable("Catalog URL is not allowed.")
        return
    if host != "bakkesplugins.com":
        raise CatalogUnavailable("Catalog URL is not allowed.")
    expected = "/plugins" if source == "bakkes_plugins" else "/maps"
    if parts.path.rstrip("/") != expected:
        raise CatalogUnavailable("Catalog URL is not allowed.")


def _details_url(source: str, source_id: int) -> str:
    if source == "steam_maps":
        return f"https://steamcommunity.com/sharedfiles/filedetails/?id={source_id}"
    if source == "bakkes_plugins":
        return f"https://bakkesplugins.com/plugin/{source_id}"
    return f"https://bakkesplugins.com/maps/{source_id}"


def _item_id(source: str, href) -> int | None:
    """Return a numeric item id only for an exact canonical item link."""
    if type(href) is not str or not href or len(href) > _MAX_URL:
        return None
    if any(ord(char) < 33 or ord(char) > 126 for char in href):
        return None
    try:
        parts = urllib.parse.urlsplit(urllib.parse.urljoin(_BASE[source], href))
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.fragment or port is not None):
        return None
    host = (parts.hostname or "").casefold()
    if source == "steam_maps":
        if host != "steamcommunity.com":
            return None
        if parts.path.rstrip("/") != "/sharedfiles/filedetails":
            return None
        pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if len(pairs) != 1 or pairs[0][0] != "id":
            return None
        value = pairs[0][1]
    else:
        if host != "bakkesplugins.com" or parts.query:
            return None
        prefix = "/plugin/" if source == "bakkes_plugins" else "/maps/"
        if not parts.path.startswith(prefix):
            return None
        value = parts.path[len(prefix):].rstrip("/")
    if _ID.fullmatch(value) is None:
        return None
    return int(value)


def _is_creator_href(href) -> bool:
    """Match the observed creator link without retaining its account id."""
    if type(href) is not str or not href or len(href) > _MAX_URL:
        return False
    if any(ord(char) < 33 or ord(char) > 126 for char in href):
        return False
    try:
        parts = urllib.parse.urlsplit(urllib.parse.urljoin(_BASE["steam_maps"], href))
        port = parts.port
    except ValueError:
        return False
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.fragment or port is not None):
        return False
    if (parts.hostname or "").casefold() != "steamcommunity.com":
        return False
    if _PROFILE_PATH.fullmatch(parts.path) is None:
        return False
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    return all(key == "appid" and value == "252950" for key, value in pairs)


def _thumbnail_url(source: str, src) -> str | None:
    """Validate a thumbnail URL as metadata only. It is never requested."""
    if type(src) is not str or not src or len(src) > _MAX_THUMBNAIL_URL:
        return None
    if any(ord(char) < 33 or ord(char) > 126 for char in src):
        return None
    try:
        parts = urllib.parse.urlsplit(urllib.parse.urljoin(_BASE[source], src))
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.fragment or port is not None):
        return None
    host = (parts.hostname or "").casefold()
    allowed = _STEAM_MEDIA_HOSTS if source == "steam_maps" else _BAKKES_MEDIA_HOSTS
    if host not in allowed:
        return None
    if not parts.path.startswith("/") or ".." in parts.path:
        return None
    return urllib.parse.urlunsplit(("https", host, parts.path, parts.query, ""))


def _clean(value) -> str:
    if type(value) is not str:
        return ""
    text = "".join(
        " " if (char < " " or char == "\x7f") else char for char in value
    )
    return " ".join(text.split())


def _bound(text: str, limit: int) -> str:
    return text[:limit].rstrip()


def _challenge(body: str) -> bool:
    lowered = body.casefold()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


# --------------------------------------------------------------------------- #
# HTML parsing
# --------------------------------------------------------------------------- #


class _CatalogParser(HTMLParser):
    """Structural card parser. No CSS class or hash selector is used."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.stack: list[str] = []
        self.skip = 0
        self.cards: list[dict] = []
        self.card: dict | None = None
        self.creator_capture: dict | None = None
        self.anchor_depth = 0
        self.marker = False
        self.pages: set[int] = set()

    # -- HTMLParser hooks --------------------------------------------------- #

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
            self.stack.append(tag)
            return
        if self.skip:
            if tag not in _VOID:
                self.stack.append(tag)
            return
        self._start(tag, {key: (value or "") for key, value in attrs})
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skip:
            self._pop(tag)
            return
        if tag in _HEADINGS and self.card is not None and self.card["heading_open"]:
            self.card["heading_open"] = False
            self.card["title_done"] = True
        self._pop(tag)
        self._maybe_close()

    def _pop(self, tag: str) -> None:
        if tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            if top in _SKIP:
                self.skip = max(0, self.skip - 1)
            if top == "a":
                self.anchor_depth = max(0, self.anchor_depth - 1)
            if top == tag:
                break

    def handle_data(self, data):
        if self.skip:
            return
        text = _clean(data)
        if not text:
            return
        if self.creator_capture is not None:
            self.creator_capture["parts"].append(text)
            return
        if self.card is not None:
            if self.card["heading_open"]:
                self.card["heading"].append(text)
            else:
                self.card["texts"].append((self.card["title_done"], text))

    # -- structure ---------------------------------------------------------- #

    def _start(self, tag: str, attrs: dict) -> None:
        if tag == "input" and attrs.get("name") == "search":
            self.marker = True
        if tag == "a":
            self.anchor_depth += 1
            href = attrs.get("href", "")
            self._note_pagination(href)
            if self._same_catalog_path(href):
                self.marker = True
            if self.source == "steam_maps" and self.creator_capture is None and _is_creator_href(href):
                self.creator_capture = {"depth": len(self.stack), "parts": []}
                return
            if self.card is None:
                identity = _item_id(self.source, href)
                if identity is not None:
                    self.marker = True
                    self.card = {
                        "id": identity,
                        "depth": len(self.stack),
                        "texts": [],
                        "heading": [],
                        "imgs": [],
                        "title_attr": attrs.get("title", ""),
                        "heading_open": False,
                        "title_done": False,
                        "creator_title": "",
                    }
                    self.cards.append(self.card)
                    return
        if self.card is not None:
            # The observed Bakkes card uses an h2 title; h3 is kept as a legacy
            # shape. Only the first heading directly inside the card anchor is the
            # title, so a rating or version span can never become one.
            if (tag in _HEADINGS and not self.card["heading"]
                    and not self.card["title_done"] and self.anchor_depth <= 1):
                self.card["heading_open"] = True
            elif tag == "img":
                src = attrs.get("src", "")
                if src:
                    self.card["imgs"].append(src)
            elif (tag == "span" and self.card["title_done"]
                    and not self.card["creator_title"] and attrs.get("title")):
                # The observed Bakkes card puts the creator name in a span title
                # attribute next to an avatar span that only shows an initial.
                self.card["creator_title"] = _clean(attrs["title"])

    def _note_pagination(self, href) -> None:
        if type(href) is not str or not href or len(href) > _MAX_URL:
            return
        try:
            parts = urllib.parse.urlsplit(urllib.parse.urljoin(_BASE[self.source], href))
        except ValueError:
            return
        if parts.scheme != "https" or parts.username or parts.password:
            return
        host = (parts.hostname or "").casefold()
        pairs = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        if self.source == "steam_maps":
            if host != "steamcommunity.com" or parts.path.rstrip("/") != "/workshop/browse":
                return
            value = pairs.get("p")
        else:
            expected = "/plugins" if self.source == "bakkes_plugins" else "/maps"
            if host != "bakkesplugins.com" or parts.path.rstrip("/") != expected:
                return
            value = pairs.get("page")
        if value and _PAGE_NUMBER.fullmatch(value):
            self.pages.add(int(value))

    def _same_catalog_path(self, href) -> bool:
        if type(href) is not str or not href or len(href) > _MAX_URL:
            return False
        try:
            parts = urllib.parse.urlsplit(urllib.parse.urljoin(_BASE[self.source], href))
        except ValueError:
            return False
        if parts.scheme != "https":
            return False
        host = (parts.hostname or "").casefold()
        if self.source == "steam_maps":
            return host == "steamcommunity.com" and parts.path.rstrip("/") == "/workshop/browse"
        expected = "/plugins" if self.source == "bakkes_plugins" else "/maps"
        return host == "bakkesplugins.com" and parts.path.rstrip("/") == expected

    def _maybe_close(self) -> None:
        if self.creator_capture is not None and len(self.stack) <= self.creator_capture["depth"]:
            capture = self.creator_capture
            self.creator_capture = None
            name = _clean(" ".join(capture["parts"]))
            if name.casefold().startswith("by "):
                name = _clean(name[3:])
            if name:
                self._attach_creator(_bound(name, _MAX_CREATOR))
        if self.card is not None and len(self.stack) <= self.card["depth"]:
            self._finish_card()

    def _attach_creator(self, name: str) -> None:
        for card in reversed(self.cards):
            if card.get("creator") is not None:
                continue
            if card.get("title") or card.get("heading") or card.get("texts"):
                card["creator"] = name
                return

    def _finish_card(self) -> None:
        card = self.card
        self.card = None
        if card is None:
            return
        creator = card.get("creator")
        description = None
        if self.source == "steam_maps":
            title = _clean(" ".join(text for _flag, text in card["texts"]))
        else:
            heading = _clean(" ".join(card["heading"]))
            if heading:
                title = heading
                # Only text after the heading can be creator/description. Anything
                # before it (rating, version) is not reinterpreted as either.
                segments = [text for flag, text in card["texts"] if flag]
                segments = [text for text in segments if text.casefold() not in _VIEW_DETAILS]
                if card.get("creator_title"):
                    creator = card["creator_title"]
                    # Remove only the observed avatar/name prefix. A genuine
                    # one-character creator name remains valid.
                    if segments and len(segments[0]) == 1 and segments[0].casefold() == creator[0].casefold():
                        segments.pop(0)
                    if segments and segments[0] == creator:
                        segments.pop(0)
                    if len(segments) == 1:
                        description = segments[0]
                else:
                    if segments and creator is None:
                        creator = segments[0]
                    if len(segments) == 2:
                        description = segments[1]
            else:
                # Without the heading the remaining text order is ambiguous, so
                # only the anchor's own title attribute is trusted.
                title = _clean(card["title_attr"])
        thumbnail = ""
        for src in card["imgs"]:
            thumbnail = _thumbnail_url(self.source, src) or ""
            if thumbnail:
                break
        card["title"] = _bound(title, _MAX_TITLE) if title else ""
        card["creator"] = _bound(creator, _MAX_CREATOR) if creator else None
        card["description"] = _bound(description, _MAX_DESCRIPTION) if description else None
        card["thumbnail"] = thumbnail

    def flush(self) -> None:
        self.stack.clear()
        self._maybe_close()


def _merge(cards: list[dict], source: str) -> list[dict]:
    """Merge duplicate anchors for one item and drop rows without a title."""
    merged: dict[int, dict] = {}
    order: list[int] = []
    for card in cards:
        identity = card["id"]
        row = merged.get(identity)
        if row is None:
            row = {"source_id": identity, "title": "", "creator": "", "description": "", "thumbnail": ""}
            merged[identity] = row
            order.append(identity)
        for key in ("title", "creator", "description", "thumbnail"):
            if not row[key] and card.get(key):
                row[key] = card[key]
    rows = []
    for identity in order:
        row = merged[identity]
        if not row["title"]:
            continue
        rows.append(_row(source, row))
    return rows


def _row(source: str, row: dict) -> dict:
    item = {
        "id": f"{source}:{row['source_id']}",
        "source": source,
        "source_id": row["source_id"],
        "kind": "plugin" if source == "bakkes_plugins" else "map",
        "title": row["title"],
        "creator": row["creator"] or "Unknown creator",
        "details_url": _details_url(source, row["source_id"]),
        # Discovery cannot know local install state, so it reports unknown rather
        # than claiming either installed or not installed.
        "installed": None,
        "installed_state": "unknown",
        "can_launch": False,
        "can_activate": False,
        "career_allowed": False,
        "catalog_only": True,
        "status": "catalog_only",
    }
    if row["description"]:
        item["description"] = row["description"]
    if row["thumbnail"]:
        item["thumbnail_url"] = row["thumbnail"]
    return item


# --------------------------------------------------------------------------- #
# Network
# --------------------------------------------------------------------------- #


def _cancel_check(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise CatalogCancelled("Catalog request cancelled.")


def _opener(opener: Callable[..., object] | None) -> Callable[..., object]:
    if opener is None:
        return _default_open
    if not callable(opener):
        raise CommunityCatalogError("Catalog request is not valid.")
    return opener


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise CatalogUnavailable("TLS certificate verification is required.")
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


def _default_open(request, timeout: float = _TIMEOUT):
    """One HTTPS GET. Redirects are not followed here; the caller checks each hop."""
    parts = urllib.parse.urlsplit(getattr(request, "full_url", ""))
    if parts.scheme != "https" or (parts.hostname or "").casefold() not in _PAGE_HOSTS:
        raise CatalogUnavailable("Catalog URL is not allowed.")
    connection = http.client.HTTPSConnection(parts.hostname, timeout=timeout, context=_tls_context())
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


def _request(opener, source: str, url: str, cancel) -> tuple[bytes, str]:
    deadline = time.monotonic() + _TIMEOUT
    current = url
    for _hop in range(_MAX_REDIRECTS + 1):
        _cancel_check(cancel)
        _validate_page_url(source, current)
        response = _open_once(opener, current)
        try:
            final = _final_url(response, current)
            _validate_final_url(source, final)
            status = getattr(response, "status", None)
            if status in _REDIRECTS:
                current = _redirect_target(current, response)
                continue
            if status != 200:
                raise CatalogUnavailable(_status_message(status))
            _require_html(response)
            return _read_body(response, cancel, deadline), final
        finally:
            closer = getattr(response, "close", None)
            if callable(closer):
                closer()
    raise CatalogUnavailable("The catalog site redirected too many times.")


def _open_once(opener, url: str):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": _ACCEPT},
        method="GET",
    )
    try:
        return opener(request, timeout=_TIMEOUT)
    except CommunityCatalogError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError, http.client.HTTPException):
        raise CatalogUnavailable("Could not reach the catalog site.") from None


def _final_url(response, current: str) -> str:
    getter = getattr(response, "geturl", None)
    if not callable(getter):
        return current
    value = getter()
    if type(value) is not str or not value:
        raise CatalogUnavailable("The catalog site returned an unexpected response.")
    return value


def _status_message(status) -> str:
    if type(status) is int and status in _STATUS_MESSAGES:
        return _STATUS_MESSAGES[status]
    if type(status) is int and 500 <= status <= 599:
        return f"The catalog site returned a server error (HTTP {status})."
    return "The catalog site returned an unexpected response."


def _redirect_target(current: str, response) -> str:
    location = _header(response, "Location")
    if location is None or not location or location != location.strip():
        raise CatalogUnavailable("The catalog site returned an invalid redirect.")
    if any(ord(char) < 33 or ord(char) == 127 or char in "\\" for char in location):
        raise CatalogUnavailable("The catalog site returned an invalid redirect.")
    return urllib.parse.urljoin(current, location)


def _header(response, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        raise CatalogUnavailable("The catalog site returned an unexpected response.")
    value = getter(name)
    if value is None:
        return None
    if type(value) is not str or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise CatalogUnavailable("The catalog site returned an unexpected response.")
    return value


def _require_html(response) -> None:
    raw = _header(response, "Content-Type")
    if raw is None or "," in raw:
        raise CatalogUnavailable("The catalog site returned an unexpected response.")
    if raw.split(";", 1)[0].strip().casefold() not in _HTML_TYPES:
        raise CatalogUnavailable("The catalog site did not return an HTML page.")


def _content_length(response) -> int | None:
    raw = _header(response, "Content-Length")
    if raw is None:
        return None
    if not raw.isdigit():
        raise CatalogUnavailable("The catalog page was too large.")
    size = int(raw)
    if size > _MAX_BODY:
        raise CatalogUnavailable("The catalog page was too large.")
    return size


def _read_body(response, cancel, deadline: float) -> bytes:
    declared = _content_length(response)
    chunks: list[bytes] = []
    count = 0
    while True:
        _cancel_check(cancel)
        if time.monotonic() >= deadline:
            raise CatalogUnavailable("The catalog request timed out.")
        try:
            chunk = response.read(min(_CHUNK, _MAX_BODY - count + 1))
        except OSError:
            raise CatalogUnavailable("The catalog request was interrupted.") from None
        if not isinstance(chunk, (bytes, bytearray)) or not chunk:
            break
        count += len(chunk)
        if count > _MAX_BODY:
            raise CatalogUnavailable("The catalog page was too large.")
        chunks.append(bytes(chunk))
    if declared is not None and count != declared:
        raise CatalogUnavailable("The catalog page was truncated.")
    return b"".join(chunks)
