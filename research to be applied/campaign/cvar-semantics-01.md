# CVAR-SEMANTICS-01: range helpers, wrapper forwarding, and limits

## Finding

The pinned SDK source contains helpers that parse parenthesized numeric ranges and randomize values. That does **not** establish that `CVarWrapper::getIntValue()` or `getFloatValue()` use those helpers. The pinned header declares the getters out of line; the installed `pluginsdk.dll` wrapper bodies forward to `BMCore::GetIntValue` and `BMCore::GetFloatValue` in the installed core DLL. Ghidra could not finish importing that larger core DLL within its 330-second startup deadline, so the host-side range-string semantics remain unknown.

For RedirectPlugin, this means the tuple-looking defaults for shot speed and X/Y offset are not proven to produce randomized getter values. Its explicit Z-offset `random()` call **is** tied to the pinned inline SDK helper. The callback reads the X/Y cvar twice; whether the two reads return equal or different values is unknown.

## Exact source and artifact identities

The project pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` with source archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`, from `work/reviewed-training/plugin/CMakeLists.txt:26-28`. The local extracted SDK headers are under `work/reviewed-training/build/native-candidate/plugin/_deps/mct_sdk-src/include`.

| Inspected source | Bytes | SHA-256 |
|---|---:|---|
| `work/reviewed-training/plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| `include/utils/parser.h` | 20,086 | `3981580267050dc31452c5a1f909b55284fab92f24c3ca25ab953fe8e4c3d23f` |
| `include/bakkesmod/wrappers/cvarwrapper.h` | 1,698 | `e3bcc15c8b32cc8ade1c25352a53097d57c17ecc7822e6b36644da657b1d876d` |
| `include/bakkesmod/wrappers/Engine/ActorWrapper.h` | 8,547 | `28a79a7b922c38be5656ba29ac2613cd920bcb8efde04bdb4dce1380dfd510a3` |
| `include/bakkesmod/wrappers/GameObject/RBActorWrapper.h` | 2,625 | `a6e02647969966561927c99d9ddade55d336e5d415d8e0cc73275880965eec00` |
| `include/bakkesmod/wrappers/GameObject/BallWrapper.h` | 4,644 | `4d6e06cc0648890c9d09055606c6b4a619042eeecb98a47318fa1baca24aef18` |
| `work/research/bakkesmod-default-plugins/RedirectPlugin/redirectplugin.cpp` | 3,019 | `bb77172ef93626c931d976535269993e068524a22607a66813756260e8718afb` |

The separate installed SDK binaries are `pluginsdk.dll`, 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`, and `bakkesmod.dll`, 4,638,208 bytes, SHA-256 `1b3226b447606f5552396907e34655de099202f371441bd4ce09bb6c74f20e3e`. These artifact identities do not prove which binaries are loaded at runtime or that the installed binaries were built from the pinned source archive.

## What the pinned parser helper does

