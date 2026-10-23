"""Build portable archive and checksums from actual Windows build outputs."""
from __future__ import annotations

import hashlib
import json
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
    smoke = json.loads((ROOT / 'build/package-smoke-receipt.json').read_text(encoding='utf-8'))
    installation = json.loads((ROOT / 'build/installer-test-receipt.json').read_text(encoding='utf-8'))
    if not smoke.get('passed') or not installation.get('passed'):
        raise RuntimeError('Successful frozen package and installer test receipts are required')
    for name, digest in smoke['artifacts'].items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Package artifact changed after smoke test: {name}')
    if installation['installer_sha256'] != hashlib.sha256(installer.read_bytes()).hexdigest():
        raise RuntimeError('Installer changed after installation testing')
    archive = release / f'MyCareerTraining-{version}-windows-x64-portable'
    shutil.make_archive(str(archive), 'zip', root_dir=bundle.parent, base_dir=bundle.name)
    sources = release / f'MyCareerTraining-{version}-third-party-sources'
    shutil.make_archive(str(sources), 'zip', root_dir=ROOT / 'build', base_dir='upstream-sources')
    outputs = [installer, Path(str(archive) + '.zip'), Path(str(sources) + '.zip')]
    plugin_receipt = bundle / '_internal' / 'my_career_training' / 'runtime' / 'plugins' / 'plugin-build-receipt.json'
    receipt_output = release / 'plugin-build-receipt.json'
    shutil.copy2(plugin_receipt, receipt_output)
    outputs.append(receipt_output)
    hashes = {}
    checksums = []
    for path in outputs:
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        hashes[path.name] = {'sha256': digest, 'bytes': path.stat().st_size}
        checksums.append(f'{digest}  {path.name}\n')
    (release / 'SHA256SUMS.txt').write_text(''.join(checksums), encoding='utf-8')
    plugin_details = json.loads(plugin_receipt.read_text(encoding='utf-8'))
    (release / 'RELEASE_RECEIPT.json').write_text(json.dumps({
        'version': version, 'source_commit': plugin_details['source_commit'],
        'artifacts': hashes, 'plugin': plugin_details,
        'package_smoke': smoke, 'installation_test': installation,
        'verification': {'windows_package_smoke': 'passed', 'installer_upgrade_uninstall': 'passed',
                         'actual_rocket_league_gameplay': 'not verified by build'},
    }, indent=2) + '\n', encoding='utf-8')
    print('Created portable ZIP and SHA256SUMS.txt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
