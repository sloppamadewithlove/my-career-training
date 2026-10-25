# Native package rewrite

Pinned in-memory transform for one menu package. It lives in
`scripts/native_package_rewrite.py` and is staged for private menu preparation.
It does not launch a game, open an installed package, write a file, or fetch
a key. Tests build synthetic packages with `struct`. They do not inspect a
retail asset.

The function returns package bytes in process memory. It has no output path.
Writing those bytes into a game install is outside this tool. A successful
synthetic round trip does not show that a modified movie loads or plays.

## API

```python
replace_final_movie(
    package_bytes,
    replacement_movie,
    *,
    expected_package_sha256,
    expected_movie_sha256,
    export_name,
    decrypt_header=None,
    encrypt_header=None,
) -> RewrittenPackage

encrypt_aes256_ecb_cng(plaintext, key) -> bytes  # Windows CNG, explicit key
```

`RewrittenPackage.data` is the rewritten package. `RewrittenPackage.metadata`
is a small JSON object. There is no save method.

Both digests are 64-character lowercase hex. `expected_package_sha256` is the
SHA-256 of `package_bytes`. `expected_movie_sha256` is the SHA-256 of the
selected export's current RawData. Any other digest, including the same value
in uppercase, is refused before a rewrite is returned.

`decrypt_header` and `encrypt_header` are `bytes -> bytes` callables. They are
used only when the reader could not parse the header as plaintext. Each one
must return a buffer of the same length as the aligned header region.
`encrypt_aes256_ecb_cng` is a separate Windows helper. Pass it an explicit
32-byte key and bind that key in your own callable if you want CNG to supply
`encrypt_header`. The key is an argument only. Nothing here embeds, searches
for, or downloads a key. Parser fixtures can use any pure callback. They do
not need CNG.

## What is rewritten

`replace_movie` has the same arguments and result as `replace_final_movie`.
It supports a selected export that is not the entire last chunk: the updated
serial is appended to the last logical chunk, and only that export's offset
and size plus the last chunk sizes are changed. Every other export keeps its
offset, size, and bytes. Earlier compressed chunks and the existing prefix of
the final logical chunk remain unchanged. The old selected serial is retained
as unreferenced bytes. Overlapping exports, unsupported framing, trailing
physical bytes, and size-limit violations are rejected. This is the path used
for the pinned MidgameMenu and EndGameMenu exports.

The stricter `replace_final_movie` API remains unchanged for MainMenu. Its
requirements follow.

The source must pass the reader's summary, table, frame, export, and RawData
checks. This rewrite then requires all of the following:

- Version 868.
- Licensee 34, with the legacy 36-byte chunk record and a zero 12-byte extension.
- Package flag `0x800` (full CTR) absent.
- The named export is one `SwfMovie`.
- That export's logical offset and size are exactly the last chunk.
- The last chunk's compressed bytes end at EOF.
- No other positive-size export overlaps that logical span.
- Header-resident serial bytes do not cover the three patched integers.

The selected serial's RawData property is the only payload that changes. The
net index, every other property, the RawData name and type, its array index,
and the bytes after RawData stay as they were. The property length and the
array count are updated to the new movie.

The new movie must be uncompressed `GFX` or `FWS`, the same SWF version byte
as the source movie, at least 8 bytes, and at most 16 MiB. Its declared
length must equal its byte length. The movie bytes are stored as given.

This checks the UE3 container and the 8-byte SWF header. It does not parse
SWF tags, reject a changed tag set, or require a shared non-ABC menu
structure. Tag-level menu identity belongs in a separate tool.
`swf_tags_validated` is false.

The new serial is compressed as zlib (RFC 1950) in 131072-byte blocks. The
chunk frame is the UE3 header of four little-endian u32 values (magic, block
size, compressed total, uncompressed total), then one compressed-size and
plain-size pair per block, then the zlib payloads. Compressed total counts
the zlib payloads only.

