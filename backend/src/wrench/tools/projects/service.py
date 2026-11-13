"""Projects tool: inventory of the projects under a root folder, git state on demand, and the
associated remote repository. The long work runs in the background; the front polls get_state."""

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from wrench.sdk import ToolContext, ToolError, ToolService, action
from wrench.shared.git import ops
from wrench.shared.git.jobs import RepoJobs
from wrench.shared.git.ops import GitOpError
from wrench.shared.git.remote import web_url
from wrench.shared.git.runner import GitNotFound, find_git
from wrench.shared.git.status import RepoStatus, read_status
from wrench.tools.projects.scan import FolderEntry, ProjectEntry, flatten, scan

DEFAULT_MAX_DEPTH = 4
MIN_DEPTH = 1
MAX_DEPTH = 6
STATUS_WORKERS = 8


class Config(BaseModel):
    root: str | None
    templates_dir: str | None
    max_depth: int
    root_missing: bool
    templates_missing: bool


class GitView(RepoStatus):
    root: str
    name: str
    rel_path: str
    web_url: str | None
    running: str | None
    error: dict[str, str] | None


class State(BaseModel):
    scanning: bool
    scan_error: dict[str, str] | None
    git_available: bool
    tree: FolderEntry | None
    git: dict[str, GitView]
    creation: None = None  # the creation view arrives with the template task


@dataclass
class _Repo:
    path: Path
    entry: ProjectEntry
    status: RepoStatus | None = None
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


