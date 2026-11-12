import hashlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from wrench.api import Api
from wrench.core.autostart import Autostart
from wrench.core.registry import ToolRegistry, discover_tools
from wrench.core.settings import SettingsStore
from wrench.core.updater import Updater


class FakeBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def release_for(payload: bytes, sha256: str | None = None) -> dict[str, Any]:
    return {
        "tag_name": "v1.3.0",
        "html_url": "https://github.com/Ergorock/wrench/releases/tag/v1.3.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "Wrench-Setup-1.3.0.exe",
                "browser_download_url": "https://github.com/Ergorock/wrench/releases/download/v1.3.0/Wrench-Setup-1.3.0.exe",
                "size": len(payload),
                "digest": "sha256:" + (sha256 or hashlib.sha256(payload).hexdigest()),
            }
        ],
    }


class FakeHttp:
    def __init__(
        self, release: Any = None, error: Exception | None = None, slow: bool = False
    ) -> None:
        self.release = release
        self.error = error
        self.slow = slow
        self.download_calls = 0
        self.started = threading.Event()
        self.gate = threading.Event()
        if not slow:
            self.gate.set()

    def get_json(self, url: str) -> Any:
        if self.error is not None:
            raise self.error
        return self.release

    def download(self, url: str, dest: Path, on_progress: Callable[[int, int], None]) -> None:
        self.download_calls += 1
        self.started.set()
        self.gate.wait(5)
        payload = self._payload()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        on_progress(len(payload), len(payload))

    def _payload(self) -> bytes:
        return getattr(self, "payload", b"x")


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


@pytest.fixture
def api_with_updater(tmp_path: Path, registry: ToolRegistry) -> Api:
    store = SettingsStore(tmp_path / "s.json", "en")
    updater = Updater(FakeHttp(release_for(b"x")), "1.2.0", True, tmp_path / "dl", lambda p: None)
    return Api(
        store,
        store.load().settings,
        registry,
        Autostart(FakeBackend(), "python.exe", frozen=False),
        [],
        updater=updater,
    )
