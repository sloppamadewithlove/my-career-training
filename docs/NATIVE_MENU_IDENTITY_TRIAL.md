# Object-header candidate experiment

The optional `--object-header-trial` flag on `native_host_trial.py prepare`
extends the separate development host trial with **read-only candidate checks**.
It is not enabled by default, installed with the product, or a native menu
adapter. See [host trial and cleanup](NATIVE_HOST_TRIAL.md).

The field positions come from the MIT-licensed
[ObscuritySRL/rlsdk Core metadata](https://github.com/ObscuritySRL/rlsdk/blob/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01/packages/steam/offsets/Core.ts),
pinned to the September 2026 commit `99c4330f8e26e037f7f343dbe75b6dd5c08c4a01`.
Its copyright and license are retained in `plugin/licenses/rlsdk-LICENSE.MIT`.
That source describes a 0x60-byte UObject base header, Name at +0x48, and Class
at +0x50. Treating Name as two little-endian 32-bit values is an explicit
candidate interpretation of its eight-byte FName, not prior proof of this build.

After the normal exact-executable, owned-process, offline and lease checks,
the host requests the two fixed tokens `GFxData_MenuStack_TA` and `Class` from
BakkesMod and round-trips each through its SDK name lookup. It reads only the
SDK-returned menu-stack object's candidate base header, its candidate class's
header, and its candidate metaclass's header: at most three reads and 288 bytes.
Each read uses `ReadProcessMemory` on the current process after checking the
address, alignment, committed readable region and full byte count. It never
passes an integer obtained from candidate memory into the SDK name resolver.

The checks compare the candidate class name to the known menu-stack token and
the candidate metaclass name to `Class`, including the proposed self-metaclass
relationship. Aliases and unreadable or mismatched records stop the experiment.
The result contains booleans and bounded reason codes, not addresses or arbitrary
memory/string dumps. No object is retained after this synchronous observation.

A match is corroboration of these three candidate headers only. Object-table
membership, object lifetime, superclass/property layout, native function
signatures, visible button ownership, label updates and action consumption are
all still unverified. The result always reports `layout_verified_for_mutation`
and `native_mutations` as false. There is no write or function-invocation API.

The pure C++ tests use synthetic memory to exercise rejection and read bounds.
Passing them does not count as a real-game observation.
