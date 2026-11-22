"""Shared, append-only cost ledger for host model calls.

Model stages (``assessment``, ``synthesis`` ...) are not research cases. Every
record therefore carries both ``task`` and ``run_id`` so a per-run cap and a
batch cap can be evaluated over the same file.

The ledger is deliberately a local JSONL file guarded by ``fcntl.flock`` (or
``msvcrt.locking`` on Windows). It adds no service, database or vendor:
concurrent engine processes (one per benchmark case) share one file.

Concurrency model
-----------------

A previous version checked the file and recorded the result in two separate
critical sections. Two processes could both observe unspent budget and both
call the host before either recorded a cost. The ledger now exposes an atomic
``reserve``/``settle`` pair:

* ``reserve`` takes the exclusive lock, re-reads every row, decides whether a
  call fits, and appends an ``in_flight`` row in the same critical section.
* ``settle`` appends the billed outcome for that ``call_id``. The reservation
  stops counting via the settle row; a crash between reserve and settle leaves
  the reservation counted, which is conservative.

Cost semantics
--------------

``cost_state`` is explicit for every row:

* ``known`` - the host reported the billed amount.
* ``unknown`` - the host did not report it. That is *not* zero.
* ``unbilled`` - the call was refused before/at the provider boundary
  (missing command, 401/402/403, rate limit, missing model), so no charge is
  expected.
* ``in_flight`` - reserved but not settled yet.

Budget enforcement is only *strict* when a per-call ceiling is known
(``max_call_usd``). Without it the ledger can only do a pre-call check, so a
concurrently running call may overshoot the cap by at most one call per worker;
that mode is reported as ``guarded`` and never as a strict hard budget.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

try:  # pragma: no cover - platform-specific locking
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]
try:  # pragma: no cover
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]


def _acquire(handle) -> None:
    """Exclusive lock across processes on POSIX and Windows."""
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    elif msvcrt is not None:  # pragma: no cover - Windows CI
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)


def _release(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    elif msvcrt is not None:  # pragma: no cover - Windows CI
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


HARD = "hard"
OBSERVE = "observe"
MODES = (HARD, OBSERVE)
BLOCKING = ("budget_exceeded", "cost_unknown")

# Enforcement levels reported to callers. Only ``strict`` is a hard guarantee.
STRICT = "strict"
GUARDED = "guarded"
OBSERVED = "observe"
UNENFORCED = "none"

# Per-call cost states.
KNOWN = "known"
UNKNOWN = "unknown"
UNBILLED = "unbilled"
IN_FLIGHT = "in_flight"

_EPSILON = 1e-9


def budget_enforcement(*, mode: str, batch_budget_usd: float | None,
                       max_call_usd: float | None) -> str:
    """Name what the configured budget can actually guarantee.

    ``strict`` requires both a batch cap and a per-call ceiling: reservations
    then keep committed spend at or below the cap. Without a ceiling only a
    pre-call check is possible, so the cap is ``guarded`` (bounded overshoot of
    one in-flight call per worker) and must not be described as strict.
    """
    if mode != HARD:
        return OBSERVED if mode == OBSERVE else UNENFORCED
    if batch_budget_usd is None:
        return UNENFORCED
    return STRICT if max_call_usd is not None else GUARDED


def _state(row: dict) -> str:
    state = row.get("cost_state")
    if state in (KNOWN, UNKNOWN, UNBILLED, IN_FLIGHT):
        return str(state)
    return KNOWN if row.get("cost_known") is True else UNKNOWN


@dataclass
class CostLedger:
    """One ledger per batch; ``None`` keeps an in-process ledger for tests."""

    path: Path | None = None
    entries: list[dict] = field(default_factory=list)
    _sequence: int = 0

    @property
    def lock_path(self) -> Path | None:
        return self.path.with_suffix(self.path.suffix + ".lock") if self.path else None

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self.path is None:
            yield
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        assert self.lock_path is not None
        with self.lock_path.open("a+b") as lock:
            _acquire(lock)
            try:
                yield
            finally:
                _release(lock)

    def _append(self, row: dict) -> None:
        if self.path is None:
            self.entries.append(row)
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _rows(self) -> list[dict]:
        if self.path is None:
            return list(self.entries)
        if not self.path.exists():
            return []
        rows: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _new_call_id(self, rows: list[dict]) -> str:
        taken = {row.get("call_id") for row in rows if isinstance(row, dict)}
        while True:
            self._sequence += 1
            # No uuid/random: the pid separates processes, ``id(self)``
            # separates model instances inside one process and the sequence
            # separates calls made by one instance.
            candidate = f"{os.getpid()}-{id(self):x}-{self._sequence}"
            if candidate not in taken:
                return candidate

    def record(self, *, run_id: str, task: str, status: str,
               cost_usd: float | None, cost_known: bool) -> dict:
        """Append one already-settled call (compatibility helper)."""
        with self._locked():
            call_id = self._new_call_id(self._rows())
            row = {
                "kind": "settle",
                "call_id": call_id,
                "run_id": run_id or "run",
                "task": task,
                "status": status,
                "cost_usd": float(cost_usd) if cost_known and cost_usd is not None else 0.0,
                "cost_known": bool(cost_known),
                "cost_state": KNOWN if cost_known and cost_usd is not None else UNKNOWN,
                "basis": "reported" if cost_known and cost_usd is not None else "not_reported",
            }
            self._append(row)
        return row

    def reserve(self, *, run_id: str, task: str, ceiling_usd: float | None = None,
                batch_budget_usd: float | None = None, run_budget_usd: float | None = None,
                mode: str = HARD) -> dict[str, Any]:
        """Atomically decide and reserve one call.

        Returns ``granted`` plus the blocking ``category`` when refused. In
        hard mode the decision and the ``in_flight`` append happen under one
        lock, so two processes can never both consume the same capacity.
        """
        with self._locked():
            rows = self._rows()
            totals = _totals(rows, run_id)
            if mode == HARD:
                category = _refusal(totals, ceiling_usd, batch_budget_usd, run_budget_usd)
                if category is not None:
                    return {"granted": False, "category": category,
                            "call_id": None, "reserved_usd": ceiling_usd}
            call_id = self._new_call_id(rows)
            if mode == OBSERVE:
                return {"granted": True, "category": None, "call_id": call_id,
                        "reserved_usd": None}
            row = {
                "kind": "reserve",
                "call_id": call_id,
                "run_id": run_id or "run",
                "task": task,
                "status": IN_FLIGHT,
                "cost_usd": None,
                "cost_known": False,
                "cost_state": IN_FLIGHT,
                "reserved_usd": float(ceiling_usd) if ceiling_usd is not None else None,
            }
            self._append(row)
        return {"granted": True, "category": None, "call_id": call_id,
                "reserved_usd": row["reserved_usd"]}

    def settle(self, call_id: str, *, run_id: str, task: str, status: str,
               cost_usd: float, cost_known: bool, cost_state: str | None = None,
               basis: str | None = None) -> dict[str, Any]:
        """Append the outcome of one reserved call.

        ``cost_usd`` is the amount charged against the cap. For an unknown
        outcome it may be the reserved ceiling (a conservative upper bound);
        ``cost_known`` then stays false so the hard budget refuses the next
        call instead of pretending the ceiling was the bill.
        """
        state = cost_state or (KNOWN if cost_known else UNKNOWN)
        charged = float(cost_usd or 0.0)
        row = {
            "kind": "settle",
            "call_id": call_id,
            "run_id": run_id or "run",
            "task": task,
            "status": status,
            "cost_usd": charged,
            "cost_known": bool(cost_known),
            "cost_state": state,
            "basis": basis or ("reported" if cost_known else "not_reported"),
        }
        with self._locked():
            rows = self._rows()
            reserved = None
            for item in rows:
                if item.get("call_id") == call_id and item.get("kind") == "reserve":
                    reserved = item.get("reserved_usd")
            self._append(row)
        overshoot = 0.0
        if (state == KNOWN and isinstance(reserved, (int, float))
                and charged > float(reserved) + _EPSILON):
            overshoot = round(charged - float(reserved), 6)
        return {"charged_usd": round(charged, 6), "overshoot_usd": overshoot,
                "cost_state": state, "reserved_usd": reserved}

    def totals(self, *, run_id: str | None = None) -> dict[str, Any]:
        with self._locked():
            return _totals(self._rows(), run_id)

    def check(self, *, run_id: str, batch_budget_usd: float | None,
              run_budget_usd: float | None, mode: str = HARD) -> str | None:
        """Return a blocking category, or ``None`` when a call may proceed.

        This pre-call check remains for callers that cannot reserve (the batch
        runner gate). The host model itself uses :meth:`reserve`, which is
        atomic with the accounting decision.
        """
        if mode != HARD:
            return None
        totals = self.totals(run_id=run_id)
        if batch_budget_usd is not None:
            if totals["spent_usd"] >= batch_budget_usd - _EPSILON:
                return "budget_exceeded"
            if totals["unknown_calls"]:
                return "cost_unknown"
        if run_budget_usd is not None:
            if totals["run_spent_usd"] >= run_budget_usd - _EPSILON:
                return "run_budget_exceeded"
            if totals["run_unknown_calls"]:
                return "cost_unknown"
        return None


def _refusal(totals: dict[str, Any], ceiling_usd: float | None,
             batch_budget_usd: float | None, run_budget_usd: float | None) -> str | None:
    batch = batch_budget_usd
    if batch is not None:
        if totals["spent_usd"] >= batch - _EPSILON:
            return "budget_exceeded"
        if totals["unknown_calls"]:
            return "cost_unknown"
        if ceiling_usd is not None and totals["committed_usd"] + ceiling_usd > batch + _EPSILON:
            return "budget_exceeded"
    run = run_budget_usd
    if run is not None:
        if totals["run_spent_usd"] >= run - _EPSILON:
            return "run_budget_exceeded"
        if totals["run_unknown_calls"]:
            return "cost_unknown"
        if ceiling_usd is not None and totals["run_committed_usd"] + ceiling_usd > run + _EPSILON:
            return "run_budget_exceeded"
    return None


def _totals(rows: list[dict], run_id: str | None) -> dict[str, Any]:
    """Aggregate committed spend, in-flight reservations and cost states.

    Rows with a ``call_id`` are paired reserve/settle. A settle supersedes its
    reservation; an unmatched reservation stays in flight and stays committed.
    Legacy rows without a call id (written by older versions) are counted as
    settled outcomes.
    """
    reservations: dict[str, dict] = {}
    settlements: dict[str, dict] = {}
    order: list[str] = []
    legacy: list[dict] = []
    for row in rows:
        call_id = row.get("call_id")
        if call_id:
            if call_id not in reservations and call_id not in settlements:
                order.append(call_id)
            if row.get("kind") == "reserve":
                reservations[call_id] = row
            else:
                settlements[call_id] = row
        else:
            legacy.append(row)

    batch = _Accumulator()
    per_run = _Accumulator()
    for call_id in order:
        settle_row = settlements.get(call_id)
        reserve_row = reservations.get(call_id)
        row = settle_row or reserve_row
        assert row is not None
        in_run = run_id is not None and row.get("run_id") == run_id
        batch.add(row, IN_FLIGHT if settle_row is None else None)
        if in_run:
            per_run.add(row, IN_FLIGHT if settle_row is None else None)
        if settle_row is not None and reserve_row is not None:
            reserved = reserve_row.get("reserved_usd")
            charged = settle_row.get("cost_usd")
            if (isinstance(reserved, (int, float)) and isinstance(charged, (int, float))
                    and _state(settle_row) == KNOWN
                    and float(charged) > float(reserved) + _EPSILON):
                extra = float(charged) - float(reserved)
                batch.overshoot += extra
                if in_run:
                    per_run.overshoot += extra
    for row in legacy:
        in_run = run_id is not None and row.get("run_id") == run_id
        batch.add(row, None)
        if in_run:
            per_run.add(row, None)

    result = {
        "entries": len(legacy) + len(order),
        "rows": len(rows),
        "spent_usd": round(batch.spent, 6),
        "unknown_calls": batch.unknown,
        "cost_known": batch.unknown == 0,
        "in_flight_calls": batch.in_flight,
        "in_flight_usd": round(batch.in_flight_usd, 6),
        "committed_usd": round(batch.spent + batch.in_flight_usd, 6),
        "overshoot_usd": round(batch.overshoot, 6),
        "states": dict(batch.states),
        "run_id": run_id,
        "run_entries": per_run.entries,
        "run_spent_usd": round(per_run.spent, 6),
        "run_unknown_calls": per_run.unknown,
        "run_in_flight_calls": per_run.in_flight,
        "run_in_flight_usd": round(per_run.in_flight_usd, 6),
        "run_committed_usd": round(per_run.spent + per_run.in_flight_usd, 6),
        "run_states": dict(per_run.states),
    }
    return result


class _Accumulator:
    def __init__(self) -> None:
        self.entries = 0
        self.spent = 0.0
        self.unknown = 0
        self.in_flight = 0
        self.in_flight_usd = 0.0
        self.overshoot = 0.0
        self.states: dict[str, int] = {}

    def add(self, row: dict, forced_state: str | None) -> None:
        self.entries += 1
        state = forced_state or _state(row)
        self.states[state] = self.states.get(state, 0) + 1
        if state == IN_FLIGHT:
            self.in_flight += 1
            reserved = row.get("reserved_usd")
            if isinstance(reserved, (int, float)):
                self.in_flight_usd += float(reserved)
            return
        charged = row.get("cost_usd")
        if isinstance(charged, (int, float)):
            self.spent += float(charged)
        if state == UNKNOWN:
            self.unknown += 1
