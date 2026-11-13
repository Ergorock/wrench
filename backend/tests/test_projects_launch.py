import subprocess
from pathlib import Path
from typing import Any

import pytest

from wrench.sdk import ToolError
from wrench.tools.projects import launch
from wrench.tools.projects.launch import terminal_args


def test_terminal_args_with_wt() -> None:
    assert terminal_args(Path(r"C:\Dev\a"), None, "wt.exe") == ["wt.exe", "-d", r"C:\Dev\a"]
    assert terminal_args(Path(r"C:\Dev\a"), "npm run build", "wt.exe") == [
        "wt.exe",
        "-d",
        r"C:\Dev\a",
        "powershell",
        "-NoExit",
        "-Command",
        "npm run build",
    ]


def test_terminal_args_without_wt() -> None:
    assert terminal_args(Path(r"C:\Dev\a"), None, None) == [
        "powershell",
        "-NoExit",
        "-Command",
        "Set-Location -LiteralPath 'C:\\Dev\\a'",
    ]
    assert terminal_args(Path(r"C:\Dev\a"), "uv build", None)[-1] == (
        "Set-Location -LiteralPath 'C:\\Dev\\a'; uv build"
    )


def test_terminal_args_doubles_apostrophes() -> None:
    args = terminal_args(Path("C:\\Dev\\l'\u00e9t\u00e9"), None, None)
    assert args[-1] == "Set-Location -LiteralPath 'C:\\Dev\\l''\u00e9t\u00e9'"


def test_spawn_is_detached(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_popen(args: list[str], **kw: Any) -> None:
        seen["args"] = args
        seen.update(kw)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    launch.spawn(["x.exe", "a"], Path("C:/d"))
    assert seen["args"] == ["x.exe", "a"]
    assert seen["cwd"] == Path("C:/d")
    assert seen["close_fds"] is True
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["stdout"] == subprocess.DEVNULL
    assert seen["stderr"] == subprocess.DEVNULL
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    assert seen["creationflags"] == flags


def test_spawn_console_keeps_window_and_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: seen.update(kw))
    launch.spawn(["wt.exe"], Path("C:/d"), True)
    flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    assert seen["creationflags"] == flags
    assert not seen["creationflags"] & subprocess.DETACHED_PROCESS
    assert not seen["creationflags"] & getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for key in ("stdin", "stdout", "stderr"):
        assert key not in seen


def test_terminal_args_wt_escapes_semicolons() -> None:
    args = terminal_args(Path(r"C:\Dev"), "npm run build; echo ok", "wt.exe")
    assert args[-1] == "npm run build\; echo ok"
    plain = terminal_args(Path(r"C:\Dev"), "npm run build; echo ok", None)
    assert plain[-1].endswith("; npm run build; echo ok")


def test_spawn_oserror_becomes_launch_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("nope")

    monkeypatch.setattr(subprocess, "Popen", boom)
    with pytest.raises(ToolError) as exc:
        launch.spawn(["x"], None)
    assert exc.value.code == "launch_failed"