Two integers in the last chunk record change: uncompressed size and compressed
size. One integer in the selected export record changes: serial size. Header
length, name bytes, import bytes, other export records, chunk offsets, the
clear prefix, the unaligned header tail, and every earlier chunk stay as they
were. Nothing is shifted to make room. The file ends at the new last chunk.

When the header was encrypted, the aligned region is
`header[nameOffset:nameOffset + floor((headerSize - nameOffset) / 16) * 16]`.
`encrypt_header` must return that many bytes. `decrypt_header` is then called
on that result and must reproduce the new plaintext region. The tail after
the aligned region is not passed to either callback. A plaintext source does
not call either callback.

The result is parsed again with the same reader limits. The replacement
RawData hash must match, other export serials must match, and non-final chunk
bytes must match. A result that fails those checks is not returned.

## Metadata

| Key | Meaning |
| --- | --- |
| `export_name` | Export name that was rewritten |
| `before_package_sha256` | SHA-256 of the source package |
| `after_package_sha256` | SHA-256 of `data` |
| `before_movie_sha256` | SHA-256 of the source RawData |
| `after_movie_sha256` | SHA-256 of the stored RawData |
| `before_package_length` | Source package length |
| `after_package_length` | Rewritten package length |
| `before_movie_length` | Source RawData length |
| `after_movie_length` | Stored RawData length |
| `before_serial_size` | Source serial length |
| `after_serial_size` | Rewritten serial length |
| `runtime_verified` | False |
| `production_ready` | False |
| `writes_files` | False |
| `swf_tags_validated` | False |

Folder strings, property values, and movie bytes are not copied into metadata.

## Limits

Limits come from `native_package_reader`.

| Bound | Maximum |
| --- | --- |
| Source and output file | 64 MiB |
| Header | 4 MiB, and the length is unchanged |
| Export, RawData, and replacement movie | 16 MiB |
| Replacement movie minimum | 8 bytes |
| One chunk, compressed or plain | 16 MiB |
| Logical stream | 256 MiB |
| Output block size | Exactly 131072 |
| CNG buffer | 4 MiB, a positive multiple of 16, with a 32-byte key |

The output block size is the reader's measured menu block size. Input chunks
may use any block size the reader accepts. Only the last chunk is recompressed,
and that recompression always uses 131072.

Licensee 32 remains readable by the reader and is refused here. The last-chunk
shape is the only layout this rewrite treats as safe to edit without moving
another object. That is a container decision. It is not evidence the game can
load the result.

## Reader coupling

`replace_final_movie` loads `scripts/native_package_reader.py` and uses these
private pieces:

- `_parse_summary`, `_decode_header`, `_validate_frames`
- `_select_export`, `_extract_serial`, `_parse_swf_movie`
- `_Reader`, `_fname`, `_KNOWN_PROPERTIES`, `_NAME_BEFORE_PAYLOAD`
- `_aligned_end`, `_call_decrypt`, `_frame_blocks`
- The reader's size caps, magic, measured block size, and `PackageReadError`

The RawData byte span is found with the same property walk as
`_parse_swf_movie`, then checked by calling `_parse_swf_movie` on the spliced
serial. Export serial size and the last chunk's size fields are located by
walking those tables with `_Reader`. This file does not keep a second copy of
the package grammar.

## Capabilities

Retained export serials have an aggregate 64 MiB budget, checked before any
serial extraction. This also bounds repeated work when different exports
alias the same logical bytes.

Root separately round-tripped the private seven-button candidate through the
owned package using explicit in-memory CNG callbacks. Re-reading the private
output produced identical candidate movie bytes. The installed source's
SHA-256 remained `d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65`.
No game was launched and no installed asset was written. This is container
validation, not an in-game loading result.

`loads_runtime`, `runtime_verified`, `writes_files`, `network_fetch`,
`redistribute_payload`, `production_ready`, and `swf_tags_validated` are false.
`encrypt_aes256_ecb_cng` exists so a later private candidate can supply its own
key to a callback. It does not make the rewrite production-ready.
