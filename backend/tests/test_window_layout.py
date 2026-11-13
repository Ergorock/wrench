import ctypes
import logging
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.window_layout import service as layout_service
from wrench.tools.window_layout.service import WindowLayoutService, match
from wrench.tools.window_layout.win32 import WINDOWPLACEMENT, OpenWindow


def open_window(hwnd: int, exe: str, title: str, left: int = 0) -> OpenWindow:
    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    placement.showCmd = 1
    placement.rcNormalPosition.left = left
    placement.rcNormalPosition.top = 10
    placement.rcNormalPosition.right = left + 800
    placement.rcNormalPosition.bottom = 610
    return OpenWindow(hwnd=hwnd, exe=exe, title=title, placement=placement)


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "window_layout",
        ToolStorage(tmp_path / "window_layout.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> WindowLayoutService:
    return WindowLayoutService(ctx)


@pytest.fixture
def desk(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Fake desktop: the open windows, and a record of the placements applied."""
    state: dict[str, object] = {
        "windows": [open_window(1, "code.exe", "main.py - Code", left=0)],
        "applied": [],
        "refuse": set(),
    }

    def enumerate_fake() -> list[OpenWindow]:
        return list(state["windows"])  # type: ignore[call-overload]

    def apply_fake(hwnd: int, placement: WINDOWPLACEMENT) -> bool:
        state["applied"].append((hwnd, placement.rcNormalPosition.left))  # type: ignore[attr-defined]
        return hwnd not in state["refuse"]  # type: ignore[operator]

    monkeypatch.setattr(layout_service.win32, "enumerate_windows", enumerate_fake)
    monkeypatch.setattr(layout_service, "apply_placement", apply_fake)
    return state


def test_list_windows_shows_open_programs(svc, desk):
    shown = svc.invoke("list_windows", {})["windows"]
    assert shown == [{"exe": "code.exe", "title": "main.py - Code"}]


def test_save_then_restore_puts_windows_back(svc, desk):
    svc.invoke("save_layout", {"name": "Dev"})
    # The user moves the editor somewhere else.
    desk["windows"] = [open_window(1, "code.exe", "main.py - Code", left=1500)]
    layout_id = svc.invoke("get_layouts", {})["layouts"][0]["id"]

    result = svc.invoke("restore_layout", {"layout_id": layout_id})

    assert result == {"restored": 1, "missing": []}
    assert desk["applied"] == [(1, 0)]


def test_restore_reports_programs_that_are_not_open(svc, desk):
    desk["windows"] = [
        open_window(1, "code.exe", "a"),
        open_window(2, "firefox.exe", "b"),
    ]
    svc.invoke("save_layout", {"name": "Mix"})
    desk["windows"] = [open_window(9, "code.exe", "a")]
    layout_id = svc.invoke("get_layouts", {})["layouts"][0]["id"]

    result = svc.invoke("restore_layout", {"layout_id": layout_id})

    assert result["restored"] == 1
    assert result["missing"] == [{"exe": "firefox.exe", "title": "b"}]


def test_refused_move_is_not_counted(svc, desk):
    svc.invoke("save_layout", {"name": "Dev"})
    desk["refuse"] = {1}
    layout_id = svc.invoke("get_layouts", {})["layouts"][0]["id"]
    assert svc.invoke("restore_layout", {"layout_id": layout_id})["restored"] == 0


def test_match_prefers_same_title_and_uses_each_window_once():
    saved = [
        layout_service.SavedWindow(
            exe="code.exe",
            title="b.py",
            placement=layout_service._to_saved(open_window(0, "x", "")).placement,
        ),
        layout_service.SavedWindow(
            exe="code.exe",
            title="a.py",
            placement=layout_service._to_saved(open_window(0, "x", "")).placement,
        ),
    ]
    open_now = [open_window(1, "code.exe", "a.py"), open_window(2, "code.exe", "b.py")]
    pairs = match(saved, open_now)
    assert [p[1].hwnd if p[1] else None for p in pairs] == [2, 1]


def test_match_does_not_reuse_a_window_for_two_saved_entries():
    saved = [
        layout_service.SavedWindow(
            exe="code.exe",
            title="x",
            placement=layout_service._to_saved(open_window(0, "x", "")).placement,
        )
    ] * 2
    pairs = match(saved, [open_window(1, "code.exe", "x")])
    assert [p[1] is None for p in pairs] == [False, True]


def test_unknown_layout_is_refused(svc, desk):
    with pytest.raises(ToolError) as e:
        svc.invoke("restore_layout", {"layout_id": "nope"})
    assert e.value.code == "unknown_layout"
    with pytest.raises(ToolError) as e:
        svc.invoke("delete_layout", {"layout_id": "nope"})
    assert e.value.code == "unknown_layout"


def test_blank_name_is_refused(svc, desk):
    with pytest.raises(ToolError) as e:
        svc.invoke("save_layout", {"name": "   "})
    assert e.value.code == "invalid_name"


def test_delete_layout(svc, desk):
    svc.invoke("save_layout", {"name": "Dev"})
    layout_id = svc.invoke("get_layouts", {})["layouts"][0]["id"]
    assert svc.invoke("delete_layout", {"layout_id": layout_id})["layouts"] == []


def test_malformed_stored_layouts_are_ignored(ctx, desk):
    valid = {"id": "ok", "name": "Ok", "saved_at": "t", "windows": []}
    ctx.storage.save({"layouts": [{"id": "x", "name": ""}, valid]})
    stored = WindowLayoutService(ctx).invoke("get_layouts", {})["layouts"]
    names = [layout["name"] for layout in stored]
    assert names == ["Ok"]


def test_real_enumeration_runs_on_this_desktop():
    # Smoke test of the real Win32 calls: must not crash, whatever is open.
    from wrench.tools.window_layout import win32

    for window in win32.enumerate_windows():
        assert window.exe
