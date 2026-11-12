import ctypes
import json
import locale
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SidebarSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    collapsed: bool = False
    category_order: list[str] = []
    tool_order: dict[str, list[str]] = {}
    favorites: list[str] = []


class ToolSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool


class WindowSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: int | None = None
    y: int | None = None
    width: int = 1100
    height: int = 720
    maximized: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: Literal[1] = 1
    language: Literal["fr", "en"] = "en"
    theme: Literal["light", "dark", "system"] = "system"
    autostart: bool = False
    sidebar: SidebarSettings = Field(default_factory=SidebarSettings)
    tools: dict[str, ToolSettings] = {}
    window: WindowSettings = Field(default_factory=WindowSettings)
    last_tool: str | None = None


def detect_system_language() -> str:
    """Return the 2-letter ISO code of the Windows UI language, "en" on any failure."""
    try:
        if sys.platform != "win32":
            return "en"
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined,unused-ignore]
        name = locale.windows_locale.get(lang_id)
        if name:
            return name.split("_")[0].lower()
    except Exception:
        pass
    return "en"


def _language_for(system_language: str) -> Literal["fr", "en"]:
    return "fr" if system_language.lower().startswith("fr") else "en"


def default_settings(system_language: str) -> Settings:
    return Settings(language=_language_for(system_language))


@dataclass
class LoadResult:
    settings: Settings
    recovered: bool


class SettingsStore:
    def __init__(self, path: Path, system_language: str) -> None:
        self._path = path
        self._system_language = system_language

    def load(self) -> LoadResult:
        if not self._path.exists():
            settings = default_settings(self._system_language)
            self.save(settings)
            return LoadResult(settings, False)
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("settings root is not an object")
            if "language" not in data:
                data["language"] = _language_for(self._system_language)
            return LoadResult(Settings.model_validate(data), False)
        except (ValueError, ValidationError, UnicodeDecodeError):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self._path.replace(self._path.with_name(f"settings.bak-{stamp}.json"))
            settings = default_settings(self._system_language)
            self.save(settings)
            return LoadResult(settings, True)

    def save(self, settings: Settings) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
