import hashlib
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from wrench.core import updater as updater_mod
from wrench.core.updater import UpdateError, Updater, launch_installer_detached


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


def make(tmp_path: Path, payload: bytes = b"installer", **kw: Any) -> tuple[Updater, FakeHttp]:
    http = FakeHttp(release_for(payload, kw.pop("sha256", None)), slow=kw.pop("slow", False))
    http.payload = payload  # type: ignore[attr-defined]
    return Updater(http, "1.2.0", True, tmp_path, kw.pop("launch", lambda p: None), **kw), http


def test_check_then_install_happy_path(tmp_path):
    launched: list[Path] = []
    closed: list[int] = []
    u, _ = make(tmp_path, launch=launched.append, request_close=lambda: closed.append(1))
    assert u.check()["status"] == "available"
    u.start_install()
    u.wait(5)
    assert launched == [tmp_path / "Wrench-Setup-1.3.0.exe"] and closed == [1]
    assert u.snapshot()["status"] == "installing"
    assert u.snapshot()["progress"] == 1.0


def test_snapshot_initial_and_keys(tmp_path):
    u, _ = make(tmp_path)
    s = u.snapshot()
    assert s == {
        "supported": True,
        "current_version": "1.2.0",
        "status": "idle",
        "info": None,
        "progress": 0.0,
        "error_code": None,
    }
    assert u.check()["info"]["version"] == "1.3.0"


def test_up_to_date(tmp_path):
    http = FakeHttp(release_for(b"x"))
    u = Updater(http, "1.3.0", True, tmp_path, lambda p: None)
    s = u.check()
    assert s["status"] == "up_to_date" and s["info"] is None


def test_non_dict_payload_is_network_error(tmp_path):
    u = Updater(FakeHttp([1, 2]), "1.2.0", True, tmp_path, lambda p: None)
    s = u.check()
    assert s["status"] == "error" and s["error_code"] == "update_network"


def test_integrity_failure(tmp_path):
    launched: list[Path] = []
    u, _ = make(tmp_path, b"x", sha256="00" * 32, launch=launched.append)
    u.check()
    u.start_install()
    u.wait(5)
    s = u.snapshot()
    assert s["status"] == "error" and s["error_code"] == "update_integrity" and launched == []


def test_retry_after_integrity_error(tmp_path):
    launched: list[Path] = []
    u, http = make(tmp_path, b"x", sha256="00" * 32, launch=launched.append)
    u.check()
    u.start_install()
    u.wait(5)
    assert u.snapshot()["error_code"] == "update_integrity"
    # a corrected release is published: re-check, then Retry must work
    http.release = release_for(b"x")
    u.check()
    u.start_install()
    u.wait(5)
    s = u.snapshot()
    assert s["status"] == "installing" and s["error_code"] is None and len(launched) == 1
    assert http.download_calls == 2


def test_retry_same_info_after_error(tmp_path):
    u, http = make(tmp_path, b"x")
    calls = {"n": 0}
    real = http.download

    def flaky(url: str, dest: Path, on_progress: Callable[[int, int], None]) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise UpdateError("update_network", "down")
        real(url, dest, on_progress)

    http.download = flaky  # type: ignore[method-assign]
    u.check()
    u.start_install()
    u.wait(5)
    assert u.snapshot()["error_code"] == "update_network"
    u.start_install()
    u.wait(5)
    assert u.snapshot()["status"] == "installing"


def test_double_start_downloads_once(tmp_path):
    u, http = make(tmp_path, b"x", slow=True)
    u.check()
    u.start_install()
    assert http.started.wait(5)
    assert u.start_install()["status"] == "downloading"
    http.gate.set()
    u.wait(5)
    assert http.download_calls == 1


def test_check_during_download_keeps_state(tmp_path):
    u, http = make(tmp_path, b"x", slow=True)
    u.check()
    u.start_install()
    assert http.started.wait(5)
    assert u.check()["status"] == "downloading"
    http.gate.set()
    u.wait(5)


def test_network_error_sets_error(tmp_path):
    u = Updater(
        FakeHttp(error=UpdateError("update_network", "x")), "1.2.0", True, tmp_path, lambda p: None
    )
    assert u.check()["error_code"] == "update_network"


def test_download_unexpected_error_is_network(tmp_path):
    u, http = make(tmp_path)

    def boom(*a: Any) -> None:
        raise RuntimeError("weird")

    http.download = boom  # type: ignore[method-assign]
    u.check()
    u.start_install()
    u.wait(5)
    assert u.snapshot()["error_code"] == "update_network"


def test_unsupported(tmp_path):
    u = Updater(FakeHttp(release_for(b"x")), "1.2.0", False, tmp_path, lambda p: None)
    with pytest.raises(UpdateError) as e:
        u.check()
    assert e.value.code == "update_unsupported"
    with pytest.raises(UpdateError) as e:
        u.start_install()
    assert e.value.code == "update_unsupported"


def test_start_install_without_info(tmp_path):
    u, _ = make(tmp_path)
    with pytest.raises(UpdateError) as e:
        u.start_install()
    assert e.value.code == "no_update"


def test_install_failed(tmp_path):
    def boom(p):
        raise OSError("nope")

    u, _ = make(tmp_path, launch=boom)
    u.check()
    u.start_install()
    u.wait(5)
    assert u.snapshot()["error_code"] == "update_install_failed"


def test_close_handler_and_missing_handler(tmp_path):
    u, _ = make(tmp_path)
    closed: list[int] = []
    u.set_close_handler(lambda: closed.append(1))
    u.check()
    u.start_install()
    u.wait(5)
    assert closed == [1]
    u2, _ = make(tmp_path)  # no handler: must not crash
    u2.check()
    u2.start_install()
    u2.wait(5)
    assert u2.snapshot()["status"] == "installing"


def test_download_dir_created(tmp_path):
    d = tmp_path / "sub" / "dir"
    http = FakeHttp(release_for(b"x"))
    u = Updater(http, "1.2.0", True, d, lambda p: None)
    u.check()
    u.start_install()
    u.wait(5)
    assert (d / "Wrench-Setup-1.3.0.exe").exists()


def test_launch_installer_detached_args(monkeypatch):
    calls: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    launch_installer_detached(Path("C:/t/Wrench-Setup-1.3.0.exe"))
    (args, kwargs) = calls[0]
    assert args[0] == [str(Path("C:/t/Wrench-Setup-1.3.0.exe")), *updater_mod.INSTALLER_ARGS]
    assert kwargs["creationflags"] == (
        subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    assert kwargs["close_fds"] is True
