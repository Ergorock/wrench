import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Editor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1)
    exe: str
    args: list[str] = []


def default_editors() -> list[Editor]:
    return [
        Editor(
            id="claude",
            name="Claude",
            exe=r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude",
        ),
        Editor(
            id="kiro",
            name="Kiro",
            exe=r"%LOCALAPPDATA%\Programs\Kiro\Kiro.exe",
            args=["{path}"],
        ),
        Editor(
            id="vscode",
            name="VS Code",
            exe=r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            args=["{path}"],
        ),
    ]


def is_shell_target(exe: str) -> bool:
    return exe.lower().startswith("shell:")


def command_for(editor: Editor, path: Path) -> list[str]:
    """Build the launch command; environment variables are expanded at launch time."""
    if is_shell_target(editor.exe):
        return ["explorer.exe", editor.exe]
    return [os.path.expandvars(editor.exe), *(a.replace("{path}", str(path)) for a in editor.args)]


def exe_exists(editor: Editor) -> bool:
    if is_shell_target(editor.exe):
        return True
    return Path(os.path.expandvars(editor.exe)).is_file()
