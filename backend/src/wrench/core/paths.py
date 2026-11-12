import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    override = os.environ.get("WRENCH_DATA_DIR")
    base = Path(override) if override else Path(os.environ["APPDATA"]) / "Wrench"
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def tools_data_dir() -> Path:
    path = app_data_dir() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))  # noqa: B009
    return Path(__file__).resolve().parents[4]


def frontend_dist_dir() -> Path:
    return resource_dir() / "frontend" / "dist"
