"""Build portable archive and checksums from actual Windows build outputs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    bundle = ROOT / 'dist' / 'MyCareerTraining'
    for name in ('MyCareerTraining.exe', 'MyCareerTrainingWorker.exe'):
        if not (bundle / name).read_bytes().startswith(b'MZ'):
            raise RuntimeError(f'Missing actual Windows executable: {name}')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    installer = release / f'MyCareerTraining-{version}-windows-x64-setup.exe'
    if not installer.read_bytes().startswith(b'MZ'):
        raise RuntimeError('The actual compiled installer is required')
    archive = release / f'MyCareerTraining-{version}-windows-x64-portable'
    shutil.make_archive(str(archive), 'zip', root_dir=bundle.parent, base_dir=bundle.name)
    sources = release / f'MyCareerTraining-{version}-third-party-sources'
    shutil.make_archive(str(sources), 'zip', root_dir=ROOT / 'build', base_dir='upstream-sources')
    outputs = [installer, Path(str(archive) + '.zip'), Path(str(sources) + '.zip')]
    checksums = []
    for path in outputs:
        with path.open('rb') as stream:
            checksums.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}\n')
    (release / 'SHA256SUMS.txt').write_text(''.join(checksums), encoding='utf-8')
    print('Created portable ZIP and SHA256SUMS.txt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
