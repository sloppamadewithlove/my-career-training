"""Windows CI installation/upgrade/uninstallation check, using temporary paths."""
from __future__ import annotations

import argparse
import base64
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


def check_shortcuts(group: str, install: Path) -> None:
    environment = dict(os.environ, MCT_TEST_SHORTCUTGROUP=group)
    script = """
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $shell = New-Object -ComObject WScript.Shell
    $roots = @($shell.SpecialFolders.Item('Programs'), $shell.SpecialFolders.Item('AllUsersPrograms')) | Select-Object -Unique
    $directories = @($roots | ForEach-Object { Join-Path $_ $env:MCT_TEST_SHORTCUTGROUP })
    $links = @(foreach ($directory in $directories) {
        if (Test-Path -LiteralPath $directory) {
            Get-ChildItem -LiteralPath $directory -Filter *.lnk | ForEach-Object {
                $shortcut = $shell.CreateShortcut($_.FullName)
                @{target=$shortcut.TargetPath; arguments=$shortcut.Arguments}
            }
        }
    })
    ConvertTo-Json -InputObject @{directories=$directories; shortcuts=$links} -Depth 4 -Compress
    """
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, text=True, encoding='utf-8',
                            timeout=30, env=environment)
    if result.returncode:
        raise RuntimeError(f'Shortcut inspection failed: {result.stderr}')
    if not result.stdout.strip():
        raise AssertionError(f'Shortcut inspection returned no JSON: {result.stderr}')
    report = json.loads(result.stdout)
    expected = install / 'MyCareerTraining.exe'
    # Windows shell links may expand a short path (RUNNER~1) to its long name.
    # Compare the actual file identity rather than spelling or case alone.
    modes = {item['arguments'] for item in report['shortcuts']
             if Path(item['target']).is_file() and os.path.samefile(item['target'], expected)}
    assert modes == {'--in-game', '--manage'}, f'Incorrect launch shortcuts: {report}'


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
                   '/NORESTART', '/SP-', '/TASKS=', f'/DIR={install}',
                   f'/LOG={root / "install.log"}']
        subprocess.run(command, check=True, timeout=120)
        try:
            check_shortcuts(group, install)
        except Exception:
            log = (root / 'install.log').read_text(encoding='utf-8-sig', errors='replace')
            print('\n'.join(log.splitlines()[-80:]))
            raise
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
    evidence_path = Path(__file__).resolve().parents[1] / 'build' / 'installer-test-receipt.json'
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps({
        'passed': True, 'installer_sha256': hashlib.sha256(args.installer.read_bytes()).hexdigest(),
        'checks': ['silent install', 'offline and management shortcuts', 'frozen package smoke',
                   'repeat install', 'uninstall',
                   'existing career bytes preserved'],
    }, indent=2) + '\n', encoding='utf-8')
    print('Silent installation, repeat installation and save-preserving uninstall passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