class ProjectsService(ToolService):
    def __init__(self, ctx: ToolContext, git_finder: Callable[[], str] = find_git) -> None:
        super().__init__(ctx)
        self._git_finder = git_finder
        self._jobs = RepoJobs(max_workers=STATUS_WORKERS)
        self._lock = threading.Lock()
        self._started = False
        self._scanning = False
        self._rescan_again = False
        self._scan_error: dict[str, str] | None = None
        self._tree: FolderEntry | None = None
        self._projects: dict[str, ProjectEntry] = {}
        self._git_projects: set[str] = set()  # inventory entries that have a `.git`
        self._repos: dict[str, _Repo] = {}  # git state cache

    # --- configuration -------------------------------------------------------------

    def _config(self) -> tuple[str | None, str | None, int]:
        data = self.ctx.storage.load()
        root = data.get("root")
        templates = data.get("templates_dir")
        depth = data.get("max_depth")
        if not isinstance(root, str) or not root.strip():
            root = None
        if not isinstance(templates, str) or not templates.strip():
            templates = None
        if not isinstance(depth, int) or isinstance(depth, bool):
            depth = DEFAULT_MAX_DEPTH
        if not MIN_DEPTH <= depth <= MAX_DEPTH:
            depth = DEFAULT_MAX_DEPTH
        return root, templates, depth

    def _config_view(self) -> Config:
        root, templates, depth = self._config()
        return Config(
            root=root,
            templates_dir=templates,
            max_depth=depth,
            root_missing=root is not None and not Path(root).is_dir(),
            templates_missing=templates is not None and not Path(templates).is_dir(),
        )

    # --- scan ----------------------------------------------------------------------

    def _start_scan(self) -> None:
        """Starts a scan; during one, asks for a single more when it ends."""
        with self._lock:
            self._started = True
            if self._scanning:
                self._rescan_again = True
                return
            self._scanning = True
        threading.Thread(target=self._scan_loop, name="projects-scan", daemon=True).start()

    def _scan_loop(self) -> None:
        while True:
            self._scan_once()
            with self._lock:
                if not self._rescan_again:
                    self._scanning = False
                    return
                self._rescan_again = False

    def _scan_once(self) -> None:
        tree: FolderEntry | None = None
        projects: dict[str, ProjectEntry] = {}
        git_projects: set[str] = set()
        error: dict[str, str] | None = None
        try:
            root, templates, depth = self._config()
            if root is not None and Path(root).is_dir():
                tree = scan(Path(root), depth, Path(templates) if templates else None)
                for entry in flatten(tree):
                    key = _key(entry.path)
                    projects[key] = entry
                    if (Path(entry.path) / ".git").exists():
                        git_projects.add(key)
        except Exception as exc:
            self.ctx.logger.exception("Projects scan failed")
            tree, projects, git_projects = None, {}, set()
            error = {"code": "scan_failed", "message": str(exc)}
        with self._lock:
            self._tree = tree
            self._projects = projects
            self._git_projects = git_projects
            self._scan_error = error
            self._repos = {k: r for k, r in self._repos.items() if k in projects}

    def _clear_git_cache(self) -> None:
        with self._lock:
            self._repos = {}

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

    def _project(self, path: str) -> ProjectEntry:
        """The inventory entry of `path`; not_a_project when it is not one."""
        with self._lock:
            entry = self._projects.get(_key(path))
        if entry is None:
            raise ToolError("not_a_project", f"Not a project of the inventory: {path}")
        return entry

    def _repo(self, entry: ProjectEntry) -> _Repo:
        key = _key(entry.path)
        with self._lock:
            repo = self._repos.get(key)
            if repo is None:
                repo = self._repos[key] = _Repo(Path(entry.path), entry)
            return repo

    def _state(self) -> State:
        root = self._config()[0] or ""
        with self._lock:
            repos = list(self._repos.items())
            scanning, scan_error, tree = self._scanning, self._scan_error, self._tree
        views: dict[str, GitView] = {}
        for key, repo in repos:
            job = self._jobs.state(key)
            status = repo.status or _blank_status(repo.path)
            views[repo.entry.path] = GitView(
                **status.model_dump(),
                root=root,
                name=repo.entry.name,
                rel_path=repo.entry.rel_path,
                web_url=web_url(status.remote_url),
                running=job.running,
                error=job.error or repo.error,
            )
        return State(
            scanning=scanning,
            scan_error=scan_error,
            git_available=self._git_available(),
            tree=tree,
            git=views,
        )

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
        self,
        root: str | None,
        templates_dir: str | None,
        max_depth: Annotated[int, Field(ge=MIN_DEPTH, le=MAX_DEPTH)],
    ) -> Config:
        data = self.ctx.storage.load()
        data["root"] = root.strip() if root and root.strip() else None
        data["templates_dir"] = (
            templates_dir.strip() if templates_dir and templates_dir.strip() else None
        )
        data["max_depth"] = max_depth
        self.ctx.storage.save(data)
        self._clear_git_cache()
        self._start_scan()
        return self._config_view()

    @action
    def get_state(self) -> State:
        with self._lock:
            started = self._started
        if not started:
            self._start_scan()
        return self._state()

    @action
    def rescan(self) -> State:
        self._clear_git_cache()
        self._start_scan()
        return self._state()

    @action
    def load_status(self, paths: list[str]) -> State:
        entries = [self._project(p) for p in paths]
        if self._git_available():
            for entry in entries:
                key = _key(entry.path)
                with self._lock:
                    known = key in self._git_projects
                    cached = self._repos.get(key)
                if not known or (cached is not None and cached.status is not None):
                    continue
                self._submit(self._repo(entry), "status", lambda: None)
        return self._state()

    @action
    def commit(self, path: str, message: str, push: bool = False) -> State:
        self._require_git()
        repo = self._repo(self._project(path))
        if not message.strip():
            raise ToolError("empty_message", "The commit message is empty")

        def work() -> None:
            ops.commit_all(repo.path, message)
            if push:
                ops.push(repo.path)

        if not self._submit(repo, "commit", work):
            # Dropping it would lose the typed message.
            raise ToolError("busy", "An operation is already running on this project")
        return self._state()

    @action
    def push(self, path: str) -> State:
        self._require_git()
        repo = self._repo(self._project(path))
        self._submit(repo, "push", lambda: ops.push(repo.path))
        return self._state()

    @action
    def set_remote(self, path: str, url: str) -> State:
        """Synchronous: a local read and a local write."""
        self._require_git()
        repo = self._repo(self._project(path))
        try:
            ops.add_origin(repo.path, url.strip())
        except GitOpError as exc:
            raise ToolError(exc.code, exc.message) from exc
        self._refresh(_key(repo.path), repo.path)
        return self._state()

    @action
    def clear_error(self, path: str) -> State:
        repo = self._repo(self._project(path))
        self._jobs.clear_error(_key(repo.path))
        with self._lock:
            repo.error = None
        return self._state()


SERVICE = ProjectsService
