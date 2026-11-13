import ctypes
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from wrench.sdk import ToolError, ToolService, action
from wrench.tools.window_layout import win32
from wrench.tools.window_layout.win32 import WINDOWPLACEMENT, OpenWindow, apply_placement

MAX_LAYOUTS = 50
MAX_WINDOWS = 200


class SavedPlacement(BaseModel):
    flags: int
    show: int
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    left: int
    top: int
    right: int
    bottom: int


class SavedWindow(BaseModel):
    exe: str
    title: str
    placement: SavedPlacement


class Layout(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=60)
    saved_at: str
    windows: list[SavedWindow]


class Layouts(BaseModel):
    layouts: list[Layout]


class OpenItem(BaseModel):
    exe: str
    title: str


class OpenWindows(BaseModel):
    windows: list[OpenItem]


class Restore(BaseModel):
    restored: int
    missing: list[OpenItem]


def _to_saved(window: OpenWindow) -> SavedWindow:
    p = window.placement
    rect = p.rcNormalPosition
    return SavedWindow(
        exe=window.exe,
        title=window.title,
        placement=SavedPlacement(
            flags=p.flags,
            show=p.showCmd,
            min_x=p.ptMinPosition.x,
            min_y=p.ptMinPosition.y,
            max_x=p.ptMaxPosition.x,
            max_y=p.ptMaxPosition.y,
            left=rect.left,
            top=rect.top,
            right=rect.right,
            bottom=rect.bottom,
        ),
    )


def _to_placement(saved: SavedPlacement) -> WINDOWPLACEMENT:
    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    placement.flags = saved.flags
    placement.showCmd = saved.show
    placement.ptMinPosition.x = saved.min_x
    placement.ptMinPosition.y = saved.min_y
    placement.ptMaxPosition.x = saved.max_x
    placement.ptMaxPosition.y = saved.max_y
    placement.rcNormalPosition.left = saved.left
    placement.rcNormalPosition.top = saved.top
    placement.rcNormalPosition.right = saved.right
    placement.rcNormalPosition.bottom = saved.bottom
    return placement


def match(
    saved: list[SavedWindow], open_windows: list[OpenWindow]
) -> list[tuple[SavedWindow, OpenWindow | None]]:
    """Pair each saved window with an open window of the same program.

    A window with the same title is preferred. Each open window is used at most once.
    """
    used: set[int] = set()
    pairs: list[tuple[SavedWindow, OpenWindow | None]] = []
    for item in saved:
        candidates = [w for w in open_windows if w.exe == item.exe and w.hwnd not in used]
        if not candidates:
            pairs.append((item, None))
            continue
        chosen = next((w for w in candidates if w.title == item.title), candidates[0])
        used.add(chosen.hwnd)
        pairs.append((item, chosen))
    return pairs


class WindowLayoutService(ToolService):
    def _layouts(self) -> list[Layout]:
        """Stored layouts. A malformed entry is ignored rather than breaking the list."""
        stored = self.ctx.storage.load().get("layouts", [])
        if not isinstance(stored, list):
            return []
        result: list[Layout] = []
        for item in stored:
            try:
                result.append(Layout.model_validate(item))
            except ValueError:
                continue
        return result

    def _save_layouts(self, layouts: list[Layout]) -> None:
        self.ctx.storage.save({"layouts": [layout.model_dump() for layout in layouts]})

    @action
    def list_windows(self) -> OpenWindows:
        return OpenWindows(
            windows=[OpenItem(exe=w.exe, title=w.title) for w in win32.enumerate_windows()]
        )

    @action
    def get_layouts(self) -> Layouts:
        return Layouts(layouts=self._layouts())

    @action
    def save_layout(self, name: str) -> Layouts:
        """Store the position of every window open now, under `name`."""
        clean = name.strip()
        if not clean:
            raise ToolError("invalid_name", "Give the layout a name.")
        layouts = self._layouts()
        if len(layouts) >= MAX_LAYOUTS:
            raise ToolError("too_many_layouts", "The list is full.")
        windows = [_to_saved(w) for w in win32.enumerate_windows()][:MAX_WINDOWS]
        layouts.append(
            Layout(
                id=uuid.uuid4().hex,
                name=clean[:60],
                saved_at=datetime.now().isoformat(timespec="minutes"),
                windows=windows,
            )
        )
        self._save_layouts(layouts)
        return Layouts(layouts=layouts)

    @action
    def delete_layout(self, layout_id: str) -> Layouts:
        layouts = self._layouts()
        remaining = [layout for layout in layouts if layout.id != layout_id]
        if len(remaining) == len(layouts):
            raise ToolError("unknown_layout", f"Unknown layout: {layout_id}")
        self._save_layouts(remaining)
        return Layouts(layouts=remaining)

    @action
    def restore_layout(self, layout_id: str) -> Restore:
        """Move each open window of the program back to its saved place.

        Programs that are not open are reported as missing, and nothing is started.
        """
        layout = next((item for item in self._layouts() if item.id == layout_id), None)
        if layout is None:
            raise ToolError("unknown_layout", f"Unknown layout: {layout_id}")
        restored = 0
        missing: list[OpenItem] = []
        for saved, open_window in match(layout.windows, win32.enumerate_windows()):
            if open_window is None:
                missing.append(OpenItem(exe=saved.exe, title=saved.title))
                continue
            if apply_placement(open_window.hwnd, _to_placement(saved.placement)):
                restored += 1
        return Restore(restored=restored, missing=missing)


SERVICE = WindowLayoutService
