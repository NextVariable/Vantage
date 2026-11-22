"""Shared, append-only cost ledger for host model calls.

Model stages (``assessment``, ``synthesis`` ...) are not research cases. Every
record therefore carries both ``task`` and ``run_id`` so a per-run cap and a
batch cap can be evaluated over the same file.

The ledger is deliberately a local JSONL file guarded by ``fcntl.flock``. It
adds no service, database or vendor: concurrent engine processes (one per
benchmark case) share one file and each call re-reads it under an exclusive
lock before deciding whether a budget is exhausted.

Cost semantics:

* ``cost_known=False`` means the host did not report what a call cost.
  That is *not* zero. A hard budget cannot prove such spend stayed under the
  cap, so the next call is refused with ``cost_unknown``.
* ``observe`` mode records spend but never blocks on it, for hosts whose
  billing is only available outside the engine.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


def _entry_cost(row: dict) -> tuple[float, bool]:
    cost = row.get("cost_usd")
    if row.get("cost_known") is True and isinstance(cost, (int, float)):
        return float(cost), True
    return 0.0, False


@dataclass
class CostLedger:
    """One ledger per batch; ``None`` keeps an in-process ledger for tests."""

    path: Path | None = None
    entries: list[dict] = field(default_factory=list)

    @property
    def lock_path(self) -> Path | None:
        return self.path.with_suffix(self.path.suffix + ".lock") if self.path else None

    def record(self, *, run_id: str, task: str, status: str,
               cost_usd: float | None, cost_known: bool) -> dict:
        row = {
            "run_id": run_id or "run",
            "task": task,
            "status": status,
            "cost_usd": float(cost_usd) if cost_known and cost_usd is not None else None,
            "cost_known": bool(cost_known),
        }
        if self.path is None:
            self.entries.append(row)
            return row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        assert self.lock_path is not None
        with self.lock_path.open("a+b") as lock:
            _acquire(lock)
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                _release(lock)
        return row

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

    def totals(self, *, run_id: str | None = None) -> dict[str, Any]:
        batch_spent = 0.0
        batch_unknown = 0
        batch_entries = 0
        run_spent = 0.0
        run_unknown = 0
        run_entries = 0
        for row in self._rows():
            cost, known = _entry_cost(row)
            batch_entries += 1
            if known:
                batch_spent += cost
            else:
                batch_unknown += 1
            if run_id is not None and row.get("run_id") == run_id:
                run_entries += 1
                if known:
                    run_spent += cost
                else:
                    run_unknown += 1
        return {
            "entries": batch_entries,
            "spent_usd": round(batch_spent, 6),
            "unknown_calls": batch_unknown,
            "cost_known": batch_unknown == 0,
            "run_id": run_id,
            "run_entries": run_entries,
            "run_spent_usd": round(run_spent, 6),
            "run_unknown_calls": run_unknown,
        }

    def check(self, *, run_id: str, batch_budget_usd: float | None,
              run_budget_usd: float | None, mode: str = HARD) -> str | None:
        """Return a blocking category, or ``None`` when a call may proceed."""
        if mode != HARD:
            return None
        totals = self.totals(run_id=run_id)
        if batch_budget_usd is not None:
            if totals["spent_usd"] >= batch_budget_usd:
                return "budget_exceeded"
            if totals["unknown_calls"]:
                return "cost_unknown"
        if run_budget_usd is not None:
            if totals["run_spent_usd"] >= run_budget_usd:
                return "run_budget_exceeded"
            if totals["run_unknown_calls"]:
                return "cost_unknown"
        return None
