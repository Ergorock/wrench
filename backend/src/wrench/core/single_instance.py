import ctypes
import ntpath
import sys
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
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


def is_wrench_window(
    title: str, window_exe: str | None, current_exe: str, expected_title: str = "Wrench"
) -> bool:
    """Pure filter: the exact title AND a process with the same executable name as ours.

    An Explorer window titled "Wrench" has the right title but belongs to explorer.exe."""
    if title != expected_title or window_exe is None:
        return False
    return ntpath.basename(window_exe).lower() == ntpath.basename(current_exe).lower()


def _window_title(hwnd: int) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_executable(hwnd: int) -> str | None:
    pid = wintypes.DWORD(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    process = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        _kernel32.CloseHandle(process)


def focus_existing_window(title: str = "Wrench") -> None:
    current_exe = sys.executable
    found: list[int] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        if is_wrench_window(_window_title(hwnd), _window_executable(hwnd), current_exe, title):
            found.append(hwnd)
            return False  # stop enumerating
        return True

    _user32.EnumWindows(_WNDENUMPROC(visit), 0)
    if not found:
        return
    _user32.ShowWindow(found[0], SW_RESTORE)
    _user32.SetForegroundWindow(found[0])
