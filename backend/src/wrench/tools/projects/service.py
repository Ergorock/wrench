"""Projects tool: inventory of the projects under a root folder, git state on demand, and the
associated remote repository. The long work runs in the background; the front polls get_state."""

import os
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from wrench.sdk import ToolContext, ToolError, ToolService, action
from wrench.shared.editors import command_for, exe_exists
from wrench.shared.git import ops
from wrench.shared.git.jobs import RepoJobs
from wrench.shared.git.ops import GitOpError
from wrench.shared.git.remote import is_remote_url, web_url
from wrench.shared.git.runner import GitNotFound, find_git
from wrench.shared.git.status import RepoStatus, read_status
from wrench.tools.projects.build import suggest_build, suggest_run
from wrench.tools.projects.launch import Spawner, find_wt, spawn, terminal_args
from wrench.tools.projects.requirements import Requirement, Runner, check, run_version
from wrench.tools.projects.scan import FolderEntry, ProjectEntry, flatten, scan, techs_of
from wrench.tools.projects.templates import copy_template, validate_name

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


class CreationView(BaseModel):
    running: bool
    error: dict[str, str] | None
    created: str | None  # path of the new project


class State(BaseModel):
    scanning: bool
    scan_error: dict[str, str] | None
    git_available: bool
    tree: FolderEntry | None
    git: dict[str, GitView]
    creation: CreationView | None


class BuildInfo(BaseModel):
    command: str | None
    suggested: str | None


class RunInfo(BaseModel):
    command: str | None
    suggested: str | None


class EditorView(BaseModel):
    id: str
    name: str
    exe: str
    available: bool


