# Opt-in developer candidate. Output stays under build/native-candidate.
# It does not replace the normal dist/MyCareerTraining release bundle.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "scripts"))

import build_native_candidate as candidate
from package_qt_runtime import windows_qt_binaries

try:
    from PyInstaller.config import CONF
except ImportError as exc:
    raise SystemExit("PyInstaller is required to freeze the native candidate") from exc

distpath = root / "build" / "native-candidate" / "dist"
workpath = root / "build" / "native-candidate" / "pyinstaller"
if distpath == root / "dist" or workpath == root / "build":
    raise SystemExit("candidate PyInstaller paths collide with the normal release")
if candidate.BUNDLE_NAME == "MyCareerTraining":
    raise SystemExit("candidate bundle name collides with the normal release")
CONF["distpath"] = str(distpath)
CONF["workpath"] = str(workpath)

package = root / "src" / "my_career_training"
core = root / "runtime" / "RLBotServer.exe"
icon = package / "ui" / "icon.ico"
if not core.is_file():
    raise SystemExit("Run scripts/fetch_runtime.py before packaging")
if not icon.is_file():
    raise SystemExit("The original app icon is missing")
for notice in ("RLBot-core-LICENSE.txt", "Python-LICENSE.txt", "dependency-manifest.json", "SOURCE_MANIFEST.json"):
    if not (root / "packaging" / "licenses" / notice).is_file():
        raise SystemExit("Run scripts/collect_licenses.py before packaging the native candidate")
try:
    staged = candidate.bundle_entries(root)
except candidate.CandidateBuildError as exc:
    raise SystemExit(f"Native candidate is not staged: {exc}") from exc

data = collect_data_files("my_career_training")
data += [(str(core), "my_career_training/runtime")]
data += staged
data += [(str(root / "packaging" / "licenses"), "licenses")]
data += [(str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), ".")]
for name in ("rlbot", "rlbot-flatbuffers", "PySide6-Essentials", "shiboken6", "pygame-ce", "psutil",
             "torch", "numpy"):
    data += copy_metadata(name)
a = Analysis(
    [str(root / "packaging" / "native_gui_entry.py")],
    pathex=[str(root / "src")], binaries=[], datas=data,
    hiddenimports=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2",
                   "PySide6.QtSvg", "pygame", "rlbot", "rlbot.flat", "torch", "numpy"],
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
coll = COLLECT(gui, worker, windows_qt_binaries(a.binaries), a.datas, windows_qt_binaries(b.binaries), b.datas,
               strip=False, upx=False, name=candidate.BUNDLE_NAME)
