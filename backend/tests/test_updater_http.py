import hashlib
import io
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from wrench._version import __version__
from wrench.core.updater import (
    SafeRedirectHandler,
    UpdateError,
    UrllibClient,
    check_url,
    verify_file,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/x",
        "https://evil.example/x",
        "https://github.com.evil.example/x",
        "https://github.com@evil.example/x",
        "file:///C:/x",
    ],
)
def test_check_url_rejects(url: str) -> None:
    with pytest.raises(UpdateError) as e:
        check_url(url)
    assert e.value.code == "update_integrity"


def test_check_url_accepts() -> None:
    check_url("https://release-assets.githubusercontent.com/a")
    check_url("https://GitHub.com/Ergorock/wrench")


def test_redirect_to_foreign_host_is_refused() -> None:
    handler = SafeRedirectHandler()
    req = urllib.request.Request("https://github.com/Ergorock/wrench/releases/download/v1/x.exe")
    with pytest.raises(UpdateError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/x.exe")  # type: ignore[arg-type]


def test_verify_file(tmp_path: Path) -> None:
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    verify_file(p, 3, hashlib.sha256(b"abc").hexdigest())
    verify_file(p, 3, hashlib.sha256(b"abc").hexdigest().upper())
    with pytest.raises(UpdateError) as e:
        verify_file(p, 3, "00" * 32)
    assert e.value.code == "update_integrity"
    assert not p.exists()


def test_verify_file_wrong_size(tmp_path: Path) -> None:
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    with pytest.raises(UpdateError) as e:
        verify_file(p, 4, hashlib.sha256(b"abc").hexdigest())
    assert e.value.code == "update_integrity"
    assert not p.exists()


class _Resp(io.BytesIO):
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        super().__init__(data)
        self.headers = headers or {}


class _Opener:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def open(self, req: urllib.request.Request, timeout: float) -> Any:
        self.requests.append(req)
        self.timeouts.append(timeout)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_get_json_sends_headers_and_parses() -> None:
    opener = _Opener(_Resp(b'{"a": 1}'))
    client = UrllibClient(opener=opener)
    assert client.get_json("https://api.github.com/x") == {"a": 1}
    req = opener.requests[0]
    assert req.get_header("User-agent") == f"Wrench/{__version__}"
    assert req.get_header("Accept") == "application/vnd.github+json"
    assert opener.timeouts == [10]


def test_get_json_checks_start_url() -> None:
    opener = _Opener(_Resp(b"{}"))
    with pytest.raises(UpdateError) as e:
        UrllibClient(opener=opener).get_json("https://evil.example/x")
    assert e.value.code == "update_integrity"
    assert opener.requests == []


def test_get_json_invalid_json_is_network_error() -> None:
    with pytest.raises(UpdateError) as e:
        UrllibClient(opener=_Opener(_Resp(b"<html>"))).get_json("https://api.github.com/x")
    assert e.value.code == "update_network"


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.HTTPError("https://api.github.com/x", 429, "Too Many", {}, None),  # type: ignore[arg-type]
        urllib.error.HTTPError("https://api.github.com/x", 403, "Forbidden", {}, None),  # type: ignore[arg-type]
        urllib.error.URLError("down"),
        TimeoutError(),
    ],
)
def test_network_errors_map_to_update_network(exc: BaseException) -> None:
    with pytest.raises(UpdateError) as e:
        UrllibClient(opener=_Opener(exc)).get_json("https://api.github.com/x")
    assert e.value.code == "update_network"


def test_redirect_handler_error_propagates_as_integrity(tmp_path: Path) -> None:
    # Real opener with the real handler: a 302 to a foreign host must surface as update_integrity.
    class _FakeHttps(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> Any:
            import email.message

            hdrs = email.message.Message()
            hdrs["Location"] = "https://evil.example/x.exe"
            resp = _Resp(b"")
            resp.code, resp.msg, resp.headers = 302, "Found", hdrs  # type: ignore[assignment]
            resp.info = lambda: hdrs  # type: ignore[method-assign]
            return resp

    client = UrllibClient()
    client._opener = urllib.request.build_opener(_FakeHttps, SafeRedirectHandler)
    dest = tmp_path / "sub" / "x.exe"
    with pytest.raises(UpdateError) as e:
        client.download("https://github.com/a/x.exe", dest, lambda r, t: None)
    assert e.value.code == "update_integrity"
    assert not dest.exists()


def test_download_streams_and_reports_progress(tmp_path: Path) -> None:
    data = b"x" * (65536 * 2 + 5)
    opener = _Opener(_Resp(data, {"Content-Length": str(len(data))}))
    calls: list[tuple[int, int]] = []
    dest = tmp_path / "a" / "b.exe"
    UrllibClient(opener=opener).download(
        "https://github.com/a/b.exe", dest, lambda r, t: calls.append((r, t))
    )
    assert dest.read_bytes() == data
    assert calls[-1] == (len(data), len(data))
    assert len(calls) == 3


def test_download_unknown_length_reports_zero_total(tmp_path: Path) -> None:
    opener = _Opener(_Resp(b"abc"))
    calls: list[tuple[int, int]] = []
    UrllibClient(opener=opener).download(
        "https://github.com/a/b.exe", tmp_path / "b.exe", lambda r, t: calls.append((r, t))
    )
    assert calls == [(3, 0)]


def test_download_failure_removes_partial_file(tmp_path: Path) -> None:
    class _Broken(_Resp):
        def read(self, n: int = -1) -> bytes:
            if self.tell() == 0:
                return super().read(4)
            raise OSError("connection reset")

    dest = tmp_path / "b.exe"
    with pytest.raises(UpdateError) as e:
        UrllibClient(opener=_Opener(_Broken(b"abcdefgh"))).download(
            "https://github.com/a/b.exe", dest, lambda r, t: None
        )
    assert e.value.code == "update_network"
    assert not dest.exists()


def test_download_checks_start_url(tmp_path: Path) -> None:
    with pytest.raises(UpdateError) as e:
        UrllibClient(opener=_Opener(_Resp(b""))).download(
            "http://github.com/x", tmp_path / "x", lambda r, t: None
        )
    assert e.value.code == "update_integrity"
