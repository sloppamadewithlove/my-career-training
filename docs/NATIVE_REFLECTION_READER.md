# Native reflection reader

This is a small read-only object-identity checker for one address supplied by
the caller. It is groundwork for discovering which native object owns a menu
control. It does not modify Rocket League, and a fixture pass is not a menu
change.

The type is header-only: `plugin/include/NativeReflectionReader.h`. The fixture
program is `plugin/tests/native_reflection_reader_tests.cpp`. No `.cpp` is
linked into the game plugin. The separate opt-in host trial is not part of
this reader and is left unchanged.

## Observed build, no descriptor

The observed Steam client is build `25914621`, file version `1.0.10897.0`,
BakkesMod `229`, executable SHA-256
`56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`.
No object layout has been verified for that executable. `readGame` returns
`layout_not_verified` for that hash and `descriptor_absent` for every other
hash. It does not read the supplied memory view.

Those four labels identify the build. They are not field offsets, a name
table, or permission to mutate.

## What a passing fixture proves

`readFixture` was given a synthetic 64-bit descriptor and a synthetic byte
image. For one candidate address it can return that object's name, the name of
the object at its class pointer, and the name of its nearest outer. The same
tests show the reader refusing the cases below without publishing a partial
name. Pointer width other than 8 bytes is refused. The fixture hash is not the
observed executable, and `layoutVerifiedOnGame` stays false.

## What it does not prove

- The retail client uses this record shape, or any shape copied from a
  generated SDK. Historical header positions are not embedded here and are not
  evidence for this build.
- A live menu object was found, a label can be changed, or an original action
  can be consumed.
- Memory was safe to write. There is no write function, no `ProcessEvent`
  call, and no detour.
- An overlay, a modal dialog, or a renamed control satisfies the native-menu
  requirement. Those are different mechanisms.

## Root integration seam

`NativeReflectionReader::readGame(executableSha256, memory, candidate)` is the
only game entry. Root records a verified layout inside that function, bound to
the full lowercase SHA-256, after an independent layout check. Until that
record exists, the function refuses.

Do not pass a descriptor, evidence string, class allowlist, or mutation flag
in from the UI, the bridge, or the host probe. `rejectCallerAuthority` refuses
those arguments. `readFixture` also refuses a descriptor that sets
`allowNativeMutation`, a non-empty `mutationAllowlist`, or any `evidence`
text, including the text `root-verified`. A caller-supplied label is not
verification.

The memory interface is `ReadOnlyBytes`: a base, a size, and a read of a
complete range. It has no write method. The reader does not scan the view for
objects. It touches the candidate, its class record, a bounded outer chain,
and the name entries those records index.

## Checks and output

Limits: 8-byte pointers, 48-byte names, 4 outer links, 6 records, 512 bytes,
4096 object indexes, 4096 name entries, 256-byte records. Names are one ASCII
identifier. Paths, mailbox text, and unterminated bytes are `bad_name` and are
not copied into the result. Only the nearest outer name is returned; farther
outers are walked so a cycle or a fifth link fails the whole observation.

| Reason | Refusal |
| --- | --- |
| `descriptor_absent` | `readGame` has no record for this hash |
| `layout_not_verified` | Observed executable, or a fixture bound to its hash |
| `caller_authority_rejected` | Mutation flag, allowlist, or evidence label |
| `pointer_width` | Not an 8-byte pointer |
| `bad_descriptor` | Malformed hash, counts, stride, or field placement |
| `ambiguous_layout` | Overlapping fields or a repeated object index |
| `overflow` | Address, view, or name-entry arithmetic wraps |
| `out_of_range` | A required byte is outside the view |
| `unaligned` | Object or followed pointer is not 8-byte aligned |
| `unreadable` | The view could not supply the complete record or name |
| `bad_pointer` | Candidate address is null |
| `missing_class` | Class pointer is null |
| `bad_object_index` / `bad_name_index` | Index is negative or outside the descriptor |
| `bad_name` | Empty, unterminated, or not a single identifier |
| `cycle` | Class or outer chain revisits an address |
| `byte_limit` / `chain_limit` | Byte cap or outer-link cap |

A success sets `validatedInFixture` and leaves `layoutVerifiedOnGame` false.
`reason` is `ok`. The strings are the three identity fields only.

## Tests

The fixture program is a C++17 `main` with no game, SDK, network, or package
dependency. Root owns CMake. The executable needs C++17 and this include
directory; it does not link the bridge or the plugin:

```cmake
add_executable(mct_native_reflection_tests tests/native_reflection_reader_tests.cpp)
target_include_directories(mct_native_reflection_tests PRIVATE include)
target_compile_features(mct_native_reflection_tests PRIVATE cxx_std_17)
add_test(NAME native_reflection_reader COMMAND mct_native_reflection_tests)
```

That target is registered in CMake. It does not attach the reader to the game
or lift the installer hold.
