import base64
import logging
import threading
import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import webview
from pydantic import ValidationError

from wrench._version import __version__
from wrench.core.autostart import Autostart
from wrench.core.categories import CATEGORIES
from wrench.core.registry import ToolRegistry
from wrench.core.settings import Settings, SettingsStore, WindowSettings
from wrench.core.updater import UpdateError, Updater
from wrench.sdk import ToolError
from wrench.shared.winicon import icon_png

logger = logging.getLogger("wrench.api")

RELEASES_URL_PREFIX = "https://github.com/Ergorock/wrench/"


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _fail(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


class Api:
    """Bridge to the front. Only the eleven public methods are exposed to JS
    (see `main._exposed`); everything else is private."""

    def __init__(
        self,
        store: SettingsStore,
        settings: Settings,
        registry: ToolRegistry,
        autostart: Autostart,
        warnings: list[str],
        updater: Updater | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._registry = registry
        self._autostart = autostart
        self._warnings = warnings
        self._updater = updater
        self._lock = threading.Lock()
        self._window: Any = None
        self._icons: dict[str, str] = {}

    def _current(self) -> Settings:
        with self._lock:
            return self._settings

    def _save_window(self, window: WindowSettings) -> None:
        with self._lock:
            self._settings = self._settings.model_copy(update={"window": window})
            self._store.save(self._settings)

    def _set_window(self, window: Any) -> None:
        """The pywebview window, needed by the native dialogs."""
        self._window = window

    def _envelope(self, fn: Callable[[], Any]) -> dict[str, Any]:
        try:
            return _ok(fn())
        except (ToolError, UpdateError) as exc:
            return _fail(exc.code, exc.message)
        except Exception as exc:
            logger.exception("Unhandled error in API call")
            return _fail("internal_error", str(exc))

    def _autostart_state(self) -> dict[str, bool]:
        return {
            "available": self._autostart.is_available(),
            "enabled": self._autostart.is_enabled(),
        }

    def get_bootstrap(self) -> dict[str, Any]:
        return self._envelope(
            lambda: {
                "settings": self._current().model_dump(mode="json"),
                "categories": [{"id": c.id, "icon": c.icon} for c in CATEGORIES],
                "tools": [m.model_dump(mode="json") for m in self._registry.manifests()],
                "autostart": self._autostart_state(),
                "warnings": list(self._warnings),
            }
        )

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            try:
                new = Settings.model_validate(settings)
            except ValidationError as exc:
                raise ToolError("invalid_settings", str(exc)) from exc
            with self._lock:
                # window and updates.last_check are owned by Python; the front only drives
                # updates.auto_check, so a stale last_check must not overwrite the real one.
                updates = new.updates.model_copy(
                    update={"last_check": self._settings.updates.last_check}
                )
                self._settings = new.model_copy(
                    update={"window": self._settings.window, "updates": updates}
                )
                self._store.save(self._settings)
                return self._settings.model_dump(mode="json")

        return self._envelope(run)

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        def run() -> dict[str, bool]:
            self._autostart.set_enabled(enabled)
            with self._lock:
                self._settings = self._settings.model_copy(
                    update={"autostart": self._autostart.is_enabled()}
                )
                self._store.save(self._settings)
            return self._autostart_state()

        return self._envelope(run)

    def tool_call(
        self, tool_id: str, action: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._envelope(lambda: self._registry.call(tool_id, action, payload or {}))

    def get_update_status(self) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            if self._updater is None:
                return {
                    "supported": False,
                    "current_version": __version__,
                    "status": "idle",
                    "info": None,
                    "progress": 0.0,
                    "error_code": None,
                }
            return self._updater.snapshot()

        return self._envelope(run)

    def _require_updater(self) -> Updater:
        if self._updater is None:
            raise UpdateError("update_unsupported", "Updates are not supported for this install")
        return self._updater

    def check_for_updates(self) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            snapshot = self._require_updater().check()
            # Reached only when a check actually ran (update_unsupported raises above); a check
            # that ended in status "error" still counts, so it is not retried in a tight loop.
            with self._lock:
                updates = self._settings.updates.model_copy(
                    update={"last_check": datetime.now(UTC)}
                )
                self._settings = self._settings.model_copy(update={"updates": updates})
                self._store.save(self._settings)
            return snapshot

        return self._envelope(run)

    def install_update(self) -> dict[str, Any]:
        return self._envelope(lambda: self._require_updater().start_install())

    def open_url(self, url: str) -> dict[str, Any]:
        def run() -> None:
            # Prefix check, plus: no space/control char (< 0x20), no backslash or percent
            # (encoded or alternate separators), and no "." / ".." path segment, which a
            # browser would normalize to escape the repository prefix.
            if (
                not isinstance(url, str)
                or not url.startswith(RELEASES_URL_PREFIX)
                or any(ch <= " " or ch in "\\%" for ch in url)
                or any(
                    seg in (".", "..")
                    for seg in url[len(RELEASES_URL_PREFIX) :]
                    .split("?")[0]
                    .split("#")[0]
                    .split("/")
                )
            ):
                raise ToolError("invalid_payload", "URL not allowed")
            # webbrowser.open returns False when no browser could be launched: "open_failed".
            if not webbrowser.open(url):
                raise ToolError("open_failed", "Could not open the browser")

        return self._envelope(run)

    def pick_folder(self, initial: str | None = None) -> dict[str, Any]:
        """Native folder picker; `data` is the chosen path, or None when cancelled."""

        def run() -> str | None:
            if self._window is None:
                raise RuntimeError("No window to attach the folder dialog to")
            result = self._window.create_file_dialog(
                webview.FileDialog.FOLDER, directory=initial or ""
            )
            if not result:
                return None
            return str(result if isinstance(result, str) else result[0])

        return self._envelope(run)

    def get_app_icon(self, exe: str) -> dict[str, Any]:
        """PNG data URL of an application's icon, or None; successes cached per process."""

        def run() -> str | None:
            if exe in self._icons:
                return self._icons[exe]
            png = icon_png(exe)
            if png is None:
                return None
            url = "data:image/png;base64," + base64.b64encode(png).decode()
            self._icons[exe] = url
            return url

        return self._envelope(run)

    def pick_exe(self, initial: str | None = None) -> dict[str, Any]:
        """Native file picker for an executable; `data` is the path, or None when cancelled."""

        def run() -> str | None:
            if self._window is None:
                raise RuntimeError("No window to attach the file dialog to")
            result = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                directory=initial or "",
                file_types=("Programmes (*.exe)", "Tous les fichiers (*.*)"),
            )
            if not result:
                return None
            return str(result if isinstance(result, str) else result[0])

        return self._envelope(run)
