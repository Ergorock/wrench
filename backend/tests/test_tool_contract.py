import json
from typing import Any

import pytest

from wrench.core import paths
from wrench.core.registry import LoadedTool, discover_tools

FRONT = paths.resource_dir() / "frontend" / "src" / "tools"


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
