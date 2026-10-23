"""Exercise the real Unicode shell API before the expensive Windows build."""
import ctypes
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from windows_shortcuts import _call, _shell_link, desktop_folders, programs_folders, read_shortcut  # noqa: E402
from test_installer import check_shortcuts  # noqa: E402


def test_installer_shortcut_check_includes_desktop_and_returns_owned_paths(tmp_path, monkeypatch):
    import test_installer

    install = tmp_path / 'Installed app'
    install.mkdir()
    executable = install / 'MyCareerTraining.exe'
    executable.write_bytes(b'not executed by this test')
    start_menu = tmp_path / 'Programs' / 'My Career Training'
    desktop = tmp_path / 'Desktop'
    start_menu.mkdir(parents=True)
    desktop.mkdir()
    links = {
        start_menu / 'My Career Training.lnk': {'target': str(executable), 'arguments': '--in-game'},
        start_menu / 'My Career Training - Setup and diagnostics.lnk': {
            'target': str(executable), 'arguments': '--manage'},
        desktop / 'My Career Training.lnk': {'target': str(executable), 'arguments': '--in-game'},
    }
    for path in links:
        path.touch()
    monkeypatch.setattr(test_installer, 'programs_folders', lambda: [start_menu.parent])
    monkeypatch.setattr(test_installer, 'desktop_folders', lambda: [desktop])
    monkeypatch.setattr(test_installer, 'read_shortcut', lambda path: links[path])

    assert set(check_shortcuts('My Career Training', install)) == set(links)


@pytest.mark.skipif(os.name != 'nt', reason='Windows native shell link regression')
def test_unicode_shortcut_target_and_arguments(tmp_path):
    target = tmp_path / 'Installed app é 球' / 'MyCareerTraining.exe'
    target.parent.mkdir()
    target.write_bytes(b'not executed by this test')
    shortcut = tmp_path / 'My Career 球.lnk'
    arguments = '--in-game --label "é 球"'
    # Create an actual link with the SDK Unicode setters, then independently
    # load it from disk through IPersistFile and verify every relevant field.
    with _shell_link() as (link, persist):
        _call(link, 20, (ctypes.c_wchar_p,), str(target))  # IShellLinkW::SetPath
        _call(link, 11, (ctypes.c_wchar_p,), arguments)  # SetArguments
        _call(persist, 6, (ctypes.c_wchar_p, ctypes.c_int), str(shortcut), 1)  # Save
    observed = read_shortcut(shortcut)
    assert Path(observed['target']).samefile(target)
    assert '球' in observed['target']
    assert observed['arguments'] == arguments
    assert programs_folders() and all(path.is_absolute() for path in programs_folders())
    assert desktop_folders() and all(path.is_absolute() for path in desktop_folders())
