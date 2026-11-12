import subprocess
from pathlib import Path

import pytest
from git_fixtures import commit_file, git, make_clone, make_remote

from wrench.shared.git.status import parse_porcelain_v2, read_status

pytestmark = pytest.mark.usefixtures("git_env")


def test_parse_porcelain_branch_ahead_behind() -> None:
    out = "# branch.oid abc\0# branch.head main\0# branch.upstream origin/main\0# branch.ab +2 -3\0"
    p = parse_porcelain_v2(out)
    assert (p["branch"], p["upstream"], p["ahead"], p["behind"]) == ("main", "origin/main", 2, 3)


def test_parse_detached() -> None:
    p = parse_porcelain_v2("# branch.head (detached)\0")
    assert p["branch"] is None and p["detached"] is True


def test_parse_entries_and_rename() -> None:
    out = (
        "# branch.head main\0"
        "1 M. N... 100644 100644 100644 a b staged.txt\0"
        "1 .M N... 100644 100644 100644 a b both side.txt\0"
        "2 R. N... 100644 100644 100644 a b R100 new name.txt\0old name.txt\0"
        "u UU N... 100644 100644 100644 100644 a b c conflict.txt\0"
        "? new file.txt\0"
    )
    p = parse_porcelain_v2(out)
    assert (p["staged"], p["unstaged"], p["conflicts"], p["untracked"]) == (2, 1, 1, 1)
    assert p["changed_files"] == [
        "staged.txt",
        "both side.txt",
        "new name.txt",
        "conflict.txt",
        "new file.txt",
    ]


def test_clean_clone(tmp_path: Path) -> None:
    s = read_status(make_clone(make_remote(tmp_path), tmp_path / "c"))
    assert (s.branch, s.ahead, s.behind, s.unstaged, s.untracked, s.host) == (
        "main",
        0,
        0,
        0,
        0,
        "other",
    )
    assert s.upstream == "origin/main" and s.operation is None and s.detached is False


def test_modified_untracked_and_accents(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "Mes Projets" / "Été")
    (r / "README.md").write_text("changed", "utf-8")
    (r / "nouveau é.txt").write_text("x", "utf-8")
    s = read_status(r)
    assert s.unstaged == 1 and s.untracked == 1 and "nouveau é.txt" in s.changed_files
    assert s.path == str(r)


def test_ahead_and_behind(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "f.txt", "1", "a1")
    git(a, "push")
    commit_file(b, "g.txt", "2", "b1")
    git(b, "fetch")
    s = read_status(b)
    assert (s.ahead, s.behind) == (1, 1)


def test_unpublished_branch_and_no_remote(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "switch", "-c", "feat")
    s = read_status(r)
    assert s.branch == "feat" and s.upstream is None and s.remote_url is not None
    git(r, "remote", "remove", "origin")
    s = read_status(r)
    assert s.host == "none" and s.remote_url is None


def test_detached_and_conflict(tmp_path: Path) -> None:
    rem = make_remote(tmp_path)
    a = make_clone(rem, tmp_path / "a")
    b = make_clone(rem, tmp_path / "b")
    commit_file(a, "README.md", "A", "a")
    git(a, "push")
    commit_file(b, "README.md", "B", "b")
    git(b, "fetch")
    subprocess.run(["git", "-C", str(b), "merge", "origin/main"], capture_output=True)
    s = read_status(b)
    assert s.conflicts == 1 and s.operation == "merge"
    git(a, "checkout", "--detach")
    s = read_status(a)
    assert s.detached is True and s.branch is None


def test_last_fetch(tmp_path: Path) -> None:
    r = make_clone(make_remote(tmp_path), tmp_path / "c")
    git(r, "fetch")
    assert read_status(r).last_fetch is not None
