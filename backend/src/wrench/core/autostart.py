import logging
import sys
import winreg
from typing import Protocol

from wrench.core import paths
from wrench.sdk.errors import ToolError

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Wrench"


class RegistryBackend(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class WinregBackend:
    def get(self, name: str) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value)

    def set(self, name: str, value: str) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


class Autostart:
    def __init__(
        self,
        backend: RegistryBackend | None = None,
        executable: str | None = None,
        frozen: bool | None = None,
    ) -> None:
        self._backend: RegistryBackend = backend if backend is not None else WinregBackend()
        self._executable = executable if executable is not None else sys.executable
        self._frozen = frozen if frozen is not None else paths.is_frozen()

    def is_available(self) -> bool:
        return self._frozen

    def is_enabled(self) -> bool:
        return self._backend.get(VALUE_NAME) is not None

    def refresh_path(self) -> None:
        """Rewrite the Run value if the executable was moved since autostart was enabled."""
        if not self.is_available():
            return
        current = self._backend.get(VALUE_NAME)
        expected = f'"{self._executable}"'
        if current is not None and current != expected:
            try:
                self._backend.set(VALUE_NAME, expected)
            except OSError:
                # A registry hiccup must not stop the application from starting.
                logging.getLogger("wrench").warning(
                    "Could not refresh autostart path", exc_info=True
                )

    def set_enabled(self, enabled: bool) -> None:
        if not self.is_available():
            raise ToolError(
                "autostart_unavailable",
                "Autostart is only available from the packaged executable.",
            )
        if enabled:
            self._backend.set(VALUE_NAME, f'"{self._executable}"')
        else:
            self._backend.delete(VALUE_NAME)
