from pathlib import Path

from conftest import FakeBackend

from wrench.api import Api
from wrench.core.autostart import Autostart
from wrench.core.registry import ToolRegistry
from wrench.core.settings import SettingsStore, WindowSettings


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
