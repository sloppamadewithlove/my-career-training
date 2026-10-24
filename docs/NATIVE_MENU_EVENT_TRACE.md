# Native menu event trace

Read-only decoder for six candidate menu functions. Button and tree clicks
record pre and post name scalars. `PushMenu` and `PopMenu` record either
phase, and only the first eight bytes of `MenuName`. That slice is not the
whole parameter block, and it does not prove a menu changed. `SetStringValue`
records either phase. `GetValue` records a post return string only. The
decoder does not consume the original action, replace a handler, or write a
string.

Root registers the SDK callbacks and checks the caller class before use. This
type never sees a caller pointer.

## What is already known

On executable SHA-256
`56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`,
BakkesMod 229, game build `261013.63066.530866`, a read-only host pass matched
the live menu stack to known SDK class tokens, including its self-metaclass.
`MenuStack` to shell at `+0x88` matched `GFxShell_TA`. The shell movie array at
`+0xc0` had count 1 and matched `GFxMoviePlayer_X`. Shell to data store at
`+0xd0` matched `GFxDataStore_X`. After the user left the start movie, the top
menu was `RootMenuMovie`. The original array check rejected its table header;
that receipt did not record the actual count or capacity, so the cause was
not established. A revised count-only check now records both numbers.
That pass performed no writes. It does not prove these function parameters.

A later read-only pass on that same executable, BakkesMod 229, and build
observed eight matched `ButtonTriggered` pre/post records. Their top menus
were `RootMenuMovie`, `GarageMainMenuMovie`, `RootMenuMovie`, and
`OptionsMenuMovie`. `SetStringValue` and `OnChildNodeClicked` were not called.
Candidate object headers matched, and the count-only table read reported
count 153 and capacity 196. That pass wrote nothing. The menu sequence and
the table count are observations, not a mutation grant or an ABI proof.
`GetValue` was not part of that pass.

## Candidate parameter packing

The shapes below are from MIT rlsdk commit
`99c4330f8e26e037f7f343dbe75b6dd5c08c4a01`
(`packages/steam/parameters/ProjectX.ts`, `packages/steam/parameters/TAGame.ts`,
`packages/steam/structs/GFxUI.ts`, and `packages/steam/enums/GFxUI.ts`). The license is
`plugin/licenses/rlsdk-LICENSE.MIT`. They are candidates, not a verified ABI.
Exports keep `verified_abi` and `action_consumption_verified` false, and
`parameter_layout` equal to `candidate`. The decoder never writes memory.
`stopToBridge` also accepts the host's write-attempt flag: a combined remap
experiment must set it, so its trace is not represented as a read-only session.
`native_mutations` conservatively flags any host write attempt, while
`host_parameter_write_attempted` and the host receipt describe the actual
attempt and verified restoration. A normal observation-only trace keeps both
flags false. Passing this reporting flag cannot authorize a write.

| Function | Record | Fields |
| --- | --- | --- |
| `Function ProjectX.GFxDataStore_X.SetStringValue` | 40 bytes | `Table` FName `+0`, `Row` int32 `+8`, `Column` FName `+0x0C`, `Value` FString `+0x18` (data uint64, count int32, max int32) |
| `Function TAGame.GFxData_MenuStack_TA.ButtonTriggered` | 8 bytes | `ButtonName` FName `+0` |
| `Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked` | 8 bytes | `ChildID` FName `+0` |
| `Function TAGame.GFxData_MenuStack_TA.PushMenu` | first 8 bytes of a longer block | `MenuName` FName `+0` only |
| `Function TAGame.GFxData_MenuStack_TA.PopMenu` | first 8 bytes of a longer block | `MenuName` FName `+0` only |
| `Function ProjectX.GFxDataStore_X.GetValue` | 64 bytes, post only | `Table` FName `+0`, `Row` int32 `+8`, `Column` FName `+0x0C`, `ReturnValue` `FASValue` `+0x18` size `0x28` |

FName is a little-endian index and number. Indexes are not passed to
`GetFNameByIndex`. A negative index or number is rejected. An index above
`1000000` is rejected; that cap is not a name-table check. `Row` must be in
`-1..4096`. Bytes between `Column` and the following value are ignored and are
not stored.

`GetValue` is decoded only for `Post`. Its `FASValue` is the pinned
`GFxUI.GFxMoviePlayer.ASValue`: `Type` is the byte at `+0` inside that struct,
so at parameter `+0x18`. The only accepted type is `4` (`AS_String`). The
FString `S` begins at `+0x10` inside `FASValue`, so its data pointer is at
parameter `+0x28`, its count at `+0x30`, and its max at `+0x34`. Boolean,
number, int, texture, and the remaining padding are not read and are not
exported. A type other than `4` drops the event, uses no slot, and does not
follow a pointer. A pre-phase `GetValue` buffer is refused before any read.

