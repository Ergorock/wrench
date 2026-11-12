"""Real git repositories for tests, isolated from the machine's git configuration.

Loaded as a pytest plugin by conftest.py. Test files that run git use
`pytestmark = pytest.mark.usefixtures("git_env")`.
"""

import subprocess
from pathlib import Path

import pytest

IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com")


@pytest.fixture
def git_env(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty global config, no system config, temporary HOME. The identity is also given
    through the environment, for the commits made by the code under test."""
    home = tmp_path_factory.mktemp("home")
    config = home / "gitconfig"
    config.write_text("", "utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for kind in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{kind}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{kind}_EMAIL", "test@example.com")


def git(repo: Path, *args: str) -> str:
    """Runs git in `repo` with the test identity; fails the test on a non-zero exit."""
    done = subprocess.run(
        ["git", *IDENTITY, "-C", str(repo), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
    )
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def make_remote(tmp_path: Path) -> Path:
    """Bare repository used as `origin`, default branch `main`."""
    remote = tmp_path / "remote.git"
    remote.mkdir(parents=True)
    git(remote, "init", "--bare", "-b", "main")
    return remote


def make_clone(remote: Path, dest: Path) -> Path:
    """Clone of `remote`. An empty remote first receives an initial commit on `main`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    git(dest.parent, "clone", str(remote), dest.name)
    if not git(remote, "branch", "--list", "main"):
        git(dest, "switch", "-c", "main")
        commit_file(dest, "README.md", "init", "initial")
        git(dest, "push", "-u", "origin", "main")
    return dest


def commit_file(repo: Path, name: str, content: str, message: str) -> None:
    (repo / name).write_text(content, "utf-8")
    git(repo, "add", "--", name)
    git(repo, "commit", "-m", message)
