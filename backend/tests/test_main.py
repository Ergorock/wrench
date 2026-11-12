import logging
from pathlib import Path

import pytest

from wrench import main as wrench_main
from wrench.api import Api
from wrench.main import _exposed


def test_only_the_four_bridge_methods_are_exposed(api: Api) -> None:
    exposed = _exposed(api)
    assert [f.__name__ for f in exposed] == [
        "get_bootstrap",
        "save_settings",
        "set_autostart",
        "tool_call",
    ]
    assert all(getattr(f, "__self__", None) is api for f in exposed)


@pytest.fixture
def startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, list[str]]:
    """Isolates main(): no real mutex, log handler, message box or window."""
    calls: dict[str, list[str]] = {"boxes": [], "windows": []}
    monkeypatch.setenv("WRENCH_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(wrench_main, "configure_logging", lambda _dir: None)
    monkeypatch.setattr(wrench_main, "acquire", lambda: True)
    monkeypatch.setattr(wrench_main, "detect_system_language", lambda: "fr")
    monkeypatch.setattr(wrench_main, "_message_box", calls["boxes"].append)
    monkeypatch.setattr(
        wrench_main.webview, "create_window", lambda *a, **k: calls["windows"].append("created")
    )
    return calls


def test_missing_webview2_shows_dedicated_message_before_the_window(
    startup: dict[str, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wrench_main, "is_webview2_installed", lambda: False)

    assert wrench_main.main() == 1

    assert startup["windows"] == []
    assert startup["boxes"] == [wrench_main._MESSAGES["fr"]]


def test_other_startup_error_shows_generic_message_with_log_path(
    startup: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(wrench_main, "is_webview2_installed", lambda: True)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(wrench_main, "discover_tools", boom)

    with caplog.at_level(logging.ERROR, logger="wrench"):
        assert wrench_main.main() == 1

    log_path = str(tmp_path / "logs" / "wrench.log")
    assert len(startup["boxes"]) == 1
    assert log_path in startup["boxes"][0]
    assert "WebView2" not in startup["boxes"][0]
    assert any(r.exc_info and r.exc_info[0] is RuntimeError for r in caplog.records)


def test_generic_message_is_english_when_language_is_not_french() -> None:
    text = wrench_main._startup_error_text("en", Path("C:/x/wrench.log"))
    assert "C:" in text and "wrench.log" in text
    assert "cannot start" in text
