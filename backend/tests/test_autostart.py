import pytest
from conftest import FakeBackend

from wrench.core.autostart import Autostart
from wrench.sdk.errors import ToolError


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


def test_refresh_rewrites_stale_path() -> None:
    b = FakeBackend()
    b.values["Wrench"] = '"C:\\Old\\Wrench.exe"'
    Autostart(b, executable=r"C:\New\Wrench.exe", frozen=True).refresh_path()
    assert b.values["Wrench"] == '"C:\\New\\Wrench.exe"'


def test_refresh_does_nothing_when_disabled() -> None:
    b = FakeBackend()
    Autostart(b, executable="x", frozen=True).refresh_path()
    assert b.values == {}


def test_refresh_does_nothing_when_unavailable() -> None:
    b = FakeBackend()
    b.values["Wrench"] = '"C:\\Old\\Wrench.exe"'
    Autostart(b, executable="python.exe", frozen=False).refresh_path()
    assert b.values["Wrench"] == '"C:\\Old\\Wrench.exe"'


def test_refresh_keeps_a_current_path() -> None:
    b = FakeBackend()
    b.values["Wrench"] = '"C:\\Program Files\\Wrench\\Wrench.exe"'
    Autostart(b, executable=r"C:\Program Files\Wrench\Wrench.exe", frozen=True).refresh_path()
    assert b.values["Wrench"] == '"C:\\Program Files\\Wrench\\Wrench.exe"'


def test_refresh_survives_a_registry_error() -> None:
    class FailingBackend(FakeBackend):
        def set(self, name: str, value: str) -> None:
            raise PermissionError("denied")

    b = FailingBackend()
    b.values["Wrench"] = '"C:\\Old\\Wrench.exe"'
    Autostart(b, executable=r"C:\New\Wrench.exe", frozen=True).refresh_path()
    assert b.values["Wrench"] == '"C:\\Old\\Wrench.exe"'
