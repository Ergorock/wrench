import ctypes
import logging
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import webview

from wrench._version import __version__
from wrench.api import Api
from wrench.core import paths
from wrench.core.autostart import Autostart
from wrench.core.logging_setup import configure_logging
from wrench.core.registry import ToolRegistry, discover_tools
from wrench.core.settings import SettingsStore, WindowSettings, detect_system_language
from wrench.core.single_instance import acquire, focus_existing_window
from wrench.core.updater import (
    Updater,
    UrllibClient,
    launch_installer_detached,
    read_install_location,
    update_supported,
)
from wrench.core.webview2 import find_free_port, is_webview2_installed
from wrench.core.window_state import ScreenRect, fit_to_screens

logger = logging.getLogger("wrench")

SETTLE_SECONDS = 0.5
DEV_URL = "http://localhost:5173"
_MESSAGES = {
    "fr": "Wrench ne peut pas démarrer : le composant Microsoft Edge WebView2 Runtime est absent. "
    "Installez-le depuis https://developer.microsoft.com/microsoft-edge/webview2/ "
    "puis relancez Wrench.",
    "en": "Wrench cannot start: the Microsoft Edge WebView2 Runtime is missing. "
    "Install it from https://developer.microsoft.com/microsoft-edge/webview2/ "
    "and restart Wrench.",
}
_STARTUP_ERROR_MESSAGES = {
    "fr": "Wrench ne peut pas démarrer à cause d'une erreur inattendue.\n\n"
    "Le détail est dans le journal :\n{log}",
    "en": "Wrench cannot start because of an unexpected error.\n\n"
    "Details are in the log file:\n{log}",
}


def _screens() -> list[ScreenRect]:
    return [ScreenRect(s.x, s.y, s.width, s.height) for s in webview.screens]


def _exposed(api: Api) -> list[Callable[..., Any]]:
    """The only Python callables reachable from JS. Passing `js_api=api` would let the page
    reach private members too: pywebview resolves dotted names with plain getattr."""
    return [
        api.get_bootstrap,
        api.save_settings,
        api.set_autostart,
        api.tool_call,
        api.get_update_status,
        api.check_for_updates,
        api.install_update,
        api.open_url,
        api.pick_folder,
    ]


def _message_box(text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, "Wrench", 0x10)  # type: ignore[attr-defined,unused-ignore]


def _show_webview_error(language: str) -> None:
    _message_box(_MESSAGES["fr" if language == "fr" else "en"])


def _startup_error_text(language: str, log_path: Path) -> str:
    return _STARTUP_ERROR_MESSAGES["fr" if language == "fr" else "en"].format(log=log_path)


def _show_startup_error(language: str) -> None:
    _message_box(_startup_error_text(language, paths.logs_dir() / "wrench.log"))


def _error_language() -> str:
    """Language for startup error boxes; never raises."""
    system = detect_system_language()
    try:
        return SettingsStore(paths.settings_file(), system).load().settings.language
    except Exception:
        return system


def main() -> int:
    configure_logging(paths.logs_dir())
    if not acquire():
        logger.info("Another instance is running, focusing it")
        focus_existing_window()
        return 0
    try:
        return _run()
    except Exception:
        logger.exception("Wrench failed to start")
        _show_startup_error(_error_language())
        return 1


def _run() -> int:
    dev = os.environ.get("WRENCH_DEV") == "1"
    store = SettingsStore(paths.settings_file(), detect_system_language())
    loaded = store.load()
    registry = ToolRegistry(
        discover_tools(),
        paths.tools_data_dir(),
        lambda: api._current().language,
        lambda: api._current().editors,
    )
    autostart = Autostart()
    autostart.refresh_path()
    updater = Updater(
        UrllibClient(),
        __version__,
        update_supported(sys.executable, paths.is_frozen(), read_install_location),
        Path(tempfile.gettempdir()) / "Wrench-update",
        launch_installer_detached,
    )
    api = Api(
        store,
        loaded.settings,
        registry,
        autostart,
        ["settings_recovered"] if loaded.recovered else [],
        updater=updater,
    )
    logger.info("Starting Wrench (dev=%s, tools=%d)", dev, len(registry.manifests()))

    if not is_webview2_installed():
        logger.error("WebView2 runtime not found")
        _show_webview_error(api._current().language)
        return 1

    url = DEV_URL if dev else str(paths.frontend_dist_dir() / "index.html")
    screens = _screens()
    win = fit_to_screens(api._current().window, screens)
    if win.x is None or win.y is None:
        # pywebview's CenterScreen is applied before the size, so it is not centered.
        primary = screens[0]
        win = win.model_copy(
            update={
                "x": primary.x + (primary.width - win.width) // 2,
                "y": primary.y + (primary.height - win.height) // 2,
            }
        )
    window = webview.create_window(
        "Wrench",
        url,
        width=win.width,
        height=win.height,
        x=win.x,
        y=win.y,
        min_size=(800, 500),
    )
    assert window is not None
    api._set_window(window)
    window.expose(*_exposed(api))
    updater.set_close_handler(window.destroy)

    # Recent normal (neither maximized nor minimized) geometries, in logical pixels.
    # Windows moves/resizes the window just before the maximized/minimized event, so
    # snapshots younger than SETTLE_SECONDS are discarded when the state changes.
    history = [(time.monotonic(), win.model_copy(update={"maximized": False}))]
    state = {"maximized": win.maximized, "minimized": False}

    def record(**changes: int) -> None:
        if not state["maximized"] and not state["minimized"]:
            history.append((time.monotonic(), history[-1][1].model_copy(update=changes)))
            del history[:-20]

    def normal() -> WindowSettings:
        return history[-1][1]

    def discard_recent() -> None:
        cutoff = time.monotonic() - SETTLE_SECONDS
        while len(history) > 1 and history[-1][0] > cutoff:
            history.pop()

    def on_shown() -> None:
        if state["maximized"]:
            window.maximize()

    def on_moved(x: int, y: int) -> None:
        if x > -30000:
            record(x=x, y=y)

    def on_resized(width: int, height: int) -> None:
        if width > 0 and height > 0:
            record(width=width, height=height)

    def on_maximized() -> None:
        discard_recent()
        state.update(maximized=True, minimized=False)

    def on_minimized() -> None:
        discard_recent()
        state["minimized"] = True

    def on_restored() -> None:
        state.update(maximized=False, minimized=False)

    def on_closing() -> None:
        api._save_window(normal().model_copy(update={"maximized": state["maximized"]}))

    window.events.shown += on_shown
    window.events.moved += on_moved
    window.events.resized += on_resized
    window.events.maximized += on_maximized
    window.events.minimized += on_minimized
    window.events.restored += on_restored
    window.events.closing += on_closing
    webview.start(
        gui="edgechromium",
        debug=dev,
        private_mode=False,
        storage_path=str(paths.webview_profile_dir()),
        http_port=find_free_port(),
    )
    return 0
