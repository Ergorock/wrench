"""Creation from a template: name validation and the copy of the template folder."""

import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wrench.sdk import ToolError

_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_RESERVED |= {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def validate_name(name: str) -> None:
    """Refuses what Windows does not accept as a folder name."""
    if not name.strip():
        raise ToolError("invalid_name", "The name is empty")
    if any(c in _FORBIDDEN or ord(c) < 32 for c in name):
        raise ToolError("invalid_name", 'A name cannot contain < > : " / \\ | ? *')
    if name.endswith((" ", ".")):
        raise ToolError("invalid_name", "A name cannot end with a space or a dot")
    if name.split(".", 1)[0].rstrip().upper() in _RESERVED:
        raise ToolError("invalid_name", f"Reserved name: {name}")


def _force_remove(func: Callable[[str], Any], path: str, _exc: BaseException) -> None:
    """git marks its object files read-only, which Windows refuses to delete."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def copy_template(src: Path, dest: Path) -> None:
    """Copies `src` to `dest` without the `.git` at the root of `src` (a nested one is kept).
    No file content is changed. On failure `dest` is removed."""
    top = os.path.normcase(os.path.abspath(src))

    def ignore(folder: str, names: list[str]) -> set[str]:
        at_root = os.path.normcase(os.path.abspath(folder)) == top
        return {".git"} & set(names) if at_root else set()

    try:
        shutil.copytree(src, dest, ignore=ignore)
    except FileExistsError as exc:
        # `dest` appeared after the caller's check: it is not ours, never remove it.
        raise ToolError("copy_failed", f"The target already exists: {exc}") from exc
    except OSError as exc:
        if dest.exists():
            shutil.rmtree(dest, onexc=_force_remove)
        raise ToolError("copy_failed", f"The copy failed: {exc}") from exc
