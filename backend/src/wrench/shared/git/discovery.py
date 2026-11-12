"""Finds the git repositories under root folders."""

import os
from collections import deque
from collections.abc import Sequence
from pathlib import Path

SKIP_DIRS = {"node_modules", ".venv", "venv", "dist", "build", "target", ".git", "__pycache__"}


def _is_link(entry: os.DirEntry[str]) -> bool:
    return entry.is_symlink() or os.path.isjunction(entry.path)


def find_repos(roots: Sequence[Path], max_depth: int) -> list[Path]:
    """Breadth-first search; depth 0 is the root itself. The search does not go below a
    repository, skips SKIP_DIRS, links and junctions, and ignores access errors."""
    found: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        queue: deque[tuple[Path, int]] = deque([(root, 0)])
        while queue:
            folder, depth = queue.popleft()
            if (folder / ".git").exists():
                found.add(folder.resolve())
                continue
            if depth >= max_depth:
                continue
            try:
                with os.scandir(folder) as entries:
                    children = [
                        Path(e.path)
                        for e in entries
                        if e.name not in SKIP_DIRS and not _is_link(e) and e.is_dir()
                    ]
            except OSError:
                continue
            queue.extend((child, depth + 1) for child in children)
    return sorted(found, key=lambda p: str(p).casefold())
