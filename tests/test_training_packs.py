import pytest

from my_career_training.training.packs import (
    FEATURED_DATE,
    LESSON_ID,
    SOURCE_KIND,
    SOURCE_URL,
    get_training_pack,
    training_packs,
    validate_pack_code,
)


EXPECTED_PACKS = (
    ("powershot-practice", "Powershot Practice", "Skogur", "Gold", "C9E4-0F05-B71A-C322"),
    ("powershots", "Powershots", "Yeeza", "Diamond", "7028-5E10-88EF-E83E"),
    ("powershot-training", "Powershot Training", "Iridium", "Diamond", "7EB0-B25B-689D-3413"),
    ("power-shot-air-roll-shot", "Power shot + Air roll shot", "Tama", "Diamond", "1C4E-D311-1506-B6C1"),
    ("powerclears-on-wall", "Powerclears on wall", "Wa eeuuuuh", "Champion", "5053-597D-C47B-B5B0"),
    (
        "powershots-super-champion",
        "Powershots (super champion)",
        "Ruzriel",
        "Grand Champion",
        "0390-AED7-109D-8770",
    ),
)


def test_catalog_matches_the_six_selected_official_entries():
    packs = training_packs()
    assert len(packs) == len(EXPECTED_PACKS)
    assert tuple(
        (pack["id"], pack["title"], pack["author"], pack["rank"], pack["code"])
        for pack in packs
    ) == EXPECTED_PACKS

    for pack in packs:
        assert pack["lesson_id"] == LESSON_ID == "power-shots"
        assert pack["source_url"] == SOURCE_URL
        assert pack["featured_date"] == FEATURED_DATE == "2020-04-30"
        assert pack["source_kind"] == SOURCE_KIND == "psyonix_featured_community"
        assert pack["description"] == f"Featured community pack ({pack['rank']} difficulty)."


def test_pack_reads_return_independent_copies():
    listed = training_packs()
    selected = get_training_pack("powershot-practice")
    assert listed[0] == selected

    listed[0]["title"] = "changed list copy"
    listed[0]["code"] = "0000-0000-0000-0000"
    listed.pop()
    selected["title"] = "changed direct copy"

    fresh_list = training_packs()
    fresh_selected = get_training_pack("powershot-practice")
    expected = EXPECTED_PACKS[0]
    assert (fresh_list[0]["id"], fresh_list[0]["title"], fresh_list[0]["code"]) == (
        expected[0],
        expected[1],
        expected[4],
    )
    assert fresh_selected["title"] == expected[1]
    assert fresh_selected["code"] == expected[4]
    assert len(fresh_list) == len(EXPECTED_PACKS)


@pytest.mark.parametrize("pack_id", [None, 17, True, [], {}])
def test_non_string_pack_ids_raise_type_error(pack_id):
    with pytest.raises(TypeError, match="must be a string"):
        get_training_pack(pack_id)


@pytest.mark.parametrize("pack_id", ["", "POWERShotS", "powershot", "powershot-practice-extra"])
def test_unknown_or_non_exact_pack_ids_raise_value_error(pack_id):
    with pytest.raises(ValueError, match="Unknown training pack"):
        get_training_pack(pack_id)


@pytest.mark.parametrize("_pack_id, _title, _author, _rank, code", EXPECTED_PACKS)
def test_each_catalog_code_passes_exact_format_validation(_pack_id, _title, _author, _rank, code):
    assert validate_pack_code(code)


@pytest.mark.parametrize(
    "code",
    [
        "c9e4-0f05-b71a-c322",
        " C9E4-0F05-B71A-C322",
        "C9E4-0F05-B71A-C322 ",
        "C9E40F05-B71A-C322",
        "C9E4-0F05-B71A-C322-0000",
        "G9E4-0F05-B71A-C322",
        "C9E4-0F05-B71A-C32",
        "C9E4-0F05-B71A-C322\n",
        None,
        123,
        True,
        b"C9E4-0F05-B71A-C322",
        [],
    ],
)
def test_invalid_or_non_string_pack_codes_return_false(code):
    assert validate_pack_code(code) is False
