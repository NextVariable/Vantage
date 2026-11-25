"""Explicit per-research ceiling for metered source requests."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock

from ..pipeline.adapters import AdapterUnavailable


@dataclass
class PaidAttempts:
    limit: int
    used: int = 0


_current: ContextVar[PaidAttempts | None] = ContextVar("paid_source_attempts", default=None)
_lock = Lock()


@contextmanager
def paid_scope(limit: int):
    if type(limit) is not int or limit < 0:
        raise ValueError("paid_source_calls must be a nonnegative integer")
    current = _current.get()
    if current is not None:
        yield current
        return
    budget = PaidAttempts(limit)
    token = _current.set(budget)
    try:
        yield budget
    finally:
        _current.reset(token)


def paid_available() -> bool:
    budget = _current.get()
    return budget is not None and budget.used < budget.limit


def charge_attempt(provider: str) -> None:
    # Reserve before I/O; HTTP failures and retries consume attempts.
    with _lock:
        budget = _current.get()
        if budget is None or budget.used >= budget.limit:
            raise AdapterUnavailable(provider, "metered source requires an explicit remaining attempt budget")
        budget.used += 1
