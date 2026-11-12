import threading
import time

from wrench.shared.git.jobs import RepoJobs
from wrench.shared.git.ops import GitOpError


def test_one_op_per_repo_and_errors_isolated() -> None:
    jobs = RepoJobs()
    gate = threading.Event()
    assert jobs.submit("r1", "push", gate.wait) is True
    assert jobs.state("r1").running == "push"
    assert jobs.submit("r1", "push", lambda: None) is False

    def boom() -> None:
        raise GitOpError("timeout", "t")

    jobs.submit("r2", "fetch", boom)
    gate.set()
    assert jobs.wait_idle(5)
    assert jobs.state("r1").error is None and jobs.state("r1").running is None
    assert jobs.state("r1").finished_at is not None
    assert jobs.state("r2").error == {"code": "timeout", "message": "t"}
    jobs.clear_error("r2")
    assert jobs.state("r2").error is None


def test_success_clears_previous_error() -> None:
    jobs = RepoJobs()

    def boom() -> None:
        raise GitOpError("timeout", "t")

    jobs.submit("r", "fetch", boom)
    jobs.wait_idle(5)
    jobs.submit("r", "fetch", lambda: None)
    jobs.wait_idle(5)
    assert jobs.state("r").error is None


def test_unexpected_exception_is_git_failed() -> None:
    jobs = RepoJobs()

    def broken() -> None:
        raise ZeroDivisionError("division by zero")

    jobs.submit("r", "fetch", broken)
    jobs.wait_idle(5)
    error = jobs.state("r").error
    assert error is not None and error["code"] == "git_failed"


def test_unknown_repo_state_is_empty() -> None:
    state = RepoJobs().state("nope")
    assert (state.running, state.error, state.finished_at) == (None, None, None)


def test_max_parallel() -> None:
    jobs = RepoJobs(max_workers=4)
    running: list[int] = []
    peak = [0]
    lock = threading.Lock()
    go = threading.Event()

    def work() -> None:
        with lock:
            running.append(1)
            peak[0] = max(peak[0], len(running))
        go.wait(2)
        with lock:
            running.pop()

    for i in range(8):
        jobs.submit(f"r{i}", "fetch", work)
    time.sleep(0.3)
    go.set()
    jobs.wait_idle(5)
    assert peak[0] == 4
