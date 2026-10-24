"""A foreign PATH dependency must not shadow the Windows ICU used by QtCore."""
import importlib.util
from pathlib import Path


def test_windows_qt_collection_excludes_foreign_icu_and_retains_actual_app_libraries():
    path = Path(__file__).resolve().parents[1] / "scripts/package_qt_runtime.py"
    spec = importlib.util.spec_from_file_location("package_qt_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    foreign = [("icuuc.dll", "ambient/poppler/icuuc.dll", "BINARY"),
               ("ICUDT78.DLL", "ambient/poppler/icudt78.dll", "BINARY"),
               ("other\\icudt79.dll", "foreign/icu-data", "BINARY")]
    expected = [("PySide6/Qt6Core.dll", "venv/Qt6Core.dll", "BINARY"),
                ("SDL2.dll", "venv/pygame/SDL2.dll", "BINARY"),
                ("python312.dll", "python/python312.dll", "BINARY"),
                ("MSVCP140.dll", "runtime/MSVCP140.dll", "BINARY")]
    entries = foreign + expected
    assert module.windows_qt_binaries(entries) == expected
    assert entries == foreign + expected
