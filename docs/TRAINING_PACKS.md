# Featured power-shot training packs

`src/my_career_training/training/packs.py` is a small, fixed public catalog of
six selected community training packs from the official news post
"Training Pack Refresh: Shoot Your Shot" (April 30, 2020):

<https://www.rocketleague.com/news/training-pack-refresh--shoot-your-shot-?lang=en>

## Attribution and honesty

- The packs are **authored by community creators**, not by Psyonix. Psyonix
  featured them in an official post; that post is our verified source for the
  titles, authors, listed difficulties and codes.
- `source_kind` is therefore `psyonix_featured_community`, and
  `featured_date` is `2020-04-30`.
- This is a six-pack excerpt of the article's nine entries. It omits "Power
  shot basic", "Power Aerials" and "Powershots - Saves".
- The excerpt has no **Supersonic Legend (SSL)** difficulty entry. Do not
  relabel a Grand Champion pack as SSL. The catalog is fixed public metadata,
  rather than an automatically refreshed list.
- No proprietary game assets, pack files or replays are copied or bundled.
  The module stores only public metadata: title, author, listed difficulty, code and a
  short description.
- Descriptions only identify a featured community pack and repeat its listed
  difficulty. The source does not give per-pack setup details, so descriptions
  do not claim particular ball motion, timing windows or shot sequences.

## Catalog contents

| id | title | author | rank | code |
| --- | --- | --- | --- | --- |
| `powershot-practice` | Powershot Practice | Skogur | Gold | `C9E4-0F05-B71A-C322` |
| `powershots` | Powershots | Yeeza | Diamond | `7028-5E10-88EF-E83E` |
| `powershot-training` | Powershot Training | Iridium | Diamond | `7EB0-B25B-689D-3413` |
| `power-shot-air-roll-shot` | Power shot + Air roll shot | Tama | Diamond | `1C4E-D311-1506-B6C1` |
| `powerclears-on-wall` | Powerclears on wall | Wa eeuuuuh | Champion | `5053-597D-C47B-B5B0` |
| `powershots-super-champion` | Powershots (super champion) | Ruzriel | Grand Champion | `0390-AED7-109D-8770` |

Every record also carries `lesson_id: "power-shots"`, `source_url`,
`featured_date` and `source_kind`. Ids are stable lowercase kebab-case.

## API contract

- `training_packs()` returns a deep copy of the list of dictionaries, in source
  order. Callers may mutate the result without affecting the module.
- `get_training_pack(pack_id)` accepts only an exact string id from the fixed
  allowlist. A non-string raises `TypeError`; an unknown id raises
  `ValueError`. There is no case folding, prefix matching or fuzzy lookup.
- `validate_pack_code(code)` returns `True` only for exactly 16 uppercase hex
  digits in four hyphenated groups (`XXXX-XXXX-XXXX-XXXX`). It returns `False`
  for anything else, including non-strings, and never raises.

## Native launch (blocked by the offline service)

The native implementation submits a fixed allowlisted code through BakkesMod's
`load_training` route. The actual Gold-pack click on source/native `5b293d2`
reached Rocket League's `Training/GetTrainingData` service, which returned
`FeatureDisabled` in the owned offline session. The game stayed at the frontend;
the exact-code confirmation timed out. No pack loaded and no shot was played.

The browser therefore keeps metadata and favorites but disables pack launch with
an explicit offline-unavailable explanation. The loader remains development
code, not a verified player capability. The owner declined a Rookie/Pro/All-Star
built-in-drill fallback; do not substitute it or invent competitive rank labels.

Evidence limits:

- Normal Rocket League Custom Training can be used to obtain packs. Whether a
  downloaded pack can reopen in this offline session remains unverified. The
  SDK's existing-editor `Load2` declaration is not a documented frontend loader.
  Do not claim that caching alone solves this failure.
- This document is reference material, not in-product messaging. The UI should
  show the pack title, rank and actual creator, and should not present this
  page as promotional copy.

## Testing

Contract tests live in `tests/test_training_packs.py` and are run with the rest
of the Python suite (`uv run pytest`). They pin the six selected IDs, titles,
authors, difficulties and codes; cover copy isolation and exact-id lookup; and
reject unknown IDs, non-string IDs, and malformed or non-string codes. No test
in this area asserts live game behaviour.
