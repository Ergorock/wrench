from pathlib import Path

import pytest
from conftest import FakeBackend
from pydantic import BaseModel

from wrench.api import Api
from wrench.core.autostart import Autostart
from wrench.core.registry import LoadedTool, ToolRegistry
from wrench.core.settings import SettingsStore, WindowSettings
from wrench.sdk import ToolContext, ToolManifest, ToolService, action


def test_bootstrap_shape(api: Api) -> None:
    r = api.get_bootstrap()
    assert r["ok"]
    assert [c["id"] for c in r["data"]["categories"]] == [
        "system",
        "productivity",
        "development",
        "files",
    ]
    assert r["data"]["autostart"] == {"available": False, "enabled": False}


def test_recovered_warning(tmp_path: Path, registry: ToolRegistry) -> None:
    p = tmp_path / "s.json"
    p.write_text("{bad", encoding="utf-8")
    store = SettingsStore(p, "en")
    res = store.load()
    api = Api(
        store,
        res.settings,
        registry,
        Autostart(FakeBackend(), "python.exe", frozen=False),
        ["settings_recovered"] if res.recovered else [],
    )
    assert api.get_bootstrap()["data"]["warnings"] == ["settings_recovered"]


def test_save_settings_keeps_python_window(api: Api) -> None:
    api._save_window(WindowSettings(x=10, y=20, width=900, height=600))
    sent = api.get_bootstrap()["data"]["settings"]
    sent["theme"] = "dark"
    sent["window"]["x"] = 999
    r = api.save_settings(sent)
    assert r["ok"] and r["data"]["theme"] == "dark" and r["data"]["window"]["x"] == 10


def test_save_settings_invalid(api: Api) -> None:
    assert api.save_settings({"theme": "pink"})["error"]["code"] == "invalid_settings"


def test_tool_call_envelope(api: Api) -> None:
    assert api.tool_call("good_tool", "ping") == {"ok": True, "data": "pong"}
    assert api.tool_call("nope", "x")["error"]["code"] == "unknown_tool"


def test_autostart_unavailable_envelope(api: Api) -> None:
    assert api.set_autostart(True)["error"]["code"] == "autostart_unavailable"


class _Strict(BaseModel):
    n: int


class _Buggy(ToolService):
    @action
    def body_error(self) -> int:
        return _Strict.model_validate({"n": "x"}).n

    @action
    def bad_return(self) -> int:
        return "x"  # type: ignore[return-value]

    @action
    def takes_int(self, n: int) -> int:
        return n


class _BrokenInit(ToolService):
    def __init__(self, ctx: ToolContext) -> None:
        super().__init__(ctx)
        _Strict.model_validate({"n": "x"})


def _manifest(tool_id: str) -> ToolManifest:
    return ToolManifest(id=tool_id, category="system", icon="x", version="1.0.0")


@pytest.fixture
def buggy_api(tmp_path: Path) -> Api:
    registry = ToolRegistry(
        [LoadedTool(_manifest("buggy"), _Buggy), LoadedTool(_manifest("broken"), _BrokenInit)],
        tmp_path / "tools",
        lambda: "en",
    )
    store = SettingsStore(tmp_path / "s.json", "en")
    return Api(
        store,
        store.load().settings,
        registry,
        Autostart(FakeBackend(), "python.exe", frozen=False),
        [],
    )


@pytest.mark.parametrize(
    ("tool_id", "action_name"),
    [("buggy", "body_error"), ("buggy", "bad_return"), ("broken", "anything")],
)
def test_tool_bugs_are_logged_internal_errors(
    buggy_api: Api, caplog: pytest.LogCaptureFixture, tool_id: str, action_name: str
) -> None:
    r = buggy_api.tool_call(tool_id, action_name, {})
    assert r["error"]["code"] == "internal_error"
    assert any(rec.levelname == "ERROR" and rec.exc_info for rec in caplog.records)


@pytest.mark.parametrize("payload", [{"n": "x"}, {}, {"n": 1, "extra": 2}, [1]])
def test_bad_arguments_are_invalid_payload_warnings(
    buggy_api: Api, caplog: pytest.LogCaptureFixture, payload: object
) -> None:
    r = buggy_api.tool_call("buggy", "takes_int", payload)  # type: ignore[arg-type]
    assert r["error"]["code"] == "invalid_payload"
    assert [rec.levelname for rec in caplog.records] == ["WARNING"]
