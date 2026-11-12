import logging
import threading
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from wrench.core.autostart import Autostart
from wrench.core.categories import CATEGORIES
from wrench.core.registry import ToolRegistry
from wrench.core.settings import Settings, SettingsStore, WindowSettings
from wrench.sdk import ToolError

logger = logging.getLogger("wrench.api")


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _fail(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


class Api:
    """Bridge to the front. Only the four public methods are exposed to JS
    (see `main._exposed`); everything else is private."""

    def __init__(
        self,
        store: SettingsStore,
        settings: Settings,
        registry: ToolRegistry,
        autostart: Autostart,
        warnings: list[str],
    ) -> None:
        self._store = store
        self._settings = settings
        self._registry = registry
        self._autostart = autostart
        self._warnings = warnings
        self._lock = threading.Lock()

    def _current(self) -> Settings:
        with self._lock:
            return self._settings

    def _save_window(self, window: WindowSettings) -> None:
        with self._lock:
            self._settings = self._settings.model_copy(update={"window": window})
            self._store.save(self._settings)

    def _envelope(self, fn: Callable[[], Any]) -> dict[str, Any]:
        try:
            return _ok(fn())
        except ToolError as exc:
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
                self._settings = new.model_copy(update={"window": self._settings.window})
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
