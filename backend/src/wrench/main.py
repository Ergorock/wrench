import ctypes
import logging
import os
import time
from collections.abc import Callable
from typing import Any

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

SETTLE_SECONDS = 0.5
DEV_URL = "http://localhost:5173"
_MESSAGES = {
    "fr": "Wrench ne peut pas démarrer : le composant WebView2 est introuvable ou a échoué.",
    "en": "Wrench cannot start: the WebView2 component is missing or failed.",
}


def _screens() -> list[ScreenRect]:
    return [ScreenRect(s.x, s.y, s.width, s.height) for s in webview.screens]


def _exposed(api: Api) -> list[Callable[..., Any]]:
    """The only Python callables reachable from JS. Passing `js_api=api` would let the page
    reach private members too: pywebview resolves dotted names with plain getattr."""
    return [api.get_bootstrap, api.save_settings, api.set_autostart, api.tool_call]


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
        window.expose(*_exposed(api))

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
        webview.start(gui="edgechromium", debug=dev, private_mode=False)
    except Exception:
        logger.exception("WebView2 failed to start")
        _show_webview_error(api._current().language)
        return 1
    return 0
