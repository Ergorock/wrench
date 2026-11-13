"""Build command suggested from the files of a project. Nothing of the project is run."""

import json
from pathlib import Path


def _package_manager(folder: Path, data: dict[str, object]) -> str:
    declared = data.get("packageManager")
    if isinstance(declared, str):
        name = declared.split("@", 1)[0]
        if name in ("npm", "pnpm", "yarn"):
            return name
    if (folder / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (folder / "yarn.lock").is_file():
        return "yarn"
    return "npm"


def _node_build(folder: Path) -> str | None:
    try:
        data = json.loads((folder / "package.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts")
    if not isinstance(scripts, dict) or "build" not in scripts:
        return None
    return f"{_package_manager(folder, data)} run build"


def suggest_build(folder: Path) -> str | None:
    if (folder / "scripts" / "build.ps1").is_file():
        return "powershell -ExecutionPolicy Bypass -File scripts/build.ps1"
    if (folder / "package.json").is_file():
        command = _node_build(folder)
        if command:
            return command
    if (folder / "pyproject.toml").is_file() and (folder / "uv.lock").is_file():
        return "uv build"
    if any(folder.glob("*.sln")):
        return "dotnet build"
    if (folder / "Cargo.toml").is_file():
        return "cargo build"
    if (folder / "go.mod").is_file():
        return "go build ./..."
    return None
