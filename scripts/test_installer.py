"""Windows CI installation/upgrade/uninstallation check, using temporary paths."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile
import time

from my_career_training.career import new_career, validate_career
from my_career_training.storage import Store, default_state

from smoke_package import run_smoke


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
        command = [str(args.installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                   '/NORESTART', '/SP-', '/NOICONS', '/TASKS=', f'/DIR={install}',
                   f'/LOG={root / "install.log"}']
        subprocess.run(command, check=True, timeout=120)
        run_smoke(install, profile)
        assert sentinel.read_bytes() == original, 'Installed app smoke changed the existing career'
        # Install the same version over itself: stable identity and upgrade paths.
        subprocess.run(command, check=True, timeout=120)
        assert sentinel.read_bytes() == original, 'Upgrade changed player data'
        uninstall_log = root / 'uninstall.log'
        subprocess.run([str(install / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                        '/NORESTART', f'/LOG={uninstall_log}'], check=True, timeout=120)
        wait_for_uninstaller_log_release(uninstall_log)
        assert not (install / 'MyCareerTraining.exe').exists(), 'Uninstall left the installed app'
        assert sentinel.read_bytes() == original, 'Uninstall changed player data'
    print('Silent installation, repeat installation and save-preserving uninstall passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
