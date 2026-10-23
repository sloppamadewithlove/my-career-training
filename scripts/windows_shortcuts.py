"""Read Windows shell links without an ANSI scripting/output round trip.

Only used by packaging checks. COM method slots follow IShellLinkW and
IPersistFile in the Windows SDK, including the three IUnknown methods.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
from uuid import UUID


class GUID(ctypes.Structure):
    _fields_ = [('data1', ctypes.c_uint32), ('data2', ctypes.c_uint16),
                ('data3', ctypes.c_uint16), ('data4', ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value: str) -> GUID:
        return cls.from_buffer_copy(UUID(value).bytes_le)


def _check(result: int) -> None:
    if result < 0:
        raise OSError(f'Windows shell API failed: HRESULT 0x{result & 0xffffffff:08X}')


def _call(interface, slot: int, types: tuple, *args) -> None:
    table = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, *types)(table[slot])
    _check(method(interface, *args))


@contextmanager
def _shell_link():
    if os.name != 'nt':
        raise OSError('Windows shell links require Windows')
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_int32
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    initialized = ole.CoInitializeEx(None, 2)
    # A caller may already have initialized COM with another apartment model.
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE
        _check(initialized)
    link, persist = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        clsid = GUID.parse('00021401-0000-0000-C000-000000000046')
        iid = GUID.parse('000214F9-0000-0000-C000-000000000046')  # IShellLinkW
        ole.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        ole.CoCreateInstance.restype = ctypes.c_int32
        _check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(link)))
        persist_iid = GUID.parse('0000010B-0000-0000-C000-000000000046')
        _call(link, 0, (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
              ctypes.byref(persist_iid), ctypes.byref(persist))
        yield link, persist
    finally:
        if persist:
            _call(persist, 2, ())  # IUnknown::Release
        if link:
            _call(link, 2, ())
        if initialized >= 0:
            ole.CoUninitialize()


def read_shortcut(path: Path) -> dict[str, str]:
    with _shell_link() as (link, persist):
        _call(persist, 5, (ctypes.c_wchar_p, ctypes.c_uint32), str(path.resolve()), 0)
        target = ctypes.create_unicode_buffer(32768)
        arguments = ctypes.create_unicode_buffer(32768)
        _call(link, 3, (ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32),
              target, len(target), None, 0)
        _call(link, 10, (ctypes.c_wchar_p, ctypes.c_int), arguments, len(arguments))
        return {'target': target.value, 'arguments': arguments.value}


def programs_folders() -> list[Path]:
    if os.name != 'nt':
        raise OSError('Windows known folders require Windows')
    shell = ctypes.WinDLL('shell32')
    shell.SHGetFolderPathW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_wchar_p]
    shell.SHGetFolderPathW.restype = ctypes.c_int32
    folders = []
    for csidl in (0x02, 0x17):  # CSIDL_PROGRAMS, CSIDL_COMMON_PROGRAMS
        value = ctypes.create_unicode_buffer(32768)
        _check(shell.SHGetFolderPathW(None, csidl, None, 0, value))
        path = Path(value.value)
        if path not in folders:
            folders.append(path)
    return folders
