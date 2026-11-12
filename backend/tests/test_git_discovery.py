import os
import subprocess
from pathlib import Path

import pytest

from wrench.shared.git.discovery import SKIP_DIRS, find_repos


def test_depth_skip_and_stop(tmp_path: Path) -> None:
    root = tmp_path / "Mes Projets"
    for p in ["a", "x/b", "x/y/z/c", "node_modules/d", "a/inner"]:
        (root / p / ".git").mkdir(parents=True)
    assert [p.name for p in find_repos([root], 2)] == ["a", "b"]
    assert [p.name for p in find_repos([root], 4)] == ["a", "b", "c"]


def test_root_itself_and_git_file(tmp_path: Path) -> None:
    (tmp_path / "Été" / ".git").mkdir(parents=True)
    (tmp_path / "wt").mkdir()
    (tmp_path / "wt" / ".git").write_text("gitdir: elsewhere", "utf-8")
    assert [p.name for p in find_repos([tmp_path], 1)] == ["wt", "Été"]
    assert find_repos([tmp_path / "Été"], 1) == [(tmp_path / "Été").resolve()]


def test_skip_dirs() -> None:
    assert {"node_modules", ".venv", "venv", "dist", "build", "target", ".git"} <= SKIP_DIRS
    assert "__pycache__" in SKIP_DIRS


def test_missing_root(tmp_path: Path) -> None:
    assert find_repos([tmp_path / "gone"], 3) == []


def test_dedup(tmp_path: Path) -> None:
    (tmp_path / "r" / ".git").mkdir(parents=True)
    assert len(find_repos([tmp_path, tmp_path], 2)) == 1


def test_symlinked_dir_is_skipped(tmp_path: Path) -> None:
    target = tmp_path / "real"
    (target / "repo" / ".git").mkdir(parents=True)
    root = tmp_path / "root"
    root.mkdir()
    try:
        os.symlink(target, root / "link", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not allowed on this machine")
    assert find_repos([root], 3) == []


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-only")
def test_junction_is_skipped(tmp_path: Path) -> None:
    target = tmp_path / "real"
    (target / "repo" / ".git").mkdir(parents=True)
    root = tmp_path / "root"
    root.mkdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / "link"), str(target)],
        check=True,
        capture_output=True,
    )
    assert find_repos([root], 3) == []
