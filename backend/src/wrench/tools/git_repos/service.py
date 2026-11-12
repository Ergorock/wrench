"""Git repositories tool: discovers the repositories under root folders, shows their state,
and runs fetch, pull, push and commit in the background."""

import functools
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from wrench.sdk import ToolContext, ToolError, ToolService, action
from wrench.shared.git import ops
from wrench.shared.git.discovery import find_repos
from wrench.shared.git.jobs import RepoJobs
from wrench.shared.git.ops import GitOpError
from wrench.shared.git.runner import GitNotFound, find_git
from wrench.shared.git.status import RepoStatus, read_status

DEFAULT_MAX_DEPTH = 3
MIN_DEPTH = 1
MAX_DEPTH = 6
STATUS_WORKERS = 8


class Config(BaseModel):
    roots: list[str]
    max_depth: int
    missing_roots: list[str]


class RepoView(RepoStatus):
    root: str
    name: str
    rel_path: str
    running: str | None
    error: dict[str, str] | None


class State(BaseModel):
    git_available: bool
    repos: list[RepoView]


@dataclass
class _Repo:
    path: Path
    root: str
    rel_path: str
    status: RepoStatus
    error: dict[str, str] | None = None


def _key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _blank_status(path: Path) -> RepoStatus:
    """Placeholder until the state of a repository could be read once."""
    return RepoStatus(
        path=str(path),
        branch=None,
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        staged=0,
        unstaged=0,
        untracked=0,
        conflicts=0,
        operation=None,
        remote_url=None,
        host="none",
        last_fetch=None,
        changed_files=[],
    )


def _read(path: Path) -> tuple[RepoStatus | None, dict[str, str] | None]:
    try:
        return read_status(path), None
    except GitOpError as exc:
        return None, {"code": exc.code, "message": exc.message}
    except Exception as exc:
        return None, {"code": "git_failed", "message": str(exc)}


class GitReposService(ToolService):
    def __init__(self, ctx: ToolContext, git_finder: Callable[[], str] = find_git) -> None:
        super().__init__(ctx)
        self._git_finder = git_finder
        self._jobs = RepoJobs()
        self._lock = threading.Lock()
        self._repos: dict[str, _Repo] = {}

    # --- configuration -------------------------------------------------------------

    def _config(self) -> tuple[list[str], int]:
        data = self.ctx.storage.load()
        roots = data.get("roots")
        depth = data.get("max_depth")
        if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
            roots = []
        if not isinstance(depth, int) or isinstance(depth, bool):
            depth = DEFAULT_MAX_DEPTH
        if not MIN_DEPTH <= depth <= MAX_DEPTH:
            depth = DEFAULT_MAX_DEPTH
        return roots, depth

    def _config_view(self) -> Config:
        roots, depth = self._config()
        missing = [r for r in roots if not Path(r).is_dir()]
        return Config(roots=roots, max_depth=depth, missing_roots=missing)

    # --- state ---------------------------------------------------------------------

    def _git_available(self) -> bool:
        try:
            self._git_finder()
        except GitNotFound:
            return False
        return True

    def _require_git(self) -> None:
        if not self._git_available():
            raise ToolError("git_not_found", "git is not installed")

    def _require_repo(self, path: str) -> _Repo:
        with self._lock:
            repo = self._repos.get(_key(path))
        if repo is None:
            raise ToolError("unknown_repo", f"Unknown repository: {path}")
        return repo

    def _state(self) -> State:
        with self._lock:
            repos = list(self._repos.items())
        views = []
        for key, repo in repos:
            job = self._jobs.state(key)
            views.append(
                RepoView(
                    **repo.status.model_dump(),
                    root=repo.root,
                    name=repo.path.name,
                    rel_path=repo.rel_path,
                    running=job.running,
                    error=job.error or repo.error,
                )
            )
        return State(git_available=self._git_available(), repos=views)

    def _refresh(self, key: str, path: Path) -> None:
        """Re-reads one repository; on failure it keeps its last known state."""
        status, error = _read(path)
        with self._lock:
            repo = self._repos.get(key)
            if repo is None:
                return
            if status is not None:
                repo.status = status
            repo.error = error

    def _submit(self, repo: _Repo, op: str, fn: Callable[[], None]) -> bool:
        key = _key(repo.path)

        def work() -> None:
            try:
                fn()
            finally:
                self._refresh(key, repo.path)

        return self._jobs.submit(key, op, work)

    # --- actions -------------------------------------------------------------------

    @action
    def get_config(self) -> Config:
        return self._config_view()

    @action
    def set_config(
        self, roots: list[str], max_depth: Annotated[int, Field(ge=MIN_DEPTH, le=MAX_DEPTH)]
    ) -> Config:
        unique: list[str] = []
        seen: set[str] = set()
        for root in roots:
            root = root.strip()
            if root and _key(root) not in seen:
                seen.add(_key(root))
                unique.append(root)
        self.ctx.storage.save({"roots": unique, "max_depth": max_depth})
        self._rescan()
        return self._config_view()

    def _rescan(self) -> None:
        roots, depth = self._config()
        found: dict[str, _Repo] = {}
        for root in roots:
            base = Path(root).resolve()
            for path in find_repos([base], depth):
                key = _key(path)
                if key not in found:
                    rel = path.relative_to(base) if path != base else Path(path.name)
                    found[key] = _Repo(path, root, str(rel), _blank_status(path))
        if self._git_available():
            with ThreadPoolExecutor(max_workers=STATUS_WORKERS) as pool:
                results = list(pool.map(lambda r: _read(r.path), found.values()))
            for repo, (status, error) in zip(found.values(), results, strict=True):
                if status is not None:
                    repo.status = status
                repo.error = error
        with self._lock:
            self._repos = found

    @action
    def rescan(self) -> State:
        self._rescan()
        return self._state()

    @action
    def get_state(self) -> State:
        return self._state()

    @action
    def fetch_all(self, auto: bool = False) -> State:
        """`auto`: the fetch made when the tool opens, without credential prompts."""
        self._require_git()
        with self._lock:
            repos = list(self._repos.values())
        for repo in repos:
            if repo.status.remote_url is not None:
                self._submit(
                    repo, "fetch", functools.partial(ops.fetch, repo.path, interactive=not auto)
                )
        return self._state()

    @action
    def fetch(self, path: str) -> State:
        self._require_git()
        repo = self._require_repo(path)
        self._submit(repo, "fetch", lambda: ops.fetch(repo.path))
        return self._state()

    @action
    def pull(self, path: str) -> State:
        self._require_git()
        repo = self._require_repo(path)
        self._submit(repo, "pull", lambda: ops.pull(repo.path))
        return self._state()

    @action
    def push(self, path: str) -> State:
        self._require_git()
        repo = self._require_repo(path)
        self._submit(repo, "push", lambda: ops.push(repo.path))
        return self._state()

    @action
    def commit(self, path: str, message: str, push: bool = False) -> State:
        self._require_git()
        repo = self._require_repo(path)
        if not message.strip():
            raise ToolError("empty_message", "The commit message is empty")

        def work() -> None:
            ops.commit_all(repo.path, message)
            if push:
                ops.push(repo.path)

        if not self._submit(repo, "commit", work):
            # Unlike a repeated fetch/pull/push, dropping it would lose the typed message.
            raise ToolError("busy", "An operation is already running on this repository")
        return self._state()

    @action
    def clear_error(self, path: str) -> State:
        repo = self._require_repo(path)
        self._jobs.clear_error(_key(repo.path))
        with self._lock:
            repo.error = None
        return self._state()


SERVICE = GitReposService
