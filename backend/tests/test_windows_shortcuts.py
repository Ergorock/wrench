import logging
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.windows_shortcuts.service import WindowsShortcutsService

KNOWN_KEYS = (
    {
        "Win", "Ctrl", "Shift", "Alt", "Tab", "Esc", "Enter", "Space", "Backspace", "Del",
        "Home", "End", "PrtSc", "Left", "Right", "Up", "Down", "PageUp", "PageDown",
        "Plus", "Minus", "Comma", "Period", "Semicolon",
    }
    | {f"F{n}" for n in range(1, 13)}
    | {chr(c) for c in range(ord("A"), ord("Z") + 1)}
    | {str(n) for n in range(10)}
)  # fmt: skip


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "windows_shortcuts",
        ToolStorage(tmp_path / "windows_shortcuts.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> WindowsShortcutsService:
    return WindowsShortcutsService(ctx)


def test_catalog_shape(svc):
    cat = svc.invoke("get_catalog", {})
    assert [g["id"] for g in cat["groups"]] == [
        "general",
        "windows_snap",
        "virtual_desktops",
        "explorer",
        "capture",
        "accessibility",
        "typing",
    ]
    n = sum(len(g["shortcuts"]) for g in cat["groups"])
    assert 60 <= n <= 80
    ids = [s["id"] for g in cat["groups"] for s in g["shortcuts"]]
    assert len(ids) == len(set(ids))
    assert cat["favorites"] == []


def test_all_keys_are_known(svc):
    for g in svc.invoke("get_catalog", {})["groups"]:
        for s in g["shortcuts"]:
            assert all(k in KNOWN_KEYS for k in s["keys"]), s


def test_set_favorite_persists_and_is_idempotent(svc, ctx):
    svc.invoke("set_favorite", {"shortcut_id": "snap_left", "favorite": True})
    again = svc.invoke("set_favorite", {"shortcut_id": "snap_left", "favorite": True})
    assert again == ["snap_left"]
    assert ctx.storage.load() == {"favorites": ["snap_left"]}
    assert svc.invoke("set_favorite", {"shortcut_id": "snap_left", "favorite": False}) == []


def test_unknown_shortcut(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("set_favorite", {"shortcut_id": "nope", "favorite": True})
    assert e.value.code == "unknown_shortcut"


def test_stale_favorites_are_ignored(ctx):
    ctx.storage.save({"favorites": ["gone", "snap_left"]})
    assert WindowsShortcutsService(ctx).invoke("get_catalog", {})["favorites"] == ["snap_left"]


def test_snap_left_is_win_left(svc):
    groups = {g["id"]: g for g in svc.invoke("get_catalog", {})["groups"]}
    snap = {s["id"]: s for s in groups["windows_snap"]["shortcuts"]}
    assert snap["snap_left"]["keys"] == ["Win", "Left"]
