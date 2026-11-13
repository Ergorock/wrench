import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from wrench.sdk import ToolError
from wrench.tools.projects.templates import copy_template, validate_name


def _force_remove(func: Callable[[str], Any], path: str, _exc: BaseException) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def test_copy_excludes_root_git_only(tmp_path: Path) -> None:
    src = tmp_path / "tpl"
    (src / ".git").mkdir(parents=True)
    (src / ".git" / "HEAD").write_text("ref", "utf-8")
    (src / "sub" / ".git").mkdir(parents=True)
    (src / "sub" / ".git" / "HEAD").write_text("ref", "utf-8")
    (src / "a.txt").write_text("{{name}}", "utf-8")
    dest = tmp_path / "out"
    copy_template(src, dest)
    assert not (dest / ".git").exists()
    assert (dest / "sub" / ".git" / "HEAD").is_file()
    assert (dest / "a.txt").read_text("utf-8") == "{{name}}"  # content never modified


@pytest.mark.parametrize(
    "name", ["a:b", "CON", "con.txt", "x.", "x ", "", "  ", "a/b", "a|b", "COM1", "lpt9.log"]
)
def test_validate_name_refuses(name: str) -> None:
    with pytest.raises(ToolError) as e:
        validate_name(name)
    assert e.value.code == "invalid_name"


def test_validate_name_accepts() -> None:
    validate_name("Mon projet été")
    validate_name("COM10")


def test_copy_failure_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "tpl"
    src.mkdir()
    dest = tmp_path / "out"

    def failing(_src: Path, dst: Path, **_kw: Any) -> None:
        dst.mkdir()
        (dst / "objs").mkdir()
        locked = dst / "objs" / "f"
        locked.write_text("x", "utf-8")
        os.chmod(locked, stat.S_IREAD)
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copytree", failing)
    with pytest.raises(ToolError) as e:
        copy_template(src, dest)
    assert e.value.code == "copy_failed"
    assert not dest.exists()
