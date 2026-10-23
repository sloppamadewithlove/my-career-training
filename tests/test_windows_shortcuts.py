"""Exercise the real Unicode shell API before the expensive Windows build."""
import ctypes
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from windows_shortcuts import _call, _shell_link, programs_folders, read_shortcut  # noqa: E402


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
