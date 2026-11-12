import pytest

from wrench.core.autostart import Autostart
from wrench.sdk.errors import ToolError


class FakeBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def test_enable_writes_quoted_exe() -> None:
    b = FakeBackend()
    a = Autostart(b, executable=r"C:\Apps\Wrench\Wrench.exe", frozen=True)
    a.set_enabled(True)
    assert b.values["Wrench"] == '"C:\\Apps\\Wrench\\Wrench.exe"'
    assert a.is_enabled()


def test_disable_removes_value() -> None:
    b = FakeBackend()
    a = Autostart(b, executable="x", frozen=True)
    a.set_enabled(True)
    a.set_enabled(False)
    assert not a.is_enabled()


def test_disable_when_absent_is_ok() -> None:
    a = Autostart(FakeBackend(), executable="x", frozen=True)
    a.set_enabled(False)
    assert not a.is_enabled()


def test_unavailable_in_dev() -> None:
    a = Autostart(FakeBackend(), executable="python.exe", frozen=False)
    assert a.is_available() is False
    with pytest.raises(ToolError) as e:
        a.set_enabled(True)
    assert e.value.code == "autostart_unavailable"
