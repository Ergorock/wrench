import logging
import os
import shutil
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from git_fixtures import commit_file, git, make_clone, make_remote

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.shared.editors import Editor
from wrench.shared.git.runner import GitNotFound
from wrench.tools.projects.service import ProjectsService

pytestmark = pytest.mark.usefixtures("git_env")


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "projects",
        ToolStorage(tmp_path / "data" / "projects.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


def wait_until(check: Callable[[], bool], timeout: float = 15.0) -> None:
    end = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < end, "timeout"
        time.sleep(0.02)


def settled(svc: ProjectsService) -> dict[str, Any]:
    wait_until(lambda: not svc.invoke("get_state", {})["scanning"])
    state: dict[str, Any] = svc.invoke("get_state", {})
    return state


def idle(svc: ProjectsService) -> dict[str, Any]:
    wait_until(
        lambda: all(v["running"] is None for v in svc.invoke("get_state", {})["git"].values())
    )
    state: dict[str, Any] = svc.invoke("get_state", {})
    return state


def make_git_project(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    commit_file(path, "README.md", "x", "init")
    return path


def force_remove(func: Callable[[str], Any], path: str, _exc: BaseException) -> None:
    """git marks its object files read-only, which Windows refuses to delete."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def configured(ctx: ToolContext, root: Path, **kw: Any) -> ProjectsService:
    svc = ProjectsService(ctx, **kw)
    svc.invoke("set_config", {"root": str(root), "templates_dir": None, "max_depth": 4})
    settled(svc)
    return svc


def test_config_defaults_and_bounds(ctx: ToolContext) -> None:
    svc = ProjectsService(ctx)
    assert svc.invoke("get_config", {}) == {
        "root": None,
        "templates_dir": None,
        "max_depth": 4,
        "root_missing": False,
        "templates_missing": False,
    }
    for bad in (0, 7):
        with pytest.raises(ToolError) as e:
            svc.invoke("set_config", {"root": None, "templates_dir": None, "max_depth": bad})
        assert e.value.code == "invalid_payload"


def test_config_reports_missing_folders(ctx: ToolContext, tmp_path: Path) -> None:
    svc = ProjectsService(ctx)
    cfg = svc.invoke(
        "set_config",
        {"root": str(tmp_path / "nope"), "templates_dir": str(tmp_path / "t"), "max_depth": 3},
    )
    assert cfg["root_missing"] and cfg["templates_missing"] and cfg["max_depth"] == 3
    state = settled(svc)
    assert state["tree"] is None and state["scan_error"] is None


def test_set_config_keeps_project_data(ctx: ToolContext, tmp_path: Path) -> None:
    ctx.storage.save({"projects": {"k": {"build_command": "make"}}})
    svc = ProjectsService(ctx)
    svc.invoke("set_config", {"root": str(tmp_path), "templates_dir": None, "max_depth": 2})
    settled(svc)
    assert ctx.storage.load()["projects"] == {"k": {"build_command": "make"}}
    assert ctx.storage.load()["max_depth"] == 2


def test_scan_runs_in_background_and_lists_tree(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    make_git_project(root / "M3", "Liste")
    (root / "plain").mkdir()
    ctx.storage.save({"root": str(root), "max_depth": 4})
    svc = ProjectsService(ctx)
    first = svc.invoke("get_state", {})  # starts the first scan
    assert first["git_available"] is True
    state = settled(svc)
    assert state["tree"]["project_count"] == 1
    assert [f["name"] for f in state["tree"]["folders"]] == ["M3", "plain"]
    assert state["git"] == {} and state["creation"] is None


def test_rescan_during_scan_ends_with_fresh_tree(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    make_git_project(root, "a")
    svc = configured(ctx, root)
    for _ in range(5):
        svc.invoke("rescan", {})
    make_git_project(root, "b")
    svc.invoke("rescan", {})
    wait_until(lambda: svc.invoke("get_state", {})["tree"]["project_count"] == 2)
    assert settled(svc)["scanning"] is False


def test_load_status_reads_only_requested_git_projects(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")
    make_git_project(root, "b")
    (root / "plain").mkdir()
    (root / "plain" / "README.md").touch()
    svc = configured(ctx, root)
    svc.invoke("load_status", {"paths": [str(a), str(root / "plain")]})
    state = idle(svc)
    assert list(state["git"]) == [str(a)]
    view = state["git"][str(a)]
    assert view["branch"] == "main" and view["name"] == "a" and view["rel_path"] == "a"
    assert view["root"] == str(root) and view["error"] is None and view["running"] is None


def test_load_status_error_isolated(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")
    b = make_git_project(root, "b")
    svc = configured(ctx, root)
    shutil.rmtree(a, onerror=force_remove)
    svc.invoke("load_status", {"paths": [str(a), str(b)]})
    state = idle(svc)
    assert state["git"][str(a)]["error"] is not None
    assert state["git"][str(b)]["error"] is None
    assert state["git"][str(b)]["branch"] == "main"


def test_rescan_clears_git_cache(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")
    svc = configured(ctx, root)
    svc.invoke("load_status", {"paths": [str(a)]})
    assert list(idle(svc)["git"]) == [str(a)]
    svc.invoke("rescan", {})
    assert settled(svc)["git"] == {}


def test_not_a_project(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    make_git_project(root, "a")
    svc = configured(ctx, root)
    other = tmp_path / "elsewhere"
    other.mkdir()
    for action, payload in [
        ("push", {"path": str(other)}),
        ("commit", {"path": str(other), "message": "m"}),
        ("set_remote", {"path": str(other), "url": "https://h/a/b"}),
        ("clear_error", {"path": str(other)}),
        ("load_status", {"paths": [str(other)]}),
    ]:
        with pytest.raises(ToolError) as e:
            svc.invoke(action, payload)
        assert e.value.code == "not_a_project", action


def test_set_remote_adds_origin_and_refuses_existing(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")
    b = make_git_project(root, "b")
    svc = configured(ctx, root)
    state = svc.invoke("set_remote", {"path": str(a), "url": "https://example.org/t/a.git"})
    assert state["git"][str(a)]["remote_url"] == "https://example.org/t/a.git"
    assert state["git"][str(a)]["web_url"] == "https://example.org/t/a"
    with pytest.raises(ToolError) as e:
        svc.invoke("set_remote", {"path": str(a), "url": "https://example.org/t/b.git"})
    assert e.value.code == "remote_exists"
    with pytest.raises(ToolError) as e:
        svc.invoke("set_remote", {"path": str(b), "url": "--upload-pack=x"})
    assert e.value.code == "invalid_url"


def test_commit_and_push(ctx: ToolContext, tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    root = tmp_path / "dev"
    a = make_clone(rem, root / "a")
    svc = configured(ctx, root)
    (a / "new.txt").write_text("x", "utf-8")
    svc.invoke("commit", {"path": str(a), "message": "add", "push": True})
    state = idle(svc)
    assert state["git"][str(a)]["error"] is None
    assert git(rem, "log", "--format=%s", "-1") == "add"
    with pytest.raises(ToolError) as e:
        svc.invoke("commit", {"path": str(a), "message": "  "})
    assert e.value.code == "empty_message"
    svc.invoke("commit", {"path": str(a), "message": "again"})
    state = idle(svc)
    assert state["git"][str(a)]["error"]["code"] == "nothing_to_commit"
    state = svc.invoke("clear_error", {"path": str(a)})
    assert state["git"][str(a)]["error"] is None


def test_git_missing(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")

    def no_git() -> str:
        raise GitNotFound("no git")

    svc = configured(ctx, root, git_finder=no_git)
    state = settled(svc)
    assert state["git_available"] is False
    assert state["tree"]["project_count"] == 1
    with pytest.raises(ToolError) as e:
        svc.invoke("push", {"path": str(a)})
    assert e.value.code == "git_not_found"


def test_non_git_project_inside_a_repo_is_refused(ctx: ToolContext, tmp_path: Path) -> None:
    # The root is a git repository; its sub-folder is a project (README) with no `.git`.
    parent = make_git_project(tmp_path, "parent")
    git(parent, "remote", "add", "origin", "https://example.org/p/parent.git")
    child = parent / "sub"
    child.mkdir()
    (child / "README.md").touch()
    svc = configured(ctx, parent)
    assert [p["path"] for p in settled(svc)["tree"]["projects"]] == [str(child)]
    for action, payload in [
        ("commit", {"path": str(child), "message": "m"}),
        ("push", {"path": str(child)}),
        ("set_remote", {"path": str(child), "url": "https://example.org/x/y.git"}),
    ]:
        with pytest.raises(ToolError) as e:
            svc.invoke(action, payload)
        assert e.value.code == "not_a_repo", action
    assert git(parent, "remote", "get-url", "origin") == "https://example.org/p/parent.git"


def test_push_busy(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    a = make_git_project(root, "a")
    svc = configured(ctx, root)
    release = threading.Event()
    key = os.path.normcase(str(a.resolve()))
    assert svc._jobs.submit(key, "fetch", lambda: release.wait(10))
    try:
        with pytest.raises(ToolError) as e:
            svc.invoke("push", {"path": str(a)})
        assert e.value.code == "busy"
    finally:
        release.set()


# --- open, terminal, build ---------------------------------------------------------


class Spawned:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []
        self.consoles: list[bool] = []

    def __call__(self, args: list[str], cwd: Path | None, console: bool) -> None:
        self.calls.append((args, cwd))
        self.consoles.append(console)


def launch_service(
    ctx: ToolContext, tmp_path: Path, editors: list[Editor] | None = None, **kw: Any
) -> tuple[ProjectsService, Spawned, Path]:
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    (root / "a" / "pyproject.toml").write_text("", encoding="utf-8")
    if editors is not None:
        ctx._get_editors = lambda: editors  # noqa: SLF001
    spawned = Spawned()
    svc = configured(ctx, root, spawner=spawned, wt_finder=lambda: None, **kw)
    return svc, spawned, root / "a"


def vscode(tmp_path: Path) -> Editor:
    exe = tmp_path / "Code.exe"
    exe.write_text("", encoding="utf-8")
    return Editor(id="vscode", name="VS Code", exe=str(exe), args=["{path}"])


def test_open_in_passes_project_path(ctx: ToolContext, tmp_path: Path) -> None:
    ed = vscode(tmp_path)
    svc, spawned, a = launch_service(ctx, tmp_path, [ed])
    svc.invoke("open_in", {"path": str(a), "editor_id": "vscode"})
    assert spawned.calls == [([ed.exe, str(a)], None)]


def test_open_in_missing_exe_or_unknown_editor(ctx: ToolContext, tmp_path: Path) -> None:
    ed = Editor(id="vscode", name="VS Code", exe=str(tmp_path / "absent.exe"), args=["{path}"])
    svc, spawned, a = launch_service(ctx, tmp_path, [ed])
    for editor_id in ("vscode", "other"):
        with pytest.raises(ToolError) as exc:
            svc.invoke("open_in", {"path": str(a), "editor_id": editor_id})
        assert exc.value.code == "editor_missing"
    assert spawned.calls == []


def test_open_in_removed_project_is_not_a_project(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path, [vscode(tmp_path)])
    shutil.rmtree(a)
    with pytest.raises(ToolError) as exc:
        svc.invoke("open_in", {"path": str(a), "editor_id": "vscode"})
    assert exc.value.code == "not_a_project"
    assert spawned.calls == []


def test_launch_actions_refuse_unknown_path(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, _a = launch_service(ctx, tmp_path)
    other = str(tmp_path / "elsewhere")
    for name, args in (
        ("open_in", {"editor_id": "x"}),
        ("open_explorer", {}),
        ("open_terminal", {}),
        ("get_build", {}),
        ("set_build", {"command": "x"}),
        ("run_build", {}),
        ("open_repo_page", {}),
    ):
        with pytest.raises(ToolError) as exc:
            svc.invoke(name, {"path": other, **args})
        assert exc.value.code == "not_a_project", name
    assert spawned.calls == []


def test_open_explorer_and_terminal(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path)
    svc.invoke("open_explorer", {"path": str(a)})
    svc.invoke("open_terminal", {"path": str(a)})
    assert spawned.calls[0] == (["explorer.exe", str(a)], None)
    assert spawned.calls[1][0][:3] == ["powershell", "-NoExit", "-Command"]
    assert spawned.consoles == [False, True]


def test_open_terminal_prefers_wt(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path)
    svc._wt_finder = lambda: "wt.exe"  # noqa: SLF001
    svc.invoke("open_terminal", {"path": str(a)})
    assert spawned.calls == [(["wt.exe", "-d", str(a)], a)]
    assert spawned.consoles == [True]


def test_build_saved_suggested_and_cleared(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path)
    assert svc.invoke("get_build", {"path": str(a)}) == {"command": None, "suggested": None}
    command = 'npm run build -- --mode "prod x"'
    info = svc.invoke("set_build", {"path": str(a), "command": f"  {command}  "})
    assert info == {"command": command, "suggested": None}
    svc.invoke("run_build", {"path": str(a)})
    assert spawned.calls == [
        (["powershell", "-NoExit", "-Command", f"Set-Location -LiteralPath '{a}'; {command}"], a)
    ]
    assert spawned.consoles == [True]
    assert svc.invoke("set_build", {"path": str(a), "command": "  "})["command"] is None
    with pytest.raises(ToolError) as exc:
        svc.invoke("run_build", {"path": str(a)})
    assert exc.value.code == "no_build_command"


def test_run_build_with_wt_escapes_semicolons(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path)
    svc._wt_finder = lambda: "wt.exe"  # noqa: SLF001
    command = 'npm run build -- --mode "prod x"; echo ok'
    svc.invoke("set_build", {"path": str(a), "command": command})
    svc.invoke("run_build", {"path": str(a)})
    escaped = 'npm run build -- --mode "prod x"\\; echo ok'
    assert spawned.calls == [
        (["wt.exe", "-d", str(a), "powershell", "-NoExit", "-Command", escaped], a)
    ]
    assert spawned.consoles == [True]


def test_run_build_apostrophe_path_fallback(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "root"
    folder = root / "l'été"
    folder.mkdir(parents=True)
    (folder / "go.mod").write_text("", encoding="utf-8")
    spawned = Spawned()
    svc = configured(ctx, root, spawner=spawned, wt_finder=lambda: None)
    svc.invoke("run_build", {"path": str(folder)})
    quoted = str(folder).replace("'", "''")
    assert spawned.calls == [
        (
            [
                "powershell",
                "-NoExit",
                "-Command",
                f"Set-Location -LiteralPath '{quoted}'; go build ./...",
            ],
            folder,
        )
    ]


def test_set_build_empty_returns_to_suggestion(ctx: ToolContext, tmp_path: Path) -> None:
    svc, spawned, a = launch_service(ctx, tmp_path)
    (a / "uv.lock").write_text("", encoding="utf-8")
    svc.invoke("set_build", {"path": str(a), "command": "make"})
    info = svc.invoke("set_build", {"path": str(a), "command": ""})
    assert info == {"command": None, "suggested": "uv build"}
    svc.invoke("run_build", {"path": str(a)})
    assert spawned.calls[-1][0][-1] == f"Set-Location -LiteralPath '{a}'; uv build"


def test_get_editors_marks_availability(ctx: ToolContext, tmp_path: Path) -> None:
    ed = vscode(tmp_path)
    absent = str(tmp_path / "absent.exe")
    eds = [ed, Editor(id="kiro", name="Kiro", exe=absent)]
    svc, _s, _a = launch_service(ctx, tmp_path, eds)
    assert svc.invoke("get_editors", {}) == [
        {"id": "vscode", "name": "VS Code", "exe": ed.exe, "available": True},
        {"id": "kiro", "name": "Kiro", "exe": absent, "available": False},
    ]


def test_open_repo_page(ctx: ToolContext, tmp_path: Path) -> None:
    opened: list[str] = []
    root = tmp_path / "root"
    a = make_git_project(root, "a")
    git(a, "remote", "add", "origin", "git@github.com:x/a.git")
    b = make_git_project(root, "b")
    (root / "c").mkdir()
    (root / "c" / "pyproject.toml").write_text("", encoding="utf-8")
    svc = configured(ctx, root, opener=lambda u: opened.append(u) or True)
    svc.invoke("open_repo_page", {"path": str(a)})
    assert opened == ["https://github.com/x/a"]
    with pytest.raises(ToolError) as exc:
        svc.invoke("open_repo_page", {"path": str(b)})
    assert exc.value.code == "invalid_url"
    with pytest.raises(ToolError) as exc2:
        svc.invoke("open_repo_page", {"path": str(root / "c")})
    assert exc2.value.code == "not_a_repo"


def test_open_repo_page_failed_open(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "root"
    a = make_git_project(root, "a")
    git(a, "remote", "add", "origin", "https://github.com/x/a.git")
    svc = configured(ctx, root, opener=lambda _u: False)
    with pytest.raises(ToolError) as exc:
        svc.invoke("open_repo_page", {"path": str(a)})
    assert exc.value.code == "launch_failed"


def test_requirements_check_runs_in_background_and_is_read_back(
    ctx: ToolContext, tmp_path: Path
) -> None:
    ran: list[Any] = []

    def runner(cmd: Any) -> str | None:
        ran.append(list(cmd))
        return "Python 3.12.4"

    svc, _spawned, a = launch_service(ctx, tmp_path, runner=runner)
    (a / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n', encoding="utf-8")
    assert svc.invoke("get_requirements", {"path": str(a)}) == {
        "running": False,
        "items": None,
        "error": None,
    }
    started = svc.invoke("check_requirements", {"path": str(a)})
    assert started == {"running": True, "items": None, "error": None}
    wait_until(lambda: not svc.invoke("get_requirements", {"path": str(a)})["running"])
    view = svc.invoke("get_requirements", {"path": str(a)})
    assert view["error"] is None
    assert [(i["tool"], i["status"], i["installed"]) for i in view["items"]] == [
        ("Python", "ok", "3.12.4")
    ]
    assert ran == [["py", "-3", "--version"]]


def test_requirements_check_failure_is_reported(ctx: ToolContext, tmp_path: Path) -> None:
    def runner(cmd: Any) -> str | None:
        raise RuntimeError("boom")

    svc, _spawned, a = launch_service(ctx, tmp_path, runner=runner)
    (a / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n', encoding="utf-8")
    svc.invoke("check_requirements", {"path": str(a)})
    wait_until(lambda: not svc.invoke("get_requirements", {"path": str(a)})["running"])
    view = svc.invoke("get_requirements", {"path": str(a)})
    assert view["items"] is None
    assert view["error"]["code"] == "check_failed"


def test_requirements_refuse_unknown_path(ctx: ToolContext, tmp_path: Path) -> None:
    svc, _spawned, _a = launch_service(ctx, tmp_path, runner=lambda cmd: None)
    for name in ("check_requirements", "get_requirements"):
        with pytest.raises(ToolError) as exc:
            svc.invoke(name, {"path": str(tmp_path / "elsewhere")})
        assert exc.value.code == "not_a_project", name


# --- creation from a template ------------------------------------------------------


def make_templates(tmp_path: Path) -> Path:
    tpl = tmp_path / "tpls"
    (tpl / "Basic" / ".git").mkdir(parents=True)
    (tpl / "Basic" / ".git" / "HEAD").write_text("x", "utf-8")
    (tpl / "Basic" / "README.md").write_text("# t", "utf-8")
    (tpl / "Alpha").mkdir()
    return tpl


def creating(ctx: ToolContext, root: Path, tpl: Path, **kw: Any) -> ProjectsService:
    svc = ProjectsService(ctx, **kw)
    svc.invoke("set_config", {"root": str(root), "templates_dir": str(tpl), "max_depth": 4})
    settled(svc)
    return svc


def created(svc: ProjectsService) -> dict[str, Any]:
    wait_until(lambda: svc.invoke("get_state", {})["creation"]["running"] is False)
    state: dict[str, Any] = svc.invoke("get_state", {})
    return state


def test_list_templates(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    svc = creating(ctx, root, make_templates(tmp_path))
    assert svc.invoke("list_templates", {}) == ["Alpha", "Basic"]
    svc.invoke(
        "set_config", {"root": str(root), "templates_dir": str(tmp_path / "no"), "max_depth": 4}
    )
    with pytest.raises(ToolError) as e:
        svc.invoke("list_templates", {})
    assert e.value.code == "templates_missing"


def test_create_project(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    (root / "perso").mkdir(parents=True)
    (root / "perso" / "x" / ".git").mkdir(parents=True)
    svc = creating(ctx, root, make_templates(tmp_path))
    url = "https://example.com/me/new.git"
    svc.invoke(
        "create_project",
        {"template": "Basic", "name": "New", "parent_rel": "perso", "remote_url": url},
    )
    state = created(svc)
    assert state["creation"]["error"] is None
    target = root / "perso" / "New"
    assert state["creation"]["created"] == str(target)
    assert (target / ".git").is_dir()
    assert git(target, "remote", "get-url", "origin").strip() == url
    perso = next(f for f in state["tree"]["folders"] if f["name"] == "perso")
    assert [p["name"] for p in perso["projects"]] == ["New", "x"]
    assert perso["project_count"] == 2
    assert state["tree"]["project_count"] == 2
    # The new project is a known project: its actions work without a rescan.
    svc.invoke("get_build", {"path": str(target)})
    svc.invoke("clear_creation", {})
    assert svc.invoke("get_state", {})["creation"] is None


def test_create_at_root_and_without_git(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()

    def no_git() -> str:
        raise GitNotFound("no git")

    svc = creating(ctx, root, make_templates(tmp_path), git_finder=no_git)
    svc.invoke(
        "create_project", {"template": "Basic", "name": "N", "parent_rel": "", "remote_url": None}
    )
    state = created(svc)
    assert state["creation"]["error"] is None
    assert not (root / "N" / ".git").exists()
    assert (root / "N" / "README.md").is_file()
    assert [p["name"] for p in state["tree"]["projects"]] == ["N"]


def test_create_refusals(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "dev"
    (root / "Taken").mkdir(parents=True)
    svc = creating(ctx, root, make_templates(tmp_path))

    def refused(**kw: Any) -> str:
        args = {"template": "Basic", "name": "N", "parent_rel": "", "remote_url": None, **kw}
        with pytest.raises(ToolError) as e:
            svc.invoke("create_project", args)
        return e.value.code

    assert refused(name="Taken") == "target_exists"
    assert refused(name="a:b") == "invalid_name"
    assert refused(remote_url="ftp://x") == "invalid_url"
    assert refused(parent_rel="nope") == "not_a_project"
    assert refused(template="..") == "templates_missing"
    assert not (root / "N").exists()
    assert svc.invoke("get_state", {})["creation"] is None


def test_create_failure_reported(
    ctx: ToolContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    svc = creating(ctx, root, make_templates(tmp_path))

    def failing(_src: Path, dst: Path, **_kw: Any) -> None:
        dst.mkdir()
        raise OSError("boom")

    monkeypatch.setattr(shutil, "copytree", failing)
    svc.invoke(
        "create_project", {"template": "Basic", "name": "N", "parent_rel": "", "remote_url": None}
    )
    state = created(svc)
    assert state["creation"]["error"]["code"] == "copy_failed"
    assert state["creation"]["created"] is None
    assert not (root / "N").exists()
    assert state["tree"]["projects"] == []
