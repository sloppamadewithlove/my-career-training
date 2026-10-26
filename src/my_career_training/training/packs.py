"""Small public catalog of Psyonix-featured community power-shot training packs.

The six packs below were featured by Psyonix in the official April 30, 2020
"Training Pack Refresh: Shoot Your Shot" news post. The packs are authored by
community creators, not by Psyonix; the post is only the verified source that
lists them. No pack data is downloaded, and no proprietary game assets are
copied or bundled here.

This module is pure data plus validation. It performs no network access and no
game interaction. A native implementation may later map a fixed allowlist of
pack ids to codes; user-supplied text must never be interpolated into a
console command.
"""

from copy import deepcopy
import re

SOURCE_URL = (
    "https://www.rocketleague.com/news/training-pack-refresh--shoot-your-shot-?lang=en"
)
FEATURED_DATE = "2020-04-30"
SOURCE_KIND = "psyonix_featured_community"
LESSON_ID = "power-shots"

_PACK_CODE = re.compile(r"^[0-9A-F]{4}(?:-[0-9A-F]{4}){3}$")

_PACKS = (
    {
        "id": "powershot-practice",
        "title": "Powershot Practice",
        "author": "Skogur",
        "rank": "Gold",
        "code": "C9E4-0F05-B71A-C322",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Gold difficulty).",
    },
    {
        "id": "powershots",
        "title": "Powershots",
        "author": "Yeeza",
        "rank": "Diamond",
        "code": "7028-5E10-88EF-E83E",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Diamond difficulty).",
    },
    {
        "id": "powershot-training",
        "title": "Powershot Training",
        "author": "Iridium",
        "rank": "Diamond",
        "code": "7EB0-B25B-689D-3413",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Diamond difficulty).",
    },
    {
        "id": "power-shot-air-roll-shot",
        "title": "Power shot + Air roll shot",
        "author": "Tama",
        "rank": "Diamond",
        "code": "1C4E-D311-1506-B6C1",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Diamond difficulty).",
    },
    {
        "id": "powerclears-on-wall",
        "title": "Powerclears on wall",
        "author": "Wa eeuuuuh",
        "rank": "Champion",
        "code": "5053-597D-C47B-B5B0",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Champion difficulty).",
    },
    {
        "id": "powershots-super-champion",
        "title": "Powershots (super champion)",
        "author": "Ruzriel",
        "rank": "Grand Champion",
        "code": "0390-AED7-109D-8770",
        "lesson_id": LESSON_ID,
        "source_url": SOURCE_URL,
        "featured_date": FEATURED_DATE,
        "source_kind": SOURCE_KIND,
        "description": "Featured community pack (Grand Champion difficulty).",
    },
)

_BY_ID = {pack["id"]: pack for pack in _PACKS}


def training_packs():
    """Return a deep copy of the featured pack list, in source order."""
    return deepcopy(list(_PACKS))


def get_training_pack(pack_id):
    """Return one pack by exact id.

    Contract choice: a non-string argument raises ``TypeError`` and an unknown
    id raises ``ValueError``. Only the fixed ids in this module are accepted;
    there is no fuzzy matching, case folding, or prefix lookup.
    """
    if not isinstance(pack_id, str):
        raise TypeError("Training pack id must be a string.")
    try:
        return deepcopy(_BY_ID[pack_id])
    except KeyError:
        raise ValueError(f"Unknown training pack: {pack_id}") from None


def validate_pack_code(code):
    """Return True only for an exact 16-hex-digit code in four hyphenated groups.

    Contract choice: this predicate returns ``False`` for any invalid input
    (including non-strings) and never raises. Lowercase hex, extra spaces,
    missing or extra groups, and non-hex characters are all rejected.
    """
    return isinstance(code, str) and _PACK_CODE.fullmatch(code) is not None


__all__ = [
    "FEATURED_DATE",
    "LESSON_ID",
    "SOURCE_KIND",
    "SOURCE_URL",
    "get_training_pack",
    "training_packs",
    "validate_pack_code",
]
