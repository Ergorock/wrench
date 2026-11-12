from pathlib import Path

import pytest

from wrench.api import Api
from wrench.core.autostart import Autostart
from wrench.core.registry import ToolRegistry, discover_tools
from wrench.core.settings import SettingsStore


class FakeBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(discover_tools("fake_tools", ["system"]), tmp_path / "tools", lambda: "en")


@pytest.fixture
def api(tmp_path: Path, registry: ToolRegistry) -> Api:
    store = SettingsStore(tmp_path / "s.json", "en")
    return Api(
        store,
        store.load().settings,
        registry,
        Autostart(FakeBackend(), "python.exe", frozen=False),
        [],
    )
