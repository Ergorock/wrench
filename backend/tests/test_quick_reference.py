import logging
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolStorage
from wrench.tools.quick_reference.service import QuickReferenceService


@pytest.fixture
def svc(tmp_path: Path) -> QuickReferenceService:
    ctx = ToolContext(
        "quick_reference",
        ToolStorage(tmp_path / "quick_reference.json"),
        lambda: "en",
        logging.getLogger("test"),
    )
    return QuickReferenceService(ctx)


def test_sheets_shape(svc):
    sheets = svc.invoke("get_sheets", {})["sheets"]
    assert [s["id"] for s in sheets] == ["git", "powershell", "sql"]
    assert all(s["entries"] for s in sheets)


def test_ids_are_unique(svc):
    sheets = svc.invoke("get_sheets", {})["sheets"]
    ids = [e["id"] for s in sheets for e in s["entries"]]
    assert len(ids) == len(set(ids))


def test_commands_are_not_empty(svc):
    sheets = svc.invoke("get_sheets", {})["sheets"]
    assert all(e["command"].strip() for s in sheets for e in s["entries"])
