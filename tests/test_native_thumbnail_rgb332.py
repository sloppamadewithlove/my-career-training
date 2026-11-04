from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_embedded_power_shots_thumbnail_matches_rgb332_contract():
    source_path = ROOT / "native_ui" / "menus" / "MctRootMenu.as"
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    payload_match = re.search(
        rb'private\s+static\s+const\s+POWER_SHOTS_PIXELS:String\s*=\s*"([A-Za-z0-9+/=]+)";',
        source_bytes,
    )
    assert payload_match is not None

    compressed = base64.b64decode(payload_match.group(1), validate=True)
    assert len(compressed) == 20648
    rgb332 = zlib.decompress(compressed)
    assert len(rgb332) == 400 * 225 == 90000
    assert hashlib.sha256(rgb332).hexdigest() == "311b1ded688e67966e89aadc9237c75268e744f58ca39641514a0a1b20683aec"

    argb = bytearray()
    for index in rgb332:
        red = (index >> 5) & 7
        green = (index >> 2) & 7
        argb.extend((
            255,
            (red << 5) | (red << 2) | (red >> 1),
            (green << 5) | (green << 2) | (green >> 1),
            (index & 3) * 85,
        ))
    assert len(argb) == 400 * 225 * 4
    assert hashlib.sha256(argb).hexdigest() == "8e6bfd08a5adf485502cf8f4ca7e559aff91867c536c76a786cc5e8813d400b1"

    decoder_start = source.index("private function loadLessonPreview() : void")
    decoder_end = source.index("private function showBrowser", decoder_start)
    decoder = source[decoder_start:decoder_end]
    for contract in (
        "bytes.length != 20648",
        "bytes.position = 0; bytes.uncompress();",
        "bytes.length != 90000",
        "for (var pixel:int = 0; pixel < 90000; ++pixel)",
        "var red:uint = (index >> 5) & 7;",
        "var green:uint = (index >> 2) & 7;",
        "pixels.writeByte(255);",
        "pixels.writeByte((red << 5) | (red << 2) | (red >> 1));",
        "pixels.writeByte((green << 5) | (green << 2) | (green >> 1));",
        "pixels.writeByte((index & 3) * 85);",
        "new BitmapData(400, 225, false, 0)",
        "bitmap.setPixels(new Rectangle(0, 0, 400, 225), pixels)",
        "catch (error:Error) { lessonPreviewState = 3; lessonPreview.visible = false; }",
    ):
        assert contract in decoder

    manifest_path = ROOT / "native_ui" / "compiled" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == "native_ui/menus/MctRootMenu.as"
    assert manifest["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert manifest["abc_bytes"] == 62429
    assert manifest["abc_bytes"] <= 65536
