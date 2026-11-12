"""Branches and commit history of one repository. Read-only: no command here changes the
repository."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from wrench.shared.git.errors import GitOpError, run_or_raise
from wrench.shared.git.runner import STATUS_TIMEOUT

DEFAULT_LIMIT = 50

_HEADS = "refs/heads/"
_REMOTES = "refs/remotes/"
_FIELD = "\x1f"
_RECORD = "\x1e"
_REF_FORMAT = "%1f".join(
    [
        "%(refname)",
        "%(HEAD)",
        "%(upstream)",
        "%(upstream:track,nobracket)",
        "%(committerdate:iso-strict)",
        "%(symref)",
    ]
)
_LOG_FORMAT = "%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1f%B%x1e"
_TRACK = re.compile(r"(ahead|behind) (\d+)")


class LocalBranch(BaseModel):
    name: str
    current: bool
    upstream: str | None
    ahead: int
    behind: int
    # Against the main branch; None for the main branch itself or without a main branch.
    merged: bool | None
    commits_not_in_main: int | None
    last_commit: datetime | None


class RemoteBranch(BaseModel):
    name: str
    last_commit: datetime | None


class BranchList(BaseModel):
    main: str | None
    local: list[LocalBranch]
    remote: list[RemoteBranch]


class CommitInfo(BaseModel):
    short_hash: str
    hash: str
    subject: str
    message: str
    author: str
    date: datetime
    unpushed: bool


@dataclass(frozen=True)
class _Ref:
    refname: str
    head: str  # "*" for the current branch
    upstream: str  # full refname, "" without one
    track: str
    date: str
    symref: str


def _git(repo: Path, *args: str) -> str:
    return run_or_raise(repo, args, STATUS_TIMEOUT)


def _refs(repo: Path) -> list[_Ref]:
    out = _git(repo, "for-each-ref", f"--format={_REF_FORMAT}", _HEADS, _REMOTES)
    return [_Ref(*line.split(_FIELD)) for line in out.splitlines() if line]


def _short(refname: str) -> str:
    return refname.removeprefix(_HEADS).removeprefix(_REMOTES)


def _date(text: str) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def _main_ref(refs: list[_Ref]) -> str | None:
    """`main`, else `master`, else the target of `origin/HEAD`, as a full refname."""
    names = {r.refname for r in refs}
    for candidate in (f"{_HEADS}main", f"{_HEADS}master"):
        if candidate in names:
            return candidate
    origin_head = next((r for r in refs if r.refname == f"{_REMOTES}origin/HEAD"), None)
    if origin_head and origin_head.symref in names:
        return origin_head.symref
    return None


def _count(repo: Path, exclude: str, include: str) -> int:
    return int(_git(repo, "rev-list", "--count", f"{exclude}..{include}").strip())


def _track(text: str) -> tuple[int, int]:
    counts = dict(_TRACK.findall(text))
    return int(counts.get("ahead", 0)), int(counts.get("behind", 0))


def list_branches(repo: Path) -> BranchList:
    refs = _refs(repo)
    names = {r.refname for r in refs}
    main = _main_ref(refs)
    local: list[LocalBranch] = []
    remote: list[RemoteBranch] = []
    for ref in refs:
        if ref.refname.startswith(_REMOTES):
            if not ref.refname.endswith("/HEAD"):
                remote.append(RemoteBranch(name=_short(ref.refname), last_commit=_date(ref.date)))
            continue
        not_in_main = _count(repo, main, ref.refname) if main and ref.refname != main else None
        ahead, behind = _track(ref.track)
        local.append(
            LocalBranch(
                name=_short(ref.refname),
                current=ref.head == "*",
                # A configured upstream that was deleted on the remote is reported as none.
                upstream=_short(ref.upstream) if ref.upstream in names else None,
                ahead=ahead,
                behind=behind,
                merged=None if not_in_main is None else not_in_main == 0,
                commits_not_in_main=not_in_main,
                last_commit=_date(ref.date),
            )
        )
    local.sort(key=lambda b: not b.current)  # stable: the current branch first
    return BranchList(main=_short(main) if main else None, local=local, remote=remote)


def _resolve(repo: Path, refs: list[_Ref], ref: str | None) -> tuple[str, str | None] | None:
    """(full refname or "HEAD", full upstream refname or None) of the history to show; None
    for a repository without any commit. A `ref` that is not an existing branch is refused,
    so that it can never be read by git as an option or a revision expression."""
    names = {r.refname: r for r in refs}
    if ref is None:
        head = _optional(repo, "symbolic-ref", "-q", "HEAD")
        if head in names:
            return head, _upstream(names[head], names)
        if _optional(repo, "rev-parse", "--verify", "-q", "HEAD") is None:
            return None  # no commit yet
        return "HEAD", None  # detached
    for full in (f"{_HEADS}{ref}", f"{_REMOTES}{ref}"):
        found = names.get(full)
        if found is not None and ref and not full.endswith("/HEAD"):
            return full, _upstream(found, names)
    raise GitOpError("unknown_ref", f"Unknown branch: {ref}")


def _upstream(ref: _Ref, names: dict[str, _Ref]) -> str | None:
    return ref.upstream if ref.upstream in names else None


def _optional(repo: Path, *args: str) -> str | None:
    """Stripped stdout, or None when the command fails (a query answered "no")."""
    try:
        return _git(repo, *args).strip()
    except GitOpError as exc:
        if exc.code in ("timeout", "not_a_repo"):
            raise
        return None


def list_commits(
    repo: Path, ref: str | None, skip: int, limit: int = DEFAULT_LIMIT
) -> list[CommitInfo]:
    """Commits of `ref` (a local or remote branch name; None for HEAD), newest first."""
    resolved = _resolve(repo, _refs(repo), ref)
    if resolved is None:
        return []
    target, upstream = resolved
    out = _git(
        repo,
        "log",
        f"--skip={max(skip, 0)}",
        f"--max-count={limit}",
        f"--format={_LOG_FORMAT}",
        "--end-of-options",
        target,
        "--",
    )
    unpushed: set[str] = set()
    if upstream is not None:
        unpushed = set(_git(repo, "rev-list", "--end-of-options", f"{upstream}..{target}").split())
    commits = []
    for record in out.split(_RECORD):
        record = record.lstrip("\n")
        if not record:
            continue
        full, short, author, date, subject, message = record.split(_FIELD, 5)
        commits.append(
            CommitInfo(
                short_hash=short,
                hash=full,
                subject=subject,
                message=message.strip(),
                author=author,
                date=datetime.fromisoformat(date),
                unpushed=full in unpushed,
            )
        )
    return commits