The pinned [`parser.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/utils/parser.h#L17-L23) defines two unrelated inline random helpers:

- Integer `random(min,max)` computes with `rand() % (max - min + 1) + min`, so the integer endpoints are included. Its modulo arithmetic can bias the distribution; the helper does not seed `rand()`.
- Float `random(min,max)` scales `rand()` by `RAND_MAX` into the supplied interval. The formula can reach the upper endpoint when `rand()` returns `RAND_MAX`; it is a discrete C library PRNG mapping, not a uniform-real-distribution guarantee. It does not reorder reversed bounds.

The helper `get_safe_int` recognizes text beginning with `(`, ending with `)`, and containing a comma. It parses the first two integer endpoints, swaps them if reversed, then calls the inclusive integer helper. Non-range text is parsed with `stoi`; invalid or out-of-range conversion returns zero. `get_safe_float` treats parenthesized text as comma-separated endpoint pairs: it selects a pair and randomizes between that pair with the float helper; non-range text goes through `atof`; conversion exceptions return zero. The separate `get_safe_float_range` helper also handles one floating-point pair, but `get_safe_float` instead calls `get_safe_float_range_exclude`.

The matching [`CVarWrapper` header](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/cvarwrapper.h#L10-L25) places `getIntValue` and `getFloatValue` behind the imported PIMPL class. It declares the API but contains no conversion or range logic.

The pinned RedirectPlugin source includes `utils/parser.h`, but its notifier uses `getIntValue()` for `redirect_shot_speed` and `redirect_pass_offset` at lines 34–46; it does not call `get_safe_int` or `get_safe_float`. It separately calls `random(offset_z / 3, offset_z)` at line 47. Since `offset_z` is a float, this selects the float overload from the included helper. The notifier obtains X and Y from two separate reads of the same cvar. The core getter’s parsing behavior, and therefore any randomization or relation between those reads, cannot be derived from the helper alone. See the pinned [RedirectPlugin source](https://github.com/bakkesmodorg/BakkesMod2-Plugins/blob/f412cd66ce0735be4aeb21ca41325337eb959aa0/RedirectPlugin/redirectplugin.cpp#L10-L58).

## Installed wrapper evidence and unresolved core body

REA inspected the installed `pluginsdk.dll` with Ghidra 12.1.4:

- `CVarWrapper::getIntValue` at `0x18007b2a0` forwards to the imported `BMCore::GetIntValue` and returns the result. It contains no visible conversion or range logic. Dossier `ev_caa2cdec3784ca85aa2b670841ce037bdc7a86f798b7e565263eb677f8cfb17c`; selected pseudocode view `ev_f136a6847f12912bc371947d7f46ce2f1b022dbccc3a828c841fa4307f727170`.
- `CVarWrapper::getFloatValue` at `0x18007b2b0` forwards to `BMCore::GetFloatValue`. Dossier `ev_3b8513d5528008a853a95bb05cba6665fa4e23377002b8e305e155375775873f`.
- The core’s complete PE export inventory contains `?GetIntValue@BMCore@@YAHPEAX@Z` at `0x180120d70` and `?GetFloatValue@BMCore@@YAMPEAX@Z` at `0x180120d80`. Export-table Evidence: `ev_d8abfbbb4c203a8c00c064f8839c9c13ab2c93d5d9fd25b3d497653b876fea9a`; selected export page: `ev_015497fcbbed8825e5b9886201d1416fd9a66ad5ae785de530e8293fbf30874d`.
- An address-focused Ghidra analysis of the first core getter timed out while importing/analyzing the core DLL at 330,000 ms. REA reported incomplete output, no confirmed out-of-memory condition, and cleanup complete. This is **provider incompleteness**, not evidence that either function or parser is absent. The core bodies were not resolved.

## Stop and angular velocity wrappers

The pinned [`ActorWrapper` header](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/Engine/ActorWrapper.h#L21-L23) declares `void Stop()` and `void SetAngularVelocity(const Vector v, bool addToCurrent)`. `BallWrapper` derives from `RBActorWrapper`, which derives from `ActorWrapper`, so `BallWrapper` inherits these methods ([RBActorWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/RBActorWrapper.h#L7-L9), [BallWrapper](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/BallWrapper.h#L11-L13)).

In the installed `pluginsdk.dll`, the recovered `ActorWrapper::Stop` body writes actor-backed fields and contains an indirect dispatch path associated with the engine routine `Engine.PrimitiveComponent.PutRigidBodyToSleep`. Evidence `ev_dc2fcbfdcfbafdaa6c4cca3fb616e4deac5bb92d77a6dd16637b6b8d94c613ec`. This supports that the wrapper attempts an engine rigid-body sleep operation; the wrapper inspection does not prove how that affects the ball on subsequent simulation ticks.

The recovered `ActorWrapper::SetAngularVelocity` body forwards its vector and boolean argument to an internal routine and returns; it does not interpret the boolean itself. Evidence `ev_769022d828af9457ce5487497c3fb1b63fbd1fe62b8bc3ca9ed7342584c930ed`. The header names the argument `addToCurrent`, but there is no explanatory comment establishing host-side behavior. No gameplay call or effect was observed.

## Limitations and usable conclusion

- The public SDK header exposes declarations, not the host implementation of `CVarWrapper` getters.
- The inline SDK range helpers are usable evidence only where code actually calls them. They are not proof of core getter behavior.
- Core behavior hypotheses such as sampling a range once when a value is set, re-sampling on each getter call, parsing tuple text directly, or clamping to a registered range remain unverified. The RedirectPlugin defaults do not distinguish these possibilities.
- RedirectPlugin’s range-looking defaults and its two reads of the offset cvar do not establish a randomized value or equality/correlation between the returned X and Y values.
- No plugin or game was loaded, no CVar was queried at runtime, and no ball or actor operation was executed.

Detailed source identities and compact Evidence references are retained in a private research receipt; the relevant hashes and conclusions are reproduced above.
