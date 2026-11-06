# Fixed private identity-observer rendezvous

Base: `d64d5dd0302e16c29f7d3738e887fb4468a96747`. Development-only source
candidate; not loaded or live accepted. Normal MCT, launcher identities, build
defaults and candidate packaging are unchanged.

## Reason and scope

The previous observer discovers its request through an inherited environment
variable. A game started by an already-running Steam process does not inherit
new variables from the operator's shell. This candidate replaces only discovery;
it does not restart Steam, change authentication/launch settings or launch/load
anything. It neither changes nor establishes anti-cheat state.

The DLL resolves Local AppData using `SHGetKnownFolderPath` and its own process
token, with `KF_FLAG_DONT_VERIFY` and no create flag. It reads exactly:

`MyCareerTraining/Development/RuntimeIdentity/<PID>-<creation-FILETIME>/native-runtime-identity-request.json`

under that known folder. Neither `LOCALAPPDATA`, `TEMP`, the former request
environment variable nor JSON can select another directory. There is no search,
poll, alternate path or automatic directory creation.

## Private operator preparation

After establishing the permitted owned session, the operator prepares the fixed
RuntimeIdentity root and the exact PID/creation-FILETIME child directory. Each
must be owned by the current process user's SID and have a protected DACL with
exactly two inheritable full-control allow entries: that SID and LocalSystem.
Equivalent directory SDDL, with a placeholder rather than an account identifier:

`O:<current-user-SID>D:P(A;OICI;FA;;;<current-user-SID>)(A;OICI;FA;;;SY)`

The request file must likewise be owned by the current user and allow only that
user and LocalSystem full control, with ordinary file inheritance flags. A file
created normally under the protected process directory inherits this policy.
The operator must not weaken an existing directory's ACL, overwrite evidence or
remove unrelated files to make preparation succeed.

The seven-field request schema, random session nonce, maximum 30-second lease,
current PID/creation-FILETIME binding, complete fixed argv and exact executable,
Bakkes core and SDK identities remain the
[previous observer contract](2026-11-06-runtime-identity-observer.md). Write the
fresh request immediately before explicitly loading the independently reviewed
DLL. This is a different binary from the environment-based observer.

Protected-directory ownership and exact ACLs are checked on the retained opened
handles before lease I/O. The lease file's opened-handle owner/ACL is checked too.
The existing directory-chain, reparse, opened-path/volume and file-hash guards
remain. The output is the fixed sibling observation JSON, created once without
overwrite while the lease's directory chain remains pinned.

This trusts authority of the same Windows user, as the prior environment/file
design did; it does not authenticate an exact operator process or defend against
a malicious process already acting as that user. It cannot establish a permitted
session from argv alone. Actual supported without-EAC selection remains a separate
operator prerequisite. Missing/partial output is inconclusive, and even a matching
journal keeps compatibility, readiness and EAC verification false.

## Checks

MSVC 19.44 compiled the DLL and all three focused native test targets. All three
CTest cases passed, including the existing real Windows ancestor-junction swap
and held-directory tests. The new Windows case accepts actual protected owner/
ACL fixtures and inherited private request/journal files; it rejects wrong owner,
broad directory/file ACLs and an unprotected root. It also verifies pinned-root
rename refusal, create-new output, distinct PID/FILETIME paths and unchanged
discovery after poisoning both former request and Local AppData environment
variables. It resolves but never creates the real known-folder rendezvous.

The fixture initially lacked READ_CONTROL on its ACL-editing handle; adding that
right alongside WRITE_DAC allowed the rejection fixtures to be established. No
production check was weakened. The existing pure scope runner is unchanged.
The focused Python/candidate suite passed 27 checks; Ruff and the evidence privacy
scan passed. The private DLL is 165,888 bytes, SHA-256
`f0899f8de89068304404ed015bfd10a2afd58c13c90cc5fce390c6e341e356b8`.
PE imports retain exactly the four intended SDK getters; no callback or mutation
API was introduced. No private request, raw log, account SID, game asset or binary
is included in the source candidate.
