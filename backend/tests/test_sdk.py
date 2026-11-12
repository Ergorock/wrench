import logging

import pytest
from pydantic import BaseModel, ValidationError

from wrench.core.categories import category_ids
from wrench.sdk import ToolContext, ToolError, ToolManifest, ToolService, ToolStorage, action


class Echo(BaseModel):
    text: str


class Demo(ToolService):
    @action
    def echo(self, text: str) -> Echo:
        return Echo(text=text)

    @action
    def boom(self) -> str:
        raise ToolError("custom", "boom")

    @action
    def _private(self) -> str:
        return "no"

    def hidden(self) -> str:
        return "no"


def make_ctx(tmp_path):
    storage = ToolStorage(tmp_path / "demo.json")
    return ToolContext("demo", storage, lambda: "fr", logging.getLogger("t"))


def test_invoke_returns_json(tmp_path):
    assert Demo(make_ctx(tmp_path)).invoke("echo", {"text": "hi"}) == {"text": "hi"}


def test_non_action_is_refused(tmp_path):
    with pytest.raises(ToolError) as e:
        Demo(make_ctx(tmp_path)).invoke("hidden", {})
    assert e.value.code == "unknown_action"


def test_underscore_and_missing_refused(tmp_path):
    for name in ("_private", "nope", "invoke", "ctx"):
        with pytest.raises(ToolError) as e:
            Demo(make_ctx(tmp_path)).invoke(name, {})
        assert e.value.code == "unknown_action"


def test_bad_payload(tmp_path):
    with pytest.raises(ToolError) as e:
        Demo(make_ctx(tmp_path)).invoke("echo", {"text": 3, "x": 1})
    assert e.value.code == "invalid_payload"


def test_tool_error_propagates(tmp_path):
    with pytest.raises(ToolError) as e:
        Demo(make_ctx(tmp_path)).invoke("boom", {})
    assert e.value.code == "custom"


def test_storage_roundtrip_and_corruption(tmp_path):
    s = ToolStorage(tmp_path / "tools" / "demo.json")
    assert s.load() == {}
    s.save({"a": 1})
    assert s.load() == {"a": 1}
    (tmp_path / "tools" / "demo.json").write_text("{bad", encoding="utf-8")
    assert s.load() == {}
    (tmp_path / "tools" / "demo.json").write_text("[1]", encoding="utf-8")
    assert s.load() == {}


def test_manifest_rejects_bad_id():
    with pytest.raises(ValidationError):
        ToolManifest(id="Bad-Id", category="system", icon="x", version="1.0.0")


def test_manifest_rejects_bad_version():
    with pytest.raises(ValidationError):
        ToolManifest(id="ok", category="system", icon="x", version="1.0")


def test_context_language(tmp_path):
    assert make_ctx(tmp_path).language == "fr"


def test_categories():
    assert category_ids() == ["system", "productivity", "development", "files"]
