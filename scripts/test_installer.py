"""Windows CI install/reinstall/uninstall check, using temporary paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from my_career_training.career import new_career, validate_career
from my_career_training.storage import Store, default_state

from smoke_package import run_smoke
from windows_shortcuts import desktop_folders, programs_folders, read_shortcut


def wait_for_uninstaller_log_release(path: Path, timeout: float = 30) -> None:
    """Inno's cleanup helper can outlive its launcher and retain the log handle.

    Removing the log successfully establishes that its delete-sharing lock has
    gone away. Retry only Windows sharing/lock violations; never hide other
    permission problems or silently leave temporary files behind.
    """
    if not path.is_file():
        raise RuntimeError(f'The uninstaller did not create its requested log: {path}')
    deadline = time.monotonic() + timeout
    while True:
        try:
            path.unlink()
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (32, 33):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'Uninstaller cleanup still holds its log after {timeout}s: {path}') from error
            time.sleep(min(0.1, remaining))


def _owned_shortcuts(directories: list[Path], expected: Path) -> list[tuple[Path, dict[str, str]]]:
    expected = expected.resolve()
    owned = []
    for directory in directories:
        for path in directory.glob('*.lnk'):
            shortcut = read_shortcut(path)
            target = Path(shortcut['target'])
            if target.is_file() and os.path.samefile(target, expected):
                owned.append((path, shortcut))
    return owned


def check_shortcuts(group: str, install: Path) -> list[Path]:
    start_menu = _owned_shortcuts([root / group for root in programs_folders()],
                                  install / 'MyCareerTraining.exe')
    desktop = _owned_shortcuts(desktop_folders(), install / 'MyCareerTraining.exe')
    report = {'start_menu': [(str(path), item) for path, item in start_menu],
              'desktop': [(str(path), item) for path, item in desktop]}
    expected = install / 'MyCareerTraining.exe'
    start_modes = {item['arguments'] for _, item in start_menu}
    assert start_modes == {'--in-game', '--manage'}, f'Incorrect Start Menu shortcuts for {expected}: {report}'
    desktop_modes = {item['arguments'] for _, item in desktop}
    assert desktop_modes == {'--in-game'}, f'Incorrect desktop shortcut for {expected}: {report}'
    return [path for path, _ in (*start_menu, *desktop)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('installer', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='MCT install ') as temporary:
        root = Path(temporary)
        install = root / 'Installed app é 球'
        data = root / 'AppData saves é 球'
        profile = data / 'test-profile'
        with Store(profile) as store:
            state = default_state()
            state['career'] = new_career('Existing player é 球', seed=73)
            validate_career(state['career'])
            store.save(state)
        sentinel = profile / 'career.json'
        original = sentinel.read_bytes()
        # DisableProgramGroupPage=yes deliberately fixes the real product group;
        # Inno ignores /GROUP in this mode. This test runs on a disposable CI host.
        group = 'My Career Training'
        command = [str(args.installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                   '/NORESTART', '/SP-', '/TASKS=desktopicon', f'/DIR={install}',
                   f'/LOG={root / "install.log"}']
        subprocess.run(command, check=True, timeout=120)
        try:
            owned_shortcuts = set(check_shortcuts(group, install))
        except Exception:
            log = (root / 'install.log').read_text(encoding='utf-8-sig', errors='replace')
            print('\n'.join(log.splitlines()[-80:]))
            raise
        run_smoke(install, profile)
        assert sentinel.read_bytes() == original, 'Installed app smoke changed the existing career'
        # Reinstall the same version to exercise the repeat-install path.
        # This does not verify upgrading from an older release.
        subprocess.run(command, check=True, timeout=120)
        assert sentinel.read_bytes() == original, 'Reinstall changed player data'
        assert set(check_shortcuts(group, install)) == owned_shortcuts, 'Reinstall changed shortcut paths'
        uninstall_log = root / 'uninstall.log'
        subprocess.run([str(install / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                        '/NORESTART', f'/LOG={uninstall_log}'], check=True, timeout=120)
        wait_for_uninstaller_log_release(uninstall_log)
        assert not (install / 'MyCareerTraining.exe').exists(), 'Uninstall left the installed app'
        remaining_shortcuts = [str(path) for path in owned_shortcuts if path.exists()]
        assert not remaining_shortcuts, f'Uninstall left owned shortcuts behind: {remaining_shortcuts}'
        assert sentinel.read_bytes() == original, 'Uninstall changed player data'
    evidence_path = Path(__file__).resolve().parents[1] / 'build' / 'installer-test-receipt.json'
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps({
        'passed': True, 'installer_sha256': hashlib.sha256(args.installer.read_bytes()).hexdigest(),
        'checks': ['silent install', 'offline and management Start Menu shortcuts',
                   'offline desktop shortcut', 'frozen package smoke',
                   'same-version reinstall', 'uninstall',
                   'owned Start Menu and desktop shortcuts removed',
                   'existing career bytes preserved'],
        'upgrade_verified': False,
    }, indent=2) + '\n', encoding='utf-8')
    print('Silent installation, same-version reinstall and save-preserving uninstall passed; upgrade not tested')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
