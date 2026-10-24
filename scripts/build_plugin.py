"""Compile the pinned in-game plugin with MSVC and stage a verifiable receipt.

This checks the native build artifact, not Rocket League compatibility or gameplay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from plugin_artifact import inspect_plugin

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if os.name != 'nt':
        raise RuntimeError('Build the in-game DLL on Windows with the MSVC x64 toolchain')
    build = ROOT / 'build' / 'plugin'
    # A developer may have reused this CMake cache for a native experiment.
    # Release staging must explicitly reset both development switches.
    subprocess.run(['cmake', '-S', str(ROOT / 'plugin'), '-B', str(build), '-A', 'x64',
                    '-DMCT_ENABLE_NATIVE_MOVIE_TRIAL=OFF', '-DMCT_BUILD_HOST_PROBE=OFF'], check=True)
    subprocess.run(['cmake', '--build', str(build), '--config', 'Release', '--parallel', '2'], check=True)
    subprocess.run(['ctest', '--test-dir', str(build), '-C', 'Release', '--output-on-failure'], check=True)
    compiled = build / 'Release' / 'MyCareerTraining.dll'
    details = inspect_plugin(compiled)
    destination = ROOT / 'runtime' / 'plugins'
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(compiled, destination / compiled.name)
    dependencies = json.loads((ROOT / 'plugin' / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    shutil.copytree(ROOT / 'plugin' / 'licenses', ROOT / 'packaging/licenses/in-game-plugin', dirs_exist_ok=True)
    sources = ROOT / 'build/upstream-sources'
    sources.mkdir(parents=True, exist_ok=True)
    source_archives = []
    # SDK is fetched for compilation only; no source redistribution grant was found.
    # Ship the separately MIT-licensed ImGui sources and our plugin instead.
    for component, source in (('imgui-bakkesmod', build / 'sdk-imgui/imgui'),
                              ('nlohmann-json', build / '_deps/mct_json-src'),
                              ('my-career-training-plugin', ROOT / 'plugin')):
        if not source.is_dir():
            raise RuntimeError(f'Missing compiled plugin source dependency: {source}')
        archive = Path(shutil.make_archive(str(sources / component), 'zip', root_dir=source))
        source_archives.append({'component': component, 'archive': archive.name,
                                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
    (sources / 'PLUGIN_SOURCE_MANIFEST.json').write_text(
        json.dumps(source_archives, indent=2) + '\n', encoding='utf-8')
    source_files = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / 'plugin').rglob('*')) if path.is_file()
    }
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    receipt = {
        'protocol': 1, 'artifact': compiled.name, 'source_commit': commit,
        'source_files': source_files, 'dependencies': dependencies, 'source_archives': source_archives,
        'sha256': hashlib.sha256(compiled.read_bytes()).hexdigest(),
        'native': details, 'configuration': 'Release', 'architecture': 'x64',
        'gameplay_verified': False, 'native_movie_trial': False, 'native_host_probe': False,
    }
    (destination / 'plugin-build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'Compiled {compiled.name}; AMD64 DLL and required exports verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
