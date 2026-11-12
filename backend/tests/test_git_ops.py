import time
from pathlib import Path

import pytest
from git_fixtures import commit_file, git, make_clone, make_remote

from wrench.shared.git.ops import GitOpError, classify_error, commit_all, fetch, pull, push
from wrench.shared.git.status import read_status

pytestmark = pytest.mark.usefixtures("git_env")


def test_fetch_then_pull_ff(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "f", "1", "x")
    git(a, "push")
    fetch(b)
    assert read_status(b).behind == 1
    pull(b)
    assert read_status(b).behind == 0


def test_pull_diverged_changes_nothing(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "f", "1", "x")
    git(a, "push")
    commit_file(b, "g", "2", "y")
    fetch(b)
    head = git(b, "rev-parse", "HEAD")
    with pytest.raises(GitOpError) as e:
        pull(b)
    assert e.value.code == "diverged" and git(b, "rev-parse", "HEAD") == head


def test_push_unpublished_branch(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "switch", "-c", "feat")
    commit_file(r, "f", "1", "x")
    push(r)
    assert read_status(r).upstream == "origin/feat"


def test_push_ahead(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    commit_file(r, "f", "1", "x")
    push(r)
    assert read_status(r).ahead == 0


def test_push_no_remote(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "remote", "remove", "origin")
    with pytest.raises(GitOpError) as e:
        push(r)
    assert e.value.code == "no_remote"


def test_fetch_no_remote(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "remote", "remove", "origin")
    with pytest.raises(GitOpError) as e:
        fetch(r)
    assert e.value.code == "no_remote"


def test_push_detached(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "checkout", "--detach")
    with pytest.raises(GitOpError) as e:
        push(r)
    assert e.value.code == "detached_head"


@pytest.mark.parametrize("msg,code", [("  ", "empty_message"), ("ok", "nothing_to_commit")])
def test_commit_refusals(tmp_path: Path, msg: str, code: str) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    with pytest.raises(GitOpError) as e:
        commit_all(r, msg)
    assert e.value.code == code


def test_commit_all(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    (r / "n.txt").write_text("x", "utf-8")
    (r / "README.md").write_text("changed", "utf-8")
    commit_all(r, "ajout")
    s = read_status(r)
    assert s.untracked == 0 and s.unstaged == 0 and s.ahead == 1
    assert git(r, "log", "-1", "--format=%s") == "ajout"


def test_commit_detached(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "checkout", "--detach")
    (r / "n").write_text("x")
    with pytest.raises(GitOpError) as e:
        commit_all(r, "m")
    assert e.value.code == "detached_head"


def test_commit_during_merge(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "README.md", "A", "a")
    git(a, "push")
    commit_file(b, "README.md", "B", "b")
    fetch(b)
    with pytest.raises(AssertionError):
        git(b, "merge", "origin/main")
    with pytest.raises(GitOpError) as e:
        commit_all(b, "m")
    assert e.value.code == "in_progress"


def test_no_prompt_on_unreachable_https(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "remote", "set-url", "origin", "https://127.0.0.1:9/x.git")
    t0 = time.monotonic()
    with pytest.raises(GitOpError) as e:
        fetch(r)
    assert e.value.code in {"auth_required", "git_failed"} and time.monotonic() - t0 < 30


def test_missing_repo_is_not_a_repo(tmp_path: Path) -> None:
    with pytest.raises(GitOpError) as e:
        fetch(tmp_path / "gone")
    assert e.value.code == "not_a_repo"


@pytest.mark.parametrize(
    "stderr,code",
    [
        ("fatal: Authentication failed for 'https://x'", "auth_required"),
        (
            "fatal: could not read Username for 'https://x': terminal prompts disabled",
            "auth_required",
        ),
        ("git@x: Permission denied (publickey).", "auth_required"),
        ("fatal: not a git repository (or any of the parent directories): .git", "not_a_repo"),
        ("fatal: Not possible to fast-forward, aborting.", "diverged"),
        ("fatal: Cannot prompt because user interactivity has been disabled.", "auth_required"),
        (" ! [rejected]        main -> main (fetch first)", "diverged"),
        (" ! [rejected]        main -> main (non-fast-forward)", "diverged"),
        ("hint: You have divergent branches", "diverged"),
        ("boom", "git_failed"),
    ],
)
def test_classify_error(stderr: str, code: str) -> None:
    assert classify_error(stderr) == code


def test_commit_refuses_conflicts_without_operation(tmp_path: Path) -> None:
    """`stash pop` leaves conflicts but no MERGE_HEAD: `add -A` would commit the markers."""
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    (r / "README.md").write_text("stashed", "utf-8")
    git(r, "stash")
    commit_file(r, "README.md", "committed", "c")
    with pytest.raises(AssertionError):
        git(r, "stash", "pop")
    s = read_status(r)
    assert s.conflicts == 1 and s.operation is None
    with pytest.raises(GitOpError) as e:
        commit_all(r, "m")
    assert e.value.code == "in_progress"
    assert "<<<<<<<" not in git(r, "show", "HEAD:README.md")


def test_push_rejected_when_diverged(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "f", "1", "x")
    git(a, "push")
    commit_file(b, "g", "2", "y")
    with pytest.raises(GitOpError) as e:
        push(b)
    assert e.value.code == "diverged"
