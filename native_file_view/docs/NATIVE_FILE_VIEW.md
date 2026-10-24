# Early private asset view

This directory is a Windows x64 offline fixture. It prepares a later owned-session file view. It is not that integration.

`production_ready: false`

`game_verified: false`

No live game process is started or modified. The launcher accepts only `MctNativeFileFixture.exe` sitting beside the test binary. It has no process-id argument and does not open an existing process to load a DLL.

## Mechanism

`DetourCreateProcessWithDllExW` creates the fixture suspended and inserts `MctNativeFileView64.dll` as the first in-memory import, so the loader maps it before the fixture entry point. The DLL exports `DetourFinishHelperProcess` at ordinal 1 and calls `DetourRestoreAfterWith` from `DllMain`. While the new process is still suspended, the launcher may call `DetourCopyPayloadToProcess` with GUID `{7B1E6A14-2C4F-4A8E-9D33-5F0B8C2E71A6}` and then resume the main thread.

The payload is `MctFileViewScopeV1`: magic, version, size, a reserved zero, and two fixed UTF-16 paths. There are no function pointers. `DllMain` reads it with `DetourFindPayloadEx`. A missing, truncated, or inconsistent payload leaves `CreateFileW` untouched.

`DllMain` does not log, open files, load libraries, start threads, or wait. The `CreateFileW` detour is attached there, which is the Detours sample pattern. The DLL stays loaded for the life of the fixture. Process exit does not detach the hook. Unloading it while a caller can still reach `CreateFileW` is not supported.

The hook compares one drive-letter path. Comparison is ordinal and case-insensitive after `GetFullPathNameW`, with `.` and `..` normalized. Inputs longer than 1023 characters are rejected before a terminator is written. The compare does not resolve reparse points, and it does not use wildcards, prefixes, or suffixes. A junction path is a different string, so it is not the configured target; `CreateFileW` then follows that junction and reads the original bytes. Only `OPEN_EXISTING` with read-only access is redirected. Write, delete, create, `WRITE_DAC`, `WRITE_OWNER`, `GENERIC_ALL`, `MAXIMUM_ALLOWED`, and other mutable requests fail with `ERROR_ACCESS_DENIED` and do not open either file. If the private open fails, that failure is returned and the original path is not opened.

The launcher rejects UNC paths, device paths, reparse points, directories, and an original/private pair that canonicalizes to one path or one file id. It repeats the file and identity checks when copying a payload, including a scope filled in by the caller, so a hard link or junction alias is not copied. A missing private file remains a valid payload and does not fall back to the original. The synthetic files are marked read-only and held open against replacement. The DLL path must fit Detours' ANSI `StringCchLengthA` limit of 4095 bytes and round-trip through the system ANSI code page, because `DetourCreateProcessWithDllExW` takes the DLL path as `LPCSTR`.

`DetourCreateProcessWithDllExW` forwards the startup information and creation flags to `CreateProcessW`. The launcher uses `STARTUPINFOEXW` with `EXTENDED_STARTUPINFO_PRESENT` and a handle list containing only the NUL input and the receipt-pipe writer. An inheritable event created beside that list is not passed to the fixture. There is no callback into the desktop app.

## Dependency

Microsoft Research Detours 4.0.1, commit `e4bfd6b03e50de46b47abfbd1e46b384f0c5f833`, MIT license, built static from the upstream sources. The official archive URL is `https://codeload.github.com/microsoft/Detours/tar.gz/e4bfd6b03e50de46b47abfbd1e46b384f0c5f833` with SHA-256 `d24f5dd1f977c33301ebd9f3be064e938a7908954df15b31235c9ca6691cb356`. `MCT_DETOURS_SOURCE_ARCHIVE` overrides that URL for an offline configure and still checks the hash. Detours is a research library, not a Microsoft support contract.

## Local verification

Recorded 24 October 2026 on this machine. Compiler MSVC 19.44.35229.0, Windows SDK 10.0.26100.0. Configure used the offline Detours archive override. The eleven headless fixture scenarios (`CREATE_NO_WINDOW`) passed against synthetic files in the process temporary directory. After fixing a numeric-handle reuse flaw in the test, the plain, missing-private, and ambient-handle scenarios each passed three consecutive runs.

Verified by those tests:

- `plain`: no DLL. The fixture's first `CreateFileW` reads the original bytes. `CREATE_NEW` returns `ERROR_FILE_EXISTS`. `MAXIMUM_ALLOWED` and `OPEN_ALWAYS` succeed. A write open is rejected by the read-only hold. An inheritable event left out of the handle list is not inherited. The original and private SHA-256 values match the manifest after the run.
- `redirect`: the DLL is loaded and the scope is active. The first open, a mixed-case path, and `..\Asset.bin` from a child directory all read the private bytes. `Asset.bin.bak` keeps its own bytes. The junction path is not the lexical target, and opening it reads the original bytes. Write, create, delete, `MAXIMUM_ALLOWED`, `GENERIC_ALL`, `WRITE_DAC`, and `OPEN_ALWAYS` on the configured path return `ERROR_ACCESS_DENIED`. A different scratch path is still created. The ambient event is not inherited. Both source hashes match the manifest.
- `missing-payload`: the DLL loads, the scope stays inactive, and the first open reads the original bytes.
- `invalid-payload`: a bad magic value and an 8-byte payload do the same. Those payloads still name two distinct real files; the fault is only the header.
- `private-missing`: the scope is active, the private file is absent, the first open returns `ERROR_FILE_NOT_FOUND` with no bytes, and the original hash is unchanged.
- `alias`: scope construction refuses same-path, case-only, `\\?\`, hard-link, junction, directory, UNC, device, and `\\?\UNC` inputs. A sibling file is accepted as a different path.
- `payload-revalidate`: a scope filled with a hard-link pair, and one filled with a junction path, are rejected when the launcher copies the payload. The owned process is not left running. A scope for two distinct files still redirects.
- `path-bounds`: canonicalization rejects 1023, 1024, 1025, and 4096 character inputs, and short `\\`, `\\?\`, and `\\.\` prefixes, without requiring those paths to exist. The test module path still canonicalizes.
- `dll-path`: the adjacent DLL path converts within the Detours ANSI limit. A 5000-character path does not.
- `timeout`: the created image is the adjacent fixture. The launcher stops that process at 1.5 seconds and closes its handles.
- `ambient-handles`: the launcher inspects the suspended child's corresponding handle with `DuplicateHandle` and compares the underlying object with [CompareObjectHandles](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-compareobjecthandles). A reused numeric value is not mistaken for the original event. Both plain and injected launches exclude it; deliberately adding the event to the inheritance list is detected before the child resumes.

Scratch cleanup deletes only a canonical `mct-nfv-*` directory directly under the process temporary directory, and only children of that directory.

The plain, redirected, and inactive-scope reads also query `GetFileSizeEx` and
`GetFileInformationByHandleEx(FileStandardInfo)` on their opened handles. Both
sizes match the bytes actually read, including the deliberately different
original/private lengths. A `GetFileAttributesExW` query of the original path
still reports the original size. This documents an API boundary: path metadata
is not redirected. These assertions passed with all eleven scenarios; they do
not establish which metadata calls Rocket League uses.

Not verified:

- Any installed game, its package reader, or a process that was already running.
- Other file-open APIs. Only `CreateFileW` is hooked; the two handle metadata
  queries above work on the genuine redirected handle without another hook.
- A callback from the hook into the career app.
- That lexical path matching follows junctions or covers every path a game binary might open.
