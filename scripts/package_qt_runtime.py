"""Keep ambient ICU copies out of this Windows Qt player distribution.

QtCore in this build imports the unversioned Windows ICU API. PyInstaller can
resolve its bare icuuc.dll name from unrelated PATH entries (for example Poppler)
and collect an incompatible, version-suffixed ICU plus its data DLL. Source Qt
loads System32 ICU successfully. Leave those OS dependencies to Windows; the
frozen UI smoke check must still pass before a package is accepted.
"""
from pathlib import PureWindowsPath
import re


def windows_qt_binaries(entries):
    return [entry for entry in entries if not _ambient_icu(entry[0])]


def _ambient_icu(destination):
    name = PureWindowsPath(destination).name.casefold()
    return name == "icuuc.dll" or re.fullmatch(r"icudt\d+\.dll", name) is not None
