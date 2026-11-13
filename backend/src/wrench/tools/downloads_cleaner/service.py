import os
import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from send2trash import send2trash

from wrench.sdk import ToolError, ToolService, action

BYTES_PER_MB = 1024 * 1024
SECONDS_PER_DAY = 24 * 60 * 60


class Filters(BaseModel):
    folder: str = Field(min_length=1)
    # Empty list: every extension. Written without the dot, compared in lower case.
    extensions: list[str] = Field(default_factory=list)
    # 0: any age. A file is a candidate when it was last modified at least this many days ago.
    min_age_days: int = Field(default=0, ge=0)
    # 0: any size.
    min_size_mb: float = Field(default=0, ge=0)


class Candidate(BaseModel):
    name: str
    size: int
    modified: str


class Scan(BaseModel):
    folder: str
    files: list[Candidate]
    total_size: int


class Failure(BaseModel):
    name: str
    reason: str


class Applied(BaseModel):
    removed: list[str]
    failed: list[Failure]


def _default_folder() -> str:
    return str(Path.home() / "Downloads")


def _check_folder(folder: str) -> Path:
    path = Path(folder)
    if not path.is_dir():
        raise ToolError("folder_not_found", f"Folder not found: {folder}")
    if path == Path(path.anchor):
        raise ToolError("root_folder", "A drive root cannot be cleaned.")
    return path


def _normalized_extensions(extensions: list[str]) -> set[str]:
    return {e.strip().lower().lstrip(".") for e in extensions if e.strip()}


def _candidates(filters: Filters, now: float) -> list[Candidate]:
    """Files directly in the folder that match the filters. Subfolders and links are skipped."""
    root = _check_folder(filters.folder)
    extensions = _normalized_extensions(filters.extensions)
    cutoff = now - filters.min_age_days * SECONDS_PER_DAY
    min_bytes = filters.min_size_mb * BYTES_PER_MB
    found: list[Candidate] = []
    with os.scandir(root) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            ext = Path(entry.name).suffix.lower().lstrip(".")
            if extensions and ext not in extensions:
                continue
            stat = entry.stat(follow_symlinks=False)
            if stat.st_mtime > cutoff or stat.st_size < min_bytes:
                continue
            found.append(
                Candidate(
                    name=entry.name,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).date().isoformat(),
                )
            )
    found.sort(key=lambda c: c.name.lower())
    return found


class DownloadsCleanerService(ToolService):
    @action
    def get_settings(self) -> Filters:
        stored = self.ctx.storage.load().get("filters")
        if isinstance(stored, dict):
            try:
                return Filters.model_validate(stored)
            except ValueError:
                pass
        return Filters(folder=_default_folder())

    @action
    def scan(self, filters: Filters) -> Scan:
        candidates = _candidates(filters, time.time())
        self.ctx.storage.save({"filters": filters.model_dump()})
        return Scan(
            folder=filters.folder,
            files=candidates,
            total_size=sum(c.size for c in candidates),
        )

    @action
    def send_to_trash(self, filters: Filters, names: list[str]) -> Applied:
        """Recycle the named files, after checking again that they still match the filters.

        The list the user saw may be stale: a file renamed, moved or changed since the scan is
        not sent to the bin.
        """
        allowed = {c.name for c in _candidates(filters, time.time())}
        root = Path(filters.folder)
        removed: list[str] = []
        failed: list[Failure] = []
        for name in names:
            if name not in allowed:
                failed.append(Failure(name=name, reason="not_in_selection"))
                continue
            try:
                send2trash(str(root / name))
            except OSError:
                failed.append(Failure(name=name, reason="delete_failed"))
            else:
                removed.append(name)
        return Applied(removed=removed, failed=failed)


SERVICE = DownloadsCleanerService
