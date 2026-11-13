import functools
import json
from importlib import resources

from pydantic import BaseModel

from wrench.sdk import ToolService, action


class Entry(BaseModel):
    id: str
    command: str


class Sheet(BaseModel):
    id: str
    entries: list[Entry]


class Reference(BaseModel):
    sheets: list[Sheet]


@functools.cache
def _load_sheets() -> tuple[Sheet, ...]:
    """Read data/sheets.json once per process."""
    path = resources.files("wrench.tools.quick_reference") / "data" / "sheets.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(Sheet.model_validate(s) for s in raw["sheets"])


class QuickReferenceService(ToolService):
    @action
    def get_sheets(self) -> Reference:
        return Reference(sheets=list(_load_sheets()))


SERVICE = QuickReferenceService
