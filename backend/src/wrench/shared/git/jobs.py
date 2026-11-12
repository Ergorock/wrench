"""Background git operations: a bounded pool, at most one operation per repository."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from wrench.shared.git.errors import GitOpError

logger = logging.getLogger("wrench.shared.git")


@dataclass(frozen=True)
class JobState:
    running: str | None
    error: dict[str, str] | None
    finished_at: datetime | None


_IDLE = JobState(None, None, None)


class RepoJobs:
    def __init__(self, max_workers: int = 4) -> None:
        # Daemon threads, not a ThreadPoolExecutor: its workers are joined at interpreter exit,
        # so closing Wrench would wait for every queued fetch while holding the
        # single-instance mutex. A git process still running at exit simply finishes alone.
        self._slots = threading.BoundedSemaphore(max_workers)
        self._states: dict[str, JobState] = {}
        self._cond = threading.Condition()

    def submit(self, repo: str, op: str, fn: Callable[[], None]) -> bool:
        """Starts `fn` in the background; False, without starting it, when an operation
        is already running on this repository."""
        with self._cond:
            current = self._states.get(repo, _IDLE)
            if current.running is not None:
                return False
            self._states[repo] = JobState(op, current.error, current.finished_at)
        threading.Thread(target=self._run, args=(repo, fn), name=f"git-{op}", daemon=True).start()
        return True

    def _run(self, repo: str, fn: Callable[[], None]) -> None:
        error: dict[str, str] | None = None
        try:
            with self._slots:
                fn()
        except GitOpError as exc:
            error = {"code": exc.code, "message": exc.message}
        except Exception as exc:
            logger.exception("Unexpected error in a git operation on %s", repo)
            error = {"code": "git_failed", "message": str(exc)}
        with self._cond:
            self._states[repo] = JobState(None, error, datetime.now(UTC))
            self._cond.notify_all()

    def state(self, repo: str) -> JobState:
        with self._cond:
            return self._states.get(repo, _IDLE)

    def clear_error(self, repo: str) -> None:
        with self._cond:
            current = self._states.get(repo)
            if current is not None:
                self._states[repo] = JobState(current.running, None, current.finished_at)

    def wait_idle(self, timeout: float) -> bool:
        """True once no operation is running; False after `timeout` seconds."""
        with self._cond:
            return self._cond.wait_for(
                lambda: all(s.running is None for s in self._states.values()), timeout
            )
