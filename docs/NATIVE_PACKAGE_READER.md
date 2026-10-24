# Native package reader

Development-only reader for one cooked menu package. It lives in
`scripts/native_package_reader.py` and is not imported by the application.
It does not launch a game, load a runtime, write a package, or write a movie.
Tests build synthetic files in a temporary directory. They do not open an
installed game package.

`MovieBytes.data` is the RawData byte string kept in process memory. Do not
write it out or redistribute it. The metadata dictionary is the only
JSON-serializable movie result.

## API

```python
inspect_menu_package(path, decrypt_header=None) -> dict
read_movie_bytes(path, exact_export_name, decrypt_header=None) -> MovieBytes
decrypt_aes256_ecb_cng(ciphertext, key) -> bytes  # Windows CNG, explicit key
```

`decrypt_header` is an optional `bytes -> bytes` callable. It receives only
the aligned header region and must return bytes of that same length. There is
no output path and no network source. A key is never embedded, searched for,
or fetched. `decrypt_aes256_ecb_cng` is a separate Windows helper: pass it an
explicit 32-byte key and bind that key in your own callable if you want CNG
to supply `decrypt_header`.

`inspect_menu_package` returns versions, counts, names, imports, exports,
compression-chunk spans, SwfMovie export identities, and capability flags.
It does not return the folder string, property values, or movie bytes.

`read_movie_bytes` matches `exact_export_name` exactly and requires the one
matching export to be a `SwfMovie`. Metadata keys are only:

| Key | Meaning |
| --- | --- |
| `export_name` | Export name |
| `class` | `SwfMovie` |
| `serial_offset` | Logical serial span start |
| `serial_size` | Logical serial span length |
| `raw_length` | RawData byte length |
| `sha256` | SHA-256 of those RawData bytes |
| `signature` | `GFX`, `FWS`, `CFX`, or `CWS` |

## Limits

| Bound | Maximum |
| --- | --- |
| File | 64 MiB |
| Header | 4 MiB |
| Names, imports, exports | 65536 each |
| String | 1024 code units, including the terminator |
| Export and RawData | 16 MiB |
| Logical stream | 256 MiB |
| Chunks | 4096 |
| One chunk, compressed or plain | 16 MiB |
| Block size | Power of two from 4 KiB through 4 MiB |

The measured menu block size is 131072. Version must be 868. Licensee must
be 32 or 34. Package flag `0x800` (full CTR) is refused. The file must be a
regular file: symbolic links and reparse points are refused. The size and
file identity are checked at open and again before a result is returned.

## Header and encryption

Little-endian fields: magic `0x9E2A83C1`, version, licensee, header size,
folder string, flags, then name count/offset, export count/offset, import
count/offset, and depends offset. Table bytes are ordered names, imports,
exports, depends. Each table must fill its declared span exactly.

Positive strings are strict ASCII. Negative strings are strict UTF-16-LE.
The terminator is required, and an interior terminator is refused.

The encrypted region starts at the name offset and contains
`floor((headerSize - nameOffset) / 16)` AES blocks. Bytes after that aligned
region stay as stored and are not a supported table. A required table that
extends into that tail is refused. Plaintext is tried first. The callable is
used only when that strict parse fails.

Licensee 34 chunk records are 36 bytes: uncompressed offset and size,
compressed offset and size, and a 12-byte extension. The extension is present
even when flag `0x800` is clear, and any nonzero byte is refused. Licensee
32 records are 24 bytes and have no extension. Chunks must be contiguous in
the logical stream from the depends offset and contiguous in the file from
the header size through EOF.

## Chunks and SwfMovie

A chunk frame is magic, block size, compressed total, uncompressed total,
then one compressed/plain size pair per block, then zlib streams (RFC 1950).
Totals and positive bounds are checked for every chunk. zlib is decoded only
for blocks that overlap the selected export, with a max output of
`expected + 1`. The output length must match, the stream must end, and there
must be no unconsumed input. A zero unused tail is allowed; any other unused
byte is refused.

The SwfMovie serial starts with a net index and UE3 property tags. `None`
ends the list. `StructProperty` and `ByteProperty` carry an extra name.
`BoolProperty` carries an extra byte. Other known simple types contribute
only their declared payload. An unknown type is refused. `RawData` must be
one `ArrayProperty` whose count equals the payload length minus 4. The movie
signature must be `GFX`, `FWS`, `CFX`, or `CWS` with a valid 8-byte header.
Uncompressed `GFX` and `FWS` lengths must equal the RawData length. Compressed
`CFX` and `CWS` declared uncompressed lengths must be between 8 bytes and
16 MiB. Compressed bytes can be longer than their uncompressed form. This
reader does not decompress SWF payloads.

## Capabilities

`loads_runtime`, `writes_assets`, `network_fetch`, `redistribute_payload`,
and `production_ready` are false. A passing synthetic test does not certify
a retail package, a menu change, or a right to redistribute bytes.

## Recorded shape

Root previously recorded one menu package at 3418271 bytes, version 868,
licensee 34, flags `0x0288028D`, header 30909, 163 names, 10 imports, 113
exports, and a 36-byte chunk stride whose extension was zero. This reader is
shaped for that record. Root then ran this reader against the owned package
with an explicit in-memory decryptor. The inventory matched, and the selected
MainMenu movie was 1136465 bytes with SHA-256
`57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`,
matching the earlier independent extraction. The package SHA-256 before and
after was `d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65`.
No game process was launched and no installed asset was written. This is reader
validation, not proof that a modified movie can be loaded or used in the game.

The focused suite passed 26 tests, with one symlink-creation test skipped by
the local Windows privilege policy. The Windows CNG known-answer test passed.
Same-size in-place changes are detected through last-write time; POSIX also
checks change time. This is a consistency check, not an atomic snapshot against
an adversarial writer that restores timestamps.
