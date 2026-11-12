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


def run_git(repo: Path, args: Sequence[str], timeout: float, git: str | None = None) -> GitResult:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    cmd = [git or find_git(), "-C", str(repo), *args]
    try:
        # On timeout, subprocess.run kills the process before raising.
        done = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeout(f"git {' '.join(args)} timed out after {timeout}s") from exc
    return GitResult(done.returncode, done.stdout or "", done.stderr or "")
