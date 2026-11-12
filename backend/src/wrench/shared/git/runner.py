"""Runs the installed `git` executable: no console window, no terminal prompt."""

import functools
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

STATUS_TIMEOUT = 10
NETWORK_TIMEOUT = 120
COMMIT_TIMEOUT = 60
KILL_GRACE = 5


class GitNotFound(Exception):
    pass


class GitTimeout(Exception):
    pass


@dataclass(frozen=True)
class GitResult:
    code: int
    stdout: str
    stderr: str


def _default_candidates() -> list[str]:
    found = shutil.which("git")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        *([found] if found else []),
        r"C:\Program Files\Git\cmd\git.exe",
        *([os.path.join(local, "Programs", "Git", "cmd", "git.exe")] if local else []),
    ]


def _first_existing(candidates: Sequence[str]) -> str:
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise GitNotFound("git executable not found")


@functools.cache
def _cached_git() -> str:
    # A GitNotFound is not cached: installing git is picked up on the next call.
    return _first_existing(_default_candidates())


def find_git(candidates: Sequence[str] | None = None) -> str:
    """First git executable found; the default lookup is cached for the process."""
    if candidates is None:
        return _cached_git()
    return _first_existing(candidates)


def run_git(
    repo: Path,
    args: Sequence[str],
    timeout: float,
    git: str | None = None,
    interactive: bool = True,
) -> GitResult:
    """Runs git in `repo`. With `interactive=False`, the Git Credential Manager fails
    instead of opening a sign-in window (for operations nobody asked for explicitly)."""
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    if not interactive:
        env["GCM_INTERACTIVE"] = "never"
    cmd = [git or find_git(), "-C", str(repo), *args]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_tree(process, flags)
            raise GitTimeout(f"git {' '.join(args)} timed out after {timeout}s") from exc
    return GitResult(process.returncode, stdout or "", stderr or "")


def _kill_tree(process: subprocess.Popen[str], flags: int) -> None:
    """Kills git and its children (git-remote-https, credential helper, ssh), which would
    otherwise keep our pipes open, then drains the pipes for a bounded time."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            creationflags=flags,
        )
    process.kill()
    try:
        process.communicate(timeout=KILL_GRACE)
    except subprocess.TimeoutExpired:
        pass  # a survivor still holds a pipe: closing them in __exit__ releases us.
