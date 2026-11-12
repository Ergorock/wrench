from dataclasses import dataclass

from wrench.core.settings import WindowSettings

MIN_WIDTH = 800
MIN_HEIGHT = 500
TITLE_BAR_HEIGHT = 40


@dataclass(frozen=True)
class ScreenRect:
    x: int
    y: int
    width: int
    height: int


def _title_bar_visible(x: int, y: int, width: int, screens: list[ScreenRect]) -> bool:
    left, right = x, x + width
    top, bottom = y, y + TITLE_BAR_HEIGHT
    return any(
        left < s.x + s.width and right > s.x and top < s.y + s.height and bottom > s.y
        for s in screens
    )


def fit_to_screens(win: WindowSettings, screens: list[ScreenRect]) -> WindowSettings:
    width = max(win.width, MIN_WIDTH)
    height = max(win.height, MIN_HEIGHT)
    x, y = win.x, win.y
    if x is None or y is None or not _title_bar_visible(x, y, width, screens):
        x = y = None
    return win.model_copy(update={"x": x, "y": y, "width": width, "height": height})
