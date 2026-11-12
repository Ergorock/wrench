import subprocess
from pathlib import Path
from typing import Any

import pytest

from wrench.shared.git.runner import GitNotFound, GitTimeout, find_git, run_git


def test_find_git_not_found() -> None:
    with pytest.raises(GitNotFound):
        find_git(candidates=[r"C:\nope\git.exe"])


def test_find_git_returns_first_existing(tmp_path: Path) -> None:
    exe = tmp_path / "git.exe"
    exe.write_bytes(b"")
    assert find_git(candidates=[r"C:\nope\git.exe", str(exe)]) == str(exe)


def test_run_git_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, "out", "err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_git(tmp_path, ["status"], 5, git="git")
    assert seen["cmd"] == ["git", "-C", str(tmp_path), "status"]
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0" and seen["env"]["LC_ALL"] == "C"
    assert seen["env"]["LANG"] == "C"
    assert seen["env"]["GIT_OPTIONAL_LOCKS"] == "0" and seen["timeout"] == 5
    assert seen["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert (result.code, result.stdout, result.stderr) == (0, "out", "err")


def test_run_git_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(cmd: list[str], **kw: Any) -> None:
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(GitTimeout):
        run_git(tmp_path, ["fetch"], 1, git="git")
