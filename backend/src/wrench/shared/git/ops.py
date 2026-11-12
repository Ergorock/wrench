"""Safe git operations: never a force push, a merge or a rebase."""

from pathlib import Path

from wrench.shared.git.errors import GitOpError, classify_error, run_or_raise
from wrench.shared.git.runner import COMMIT_TIMEOUT, NETWORK_TIMEOUT
from wrench.shared.git.status import RepoStatus, read_status

__all__ = ["GitOpError", "classify_error", "fetch", "pull", "push", "commit_all"]


def _require_remote(status: RepoStatus) -> None:
    if status.remote_url is None:
        raise GitOpError("no_remote", "The repository has no remote")


def _require_branch(status: RepoStatus) -> None:
    if status.detached:
        raise GitOpError("detached_head", "HEAD is detached")
    if status.operation is not None:
        raise GitOpError("in_progress", f"A {status.operation} is in progress")


def fetch(repo: Path, interactive: bool = True) -> None:
    """`interactive=False` for automatic fetches: no credential prompt, auth_required."""
    _require_remote(read_status(repo))
    run_or_raise(repo, ["fetch", "--prune"], NETWORK_TIMEOUT, interactive=interactive)


def pull(repo: Path) -> None:
    status = read_status(repo)
    _require_remote(status)
    _require_branch(status)
    run_or_raise(repo, ["pull", "--ff-only"], NETWORK_TIMEOUT)


def push(repo: Path) -> None:
    status = read_status(repo)
    _require_remote(status)
    _require_branch(status)
    if status.upstream is None and status.branch is not None:
        remotes = run_or_raise(repo, ["remote"], NETWORK_TIMEOUT).split()
        if "origin" in remotes:
            run_or_raise(repo, ["push", "-u", "origin", status.branch], NETWORK_TIMEOUT)
            return
    run_or_raise(repo, ["push"], NETWORK_TIMEOUT)


def commit_all(repo: Path, message: str) -> None:
    """Stages every change (`add -A`) and commits it."""
    message = message.strip()
    if not message:
        raise GitOpError("empty_message", "The commit message is empty")
    status = read_status(repo)
    _require_branch(status)
    if status.conflicts > 0:
        # Conflicts without an operation marker (`stash pop`, `checkout -m`): `add -A` would
        # mark them resolved and commit the conflict markers.
        raise GitOpError("in_progress", "Unresolved conflicts")
    if status.staged + status.unstaged + status.untracked + status.conflicts == 0:
        raise GitOpError("nothing_to_commit", "Nothing to commit")
    run_or_raise(repo, ["add", "-A"], COMMIT_TIMEOUT)
    run_or_raise(repo, ["commit", "-m", message], COMMIT_TIMEOUT)
