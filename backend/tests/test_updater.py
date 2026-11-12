from typing import Any

import pytest

from wrench.core.updater import (
    UpdateError,
    is_newer,
    parse_version,
    select_update,
    update_supported,
)


@pytest.mark.parametrize(
    "s,expected",
    [
        ("1.2.3", (1, 2, 3, False)),
        ("1.2.3-beta.1", (1, 2, 3, True)),
        ("v1.2.3", None),
        ("1.2", None),
        ("", None),
    ],
)
def test_parse_version(s: str, expected: tuple[int, int, int, bool] | None) -> None:
    assert parse_version(s) == expected


@pytest.mark.parametrize(
    "remote,local,expected",
    [
        ("1.2.0", "1.1.9", True),
        ("1.2.0", "1.2.0", False),
        ("1.1.0", "1.2.0", False),
        ("1.2.0", "1.2.0-beta.1", True),
        ("1.2.0-beta.2", "1.2.0", False),
        ("garbage", "1.0.0", False),
    ],
)
def test_is_newer(remote: str, local: str, expected: bool) -> None:
    assert is_newer(remote, local) is expected


def release(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "tag_name": "v1.3.0",
        "draft": False,
        "prerelease": False,
        "html_url": "https://github.com/Ergorock/wrench/releases/tag/v1.3.0",
        "assets": [
            {
                "name": "Wrench-Setup-1.3.0.exe",
                "size": 123,
                "browser_download_url": "https://github.com/Ergorock/wrench/releases/download/v1.3.0/Wrench-Setup-1.3.0.exe",
                "digest": "sha256:" + "ab" * 32,
            }
        ],
    }
    return base | over


def test_select_update_ok() -> None:
    info = select_update(release(), "1.2.0")
    assert info is not None
    assert info.version == "1.3.0" and info.size == 123 and info.sha256 == "ab" * 32


@pytest.mark.parametrize(
    "over",
    [
        {"draft": True},
        {"prerelease": True},
        {"tag_name": "1.3.0"},
        {"tag_name": "v1.2.0"},
        {"assets": []},
    ],
)
def test_select_update_none(over: dict[str, Any]) -> None:
    assert select_update(release(**over), "1.2.0") is None


def test_select_update_requires_digest() -> None:
    r = release()
    del r["assets"][0]["digest"]
    assert select_update(r, "1.2.0") is None


def test_select_update_asset_must_match_tag_version() -> None:
    r = release()
    r["assets"][0]["name"] = "Wrench-Setup-1.2.9.exe"
    assert select_update(r, "1.2.0") is None


def test_update_error_exposes_code_and_message() -> None:
    e = UpdateError("update_network", "boom")
    assert e.code == "update_network" and e.message == "boom"


def test_update_supported() -> None:
    exe = r"C:\Users\u\AppData\Local\Programs\Wrench\Wrench.exe"
    assert update_supported(exe, True, lambda: r"c:\users\u\appdata\local\programs\wrench" + "\\")
    assert not update_supported(exe, False, lambda: r"C:\Users\u\AppData\Local\Programs\Wrench")
    assert not update_supported(exe, True, lambda: None)
    assert not update_supported(
        r"C:\dev\dist\Wrench\Wrench.exe", True, lambda: r"C:\Users\u\AppData\Local\Programs\Wrench"
    )
