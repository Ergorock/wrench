"""Walks a root folder and sorts what it finds into projects and plain folders."""

import os
from pathlib import Path

from pydantic import BaseModel

from wrench.shared.git.discovery import SKIP_DIRS, _is_link

# Technology -> exact marker file names (casefolded) or suffixes. Order is the display order.
_TECHS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("Python", ("pyproject.toml", "requirements.txt"), ()),
    ("Node", ("package.json",), ()),
    (".NET", (), (".sln", ".csproj")),
    ("Rust", ("cargo.toml",), ()),
    ("Go", ("go.mod",), ()),
    ("Java", ("pom.xml", "build.gradle", "build.gradle.kts"), ()),
    ("PHP", ("composer.json",), ()),
]


class ProjectEntry(BaseModel):
    name: str
    path: str
    rel_path: str  # parts joined with os.sep (`\` on Windows)
    techs: list[str]
    is_template: bool


class FolderEntry(BaseModel):
    name: str
    path: str
    rel_path: str  # empty for the root
    project_count: int
    folders: list["FolderEntry"]
    projects: list[ProjectEntry]


def _names(folder: Path) -> set[str]:
    """Casefolded entry names of a folder; empty when it cannot be read."""
    try:
        with os.scandir(folder) as entries:
            return {e.name.casefold() for e in entries}
    except OSError:
        return set()


def _is_project(names: set[str]) -> bool:
    if ".git" in names or "readme.md" in names:
        return True
    return any(
        n in exact or n.endswith(suffixes)
        for _, exact, suffixes in _TECHS
        for n in names
        if exact or suffixes
    )


def _techs(names: set[str]) -> list[str]:
    return [
        tech
        for tech, exact, suffixes in _TECHS
        if any(n in exact or (suffixes and n.endswith(suffixes)) for n in names)
    ]


def is_project(folder: Path) -> bool:
    return _is_project(_names(folder))


def techs_of(folder: Path) -> list[str]:
    return _techs(_names(folder))


def _key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def scan(root: Path, max_depth: int, templates_dir: Path | None) -> FolderEntry:
    """The root is always a folder (its own markers are ignored). A folder at depth `d` is
    listed when `d <= max_depth`; the walk does not go below a project."""
    templates = _key(templates_dir) if templates_dir is not None else None

    def is_template(path: Path) -> bool:
        if templates is None:
            return False
        key = _key(path)
        return key == templates or key.startswith(templates.rstrip(os.sep) + os.sep)

    def walk(folder: Path, rel: str, depth: int) -> FolderEntry:
        folders: list[FolderEntry] = []
        projects: list[ProjectEntry] = []
        if depth < max_depth:
            try:
                with os.scandir(folder) as it:
                    children = [
                        Path(e.path)
                        for e in it
                        if not e.name.startswith(".")
                        and e.name not in SKIP_DIRS
                        and not _is_link(e)
                        and e.is_dir()
                    ]
            except OSError:
                children = []
            for child in children:
                child_rel = f"{rel}{os.sep}{child.name}" if rel else child.name
                names = _names(child)
                if _is_project(names):
                    projects.append(
                        ProjectEntry(
                            name=child.name,
                            path=str(child),
                            rel_path=child_rel,
                            techs=_techs(names),
                            is_template=is_template(child),
                        )
                    )
                else:
                    folders.append(walk(child, child_rel, depth + 1))
        folders.sort(key=lambda f: f.name.casefold())
        projects.sort(key=lambda p: p.name.casefold())
        return FolderEntry(
            name=folder.name,
            path=str(folder),
            rel_path=rel,
            project_count=len(projects) + sum(f.project_count for f in folders),
            folders=folders,
            projects=projects,
        )

    return walk(root, "", 0)


def flatten(tree: FolderEntry) -> list[ProjectEntry]:
    """Every project of the tree, at any depth, sorted by name."""
    found = list(tree.projects)
    for folder in tree.folders:
        found.extend(flatten(folder))
    return sorted(found, key=lambda p: p.name.casefold())
