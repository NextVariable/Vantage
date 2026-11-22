"""Stage-aware synthesis budget and metered host model.

The synthesis phase (clustering → contradiction → semantic factors → facts →
inference → GTM) shares one wall-clock deadline. A per-cluster low-priority call
must never consume the time reserved for the fact layer and the final brief.

Design rules:
  * execution order stays unchanged; only admission is prioritized
  * the fact reserve and the brief floor are protected by every gate
  * a refused call is reported as UNAVAILABLE with a reason, never raised
  * the full evidence ledger is never touched here; only payload bytes are metered
  * clock is injectable for deterministic tests
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from statistics import median
from time import monotonic
from typing import Any, Callable, Mapping

from .deadline import deadline_scope, remaining_time
from .intelligence.model import ModelResponse, ModelStatus

STAGE_ORDER = (
    "clustering",
    "contradiction",
    "semantic_factors",
    "fact_synthesis",
    "claim_verification",
    "inference_synthesis",
    "gtm_implications",
    "recommendations",
    "brief",
)

# Lower number = more important when time is scarce.
STAGE_PRIORITY = {
    "clustering": 1,
    "contradiction": 2,
    "fact_synthesis": 3,
    "claim_verification": 4,
    "brief": 5,
    "inference_synthesis": 6,
    "semantic_factors": 7,
    "gtm_implications": 8,
    "recommendations": 9,
}

TASK_TO_STAGE = {
    "clustering": "clustering",
    "contradiction": "contradiction",
    "semantic_factors": "semantic_factors",
    "fact_synthesis": "fact_synthesis",
    "claim_support_verification": "claim_verification",
    "inference_synthesis": "inference_synthesis",
    "gtm_implications": "gtm_implications",
    "recommendations": "recommendations",
    "recommendation_generation": "recommendations",
    "recommendation_assessment": "recommendations",
    "recommendation_dedup": "recommendations",
    "recommendation_conflict": "recommendations",
}

BRIEF_FLOOR_SECONDS = 1.5
DEFAULT_CALL_SECONDS = 10.0
_FACT_MIN = 15.0
_FACT_MAX = 60.0
_INFERENCE_MAX = 20.0


@dataclass
class StageState:
    """Runtime record for one synthesis stage."""

    name: str
    status: str = "pending"  # pending | ok | degraded | skipped | failed
    seconds: float = 0.0
    calls: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "seconds": round(self.seconds, 2),
            "calls": self.calls,
            "reasons": list(self.reasons),
        }


@dataclass
class SynthesisBudget:
    """Wall-clock plan for one synthesis phase."""

    deadline: float | None
    clock: Callable[[], float] = monotonic
    initial_seconds: float = 0.0
    fact_reserve_seconds: float = 0.0
    inference_reserve_seconds: float = 0.0
    brief_floor_seconds: float = BRIEF_FLOOR_SECONDS
    semantic_call_cap: int = 0
    stages: dict[str, StageState] = field(default_factory=dict)
    calls_by_task: dict[str, int] = field(default_factory=dict)
    input_chars_by_task: dict[str, int] = field(default_factory=dict)
    seconds_by_task: dict[str, float] = field(default_factory=dict)
    observed_seconds: list[float] = field(default_factory=list)
    refusals: list[dict[str, str]] = field(default_factory=list)
    host_usage: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in STAGE_ORDER:
            self.stages.setdefault(name, StageState(name))

    # ---- construction -------------------------------------------------
    @classmethod
    def from_remaining(
        cls,
        remaining: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> "SynthesisBudget":
        """Split the remaining wall clock into protected and opportunistic time."""
        remaining = max(0.0, float(remaining))
        fact = min(max(0.35 * remaining, _FACT_MIN), _FACT_MAX)
        fact = min(fact, max(0.0, (remaining - BRIEF_FLOOR_SECONDS) / 2))
        inference = min(max(0.12 * remaining, 0.0), _INFERENCE_MAX)
        return cls(
            deadline=clock() + remaining,
            clock=clock,
            initial_seconds=remaining,
            fact_reserve_seconds=fact,
            inference_reserve_seconds=inference,
        )

    # ---- time ---------------------------------------------------------
    def remaining(self) -> float:
        if self.deadline is None:
            return float("inf")
        return max(0.0, self.deadline - self.clock())

    def observed_call_seconds(self) -> float:
        return median(self.observed_seconds) if self.observed_seconds else DEFAULT_CALL_SECONDS

    def refresh_semantic_cap(self) -> int:
        """Recompute how many semantic calls still fit without touching reserves."""
        if self.deadline is None:
            self.semantic_call_cap = 10_000
            return self.semantic_call_cap
        available = (
            self.remaining()
            - self.fact_reserve_seconds
            - self.inference_reserve_seconds
            - self.brief_floor_seconds
        )
        per_call = max(1.0, self.observed_call_seconds())
        self.semantic_call_cap = self.calls_by_task.get("semantic_factors", 0) + max(0, int(available // per_call))
        return self.semantic_call_cap

    def stage_deadline(self, stage: str) -> float | None:
        """Absolute deadline for a stage, preserving the stages that follow it."""
        if self.deadline is None:
            return None
        if stage == "clustering":
            return self.deadline - self.fact_reserve_seconds - self.brief_floor_seconds
        if stage == "contradiction":
            return self.deadline - self.fact_reserve_seconds - self.brief_floor_seconds
        if stage == "semantic_factors":
            return (
                self.deadline
                - self.fact_reserve_seconds
                - self.inference_reserve_seconds
                - self.brief_floor_seconds
            )
        if stage == "claim_verification":
            return (
                self.deadline
                - self.inference_reserve_seconds
                - self.brief_floor_seconds
            )
        if stage in ("fact_synthesis", "inference_synthesis", "gtm_implications", "recommendations"):
            return self.deadline - self.brief_floor_seconds
        return self.deadline

    # ---- admission ----------------------------------------------------
    def allow(self, task: str) -> tuple[bool, str]:
        """Return (allowed, reason). Unknown tasks are always allowed."""
        stage = TASK_TO_STAGE.get(task)
        if stage is None or self.deadline is None:
            return True, ""
        remaining = self.remaining()
        if stage in ("clustering", "contradiction"):
            need = self.fact_reserve_seconds + self.brief_floor_seconds
        elif stage == "semantic_factors":
            if self.calls_by_task.get(task, 0) >= self.semantic_call_cap:
                return False, "semantic factors skipped: call cap reached"
            need = (
                self.fact_reserve_seconds
                + self.inference_reserve_seconds
                + self.brief_floor_seconds
            )
        elif stage == "fact_synthesis":
            need = self.brief_floor_seconds
        elif stage == "claim_verification":
            need = (
                self.inference_reserve_seconds
                + self.brief_floor_seconds
                + min(self.observed_call_seconds(), 10.0)
            )
        elif stage == "inference_synthesis":
            need = self.brief_floor_seconds + 1.0
        elif stage in ("gtm_implications", "recommendations"):
            need = 8.0
        else:  # pragma: no cover - future stages
            need = 5.0
        if remaining <= need:
            return False, (
                f"{stage} skipped: {remaining:.1f}s left, "
                f"{need:.1f}s reserved for higher-priority stages"
            )
        return True, ""

    # ---- records ------------------------------------------------------
    def mark_stage(self, stage: str, status: str, reason: str = "") -> None:
        state = self.stages.setdefault(stage, StageState(stage))
        state.status = status
        if reason:
            state.reasons.append(reason)

    def record_refusal(self, task: str, reason: str) -> None:
        self.refusals.append({"task": task, "reason": reason})

    def record_call(
        self,
        task: str,
        *,
        input_chars: int,
        seconds: float,
        ok: bool,
    ) -> None:
        self.calls_by_task[task] = self.calls_by_task.get(task, 0) + 1
        self.input_chars_by_task[task] = self.input_chars_by_task.get(task, 0) + input_chars
        self.seconds_by_task[task] = self.seconds_by_task.get(task, 0.0) + seconds
        stage = TASK_TO_STAGE.get(task)
        if stage:
            state = self.stages.setdefault(stage, StageState(stage))
            state.calls += 1
            state.seconds += seconds
        if ok:
            self.observed_seconds.append(seconds)
        self.refresh_semantic_cap()

    # ---- reporting ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        approx_tokens = {
            task: int(chars / 4) for task, chars in sorted(self.input_chars_by_task.items())
        }
        return {
            "budget_seconds": round(self.initial_seconds, 2),
            "remaining_seconds": (
                None if self.deadline is None else round(self.remaining(), 2)
            ),
            "fact_reserve_seconds": round(self.fact_reserve_seconds, 2),
            "inference_reserve_seconds": round(self.inference_reserve_seconds, 2),
            "brief_floor_seconds": round(self.brief_floor_seconds, 2),
            "semantic_call_cap": self.semantic_call_cap,
            "observed_call_seconds": round(self.observed_call_seconds(), 2),
            "stages": {name: state.to_dict() for name, state in self.stages.items()},
            "model_io": {
                "calls_by_task": dict(sorted(self.calls_by_task.items())),
                "input_chars_by_task": dict(sorted(self.input_chars_by_task.items())),
                "approx_input_tokens_by_task": approx_tokens,
                "total_calls": sum(self.calls_by_task.values()),
                "host_usage": dict(self.host_usage) if self.host_usage else None,
            },
            "refusals": list(self.refusals[-25:]),
            "host_contract": {
                "protocol": "sourceglint-host/v2",
                "correlation": "host echoes request_id; legacy sequential hosts stay supported",
                "timeout_enforcement": "cooperative — engine admission gates plus the host per-call timeout",
                "recovery": (
                    "correlated hosts may continue after a timeout; "
                    "legacy hosts close the stream and later calls fail closed"
                ),
            },
        }


def _payload_chars(payload: Mapping[str, Any] | None) -> int:
    if not payload:
        return 0
    try:
        return len(json.dumps(payload, ensure_ascii=False, default=str))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0


class MeteredModel:
    """Transparent model wrapper that enforces the budget and records usage."""

    def __init__(self, inner: Any, budget: SynthesisBudget) -> None:
        self.inner = inner
        self.budget = budget

    @property
    def model_id(self) -> str:
        return str(getattr(self.inner, "model_id", "unknown"))

    def complete_structured(
        self,
        *,
        task: str,
        payload: Mapping[str, Any],
        response_schema: Mapping[str, Any],
    ) -> ModelResponse:
        stage = TASK_TO_STAGE.get(task, "")
        allowed, reason = self.budget.allow(task)
        cutoff = self.budget.stage_deadline(stage)
        effective = None if cutoff is None else monotonic() + (cutoff - self.budget.clock())
        with deadline_scope(effective):
            if not allowed or remaining_time() == 0:
                reason = reason or "stage or parent deadline reached before model dispatch"
                self.budget.record_refusal(task, reason)
                return ModelResponse(
                    task=task,
                    status=ModelStatus.UNAVAILABLE,
                    error=f"synthesis budget: {reason}",
                )
            chars = _payload_chars(payload)
            started = self.budget.clock()
            response = None
            try:
                response = self.inner.complete_structured(
                    task=task, payload=payload, response_schema=response_schema
                )
                return response
            except TimeoutError:
                return ModelResponse(task=task, status=ModelStatus.TIMEOUT, error="model call timed out")
            finally:
                elapsed = max(0.0, self.budget.clock() - started)
                self.budget.record_call(
                    task, input_chars=chars, seconds=elapsed, ok=bool(getattr(response, "ok", False))
                )

    def finalize(self) -> None:
        """Copy host-reported usage (tokens/cost) when the host exposes it."""
        summary = getattr(self.inner, "usage_summary", None)
        if callable(summary):
            try:
                self.budget.host_usage = dict(summary())
            except Exception:  # pragma: no cover - host reporting is best effort
                self.budget.host_usage = None
