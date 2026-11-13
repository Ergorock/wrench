import os
from pathlib import Path

import pytest

from wrench.tools.projects.scan import flatten, is_project, scan, techs_of


def test_markers(tmp_path: Path) -> None:
    for name, marker in [
        ("g", ".git"),
        ("r", "README.md"),
        ("readme", "readme.MD"),
        ("n", "package.json"),
        ("s", "App.sln"),
        ("c", "x.csproj"),
        ("gr", "build.gradle.kts"),
    ]:
        (tmp_path / name).mkdir()
        (tmp_path / name / marker).touch()
    (tmp_path / "only_claude" / ".claude").mkdir(parents=True)
    tree = scan(tmp_path, 4, None)
    assert {p.name for p in tree.projects} == {"g", "r", "readme", "n", "s", "c", "gr"}
    assert [f.name for f in tree.folders] == ["only_claude"]
    assert not is_project(tmp_path / "only_claude")


def test_root_is_always_a_folder(tmp_path: Path) -> None:  # Review Focus 1
    (tmp_path / "README.md").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "go.mod").touch()
    tree = scan(tmp_path, 4, None)
    assert tree.rel_path == "" and [p.name for p in tree.projects] == ["sub"]


def test_depth_counts_and_no_nesting(tmp_path: Path) -> None:
    liste = tmp_path / "M3" / "Liste"
    (liste / "sub").mkdir(parents=True)
    (liste / "package.json").touch()
    (liste / "sub" / "README.md").touch()
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / "README.md").touch()
    tree = scan(tmp_path, 4, None)
    m3 = next(f for f in tree.folders if f.name == "M3")
    assert m3.project_count == 1 and m3.projects[0].name == "Liste"
    assert m3.projects[0].rel_path == "M3" + os.sep + "Liste"
    assert tree.project_count == 1  # e is at depth 5
    assert [p.name for p in flatten(tree)] == ["Liste"]


def test_accents_spaces_and_skips(tmp_path: Path) -> None:  # Review Focus 2
    for rel in ["Génération aspx", "node_modules/x", ".hidden/y", "build/z"]:
        (tmp_path / rel).mkdir(parents=True)
        (tmp_path / rel / "README.md").touch()
    names = [p.name for p in flatten(scan(tmp_path, 4, None))]
    assert names == ["Génération aspx"]


def test_permission_error_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ["locked", "ok"]:
        (tmp_path / name / "inner").mkdir(parents=True)
        (tmp_path / name / "inner" / "README.md").touch()
    real = os.scandir

    def fake(path: str | os.PathLike[str]):  # type: ignore[no-untyped-def]
        if Path(path).name == "locked":
            raise PermissionError(path)
        return real(path)

    monkeypatch.setattr(os, "scandir", fake)
    tree = scan(tmp_path, 4, None)
    assert [p.name for p in flatten(tree)] == ["inner"]
    assert flatten(tree)[0].rel_path == "ok" + os.sep + "inner"


def test_template_flag_and_techs(tmp_path: Path) -> None:
    py = tmp_path / "templates" / "py"
    py.mkdir(parents=True)
    (py / "pyproject.toml").touch()
    (py / "package.json").touch()
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "Cargo.toml").touch()
    (tmp_path / "other" / "pom.xml").touch()
    tree = scan(tmp_path, 4, tmp_path / "templates")
    by_name = {p.name: p for p in flatten(tree)}
    assert by_name["py"].is_template and by_name["py"].techs == ["Python", "Node"]
    assert not by_name["other"].is_template
    assert by_name["other"].techs == ["Rust", "Java"]


def test_sorted_casefold_and_links(tmp_path: Path) -> None:
    for name in ["b", "A", "c"]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "README.md").touch()
    tree = scan(tmp_path, 4, None)
    assert [p.name for p in tree.projects] == ["A", "b", "c"]
    assert techs_of(tmp_path / "A") == []
