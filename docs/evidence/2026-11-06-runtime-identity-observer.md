# Updated-game identity observer candidate

Base: `9ee0c3333686be74afdd5de0e24cde2932b1af61`. Development-only, no live
execution or compatibility acceptance. Normal MCT/launcher pins remain unchanged.

## Evidence and scope

Steam's local update record identifies build 26349479 after the last accepted
old-game session. The updated executable is 39,729,664 bytes, SHA-256
`bcfb323316bc9f4e44cc1dc761e47a55d5529ebdb42ed14217361cda51a6bd1c`.
Its embedded `261031.63733.533021` string is a runtime identity hypothesis.
The three pinned menu packages are unchanged. Installed Bakkes core 229 and
relevant SDK headers match the previously inspected versions. A fresh official
[updater response](https://updater.bakkesmod.com/updater/229) lists both Steam
25914621 and 26349479, while the
[official release](https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/tag/2.0.78)
identifies RL2.78/BM229. These establish support metadata, not MCT compatibility.

The normal Steam/Bakkes-only observation was inconclusive: it did not establish
the intended RLBot invocation or a runtime Psy build ID. This candidate provides
a smaller next observation than enabling the full MCT lifecycle on unknown code.

## What actually executes

`MCTRuntimeIdentityObserver` is a separate, default-OFF CMake DLL target. It has
one `onLoad()` and an empty `onUnload()`. It does not construct MyCareerTraining,
NativeMovieHost or a file-view redirect. There is no tick, notifier, hook,
drawable, timer, input, actor/clock/cosmetic setter, engine command or UI action.
Normal Bakkes plugin loading still executes the host loader and dependency code;
this is not a promise that an entire game session or another plugin is read-only.

Before its explicit SDK getter calls, OS checks require the exact new executable
hash/size, exact loaded Bakkes core and SDK file hashes, current PID and creation
FILETIME, the project's complete fixed four-argument RLBot invocation, and a
fresh operator-issued nonce lease of at most 30 seconds. Held file handles deny
write/delete while their identities are used. Reparse paths and malformed,
duplicate, nested or oversized requests are refused. No file or SDK log is
written for an invalid request.

The shared tested runner then calls only GetBakkesModVersion, GetPsyBuildID,
IsInOnlineGame and IsInReplay, in that order, checking lease freshness between
calls. A version/build mismatch prevents remaining getters. Unexpected build
text is bounded and filtered. It writes at most one create-new private JSON
journal under the request directory, never overwriting evidence. A partial
write is inconclusive. No callbacks outlive `onLoad()` and unload acquires no
new resources or game effects.

Even a matching observation keeps compatibility_verified, readiness_verified
and eac_off_verified false. The fixed invocation and a momentary offline getter
do not establish anti-cheat state. Nothing changes anti-cheat, injector settings,
normal production pins, or the old supported profile.

## Operator handoff after independent review

Do not launch or load from this observer itself. The sole tester must establish
the owned protected normal offline/RLBot session, retain original profile/plugin
baselines, and ensure ordinary MCT is not loaded. This DLL has no install or
autoload rule and is excluded from the normal candidate payload.

Before process creation, set `MCT_RUNTIME_IDENTITY_REQUEST` to an absolute private
ordinary path ending `native-runtime-identity-request.json`. Once the exact PID
and creation FILETIME are known, write a UTF-8 request with exactly these fields:
schema (integer 1), profile (`steam26349479-identity-only`), session (lowercase UUID),
pid (positive JSON integer), created_filetime (exact 18-digit decimal string),
issued_at and expires_at (Unix seconds, no more than 30 seconds apart).
Explicitly load only the reviewed observer while that lease is fresh.

Read `native-runtime-identity-observation.json` in that same directory and match
its nonce, PID, FILETIME and hashes. Missing/partial output is a failed observation.
A different actual build is a refusal, never permission to substitute a new pin.
Unload/close through the owned documented route and reconcile original files and
game profile writes. Review that evidence before proposing any MCT readiness or
menu-command trial. No source from this candidate enables those commands.

## Checks

MSVC 19.44 compiled the separate observer and its shared-runner test target.
The native CTest covers identity/lease refusal before any getter, exact argument
selection, crossed old/new identities, core/build mismatch ordering, expiry
between getters, online/replay refusal and filtered errors. Three Python checks
cover the actual adapter's SDK surface, absent background lifecycle, default-OFF
and packaging boundary, and preserved old launcher pins. Ruff passed.
With the existing candidate suite, 26 Python checks passed. The observer CTest
passed 1/1. The private compiled DLL is 156,160 bytes, SHA-256
`ab8f69f28a63975f291828092448125203cceef25d67b5ff5aa05085ddd86c00`.

PE inspection found exactly the four intended SDK imports; static inspection of
the installed identity getters shows forwarding to the core's version value and
cached build-string copy. That is source/static evidence, not a live observation.
No game package/asset, private request, binary, raw log or account-bearing data is
included in this commit. The observer must be independently reviewed before use.
