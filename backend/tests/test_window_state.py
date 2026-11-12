from wrench.core.settings import WindowSettings
from wrench.core.window_state import ScreenRect, fit_to_screens

SCREEN = [ScreenRect(0, 0, 1920, 1080)]


def test_position_kept_when_on_screen() -> None:
    w = fit_to_screens(WindowSettings(x=100, y=100), SCREEN)
    assert (w.x, w.y) == (100, 100)


def test_off_screen_is_recentered() -> None:
    w = fit_to_screens(WindowSettings(x=3000, y=100), SCREEN)
    assert (w.x, w.y) == (None, None)


def test_second_monitor_position_kept() -> None:
    screens = SCREEN + [ScreenRect(1920, 0, 1920, 1080)]
    assert fit_to_screens(WindowSettings(x=2500, y=50), screens).x == 2500


def test_too_small_is_enlarged() -> None:
    w = fit_to_screens(WindowSettings(width=200, height=100), SCREEN)
    assert (w.width, w.height) == (800, 500)


def test_none_position_stays_none_and_input_not_mutated() -> None:
    src = WindowSettings(width=200, maximized=True)
    w = fit_to_screens(src, SCREEN)
    assert (w.x, w.y) == (None, None)
    assert w.maximized is True
    assert src.width == 200