`PushMenu` and `PopMenu` follow the MIT layouts at `TAGame.ts` lines
57023–57039. `PushMenu` has `MenuName` at `+0` size 8 (`CPF_Parm`). `PrevMenu`
at `+8` and `LP` at `+0x10` are unmarked locals. `PopMenu` has `MenuName` at
`+0` size 8 (`CPF_Parm`) and optional `bClearingStack` at `+8` size 4
(`CPF_Parm`). `NameIndex` at `+0x0C` and `LP` at `+0x10` are locals. The
decoder reads `MenuName` and does not read, dereference, or export anything
after it. A buffer of eight or more bytes is accepted; the tail is ignored.
A shorter buffer is rejected. Eight bytes is the observed name, not the size
of the parameter block. A stored name does not prove that a menu was pushed
or popped.

The FString load is optional. Count must be `1..65`. Max must be at least
Count and at most 256. The data pointer must be 8-byte aligned, inside the
canonical user range used by the other read-only trials, and `pointer + count * 2`
must not wrap. A false or short read rejects that observation. There is no
string write and no `OverrideParams` entry.

UTF-16 content is kept only when, aside from one trailing NUL, it is an exact
case-insensitive match for one of: `PLAY`, `GARAGE`, `SETTINGS`, `TRAINING`,
`ROCKET PASS`, `ITEM SHOP`, `PROFILE`, `EXTRAS`, `QUIT GAME`, `EXIT GAME`,
`OPTIONS`, `PLAY ONLINE`, `CHALLENGES`, `ESPORTS`, `TOURNAMENTS`. The stored
text is that canonical label. With a reader, any other Unicode or ASCII is
dropped: the table, row, and column are not stored and the event uses no slot.
A null reader still records those scalars for a synthetic diagnostic and does
not load the string. Addresses and the caller's parameter bytes are not exported.

## Scope and limits

`start` requires `scopeValid`, a lowercase UUID session, and a short thread
token. Root may set `scopeValid` only after the current process, the
executable hash, offline state, and the lease all match. A missing, changed,
or invalid scope or thread erases the trace and blocks export. Those checks
authorize this diagnostic read only.

`SetStringValue` and `GetValue` share a cap of 192 text events. `PushMenu`
and `PopMenu` do not use that text cap. They share the 256-event total with
`ButtonTriggered` and `OnChildNodeClicked`, so at least 64 slots remain for
those non-text records. Further text is refused while the trace stays active
for them. The whole trace stops at 256 events or 60 seconds. An invalid kind
or phase is refused. `GetValue` pre is refused even though `Pre` is a valid
phase for the other functions, including push and pop. `clear` and a
new `start` reset both counts. `stopToBridge` writes
`native-menu-event-trace.json` under the bridge directory. `clear` drops the
in-memory trace and does not delete an older file.

## Host opt-in

`scripts/native_host_trial.py prepare --menu-event-trace` sets
`menu_event_trace` on the trial plan and the launched session. It also turns
on the object-header trial. It does not enable the menu-graph trial. The host
requests the six pre/post hooks only when that session flag is set, the top
menu is `RootMenuMovie`, and the object-header candidate matched. The load
receipt reports `hooks_requested`. The SDK does not prove that a requested
hook was installed or that it owns the call, so hook ownership stays
unverified. The callbacks only observe. They require the same thread that
loaded the probe, and the receipt keeps `parameter_layout_verified` and
`action_consumption_verified` false. `GetValue` is separate from those six
hooks: root registers only its post callback, for
`Function ProjectX.GFxDataStore_X.GetValue`, after the caller class matches
`GFxDataStore_X`, and passes a 64-byte bounded read. This decoder does not
register that hook. `PushMenu` and `PopMenu` are decoded here and are not
part of those requests. Root owns any later hook wiring.

## What the fixture proves

`plugin/tests/native_menu_event_trace_tests.cpp` uses synthetic buffers. It
checks truncation, index and row bounds, string count and capacity, alignment,
wrapping ranges, a failed read, UTF-16 allowlisting, invalid kind and phase,
erasure when the session, thread, or scope changes, and both caps. Unlisted
text with a reader uses no slot, and filling the text cap still leaves room
for a button and a click. `PushMenu` and `PopMenu` pre and post records are
kept from an eight-byte name and from a longer frame whose tail is not
exported. A truncated name, a negative index or number, and an index above
`1000000` use no slot. Filling the text cap still accepts a push and a pop,
and those records do not make another text label fit. A `GetValue` post with
an allowlisted label is kept.
A non-string return, a string tag in any other byte, a pre-phase buffer, a
63-byte record, and private text use no slot. The number, texture, and padding
bytes in that return value are not read and do not appear in the export. A
private sentinel in a `SetStringValue` string and the ignored gap do not
appear either. `GetValue` shares the 192 text cap, so a full text cap still
accepts a later button and click.

The fixture does not show that the retail client uses this packing. The live
button observations above are separate from these synthetic buffers, and they
do not prove the `GetValue` return layout. A trace cannot replace the
original button, click, or value handler.
