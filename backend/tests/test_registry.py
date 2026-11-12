from pathlib import Path

import pytest

from wrench.core.registry import ToolRegistry, discover_tools
from wrench.sdk import ToolError


def test_only_valid_tools_are_loaded(caplog: pytest.LogCaptureFixture) -> None:
    tools = discover_tools("fake_tools", known_categories=["system"])
    assert [t.manifest.id for t in tools] == ["good_tool"]
    for name in ("bad_category", "wrong_id", "no_service"):
        assert name in caplog.text


def test_call_dispatches_and_reuses_instance(tmp_path: Path) -> None:
    reg = ToolRegistry(discover_tools("fake_tools", ["system"]), tmp_path, lambda: "en")
    assert reg.call("good_tool", "ping", {}) == "pong"
    assert reg.call("good_tool", "count", {}) == 1
    assert reg.call("good_tool", "count", {}) == 2


def test_unknown_tool(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as e:
        ToolRegistry([], tmp_path, lambda: "en").call("nope", "x", {})
    assert e.value.code == "unknown_tool"