class RequirementsView(BaseModel):
    running: bool
    items: list[Requirement] | None
    error: dict[str, str] | None


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
    def __init__(
        self,
        ctx: ToolContext,
        git_finder: Callable[[], str] = find_git,
        spawner: Spawner = spawn,
        wt_finder: Callable[[], str | None] = find_wt,
        opener: Callable[[str], bool] = webbrowser.open,
        runner: Runner = run_version,
    ) -> None:
        super().__init__(ctx)
        self._git_finder = git_finder
        self._spawner = spawner
        self._wt_finder = wt_finder
        self._opener = opener
        self._runner = runner
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
        self._requirements: dict[str, RequirementsView] = {}  # kept for the process lifetime
        self._creation: CreationView | None = None

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

    def _folder(self, path: str) -> Path:
        """The folder of a project that is still on disk; not_a_project otherwise."""
        folder = Path(self._project(path).path)
        if not folder.is_dir():
            raise ToolError("not_a_project", f"The project folder no longer exists: {path}")
        return folder

    def _build_info(self, folder: Path) -> BuildInfo:
        builds = self.ctx.storage.load().get("builds")
        saved = builds.get(_key(folder)) if isinstance(builds, dict) else None
        command = saved if isinstance(saved, str) and saved.strip() else None
        return BuildInfo(command=command, suggested=suggest_build(folder))

    def _run_info(self, folder: Path) -> RunInfo:
        runs = self.ctx.storage.load().get("runs")
        saved = runs.get(_key(folder)) if isinstance(runs, dict) else None
        command = saved if isinstance(saved, str) and saved.strip() else None
        return RunInfo(command=command, suggested=suggest_run(folder))

    def _open_terminal(self, folder: Path, command: str | None) -> None:
        self._spawner(terminal_args(folder, command, self._wt_finder()), folder, True)

    def _repo(self, entry: ProjectEntry) -> _Repo:
        key = _key(entry.path)
        with self._lock:
            repo = self._repos.get(key)
            if repo is None:
                repo = self._repos[key] = _Repo(Path(entry.path), entry)
            return repo

    def _git_repo(self, path: str) -> _Repo:
        """Like _project, and refuses a project without its own `.git`: git would act on
        the repository that contains it."""
        entry = self._project(path)
        with self._lock:
            is_git = _key(entry.path) in self._git_projects
        # Checked again now: a `.git` deleted since the scan would send git to the parent.
        if not is_git or not (Path(entry.path) / ".git").exists():
            raise ToolError("not_a_repo", f"Not a git repository: {path}")
        return self._repo(entry)

    def _state(self) -> State:
        root = self._config()[0] or ""
        with self._lock:
            repos = [(k, r.path, r.entry, r.status, r.error) for k, r in self._repos.items()]
            scanning, scan_error, tree = self._scanning, self._scan_error, self._tree
            creation = self._creation
        views: dict[str, GitView] = {}
        for key, path, entry, repo_status, repo_error in repos:
            job = self._jobs.state(key)
            status = repo_status or _blank_status(path)
            views[entry.path] = GitView(
                **status.model_dump(),
                root=root,
                name=entry.name,
                rel_path=entry.rel_path,
                web_url=web_url(status.remote_url),
                running=job.running,
                error=job.error or repo_error,
            )
        return State(
            scanning=scanning,
            scan_error=scan_error,
            git_available=self._git_available(),
            tree=tree,
            git=views,
            creation=creation,
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
        repo = self._git_repo(path)
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
        repo = self._git_repo(path)
        if not self._submit(repo, "push", lambda: ops.push(repo.path)):
            raise ToolError("busy", "An operation is already running on this repository")
        return self._state()

    @action
    def set_remote(self, path: str, url: str) -> State:
        """Synchronous: a local read and a local write."""
        self._require_git()
        repo = self._git_repo(path)
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

    # --- open, terminal, build -----------------------------------------------------

    @action
    def get_editors(self) -> list[EditorView]:
        return [
            EditorView(id=e.id, name=e.name, exe=e.exe, available=exe_exists(e))
            for e in self.ctx.editors()
        ]

    @action
    def open_in(self, path: str, editor_id: str) -> None:
        folder = self._folder(path)
        editor = next((e for e in self.ctx.editors() if e.id == editor_id), None)
        if editor is None or not exe_exists(editor):
            raise ToolError("editor_missing", f"Editor not found: {editor_id}")
        self._spawner(command_for(editor, folder), None, False)

    def _explore(self, folder: Path) -> None:
        self._spawner(["explorer.exe", str(folder)], None, False)

    @action
    def open_explorer(self, path: str) -> None:
        self._explore(self._folder(path))

    @action
    def open_folder(self, path: str) -> None:
        """Opens a folder of the inventory (the root, a group or a project) in Explorer."""
        key = _key(path)
        with self._lock:
            pending = [self._tree] if self._tree is not None else []
            found = key in self._projects
            while pending and not found:
                node = pending.pop()
                found = _key(node.path) == key
                pending.extend(node.folders)
        folder = Path(path)
        if not found or not folder.is_dir():
            raise ToolError("not_a_project", f"Not a folder of the inventory: {path}")
        self._explore(folder)

    @action
    def open_terminal(self, path: str) -> None:
        self._open_terminal(self._folder(path), None)

    @action
    def open_repo_page(self, path: str) -> None:
        """Opens the remote page of the project's own repository in the default browser."""
        repo = self._git_repo(path)
        with self._lock:
            status = repo.status
        if status is None:
            status, _error = _read(repo.path)
        url = web_url(status.remote_url) if status else None
        if url is None or not url.startswith("https://"):
            raise ToolError("invalid_url", "This project has no usable remote address")
        if not self._opener(url):
            raise ToolError("launch_failed", "The browser could not be opened")

    @action
    def get_build(self, path: str) -> BuildInfo:
        return self._build_info(self._folder(path))

    @action
    def set_build(self, path: str, command: str) -> BuildInfo:
        folder = self._folder(path)
        data = self.ctx.storage.load()
        raw = data.get("builds")
        builds: dict[str, str] = dict(raw) if isinstance(raw, dict) else {}
        if command.strip():
            builds[_key(folder)] = command.strip()
        else:
            builds.pop(_key(folder), None)
        data["builds"] = builds
        self.ctx.storage.save(data)
        return self._build_info(folder)

    @action
    def run_build(self, path: str) -> None:
        """Runs the saved (else suggested) command in the user's own new terminal window."""
        folder = self._folder(path)
        info = self._build_info(folder)
        command = info.command or info.suggested
        if command is None:
            raise ToolError("no_build_command", "No build command is saved or suggested")
        self._open_terminal(folder, command)

    @action
    def get_run(self, path: str) -> RunInfo:
        return self._run_info(self._folder(path))

    @action
    def set_run(self, path: str, command: str) -> RunInfo:
        folder = self._folder(path)
        data = self.ctx.storage.load()
        raw = data.get("runs")
        runs: dict[str, str] = dict(raw) if isinstance(raw, dict) else {}
        if command.strip():
            runs[_key(folder)] = command.strip()
        else:
            runs.pop(_key(folder), None)
        data["runs"] = runs
        self.ctx.storage.save(data)
        return self._run_info(folder)

    @action
    def run_run(self, path: str) -> None:
        """Runs the saved (else suggested) launch command in a new terminal window."""
        folder = self._folder(path)
        info = self._run_info(folder)
        command = info.command or info.suggested
        if command is None:
            raise ToolError("no_run_command", "No run command is saved or suggested")
        self._open_terminal(folder, command)

    # --- requirements --------------------------------------------------------------

    def _run_check(self, key: str, folder: Path) -> None:
        try:
            view = RequirementsView(running=False, items=check(folder, self._runner), error=None)
        except Exception as exc:
            self.ctx.logger.exception("Requirements check failed")
            view = RequirementsView(
                running=False, items=None, error={"code": "check_failed", "message": str(exc)}
            )
        with self._lock:
            self._requirements[key] = view

    @action
    def check_requirements(self, path: str) -> RequirementsView:
        """Starts the check in the background; get_requirements reads the result."""
        folder = self._folder(path)
        key = _key(folder)
        running = RequirementsView(running=True, items=None, error=None)
        with self._lock:
            current = self._requirements.get(key)
            if current is not None and current.running:
                return current
            self._requirements[key] = running
        threading.Thread(
            target=self._run_check, args=(key, folder), name="projects-requirements", daemon=True
        ).start()
        return running

    @action
    def get_requirements(self, path: str) -> RequirementsView:
        key = _key(self._project(path).path)
        with self._lock:
            view = self._requirements.get(key)
        return view or RequirementsView(running=False, items=None, error=None)

    # --- creation from a template --------------------------------------------------

    def _templates_dir(self) -> Path:
        templates = self._config()[1]
        if templates is None or not Path(templates).is_dir():
            raise ToolError("templates_missing", "The templates folder was not found")
        return Path(templates)

    @action
    def list_templates(self) -> list[str]:
        folder = self._templates_dir()
        try:
            names = [e.name for e in folder.iterdir() if e.is_dir()]
        except OSError as exc:
            raise ToolError("templates_missing", str(exc)) from exc
        return sorted(names, key=str.casefold)

    def _chain(self, parent_rel: str) -> list[FolderEntry]:
        """The folders from the root down to `parent_rel` ("" is the root); not_a_project
        when it is not a folder of the inventory. The caller holds the lock."""
        node = self._tree
        if node is None:
            raise ToolError("not_a_project", "No inventory yet")
        chain = [node]
        for part in parent_rel.split(os.sep) if parent_rel else []:
            node = next((f for f in node.folders if f.name == part), None)
            if node is None:
                raise ToolError("not_a_project", f"Not a folder of the inventory: {parent_rel}")
            chain.append(node)
        return chain

    @action
    def create_project(
        self, template: str, name: str, parent_rel: str, remote_url: str | None
    ) -> State:
        """Validates synchronously, then copies in the background (see State.creation)."""
        validate_name(name)
        url = remote_url.strip() if remote_url and remote_url.strip() else None
        if url is not None and not is_remote_url(url):
            raise ToolError("invalid_url", "Not a valid remote URL")
        if template not in self.list_templates():
            raise ToolError("templates_missing", f"Template not found: {template}")
        with self._lock:
            parent = Path(self._chain(parent_rel)[-1].path)
        if not parent.is_dir():
            raise ToolError("not_a_project", f"The folder no longer exists: {parent_rel}")
        target = parent / name
        if os.path.lexists(target):
            raise ToolError("target_exists", f"{name} already exists in this folder")
        with self._lock:
            if self._creation is not None and self._creation.running:
                raise ToolError("busy", "A creation is already running")
            self._creation = CreationView(running=True, error=None, created=None)
        threading.Thread(
            target=self._create,
            args=(self._templates_dir() / template, target, parent_rel, url),
            name="projects-create",
            daemon=True,
        ).start()
        return self._state()

    def _create(self, src: Path, target: Path, parent_rel: str, url: str | None) -> None:
        error: dict[str, str] | None = None
        created: str | None = None
        try:
            copy_template(src, target)
            created = str(target)
            if self._git_available():
                try:
                    ops.init_repo(target)
                    if url is not None:
                        ops.add_origin(target, url)
                except GitOpError as exc:
                    error = {"code": exc.code, "message": exc.message}
            self._insert(target, parent_rel)
        except ToolError as exc:
            error = {"code": exc.code, "message": exc.message}
        except Exception as exc:
            self.ctx.logger.exception("Project creation failed")
            error = {"code": "copy_failed", "message": str(exc)}
        with self._lock:
            self._creation = CreationView(running=False, error=error, created=created)

    def _insert(self, target: Path, parent_rel: str) -> None:
        """Adds the new project to the in-memory inventory, without a rescan."""
        rel = f"{parent_rel}{os.sep}{target.name}" if parent_rel else target.name
        entry = ProjectEntry(
            name=target.name,
            path=str(target),
            rel_path=rel,
            techs=techs_of(target),
            is_template=False,
        )
        with self._lock:
            if self._scanning:
                self._rescan_again = True  # a scan begun before the copy would drop it
            try:
                chain = self._chain(parent_rel)
            except ToolError:
                return  # the inventory changed meanwhile: the next scan will find it
            chain[-1].projects.append(entry)
            chain[-1].projects.sort(key=lambda p: p.name.casefold())
            for folder in chain:
                folder.project_count += 1
            key = _key(target)
            self._projects[key] = entry
            if (target / ".git").exists():
                self._git_projects.add(key)

    @action
    def clear_creation(self) -> State:
        with self._lock:
            if self._creation is not None and not self._creation.running:
                self._creation = None
        return self._state()


SERVICE = ProjectsService
