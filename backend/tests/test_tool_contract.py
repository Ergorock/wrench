import importlib
import json
import pkgutil
import re
from typing import Any

import pytest

from wrench.core import paths
from wrench.core.categories import CATEGORIES
from wrench.core.registry import LoadedTool, discover_tools

FRONT = paths.resource_dir() / "frontend" / "src" / "tools"
ICON_TABLE = paths.resource_dir() / "frontend" / "src" / "shell" / "iconTable.ts"


def icon_table_keys() -> set[str]:
    """Keys of the explicit icon table (`monitor: Monitor,` or `'file-text': FileText,`)."""
    text = ICON_TABLE.read_text("utf-8")
    pattern = r"^\s*['\"]?([a-z][a-z0-9-]*)['\"]?\s*:\s*[A-Z]\w*\s*,"
    return set(re.findall(pattern, text, re.MULTILINE))


@pytest.mark.parametrize("category", CATEGORIES, ids=lambda c: c.id)
def test_category_icon_is_in_icon_table(category: Any) -> None:
    assert category.icon in icon_table_keys()


@pytest.mark.parametrize("tool", discover_tools(), ids=lambda t: t.manifest.id)
def test_tool_icon_is_in_icon_table(tool: LoadedTool) -> None:
    assert tool.manifest.icon in icon_table_keys()


def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in d.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, f"{full}."))
        else:
            out[full] = value
    return out


@pytest.mark.parametrize("tool", discover_tools(), ids=lambda t: t.manifest.id)
def test_tool_contract(tool: LoadedTool) -> None:
    d = FRONT / tool.manifest.id
    assert (d / "index.ts").is_file()
    fr = flatten(json.loads((d / "i18n" / "fr.json").read_text("utf-8")))
    en = flatten(json.loads((d / "i18n" / "en.json").read_text("utf-8")))
    assert fr.keys() == en.keys()
    assert {"name", "description"} <= fr.keys()


def _package_names(package: str) -> set[str]:
    pkg = importlib.import_module(package)
    return {i.name for i in pkgutil.iter_modules(pkg.__path__) if i.ispkg}


def test_every_tool_package_is_valid() -> None:
    assert _package_names("wrench.tools") == {t.manifest.id for t in discover_tools()}


def test_contract_check_detects_rejected_tools() -> None:
    discovered = {t.manifest.id for t in discover_tools("fake_tools", ["system"])}
    assert _package_names("fake_tools") != discovered
