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

    encoded = payload_match.group(1).decode("ascii")
    compressed = base64.b64decode(encoded, validate=True)
    assert len(compressed) == 20648

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    decoded = bytearray()
    value = 0
    bits = 0
    for character in encoded:
        if character == "=":
            break
        digit = alphabet.index(character)
        value = (value << 6) | digit
        bits += 6
        if bits >= 8:
            bits -= 8
            decoded.append((value >> bits) & 255)
            value &= (1 << bits) - 1
    assert bytes(decoded) == compressed

    rgb332 = zlib.decompress(compressed)
    assert len(rgb332) == 400 * 225 == 90000
    assert hashlib.sha256(rgb332).hexdigest() == (
        "311b1ded688e67966e89aadc9237c75268e744f58ca39641514a0a1b20683aec"
    )

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
    assert hashlib.sha256(argb).hexdigest() == (
        "8e6bfd08a5adf485502cf8f4ca7e559aff91867c536c76a786cc5e8813d400b1"
    )

    decoder_start = source.index("private function loadLessonPreview() : void")
    decoder_end = source.index("private function showBrowser", decoder_start)
    decoder = source[decoder_start:decoder_end]
    for contract in (
        'var alphabet:String = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";',
        "for (var i:int = 0; i < POWER_SHOTS_PIXELS.length; ++i)",
        "var character:String = POWER_SHOTS_PIXELS.charAt(i);",
        'if (character == "=") break;',
        "var digit:int = alphabet.indexOf(character);",
        "value = (value << 6) | digit; bits += 6;",
        "if (bits >= 8)",
        "bits -= 8; bytes.writeByte((value >> bits) & 255);",
        "value &= (1 << bits) - 1;",
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
        "pixels.position = 0;",
        "bitmap.setPixels(new Rectangle(0, 0, 400, 225), pixels)",
        "lessonPreview.bitmapData = bitmap;",
        "lessonPreviewState = 2;",
        "catch (error:Error) { lessonPreviewState = 3; lessonPreview.visible = false; }",
    ):
        assert contract in decoder, contract
    base64_steps = (
        "var character:String = POWER_SHOTS_PIXELS.charAt(i);",
        'if (character == "=") break;',
        "var digit:int = alphabet.indexOf(character);",
        "value = (value << 6) | digit; bits += 6;",
        "if (bits >= 8)",
        "bits -= 8; bytes.writeByte((value >> bits) & 255);",
        "value &= (1 << bits) - 1;",
    )
    def source_block(marker, start=0):
        block_start = decoder.index(marker, start)
        opening = decoder.index("{", block_start)
        depth = 0
        for position in range(opening, len(decoder)):
            if decoder[position] == "{":
                depth += 1
            elif decoder[position] == "}":
                depth -= 1
                if depth == 0:
                    return decoder[opening + 1 : position], opening, position
        raise AssertionError(f"unterminated source block: {marker}")

    base64_body, base64_open, base64_close = source_block(
        "for (var i:int = 0; i < POWER_SHOTS_PIXELS.length; ++i)"
    )
    base64_offsets = [base64_body.index(step) for step in base64_steps]
    assert base64_offsets == sorted(base64_offsets)
    conditional_body, conditional_open, conditional_close = source_block(
        "if (bits >= 8)", base64_open
    )
    assert base64_open < conditional_open < conditional_close < base64_close
    for step in (
        "bits -= 8; bytes.writeByte((value >> bits) & 255);",
        "value &= (1 << bits) - 1;",
    ):
        assert step in conditional_body
    assert conditional_body.index("bytes.writeByte(") < conditional_body.index("value &=")

    pixel_steps = (
        "var index:uint = bytes.readUnsignedByte();",
        "var red:uint = (index >> 5) & 7;",
        "var green:uint = (index >> 2) & 7;",
        "pixels.writeByte(255);",
        "pixels.writeByte((red << 5) | (red << 2) | (red >> 1));",
        "pixels.writeByte((green << 5) | (green << 2) | (green >> 1));",
        "pixels.writeByte((index & 3) * 85);",
    )
    pixel_body, _pixel_open, pixel_close = source_block(
        "for (var pixel:int = 0; pixel < 90000; ++pixel)"
    )
    pixel_offsets = [pixel_body.index(step) for step in pixel_steps]
    assert pixel_offsets == sorted(pixel_offsets)
    pixels_reset = decoder.rfind("pixels.position = 0;")
    assert pixels_reset > pixel_close, "pixel buffer rewind must follow the RGB332 expansion loop"
    bitmap_create = decoder.index("new BitmapData(400, 225, false, 0)", pixels_reset)
    set_pixels = decoder.index("bitmap.setPixels(", bitmap_create)
    assert decoder.index("if (bytes.length != 20648)") < decoder.index("bytes.position = 0; bytes.uncompress();"), "compressed-size guard must precede decompression"
    pipeline = (
        decoder.index("var bytes:ByteArray = new ByteArray();"),
        decoder.index("for (var i:int = 0; i < POWER_SHOTS_PIXELS.length; ++i)"),
        base64_close,
        decoder.index("if (bytes.length != 20648)"),
        decoder.index("bytes.position = 0; bytes.uncompress();"),
        decoder.index("if (bytes.length != 90000)"),
        decoder.index("var pixels:ByteArray = new ByteArray();"),
        decoder.index("for (var pixel:int = 0; pixel < 90000; ++pixel)"),
        pixel_close,
        pixels_reset,
        bitmap_create,
        set_pixels,
        decoder.index("lessonPreview.bitmapData = bitmap;"),
        decoder.index("lessonPreviewState = 2;"),
        decoder.index("catch (error:Error) { lessonPreviewState = 3; lessonPreview.visible = false; }"),
    )
    assert pipeline == tuple(sorted(pipeline))

    manifest_path = ROOT / "native_ui" / "compiled" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    abc_path = ROOT / "native_ui" / "compiled" / "MctRootMenu.abc"
    abc_bytes = abc_path.read_bytes()
    assert manifest["source"] == "native_ui/menus/MctRootMenu.as"
    assert manifest["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert manifest["abc_sha256"] == hashlib.sha256(abc_bytes).hexdigest()
    assert manifest["abc_bytes"] == len(abc_bytes) == 62429
    assert len(abc_bytes) <= 65536
