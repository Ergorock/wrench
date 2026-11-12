import winreg
from collections.abc import Callable

# Source: Microsoft, "Distribute your app and the WebView2 Runtime" (Detect if a WebView2
# Runtime is already installed). The value `pv` (REG_SZ) holds the runtime version.
_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
HKLM_SUBKEY = "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\" + _CLIENT_GUID
HKCU_SUBKEY = "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\" + _CLIENT_GUID
_HIVES = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}

ReadPv = Callable[[str, str], str | None]


def _read_pv_from_registry(hive: str, subkey: str) -> str | None:
    try:
        with winreg.OpenKey(_HIVES[hive], subkey) as key:
            value, _ = winreg.QueryValueEx(key, "pv")
    except OSError:
        return None
    return value if isinstance(value, str) else None


def is_webview2_installed(read_pv: ReadPv = _read_pv_from_registry) -> bool:
    """True if the WebView2 runtime is installed (per-machine or per-user).

    Windows 32 bits is not handled: Windows 11 is 64-bit only and the executable is 64-bit.
    A missing, empty or "0.0.0.0" `pv` means not installed, as documented by Microsoft.
    `read_pv(hive, subkey)` returns the `pv` value or None; it is injectable for tests.
    """
    for hive, subkey in (("HKLM", HKLM_SUBKEY), ("HKCU", HKCU_SUBKEY)):
        version = read_pv(hive, subkey)
        if version and version != "0.0.0.0":
            return True
    return False
