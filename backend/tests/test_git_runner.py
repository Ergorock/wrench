import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from wrench.shared.git.runner import GitNotFound, GitTimeout, find_git, run_git

windows_only = pytest.mark.skipif(os.name != "nt", reason="the fake git is a .cmd script")


def test_find_git_not_found() -> None:
    with pytest.raises(GitNotFound):
        find_git(candidates=[r"C:\nope\git.exe"])


def test_find_git_returns_first_existing(tmp_path: Path) -> None:
    exe = tmp_path / "git.exe"
    exe.write_bytes(b"")
    assert find_git(candidates=[r"C:\nope\git.exe", str(exe)]) == str(exe)


def _fake_git(tmp_path: Path, *lines: str) -> str:
    script = tmp_path / "fake git.cmd"
    script.write_text("\r\n".join(["@echo off", *lines, ""]), "utf-8")
    return str(script)


@windows_only
def test_run_git_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    real_popen = subprocess.Popen

    def spy(cmd: list[str], **kw: Any) -> Any:
        seen["cmd"] = cmd
        seen.update(kw)
        return real_popen(cmd, **kw)

    monkeypatch.setattr(subprocess, "Popen", spy)
    git = _fake_git(
        tmp_path,
        "echo %GIT_TERMINAL_PROMPT% %LC_ALL% %LANG% %GIT_OPTIONAL_LOCKS% %*",
        "echo oops 1>&2",
    )
    result = run_git(tmp_path, ["status"], 5, git=git)
    assert seen["cmd"] == [git, "-C", str(tmp_path), "status"]
    assert seen["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert result.code == 0
    assert result.stdout.split() == ["0", "C", "C", "0", "-C", str(tmp_path), "status"]
    assert result.stderr.strip() == "oops"


@windows_only
def test_run_git_timeout(tmp_path: Path) -> None:
    git = _fake_git(tmp_path, "ping -n 30 127.0.0.1 > nul 2>&1")
    with pytest.raises(GitTimeout):
        run_git(tmp_path, ["fetch"], 1, git=git)


@windows_only
def test_run_git_timeout_kills_grandchildren_holding_the_pipes(tmp_path: Path) -> None:
    """git-remote-https or a credential helper keeps our pipes open after git.exe dies:
    the timeout must still return promptly."""
    git = _fake_git(tmp_path, "ping -n 30 127.0.0.1")
    t0 = time.monotonic()
    with pytest.raises(GitTimeout):
        run_git(tmp_path, ["fetch"], 1, git=git)
    assert time.monotonic() - t0 < 10
