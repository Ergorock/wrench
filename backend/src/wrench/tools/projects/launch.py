"""Launching external programs without blocking Wrench or showing a console window."""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from wrench.sdk import ToolError

# (args, cwd, console): console=True opens a visible, interactive console window.
Spawner = Callable[[list[str], Path | None, bool], None]


def spawn(args: list[str], cwd: Path | None, console: bool = False) -> None:
    try:
        if console:
            # A terminal keeps its own handles and window: not detached, no redirection.
            subprocess.Popen(
                args,
                cwd=cwd,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                args,
                cwd=cwd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError as exc:
        raise ToolError("launch_failed", str(exc)) from exc


def find_wt() -> str | None:
    return shutil.which("wt")


def terminal_args(folder: Path, command: str | None, wt: str | None) -> list[str]:
    """A new terminal window in `folder`, left open after `command`."""
    if wt:
        args = [wt, "-d", str(folder).replace(";", r"\;")]
        if command:
            # wt reads an unescaped `;` as its own command separator.
            args += ["powershell", "-NoExit", "-Command", command.replace(";", r"\;")]
        return args
    quoted = str(folder).replace("'", "''")
    script = f"Set-Location -LiteralPath '{quoted}'" + (f"; {command}" if command else "")
    return ["powershell", "-NoExit", "-Command", script]
