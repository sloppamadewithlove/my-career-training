# REPRODUCIBILITY-HANDOFF-01

## Source reconstruction: closed

The published [frozen Python archive manifest](../evidence/frozen-python-archive-manifest.json) contains 55 Python source files, `pyproject.toml` and four license/notice files: 60 JSON records. Each stores exact UTF-8 text, including original newlines, and a SHA-256 over its reconstructed bytes. The source matches the pause and render manifests (55/55 each). The [source-reconstruction receipt](../evidence/reconstructed-probes-01.json) records restoring and hash-checking the initial 56 source/metadata records, running the diagnostics, then restoring the four notices without changing the tested source. Existing vendored Necto/Nexto observation helpers retain their separate license and notice. The archive is a frozen research candidate, not a deployed build or the canonical active checkout.

That closes the published-source gap for these Python probes: the original four diagnostic text copies plus the archived project files can now be staged from the published folder. It does not make the Python environment self-contained. The archive includes `pyproject.toml`, but not `uv.lock`, wheels, or interpreter binaries. The source provenance also remains distinct from the current or deployed product.

## Windows reconstruction and run commands

Start inside the checkout's `research to be applied` directory. Restore each archive record into a fresh directory under the checkout's separate `work` folder. Write decoded text as UTF-8 without adding a BOM, preserving any BOM character already present in the archived text. These PowerShell 7 commands reconstruct source only:

```powershell
$publication = (Get-Location).Path
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $publication -Parent) 'work\reconstructed-probes-01'))
if (Test-Path -LiteralPath $sourceRoot) { throw 'Choose a fresh reconstruction directory.' }
$manifest = Get-Content '.\evidence\frozen-python-archive-manifest.json' -Raw -Encoding utf8 | ConvertFrom-Json
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($entry in $manifest.files) {
    $record = Get-Content (Join-Path $publication $entry.archive) -Raw -Encoding utf8 | ConvertFrom-Json
    $bytes = $utf8.GetBytes([string]$record.utf8_text)
    if ($record.path -ne $entry.path -or $record.sha256 -ne $entry.sha256) { throw 'Archive identity mismatch.' }
    $destination = [System.IO.Path]::GetFullPath((Join-Path $sourceRoot $record.path))
    if (-not $destination.StartsWith($sourceRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path escapes destination.' }
    New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
    [System.IO.File]::WriteAllBytes($destination, $bytes)
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) { throw "Source hash mismatch: $($entry.path)" }
}
New-Item -ItemType Directory -Force -Path (Join-Path $sourceRoot 'tools') | Out-Null
Copy-Item '.\experiments\research_outcome_probe.py.txt' (Join-Path $sourceRoot 'tools\research_outcome_probe.py')
Copy-Item '.\experiments\research_import_probe.py.txt' (Join-Path $sourceRoot 'tools\research_import_probe.py')
Copy-Item '.\experiments\research_pause_clock_probe.py.txt' (Join-Path $sourceRoot 'tools\research_pause_clock_probe.py')
Copy-Item '.\experiments\research_render_packet_probe.py.txt' (Join-Path $sourceRoot 'tools\research_render_packet_probe.py')
Set-Location $sourceRoot
New-Item -ItemType Directory -Force -Path work | Out-Null
$env:QT_QPA_PLATFORM = 'offscreen'
```

Then use the same existing CPython 3.12.13 x64 environment for parity. The five recorded argument vectors were:

```powershell
python -B -X utf8 tools/research_outcome_probe.py --self-test
python -B -X utf8 tools/research_import_probe.py --work-root work --self-test
python -B -X utf8 tools/research_import_probe.py --work-root work
python -B -X utf8 tools/research_pause_clock_probe.py
python -B -X utf8 tools/research_render_packet_probe.py
```

The coordinator invoked the chosen project interpreter by its explicit private path, with the reconstructed root as working directory. The public receipt records that scope and argument vectors without publishing the personal path; the commands above assume `python` resolves to the chosen interpreter. The import probe’s `--self-test` run and full probe run are separate: only the latter exercises the four-case Backend import/storage/reload route. The source archive and runs are documented in the [reconstruction receipt](../evidence/reconstructed-probes-01.json) and [run receipt](../evidence/reconstructed-runs-01.json). Individual observed outputs are [outcome](../evidence/reconstructed-outcome.json), [import self-test](../evidence/reconstructed-import.json), [full import](../evidence/reconstructed-import-full.json), [pause clock](../evidence/reconstructed-pause-clock.json) and [render packet](../evidence/reconstructed-render-packet.json).

