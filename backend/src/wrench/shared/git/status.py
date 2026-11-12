"""State of one repository, read from `git status --porcelain=v2`."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from wrench.shared.git.errors import GitOpError, run_or_raise
from wrench.shared.git.remote import HostKind, host_kind
from wrench.shared.git.runner import STATUS_TIMEOUT

MAX_CHANGED_FILES = 200

Operation = Literal["merge", "rebase", "cherry-pick", "revert"]

# Marker in the git directory → operation in progress.
_OPERATION_MARKERS: tuple[tuple[str, Operation], ...] = (
    ("MERGE_HEAD", "merge"),
    ("rebase-merge", "rebase"),
    ("rebase-apply", "rebase"),
    ("CHERRY_PICK_HEAD", "cherry-pick"),
    ("REVERT_HEAD", "revert"),
)


class RepoStatus(BaseModel):
    path: str
    branch: str | None
    detached: bool
    upstream: str | None
    ahead: int
    behind: int
    staged: int
    unstaged: int
    untracked: int
    conflicts: int
    operation: Operation | None
    remote_url: str | None
    host: HostKind
    last_fetch: datetime | None
    changed_files: list[str]


def parse_porcelain_v2(output: str) -> dict[str, Any]:
    """Parses `git status --porcelain=v2 --branch -z` output."""
    result: dict[str, Any] = {
        "branch": None,
        "detached": False,
        "upstream": None,
        "ahead": 0,
        "behind": 0,
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "conflicts": 0,
        "changed_files": [],
    }
    files: list[str] = result["changed_files"]

    def add_file(path: str) -> None:
        if len(files) < MAX_CHANGED_FILES:
            files.append(path)

    entries = iter(output.split("\0"))
    for entry in entries:
        if entry.startswith("# branch.head "):
            head = entry.removeprefix("# branch.head ")
            result["detached"] = head == "(detached)"
            result["branch"] = None if result["detached"] else head
        elif entry.startswith("# branch.upstream "):
            result["upstream"] = entry.removeprefix("# branch.upstream ")
        elif entry.startswith("# branch.ab "):
            ahead, behind = entry.removeprefix("# branch.ab ").split()
            result["ahead"], result["behind"] = abs(int(ahead)), abs(int(behind))
        elif entry.startswith(("1 ", "2 ")):
            fields = entry.split(" ", 8 if entry[0] == "1" else 9)
            xy = fields[1]
            result["staged"] += xy[0] != "."
            result["unstaged"] += xy[1] != "."
            add_file(fields[-1])
            if entry[0] == "2":
                next(entries, None)  # original path of a rename or copy
        elif entry.startswith("u "):
            result["conflicts"] += 1
            add_file(entry.split(" ", 10)[-1])
        elif entry.startswith("? "):
            result["untracked"] += 1
            add_file(entry[2:])
    return result


def _git(repo: Path, *args: str) -> str:
    return run_or_raise(repo, args, STATUS_TIMEOUT)


def _remote_url(repo: Path) -> str | None:
    for name in ("origin", *_git(repo, "remote").split()):
        try:
            return _git(repo, "remote", "get-url", name).strip() or None
        except GitOpError:
            continue
    return None


def read_status(repo: Path) -> RepoStatus:
    if not repo.is_dir():
        raise GitOpError("not_a_repo", f"Not a directory: {repo}")
    parsed = parse_porcelain_v2(
        _git(repo, "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=normal")
    )
    git_dir_line, fetch_head_line = _git(
        repo, "rev-parse", "--absolute-git-dir", "--git-path", "FETCH_HEAD"
    ).splitlines()[:2]
    git_dir = Path(git_dir_line)
    operation = next((op for marker, op in _OPERATION_MARKERS if (git_dir / marker).exists()), None)
    fetch_head = Path(fetch_head_line)
    if not fetch_head.is_absolute():
        fetch_head = repo / fetch_head
    try:
        last_fetch: datetime | None = datetime.fromtimestamp(fetch_head.stat().st_mtime, UTC)
    except OSError:
        last_fetch = None
    url = _remote_url(repo)
    return RepoStatus(
        path=str(repo),
        operation=operation,
        remote_url=url,
        host=host_kind(url),
        last_fetch=last_fetch,
        **parsed,
    )
