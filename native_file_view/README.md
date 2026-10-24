# Native file view fixture

Offline Windows x64 experiment. It builds three test-only binaries:

- `MctNativeFileFixture.exe` opens a synthetic asset, then probes unrelated names and write, create, and delete access.
- `MctNativeFileView64.dll` detours `CreateFileW` for one canonical path and redirects a read-only open onto a private file.
- `mct_native_file_view_tests.exe` launches only the adjacent fixture. It cannot attach to a process that is already running.

The DLL is mapped by `DetourCreateProcessWithDllExW` before the fixture entry point. Scope is a fixed in-memory payload from that launcher. There is no installed runtime and no general injection tool.

`production_ready: false`

`game_verified: false`

Detours 4.0.1 is pinned to commit `e4bfd6b03e50de46b47abfbd1e46b384f0c5f833`. See `NOTICE` for the dependency license. Microsoft Research Detours is not a supported product guarantee for this experiment.

Configure and build from the repository root with the installed MSVC tools. Point the archive override at the pinned local tarball when the machine should not download it:

```
cmake -S native_file_view -B build/native-file-view -G "Visual Studio 17 2022" -A x64 -DMCT_DETOURS_SOURCE_ARCHIVE=C:/path/to/detours-v4.0.1.tar.gz
cmake --build build/native-file-view --config Release
ctest --test-dir build/native-file-view -C Release --output-on-failure
```

What the local tests can and cannot show is recorded in `docs/NATIVE_FILE_VIEW.md`.
