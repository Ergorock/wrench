from pathlib import Path

import pytest
from git_fixtures import commit_file, git, make_clone, make_remote

from wrench.shared.git.errors import GitOpError
from wrench.shared.git.history import BranchList, LocalBranch, list_branches, list_commits

pytestmark = pytest.mark.usefixtures("git_env")


def _clone(tmp_path: Path) -> Path:
    return make_clone(make_remote(tmp_path), tmp_path / "work")


def _local(branches: BranchList, name: str) -> LocalBranch:
    return next(b for b in branches.local if b.name == name)


# --- list_branches -------------------------------------------------------------------


def test_merged_and_not_merged_branches(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    git(repo, "switch", "-c", "done")
    commit_file(repo, "done.txt", "d", "done work")
    git(repo, "switch", "main")
    git(repo, "merge", "--ff-only", "done")
    git(repo, "switch", "-c", "feature/x")
    commit_file(repo, "x1.txt", "1", "x one")
    commit_file(repo, "x2.txt", "2", "x two")

    branches = list_branches(repo)

    assert branches.main == "main"
    # The current branch comes first.
    assert branches.local[0].name == "feature/x" and branches.local[0].current
    done = _local(branches, "done")
    assert (done.merged, done.commits_not_in_main) == (True, 0)
    feature = _local(branches, "feature/x")
    assert (feature.merged, feature.commits_not_in_main) == (False, 2)
    main = _local(branches, "main")
    # The main branch is the reference: no merge indicator on itself.
    assert (main.merged, main.commits_not_in_main) == (None, None)
    assert main.last_commit is not None


def test_remote_branches_without_origin_head(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    git(repo, "switch", "-c", "feature/y")
    commit_file(repo, "y.txt", "y", "y")
    git(repo, "push", "-u", "origin", "feature/y")
    git(repo, "remote", "set-head", "origin", "main")

    branches = list_branches(repo)

    assert sorted(b.name for b in branches.remote) == ["origin/feature/y", "origin/main"]
    assert all(b.last_commit is not None for b in branches.remote)
    feature = _local(branches, "feature/y")
    assert feature.upstream == "origin/feature/y"


def test_ahead_behind_of_local_branch(tmp_path: Path) -> None:
    remote = make_remote(tmp_path)
    repo = make_clone(remote, tmp_path / "a")
    other = make_clone(remote, tmp_path / "b")
    commit_file(other, "o1.txt", "1", "o1")
    commit_file(other, "o2.txt", "2", "o2")
    git(other, "push")
    commit_file(repo, "mine.txt", "m", "mine")
    git(repo, "fetch")

    main = _local(list_branches(repo), "main")

    assert main.upstream == "origin/main"
    assert (main.ahead, main.behind) == (1, 2)


def test_branch_without_upstream(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    git(repo, "branch", "local-only")
    b = _local(list_branches(repo), "local-only")
    assert (b.upstream, b.ahead, b.behind) == (None, 0, 0)


def test_main_is_master_when_no_main(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-b", "master")
    commit_file(repo, "a.txt", "a", "a")
    git(repo, "switch", "-c", "topic")
    commit_file(repo, "b.txt", "b", "b")

    branches = list_branches(repo)

    assert branches.main == "master"
    topic = _local(branches, "topic")
    assert (topic.merged, topic.commits_not_in_main) == (False, 1)
    assert branches.remote == []


def test_main_from_origin_head(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare", "-b", "develop")
    seed = tmp_path / "seed"
    git(tmp_path, "clone", str(remote), "seed")
    git(seed, "switch", "-c", "develop")
    commit_file(seed, "a.txt", "a", "a")
    git(seed, "push", "-u", "origin", "develop")
    git(tmp_path, "clone", str(remote), "work")
    repo = tmp_path / "work"
    git(repo, "switch", "-c", "topic")
    commit_file(repo, "t.txt", "t", "t")

    branches = list_branches(repo)

    assert branches.main == "origin/develop"
    topic = _local(branches, "topic")
    assert (topic.merged, topic.commits_not_in_main) == (False, 1)
    develop = _local(branches, "develop")
    assert (develop.merged, develop.commits_not_in_main) == (True, 0)


def test_no_main_branch(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-b", "trunk")
    commit_file(repo, "a.txt", "a", "a")

    branches = list_branches(repo)

    assert branches.main is None
    trunk = _local(branches, "trunk")
    assert (trunk.merged, trunk.commits_not_in_main) == (None, None)


def test_branches_of_a_repository_without_commits(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    branches = list_branches(repo)
    assert (branches.main, branches.local, branches.remote) == (None, [], [])


# --- list_commits --------------------------------------------------------------------


def test_commits_of_current_branch_with_full_message(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    (repo / "b.txt").write_text("b", "utf-8")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-m", "subject line", "-m", "body line 1\nbody line 2")

    commits = list_commits(repo, None, 0)

    assert [c.subject for c in commits] == ["subject line", "initial"]
    first = commits[0]
    assert first.message == "subject line\n\nbody line 1\nbody line 2"
    assert first.author == "Test"
    assert len(first.hash) == 40 and first.hash.startswith(first.short_hash)
    assert first.date.tzinfo is not None


def test_unpushed_commits(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    commit_file(repo, "1.txt", "1", "one")
    commit_file(repo, "2.txt", "2", "two")

    commits = list_commits(repo, None, 0)

    assert [(c.subject, c.unpushed) for c in commits] == [
        ("two", True),
        ("one", True),
        ("initial", False),
    ]


def test_no_unpushed_marks_without_upstream(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    git(repo, "switch", "-c", "local-only")
    commit_file(repo, "1.txt", "1", "one")
    assert not any(c.unpushed for c in list_commits(repo, None, 0))
    assert not any(c.unpushed for c in list_commits(repo, "origin/main", 0))


def test_pagination_with_skip(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    for i in range(1, 6):
        commit_file(repo, f"{i}.txt", str(i), f"c{i}")

    page1 = list_commits(repo, None, 0, limit=2)
    page2 = list_commits(repo, None, 2, limit=2)
    page4 = list_commits(repo, None, 6, limit=2)

    assert [c.subject for c in page1] == ["c5", "c4"]
    assert [c.subject for c in page2] == ["c3", "c2"]
    assert page4 == []


def test_commits_of_a_slashed_branch(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    git(repo, "switch", "-c", "feature/x")
    commit_file(repo, "x.txt", "x", "on feature")
    git(repo, "switch", "main")

    commits = list_commits(repo, "feature/x", 0)

    assert [c.subject for c in commits] == ["on feature", "initial"]
    assert commits[0].unpushed is False  # no upstream


def test_commits_of_a_remote_branch(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    commit_file(repo, "1.txt", "1", "local only")
    assert [c.subject for c in list_commits(repo, "origin/main", 0)] == ["initial"]


@pytest.mark.parametrize(
    "ref", ["nope", "-n1", "--output=out.txt", "--all", "HEAD~1", "main..feature", ""]
)
def test_unknown_or_option_like_ref_refused(tmp_path: Path, ref: str) -> None:
    repo = _clone(tmp_path)
    with pytest.raises(GitOpError) as e:
        list_commits(repo, ref, 0)
    assert e.value.code == "unknown_ref"
    assert not (repo / "out.txt").exists()


def test_commits_of_a_repository_without_commits(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    assert list_commits(repo, None, 0) == []


def test_commits_in_detached_head(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    commit_file(repo, "1.txt", "1", "one")
    git(repo, "switch", "--detach", "HEAD~1")
    commits = list_commits(repo, None, 0)
    assert [(c.subject, c.unpushed) for c in commits] == [("initial", False)]
