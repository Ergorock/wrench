import logging
import os
import time
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.downloads_cleaner import service as cleaner
from wrench.tools.downloads_cleaner.service import DownloadsCleanerService

DAY = 24 * 60 * 60


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "downloads_cleaner",
        ToolStorage(tmp_path / "downloads_cleaner.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> DownloadsCleanerService:
    return DownloadsCleanerService(ctx)


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    root = tmp_path / "Downloads"
    root.mkdir()
    return root


@pytest.fixture
def trashed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the real recycle bin: record the paths and delete nothing outside the test."""
    calls: list[str] = []
    monkeypatch.setattr(cleaner, "send2trash", calls.append)
    return calls


def make_file(root: Path, name: str, size: int = 10, age_days: float = 0) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    when = time.time() - age_days * DAY
    os.utime(path, (when, when))
    return path


def filters(folder: Path, **kwargs: object) -> dict[str, object]:
    return {"folder": str(folder), **kwargs}


def names(scan: dict[str, object]) -> list[str]:
    return [f["name"] for f in scan["files"]]  # type: ignore[index, misc]


def test_default_folder_is_downloads(svc):
    assert svc.invoke("get_settings", {})["folder"].endswith("Downloads")


def test_scan_lists_files_only_and_sorts_by_name(svc, folder):
    make_file(folder, "b.txt")
    make_file(folder, "A.txt")
    (folder / "sub").mkdir()
    make_file(folder / "sub", "deep.txt")
    scan = svc.invoke("scan", {"filters": filters(folder)})
    assert names(scan) == ["A.txt", "b.txt"]
    assert scan["total_size"] == 20


def test_extension_filter_ignores_case_and_dots(svc, folder):
    make_file(folder, "setup.EXE")
    make_file(folder, "notes.txt")
    make_file(folder, "archive.zip")
    scan = svc.invoke("scan", {"filters": filters(folder, extensions=[".exe", "ZIP"])})
    assert names(scan) == ["archive.zip", "setup.EXE"]


def test_age_filter_keeps_only_old_files(svc, folder):
    make_file(folder, "old.bin", age_days=40)
    make_file(folder, "recent.bin", age_days=1)
    scan = svc.invoke("scan", {"filters": filters(folder, min_age_days=30)})
    assert names(scan) == ["old.bin"]


def test_size_filter_keeps_only_big_files(svc, folder):
    make_file(folder, "small.dat", size=1_000)
    make_file(folder, "big.dat", size=2 * 1024 * 1024)
    scan = svc.invoke("scan", {"filters": filters(folder, min_size_mb=1)})
    assert names(scan) == ["big.dat"]


def test_scan_saves_filters_for_next_time(svc, ctx, folder):
    svc.invoke("scan", {"filters": filters(folder, extensions=["zip"], min_age_days=7)})
    again = svc.invoke("get_settings", {})
    assert again["folder"] == str(folder)
    assert again["extensions"] == ["zip"]
    assert again["min_age_days"] == 7


def test_missing_folder_and_drive_root_are_refused(svc, folder):
    with pytest.raises(ToolError) as e:
        svc.invoke("scan", {"filters": filters(folder / "absent")})
    assert e.value.code == "folder_not_found"
    with pytest.raises(ToolError) as e:
        svc.invoke("scan", {"filters": {"folder": Path(folder.anchor).as_posix()}})
    assert e.value.code == "root_folder"


def test_send_to_trash_recycles_only_selected_files(svc, folder, trashed):
    make_file(folder, "a.zip")
    make_file(folder, "b.zip")
    applied = svc.invoke(
        "send_to_trash", {"filters": filters(folder), "names": ["a.zip"]}
    )
    assert applied == {"removed": ["a.zip"], "failed": []}
    assert trashed == [str(folder / "a.zip")]


def test_names_outside_the_current_selection_are_not_trashed(svc, folder, trashed):
    make_file(folder, "keep.txt")
    make_file(folder, "gone.zip")
    applied = svc.invoke(
        "send_to_trash",
        {"filters": filters(folder, extensions=["zip"]), "names": ["keep.txt", "../x", "gone.zip"]},
    )
    assert applied["removed"] == ["gone.zip"]
    assert {f["name"]: f["reason"] for f in applied["failed"]} == {
        "keep.txt": "not_in_selection",
        "../x": "not_in_selection",
    }
    assert trashed == [str(folder / "gone.zip")]


def test_file_changed_since_scan_is_not_trashed(svc, folder, trashed):
    path = make_file(folder, "report.zip", age_days=0)
    scan_filters = filters(folder, min_age_days=30)
    applied = svc.invoke("send_to_trash", {"filters": scan_filters, "names": ["report.zip"]})
    assert applied["removed"] == []
    assert trashed == []
    assert path.exists()


def test_failed_trash_is_reported_and_others_continue(svc, folder, monkeypatch):
    make_file(folder, "locked.zip")
    make_file(folder, "free.zip")

    def fake(path: str) -> None:
        if path.endswith("locked.zip"):
            raise PermissionError("in use")

    monkeypatch.setattr(cleaner, "send2trash", fake)
    applied = svc.invoke(
        "send_to_trash",
        {"filters": filters(folder), "names": ["locked.zip", "free.zip"]},
    )
    assert applied["removed"] == ["free.zip"]
    assert applied["failed"] == [{"name": "locked.zip", "reason": "delete_failed"}]