## Reconstructed run results

Root ran these probes from the restored public source between 13:31:52 and 13:31:59 UTC on 2026-10-27, then reran the full import probe at 13:35:20–13:35:21 UTC. Every recorded invocation exited 0 with zero stderr. Counts are per run and are not pooled with earlier results.

| Run | Evidence in reconstructed JSON | Scope limit |
| --- | --- | --- |
| Outcome | Six cases, 33 checks passed | Synthetic touch/phase frames; no game physics |
| Import self-test | Six named controls passed | Protocol/control self-test only |
| Import full | Four cases, 12 named checks passed | Fake process/dialog/transport and temporary store; no game launch or playback |
| Pause clock | Four cases; 11 preconditions and two controls passed | Synthetic packets and recordings; no game pause delivery |
| Render packet | Ten fixtures, 257 checks, zero failures | Client serializer pipeline with synthetic fixtures; no renderer server or game |

The full import rerun resolves the earlier self-test-only gap; its recorded checks and observations support the full-mode report. None of these runs proves live game behavior.

## Environment and dependency limits

The archived `pyproject.toml` (SHA-256 `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b`) requires Python `>=3.12,<3.13` and pins direct application packages. The local `uv.lock` (SHA-256 `8a255b76c2c7175647df67578381001074752319186ba298acf67c711b48ed22`) was not included in the published archive. The selected MCT interpreter currently reports CPython 3.12.13 x64 on Windows 11 build 10.0.26200; package metadata reports PySide6-Essentials/Shiboken6 6.12.0, psutil 7.2.2, RLBot 2.0.0b56, rlbot-flatbuffers 0.19.0, pygame-ce 2.5.6, NumPy 2.1.3 and Torch 2.6.0+cpu. This environment metadata is not stored in the run receipt; those runs reused the already-installed interpreter and dependencies without a clean install.

Minimum visible dependencies remain narrower than the full application environment: outcome and pause use standard-library/project imports; import uses PySide6-Essentials/Shiboken6 and psutil through its bridge imports; render uses RLBot and rlbot-flatbuffers, with psutil in RLBot’s dependency chain. There is no evidence these probes need the app’s Torch/NumPy/pygame stack. The [five-package requirements list](../experiments/requirements-diagnostics.txt) pins the versions observed here, and the [environment receipt](../evidence/reconstructed-environment-01.json) records their declared dependencies. Optional development/test extras are excluded. This is not a wheel-hash lock or proof of a fresh-environment installation; source JSON records alone do not pin interpreter or binary dependencies.

## Cosmetic restore build

The [probe source](../experiments/research_cosmetic_restore_probe.cpp.txt), [CMake file](../experiments/cosmetic_restore_probe_CMakeLists.txt), [header](../experiments/cosmetic_restore_probe_CosmeticOverrideState.h.txt) and [original run receipt](../evidence/cosmetic-restore-probe-01.json) make the small standalone C++ probe source-complete. The private CMake cache and logs identify CMake 3.31.6, Visual Studio 17 2022 Build Tools, v143/MSVC 14.44.35207 (compiler 19.44.35229.0), Windows SDK 10.0.26100.0, Windows 11 build 10.0.26200 AMD64, x64 Release, C++17 and one build job. The Release compiler used `/O2 /MD /std:c++17`; no third-party libraries were involved. Exact original shell lines were not retained; these equivalent commands are reconstructed from the cache and tlogs. Run from the staged input root with the listed toolchain and SDK installed:

```powershell
cmake -S . -B build-probe -G "Visual Studio 17 2022" -A x64
cmake --build build-probe --config Release --target research_cosmetic_restore_probe --parallel 1
.\build-probe\Release\research_cosmetic_restore_probe.exe
```

These commands assume `cmake` is on PATH, for example in the appropriate Visual Studio developer shell. In this machine's later prototype run it was not on PATH; the coordinator successfully used the installed Visual Studio CMake executable by its explicit path instead. A missing command is a launcher failure, not a failed C++ compilation.

## Comparing reruns

Keep stdout hashes as historical receipt identities, not rerun pass criteria. UUIDs, timestamps, and process-derived renderer group IDs may vary. Compare case outcomes, named checks, fixture counts and measured packet sizes while ignoring those dynamic identifiers. Do not treat successful offline reconstruction or synthetic checks as a deployed artifact or game acceptance result.
