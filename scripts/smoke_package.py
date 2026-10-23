"""Exercise the frozen UI/worker bundle without starting a game or launcher."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from plugin_artifact import inspect_plugin

CORE_SHA256 = '454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1'


def run_smoke(bundle: Path, data: Path) -> None:
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       SDL_VIDEODRIVER='dummy')
    core = bundle / '_internal' / 'my_career_training' / 'runtime' / 'RLBotServer.exe'
    with core.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != CORE_SHA256:
            raise AssertionError('Bundled RLBot core failed checksum verification')
    if not (bundle / '_internal' / 'licenses' / 'RLBot-core-LICENSE.txt').is_file():
        raise AssertionError('Redistributed RLBot core license is missing')
    plugin_directory = bundle / '_internal' / 'my_career_training' / 'runtime' / 'plugins'
    plugin = plugin_directory / 'MyCareerTraining.dll'
    receipt = json.loads((plugin_directory / 'plugin-build-receipt.json').read_text(encoding='utf-8'))
    if receipt.get('sha256') != hashlib.sha256(plugin.read_bytes()).hexdigest():
        raise AssertionError('Bundled plugin differs from its native build receipt')
    if receipt.get('native') != inspect_plugin(plugin):
        raise AssertionError('Plugin native export/import inspection differs from its receipt')
    if not receipt.get('source_commit') or not receipt.get('dependencies') or not receipt.get('source_files'):
        raise AssertionError('Plugin source and pinned dependencies are missing from its receipt')
    if receipt.get('gameplay_verified') is not False:
        raise AssertionError('A native build must not claim gameplay verification')
    for flag in ('--self-test', '--smoke-test'):
        subprocess.run([str(bundle / 'MyCareerTraining.exe'), flag, '--data-dir', str(data)],
                       check=True, timeout=60, env=environment)
    subprocess.run([str(bundle / 'MyCareerTrainingWorker.exe'), '--self-test'],
                   check=True, timeout=60, env=environment)
    requests = [dict(id='package-ping', type='ping'), dict(id='package-stop', type='shutdown')]
    result = subprocess.run([str(bundle / 'MyCareerTrainingWorker.exe')],
                            input=''.join(json.dumps(item) + '\n' for item in requests),
                            capture_output=True, text=True, encoding='utf-8',
                            check=True, timeout=30, env=environment)
    messages = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert any(item.get('type') == 'ready' and item.get('protocol') == 1 for item in messages), messages
    assert any(item.get('id') == 'package-ping' and item.get('type') == 'pong'
               for item in messages), messages
    assert any(item.get('id') == 'package-stop' and item.get('type') == 'stopped'
               for item in messages), messages
    print('Frozen UI load, worker pipes, plugin PE exports/imports and runtime checksums passed; '
          'the plugin requires its BakkesMod game host and is not loaded by this smoke test')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path('dist/MyCareerTraining'))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='MCT package ') as temp:
        root = Path(temp)
        destination = root / 'My Career Training é 球'
        shutil.copytree(args.bundle.resolve(), destination)
        run_smoke(destination, root / 'Player data é 球')
    bundle = args.bundle.resolve()
    evidence = {
        'passed': True,
        'artifacts': {str(path.relative_to(bundle)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (bundle / 'MyCareerTraining.exe', bundle / 'MyCareerTrainingWorker.exe',
                                   bundle / '_internal/my_career_training/runtime/plugins/MyCareerTraining.dll')},
        'checks': ['frozen UI', 'worker pipes', 'RLBot checksum', 'plugin PE exports/imports'],
        'gameplay_verified': False,
    }
    evidence_path = Path(__file__).resolve().parents[1] / 'build' / 'package-smoke-receipt.json'
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
