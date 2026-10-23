"""Windows CI installation/upgrade/uninstallation check, using temporary paths."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile

from smoke_package import run_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('installer', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='MCT install ') as temporary:
        root = Path(temporary)
        install = root / 'Installed app é 球'
        data = root / 'AppData saves é 球'
        data.mkdir()
        sentinel = data / 'existing-player-save.json'
        original = b'{"existing_player_progress":"preserve"}'
        sentinel.write_bytes(original)
        command = [str(args.installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                   '/NORESTART', '/SP-', '/NOICONS', '/TASKS=', f'/DIR={install}',
                   f'/LOG={root / "install.log"}']
        subprocess.run(command, check=True, timeout=120)
        run_smoke(install, data / 'test-profile')
        # Install the same version over itself: stable identity and upgrade paths.
        subprocess.run(command, check=True, timeout=120)
        assert sentinel.read_bytes() == original, 'Upgrade changed player data'
        subprocess.run([str(install / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                        '/NORESTART', f'/LOG={root / "uninstall.log"}'], check=True, timeout=120)
        assert not (install / 'MyCareerTraining.exe').exists(), 'Uninstall left the installed app'
        assert sentinel.read_bytes() == original, 'Uninstall changed player data'
    print('Silent installation, repeat installation and save-preserving uninstall passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
