import logging
import os
import shutil
import stat
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from git_fixtures import make_clone, make_remote

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.shared.git import ops
from wrench.shared.git.runner import GitNotFound
from wrench.tools.git_repos.manifest import MANIFEST
from wrench.tools.git_repos.service import GitReposService

pytestmark = pytest.mark.usefixtures("git_env")


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "git_repos",
        ToolStorage(tmp_path / "data" / "git_repos.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


def _force_remove(func: Callable[[str], Any], path: str, _exc: BaseException) -> None:
    """git marks its object files read-only, which Windows refuses to delete."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _configured(ctx: ToolContext, root: Path, depth: int = 2) -> GitReposService:
    svc = GitReposService(ctx)
    svc.invoke("set_config", {"roots": [str(root)], "max_depth": depth})
    return svc


def test_manifest() -> None:
    assert (MANIFEST.id, MANIFEST.category, MANIFEST.icon, MANIFEST.version) == (
        "git_repos",
        "development",
        "git-branch",
        "1.0.0",
    )


def test_config_defaults_and_validation(ctx: ToolContext) -> None:
    svc = GitReposService(ctx)
    assert svc.invoke("get_config", {}) == {"roots": [], "max_depth": 3, "missing_roots": []}
    for bad in (0, 7, 9):
        with pytest.raises(ToolError) as e:
            svc.invoke("set_config", {"roots": [], "max_depth": bad})
        assert e.value.code == "invalid_payload"


def test_config_saved_and_deduplicated(ctx: ToolContext, tmp_path: Path) -> None:
    svc = GitReposService(ctx)
    cfg = svc.invoke("set_config", {"roots": [str(tmp_path), str(tmp_path), "  "], "max_depth": 4})
    assert cfg == {"roots": [str(tmp_path)], "max_depth": 4, "missing_roots": []}
    assert ctx.storage.load() == {"roots": [str(tmp_path)], "max_depth": 4}


def test_corrupt_config_falls_back_to_defaults(ctx: ToolContext) -> None:
    ctx.storage.save({"roots": "nope", "max_depth": 42})
    assert GitReposService(ctx).invoke("get_config", {}) == {
        "roots": [],
        "max_depth": 3,
        "missing_roots": [],
    }


def test_missing_root_listed(ctx: ToolContext, tmp_path: Path) -> None:
    svc = GitReposService(ctx)
    svc.invoke("set_config", {"roots": [str(tmp_path / "gone")], "max_depth": 3})
    assert svc.invoke("get_config", {})["missing_roots"] == [str(tmp_path / "gone")]
    assert svc.invoke("rescan", {})["repos"] == []


def test_rescan_and_state(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Mes Dépôts"
    make_clone(make_remote(tmp_path), root / "Été" / "proj")
    svc = _configured(ctx, root, 3)
    st = svc.invoke("get_state", {})
    assert st["git_available"] is True and len(st["repos"]) == 1
    repo = st["repos"][0]
    assert repo["name"] == "proj" and repo["rel_path"] == os.path.join("Été", "proj")
    assert repo["root"] == str(root) and repo["running"] is None and repo["error"] is None
    assert repo["branch"] == "main" and repo["host"] == "other"


def test_unknown_repo(ctx: ToolContext) -> None:
    with pytest.raises(ToolError) as e:
        GitReposService(ctx).invoke("fetch", {"path": r"C:\nope"})
    assert e.value.code == "unknown_repo"


def test_git_missing(ctx: ToolContext, tmp_path: Path) -> None:
    def missing() -> str:
        raise GitNotFound()

    root = tmp_path / "Dev"
    (root / "r" / ".git").mkdir(parents=True)
    svc = GitReposService(ctx, git_finder=missing)
    svc.invoke("set_config", {"roots": [str(root)], "max_depth": 2})
    assert svc.invoke("get_state", {})["git_available"] is False
    for action, payload in (("fetch_all", {}), ("fetch", {"path": str(root / "r")})):
        with pytest.raises(ToolError) as e:
            svc.invoke(action, payload)
        assert e.value.code == "git_not_found"


def test_fetch_all_updates_last_fetch(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    make_clone(make_remote(tmp_path), root / "p")
    svc = _configured(ctx, root)
    svc.invoke("fetch_all", {})
    assert svc._jobs.wait_idle(30)
    repo = svc.invoke("get_state", {})["repos"][0]
    assert repo["last_fetch"] is not None and repo["error"] is None


def test_commit_and_push_in_background(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    (r / "n.txt").write_text("x", "utf-8")
    svc = _configured(ctx, root)
    svc.invoke("commit", {"path": str(r), "message": "m", "push": True})
    assert svc._jobs.wait_idle(30)
    repo = svc.invoke("get_state", {})["repos"][0]
    assert repo["ahead"] == 0 and repo["untracked"] == 0 and repo["error"] is None


def test_commit_without_push(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    (r / "n.txt").write_text("x", "utf-8")
    svc = _configured(ctx, root)
    svc.invoke("commit", {"path": str(r), "message": "m"})
    assert svc._jobs.wait_idle(30)
    assert svc.invoke("get_state", {})["repos"][0]["ahead"] == 1


def test_empty_message_is_synchronous(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    svc = _configured(ctx, root)
    with pytest.raises(ToolError) as e:
        svc.invoke("commit", {"path": str(r), "message": " "})
    assert e.value.code == "empty_message"


def test_background_error_on_its_row_then_cleared(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    svc = _configured(ctx, root)
    svc.invoke("commit", {"path": str(r), "message": "m"})  # nothing to commit
    assert svc._jobs.wait_idle(30)
    repo = svc.invoke("get_state", {})["repos"][0]
    assert repo["error"]["code"] == "nothing_to_commit"
    state = svc.invoke("clear_error", {"path": str(r)})
    assert state["repos"][0]["error"] is None


def test_double_push_runs_once(
    ctx: ToolContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    svc = _configured(ctx, root)
    gate = threading.Event()
    calls: list[Path] = []

    def slow_push(repo: Path) -> None:
        calls.append(repo)
        gate.wait(10)

    monkeypatch.setattr(ops, "push", slow_push)
    first = svc.invoke("push", {"path": str(r)})
    second = svc.invoke("push", {"path": str(r)})
    assert first["repos"][0]["running"] == "push" and second["repos"][0]["running"] == "push"
    gate.set()
    assert svc._jobs.wait_idle(30)
    assert len(calls) == 1
    assert svc.invoke("get_state", {})["repos"][0]["running"] is None


def test_deleted_repo_marked_not_a_repo(ctx: ToolContext, tmp_path: Path) -> None:
    root = tmp_path / "Dev"
    a = make_clone(make_remote(tmp_path), root / "a")
    make_clone(make_remote(tmp_path / "r2"), root / "b")
    svc = _configured(ctx, root)
    shutil.rmtree(a, onexc=_force_remove)
    svc.invoke("fetch_all", {})
    assert svc._jobs.wait_idle(30)
    repos = {x["name"]: x for x in svc.invoke("get_state", {})["repos"]}
    assert repos["a"]["error"]["code"] == "not_a_repo" and repos["b"]["error"] is None
    assert repos["a"]["branch"] == "main"  # last known state is kept


def test_fetch_all_auto_is_not_interactive(
    ctx: ToolContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    svc = _configured(ctx, root)
    seen: list[tuple[str, bool]] = []

    def record(repo: Path, interactive: bool = True) -> None:
        seen.append((repo.name, interactive))

    monkeypatch.setattr(ops, "fetch", record)
    svc.invoke("fetch_all", {"auto": True})
    assert svc._jobs.wait_idle(30)
    svc.invoke("fetch_all", {})
    assert svc._jobs.wait_idle(30)
    svc.invoke("fetch", {"path": str(r)})
    assert svc._jobs.wait_idle(30)
    assert seen == [("p", False), ("p", True), ("p", True)]


def test_commit_while_busy_is_refused(
    ctx: ToolContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "Dev"
    r = make_clone(make_remote(tmp_path), root / "p")
    (r / "n.txt").write_text("x", "utf-8")
    svc = _configured(ctx, root)
    gate = threading.Event()
    monkeypatch.setattr(ops, "fetch", lambda repo, interactive=True: gate.wait(10))
    svc.invoke("fetch", {"path": str(r)})
    with pytest.raises(ToolError) as e:
        svc.invoke("commit", {"path": str(r), "message": "m"})
    gate.set()
    assert svc._jobs.wait_idle(30)
    assert e.value.code == "busy"
    assert svc.invoke("get_state", {})["repos"][0]["untracked"] == 1
