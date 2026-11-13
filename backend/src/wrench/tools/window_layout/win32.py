"""Win32 calls that read and place top-level windows. Windows only."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

SW_SHOWMINIMIZED = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", _POINT),
        ("ptMaxPosition", _POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


@dataclass(frozen=True)
class OpenWindow:
    hwnd: int
    exe: str
    title: str
    placement: WINDOWPLACEMENT


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
_user32.GetWindowPlacement.restype = wintypes.BOOL
_user32.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
_user32.SetWindowPlacement.restype = wintypes.BOOL
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


def _exe_name(pid: int) -> str:
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(1024)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name.lower()
    finally:
        _kernel32.CloseHandle(handle)


def _title(hwnd: int, length: int) -> str:
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def enumerate_windows() -> list[OpenWindow]:
    """Visible, titled, non-tool windows that are not minimized."""
    found: list[OpenWindow] = []

    def visit(hwnd: int, _: int) -> bool:
        if not _user32.IsWindowVisible(hwnd):
            return True
        if _user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(WINDOWPLACEMENT)
        if not _user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
            return True
        if placement.showCmd == SW_SHOWMINIMIZED:
            return True
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = _exe_name(pid.value)
        if exe:
            found.append(OpenWindow(hwnd, exe, _title(hwnd, length), placement))
        return True

    _user32.EnumWindows(_WNDENUMPROC(visit), 0)
    return found


def apply_placement(hwnd: int, placement: WINDOWPLACEMENT) -> bool:
    """Put the window back where it was, normal or maximized. Returns False if it refused."""
    return bool(_user32.SetWindowPlacement(hwnd, ctypes.byref(placement)))
