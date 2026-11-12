"""Errors of git operations, with a stable code the interface can translate."""

from collections.abc import Sequence
from pathlib import Path

from wrench.shared.git.runner import GitTimeout, run_git

MAX_MESSAGE = 500

_AUTH_MARKERS = (
    "Authentication failed",
    "could not read Username",
    "terminal prompts disabled",
    "Permission denied (publickey)",
    "cannot prompt because user interactivity has been disabled",  # GCM_INTERACTIVE=never
)
_DIVERGED_MARKERS = (
    "Not possible to fast-forward",
    "diverging",
    "divergent",
    # push refused because the remote has commits we do not have
    "[rejected]",
    "non-fast-forward",
    "fetch first",
)


class GitOpError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def classify_error(stderr: str) -> str:
    """Code of a failed git command, from its error output."""
    lowered = stderr.lower()
    if any(marker.lower() in lowered for marker in _AUTH_MARKERS):
        return "auth_required"
    if "not a git repository" in stderr:
        return "not_a_repo"
    if any(marker in stderr for marker in _DIVERGED_MARKERS):
        return "diverged"
    return "git_failed"


def run_or_raise(repo: Path, args: Sequence[str], timeout: float, interactive: bool = True) -> str:
    """Stdout of a successful git command; GitOpError otherwise."""
    try:
        result = run_git(repo, args, timeout, interactive=interactive)
    except GitTimeout as exc:
        raise GitOpError("timeout", str(exc)) from exc
    if result.code != 0:
        raise GitOpError(classify_error(result.stderr), result.stderr.strip()[-MAX_MESSAGE:])
    return result.stdout
