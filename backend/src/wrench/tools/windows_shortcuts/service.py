import functools
import json
from importlib import resources

from pydantic import BaseModel

from wrench.sdk import ToolError, ToolService, action


class Shortcut(BaseModel):
    id: str
    keys: list[str]


class ShortcutGroup(BaseModel):
    id: str
    shortcuts: list[Shortcut]


class Catalog(BaseModel):
    groups: list[ShortcutGroup]
    favorites: list[str]


@functools.cache
def _load_groups() -> tuple[ShortcutGroup, ...]:
    """Read data/shortcuts.json once per process."""
    path = resources.files("wrench.tools.windows_shortcuts") / "data" / "shortcuts.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(ShortcutGroup.model_validate(g) for g in raw["groups"])


def _known_ids() -> set[str]:
    return {s.id for g in _load_groups() for s in g.shortcuts}


class WindowsShortcutsService(ToolService):
    def _favorites(self) -> list[str]:
        """Stored favorites, without duplicates and without ids that left the catalog."""
        stored = self.ctx.storage.load().get("favorites", [])
        if not isinstance(stored, list):
            return []
        known = _known_ids()
        result: list[str] = []
        for item in stored:
            if isinstance(item, str) and item in known and item not in result:
                result.append(item)
        return result

    @action
    def get_catalog(self) -> Catalog:
        return Catalog(groups=list(_load_groups()), favorites=self._favorites())

    @action
    def set_favorite(self, shortcut_id: str, favorite: bool) -> list[str]:
        if shortcut_id not in _known_ids():
            raise ToolError("unknown_shortcut", f"Unknown shortcut: {shortcut_id}")
        favorites = self._favorites()
        if favorite and shortcut_id not in favorites:
            favorites.append(shortcut_id)
        elif not favorite and shortcut_id in favorites:
            favorites.remove(shortcut_id)
        data = self.ctx.storage.load()
        data["favorites"] = favorites
        self.ctx.storage.save(data)
        return favorites


SERVICE = WindowsShortcutsService
