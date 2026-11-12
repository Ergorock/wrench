import ctypes
import logging
import os

import webview

from wrench.api import Api
from wrench.core import paths
from wrench.core.autostart import Autostart
from wrench.core.logging_setup import configure_logging
from wrench.core.registry import ToolRegistry, discover_tools
from wrench.core.settings import SettingsStore, WindowSettings, detect_system_language
from wrench.core.single_instance import acquire, focus_existing_window
from wrench.core.window_state import ScreenRect, fit_to_screens

logger = logging.getLogger("wrench")

DEV_URL = "http://localhost:5173"
_MESSAGES = {
    "fr": "Wrench ne peut pas démarrer : le composant WebView2 est introuvable ou a échoué.",
    "en": "Wrench cannot start: the WebView2 component is missing or failed.",
}


def _screens() -> list[ScreenRect]:
    return [ScreenRect(s.x, s.y, s.width, s.height) for s in webview.screens]


def _show_webview_error(language: str) -> None:
    text = _MESSAGES["fr" if language == "fr" else "en"]
    ctypes.windll.user32.MessageBoxW(None, text, "Wrench", 0x10)  # type: ignore[attr-defined,unused-ignore]


def main() -> int:
    configure_logging(paths.logs_dir())
    if not acquire():
        logger.info("Another instance is running, focusing it")
        focus_existing_window()
        return 0

    dev = os.environ.get("WRENCH_DEV") == "1"
    store = SettingsStore(paths.settings_file(), detect_system_language())
    loaded = store.load()
    registry = ToolRegistry(
        discover_tools(),
        paths.tools_data_dir(),
        lambda: api._current().language,
    )
    api = Api(
        store,
        loaded.settings,
        registry,
        Autostart(),
        ["settings_recovered"] if loaded.recovered else [],
    )
    logger.info("Starting Wrench (dev=%s, tools=%d)", dev, len(registry.manifests()))

    url = DEV_URL if dev else str(paths.frontend_dist_dir() / "index.html")
    try:
        win = fit_to_screens(api._current().window, _screens())
        window = webview.create_window(
            "Wrench",
            url,
            js_api=api,
            width=win.width,
            height=win.height,
            x=win.x,
            y=win.y,
            min_size=(800, 500),
        )
        assert window is not None

        state = {"maximized": win.maximized}

        def on_shown() -> None:
            if state["maximized"]:
                window.maximize()

        def on_closing() -> None:
            current = api._current().window
            if state["maximized"]:
                api._save_window(current.model_copy(update={"maximized": True}))
            else:
                api._save_window(
                    WindowSettings(
                        x=window.x,
                        y=window.y,
                        width=window.width,
                        height=window.height,
                        maximized=False,
                    )
                )

        window.events.shown += on_shown
        window.events.maximized += lambda: state.update(maximized=True)
        window.events.restored += lambda: state.update(maximized=False)
        window.events.closing += on_closing
        webview.start(gui="edgechromium", debug=dev, private_mode=False)
    except Exception:
        logger.exception("WebView2 failed to start")
        _show_webview_error(api._current().language)
        return 1
    return 0
