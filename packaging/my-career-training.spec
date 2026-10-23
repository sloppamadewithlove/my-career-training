# Build on Windows with the locked project environment.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
package = root / "src" / "my_career_training"
core = root / "runtime" / "RLBotServer.exe"
icon = package / "ui" / "icon.ico"
if not core.is_file():
    raise SystemExit("Run scripts/fetch_runtime.py before packaging")
if not icon.is_file():
    raise SystemExit("The original app icon is missing")
data = collect_data_files("my_career_training")
data += [(str(core), "my_career_training/runtime")]
data += [(str(root / "packaging" / "licenses"), "licenses")]
data += [(str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), ".")]
for name in ("rlbot", "rlbot-flatbuffers", "PySide6-Essentials", "shiboken6", "pygame-ce", "psutil"):
    data += copy_metadata(name)
a = Analysis(
    [str(root / "packaging" / "gui_entry.py")],
    pathex=[str(root / "src")], binaries=[], datas=data,
    hiddenimports=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2",
                   "PySide6.QtSvg", "pygame", "rlbot", "rlbot.flat"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2"], noarchive=False,
)
b = Analysis(
    [str(root / "packaging" / "worker_entry.py")],
    pathex=[str(root / "src")], binaries=[], datas=[], hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2"], noarchive=False,
)
gui = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True,
          name="MyCareerTraining", debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, icon=str(icon))
worker = EXE(PYZ(b.pure), b.scripts, [], exclude_binaries=True,
             name="MyCareerTrainingWorker", debug=False, bootloader_ignore_signals=False,
             strip=False, upx=False, console=True, icon=str(icon))
coll = COLLECT(gui, worker, a.binaries, a.datas, b.binaries, b.datas,
               strip=False, upx=False, name="MyCareerTraining")
