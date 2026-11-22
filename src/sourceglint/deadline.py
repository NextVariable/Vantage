"""Cooperative request deadlines for built-in research tools."""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

_deadline: ContextVar[float | None] = ContextVar("research_deadline", default=None)


@contextmanager
def deadline_scope(deadline: float | None):
    parent = _deadline.get()
    effective = min(parent, deadline) if parent is not None and deadline is not None else (
        parent if deadline is None else deadline
    )
    token = _deadline.set(effective)
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_time() -> float | None:
    deadline = _deadline.get()
    return None if deadline is None else max(0.0, deadline - monotonic())


def limit_timeout(timeout: float) -> float:
    remaining = remaining_time()
    if remaining is None:
        return timeout
    if remaining <= 0:
        raise TimeoutError("research deadline exceeded")
    return min(remaining, timeout)
