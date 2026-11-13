import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import webview
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


def test_update_methods_without_updater(api: Api) -> None:
    assert api.check_for_updates()["error"]["code"] == "update_unsupported"
    assert api.install_update()["error"]["code"] == "update_unsupported"
    status = api.get_update_status()["data"]
    assert status["supported"] is False and status["status"] == "idle"
    assert status["info"] is None and status["progress"] == 0.0 and status["error_code"] is None


def test_check_for_updates_sets_last_check(api_with_updater: Api) -> None:
    assert api_with_updater._current().updates.last_check is None
    r = api_with_updater.check_for_updates()
    assert r["ok"] and r["data"]["status"] == "available"
    assert api_with_updater._current().updates.last_check is not None
    assert api_with_updater.get_update_status()["data"]["status"] == "available"


def test_unsupported_check_does_not_set_last_check(tmp_path: Path, registry: ToolRegistry) -> None:
    from conftest import FakeHttp, release_for

    from wrench.core.updater import Updater

    store = SettingsStore(tmp_path / "s.json", "en")
    updater = Updater(FakeHttp(release_for(b"x")), "1.2.0", False, tmp_path, lambda p: None)
    api = Api(
        store,
        store.load().settings,
        registry,
        Autostart(FakeBackend(), "python.exe", frozen=False),
        [],
        updater=updater,
    )
    assert api.check_for_updates()["error"]["code"] == "update_unsupported"
    assert api._current().updates.last_check is None


def test_save_settings_keeps_python_last_check(api: Api) -> None:
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    with api._lock:
        api._settings = api._settings.model_copy(
            update={"updates": api._settings.updates.model_copy(update={"last_check": stamp})}
        )
    sent = api._current().model_dump(mode="json")
    sent["updates"] = {"auto_check": False, "last_check": None}
    r = api.save_settings(sent)
    assert r["ok"] and r["data"]["updates"]["auto_check"] is False
    assert api._current().updates.last_check == stamp


def test_open_url_restricted(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u) or True)
    good = "https://github.com/Ergorock/wrench/releases/tag/v1.0.0"
    assert api.open_url(good)["ok"]
    for bad in (
        "https://evil.example/",
        "http://github.com/Ergorock/wrench/",
        "https://github.com/Ergorock/wrench",
        "https://github.com/Ergorock/wrench/ x",
        "https://github.com/Ergorock/wrench/\nx",
        "https://github.com/Ergorock/wrench/../../x/y",
        "https://github.com/Ergorock/wrench/./x",
        "https://github.com/Ergorock/wrench/..",
        "https://github.com/Ergorock/wrench/..?a=1",
        "https://github.com/Ergorock/wrench/a/../../x",
        "https://github.com/Ergorock/wrench/%2e%2e/x",
        "https://github.com/Ergorock/wrench/a%2Fb",
        "https://github.com/Ergorock/wrench/a%5Cb",
        "https://github.com/Ergorock/wrench/a\\b",
        None,
    ):
        assert api.open_url(bad)["error"]["code"] == "invalid_payload"  # type: ignore[arg-type]
    assert opened == [good]


def test_open_url_reports_browser_failure(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webbrowser, "open", lambda u: False)
    r = api.open_url("https://github.com/Ergorock/wrench/releases")
    assert r["error"]["code"] == "open_failed"


class FakeWindow:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[Any, str]] = []
        self.file_types: tuple[str, ...] = ()

    def create_file_dialog(
        self, dialog_type: Any, directory: str = "", file_types: tuple[str, ...] = ()
    ) -> Any:
        self.calls.append((dialog_type, directory))
        self.file_types = file_types
        return self.result


def test_pick_folder_returns_path(api: Api) -> None:
    w = FakeWindow((r"C:\Dev",))
    api._set_window(w)
    assert api.pick_folder(r"C:\Users") == {"ok": True, "data": r"C:\Dev"}
    assert w.calls == [(webview.FileDialog.FOLDER, r"C:\Users")]


def test_pick_folder_cancel(api: Api) -> None:
    w = FakeWindow(None)
    api._set_window(w)
    assert api.pick_folder() == {"ok": True, "data": None}
    assert w.calls[0][1] == ""


def test_pick_folder_without_window(api: Api) -> None:
    assert api.pick_folder()["error"]["code"] == "internal_error"


def test_pick_exe_returns_path(api: Api) -> None:
    w = FakeWindow([r"C:\Apps\a.exe"])
    api._set_window(w)
    assert api.pick_exe(r"C:\Apps") == {"ok": True, "data": r"C:\Apps\a.exe"}
    assert w.calls == [(webview.FileDialog.OPEN, r"C:\Apps")]
    assert w.file_types == ("Programmes (*.exe)", "Tous les fichiers (*.*)")


def test_pick_exe_cancel_and_without_window(api: Api) -> None:
    assert api.pick_exe()["error"]["code"] == "internal_error"
    api._set_window(FakeWindow(None))
    assert api.pick_exe() == {"ok": True, "data": None}


def test_get_app_icon_data_url_and_cache(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("wrench.api.icon_png", lambda t: calls.append(t) or b"PNG")
    assert api.get_app_icon("x.exe") == {"ok": True, "data": "data:image/png;base64,UE5H"}
    api.get_app_icon("x.exe")
    assert calls == ["x.exe"]


def test_get_app_icon_none(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wrench.api.icon_png", lambda t: None)
    assert api.get_app_icon("x.exe") == {"ok": True, "data": None}


def test_get_app_icon_retries_after_none(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[bytes | None] = [None, b"PNG"]
    calls: list[str] = []
    monkeypatch.setattr("wrench.api.icon_png", lambda t: calls.append(t) or answers.pop(0))
    assert api.get_app_icon("x.exe") == {"ok": True, "data": None}
    assert api.get_app_icon("x.exe") == {"ok": True, "data": "data:image/png;base64,UE5H"}
    assert calls == ["x.exe", "x.exe"]


def test_save_settings_rejects_editor_without_name(api: Api) -> None:
    r = api.save_settings({"editors": [{"id": "a", "exe": "a.exe"}]})
    assert r["error"]["code"] == "invalid_settings"
