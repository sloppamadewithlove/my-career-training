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
    print('Frozen UI load, headless contracts, worker pipes and runtime checksum passed')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path('dist/MyCareerTraining'))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='MCT package ') as temp:
        root = Path(temp)
        destination = root / 'My Career Training é 球'
        shutil.copytree(args.bundle.resolve(), destination)
        run_smoke(destination, root / 'Player data é 球')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
