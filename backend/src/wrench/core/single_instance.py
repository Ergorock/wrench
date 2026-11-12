import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = wintypes.BOOL
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL

# Kept at module level so the mutex lives as long as the process.
_mutex_handle: int | None = None


def acquire(name: str = "Local\\WrenchSingleInstance") -> bool:
    global _mutex_handle
    handle = _kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if handle:
            _kernel32.CloseHandle(handle)
        return False
    _mutex_handle = handle
    return True


def focus_existing_window(title: str = "Wrench") -> None:
    hwnd = _user32.FindWindowW(None, title)
    if not hwnd:
        return
    _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
