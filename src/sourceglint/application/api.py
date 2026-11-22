"""canonical public entry point.

``run_sourceglint(...)`` is THE single public API. Hosts, the CLI
and the Skill runtime all call exactly this function (Gate F). It:

    natural-language query
    -> SkillRequest normalization (interface.request)
    -> deterministic parsing (interface.parser)
    -> full-stack application orchestration (application.orchestrator)
    -> SkillResult (interface.result)

The pipeline composition is delegated — this module only wires the
runtime (model + adapters + registry) and packages the result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Mapping, Sequence

from ..deadline import deadline_scope
from ..interface.parser import parse_request
from ..interface.request import MODES, SkillRequest
from ..interface.result import SkillResult, Status
from ..ledger import EvidenceLedger
from ..synthesis_budget import MeteredModel, SynthesisBudget
from .orchestrator import OrchestrationContext, orchestrate
from .runtime import default_adapter_factory, default_sources

# Re-export the pipeline types callers need to construct offline runs.
from ..pipeline.orchestrator import PipelineConfig, ResearchPipeline

__all__ = ["run_sourceglint"]

# The adaptive phase gets ``timeout_seconds + 45`` of wall clock. A bounded
# share is held back for synthesis so a slow final retrieval round cannot leave
# the brief with no model budget. The reserve scales with request complexity
# (entities, languages, mode) instead of assuming one fixed percentage fits
# every run; it is still capped by a share of the total budget.
_SYNTHESIS_RESERVE_MIN = 60.0
_SYNTHESIS_RESERVE_MAX = 140.0
_SYNTHESIS_RESERVE_SHARE_CAP = 0.45
_RESEARCH_FLOOR_SECONDS = 30.0
_DECISION_HEAVY_MODES = {"competitor", "opportunity", "market"}
# The adaptive planner runs after the reserve is fixed. Typical plans contain
# 2-4 subquestions; 3 is the observed median for industry/competitor requests.
_DEFAULT_EXPECTED_SUBQUESTIONS = 3


def _synthesis_reserve(
    total: float,
    *,
    entities: int,
    languages: int,
    mode: str,
    subquestions: int = 0,
) -> tuple[float, int]:
    """Return (seconds, complexity score, preferred target) for synthesis.

    The reserve is always non-negative and never exceeds the share cap, so a
    short budget cannot reserve more time than the run actually has. The
    preferred minimum shrinks with the budget instead of overriding it.

    Synthesis cost scales with the number of evidence clusters and therefore
    with the number of research subquestions; entities and languages add
    clustering payload but at a smaller rate.
    """
    complexity = (
        1
        + min(4, max(0, entities))
        + min(3, max(0, languages))
        + min(6, max(0, subquestions))
    )
    if total <= 0:
        return 0.0, complexity
    upper = min(_SYNTHESIS_RESERVE_MAX, total * _SYNTHESIS_RESERVE_SHARE_CAP)
    target = 40.0 + 11.0 * complexity
    if mode in _DECISION_HEAVY_MODES:
        target += 8.0
    reserve = max(min(_SYNTHESIS_RESERVE_MIN, upper), min(upper, target))
    return max(0.0, min(upper, reserve)), complexity


def _to_iso(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def run_sourceglint(
    query: str,
    *,
    # --- optional request overrides (empty => parsed from the query) -----
    mode: str = "",
    market: str = "",
    window_days: int | None = None,
    languages: Sequence[str] = (),
    entities: Sequence[str] = (),
    target: str = "",
    baseline: bool = False,
    decision_support: bool = False,
    source_preferences: Sequence[str] = (),
    decision_context: str = "",
    # --- runtime injection (host-neutral) --------------------------------
    model: Any = None,
    adapter_factory: Any = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
    retrieval_cache: Any = None,
    semantic_cache: Any = None,
    as_of: datetime | str | None = None,
    ledger: Any = None,
    raw_output: str | None = None,
    adaptive: bool = False,
    opportunities: bool = False,
    start_date: str = "",
    end_date: str = "",
    research_rounds: int = 2,
    research_timeout_seconds: float = 90,
) -> SkillResult:
    """Run the canonical sourceglint pipeline for one request.

    ``query`` is required; ``model`` is required (host-injected union
    model implementing the Phase 5/6A/6B complete_structured contract).
    ``adapter_factory`` and ``sources`` default to the repository
    registry wiring; inject fakes for offline/deterministic runs.
    """
    if not query or not str(query).strip():
        raise ValueError("query is required and non-empty")
    if model is None:
        raise ValueError(
            "run_sourceglint requires a host-injected model "
            "(IntelligenceModel protocol). The core is host-neutral; no "
            "vendor client is bundled."
        )
    if mode and mode not in MODES:
        raise ValueError(f"mode must be one of {MODES!r}; got {mode!r}")
    if baseline:
        raise ValueError(
            "prior-window retrieval is not wired in the public runtime; "
            "baseline comparisons are not yet available"
        )

    # 1) Normalize + parse.
    request = SkillRequest(
        query=str(query),
        mode=mode,
        market=market,
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        languages=tuple(languages),
        entities=tuple(entities),
        target=target,
        baseline=baseline,
        source_preferences=tuple(source_preferences),
        decision_context=decision_context,
    )
    parsed = parse_request(request)

    if parsed.needs_clarification:
        return SkillResult(
            status=Status.FAILED,
            request=parsed,
            warnings=(parsed.clarification_reason,),
            stage_statuses={"parse": "needs_clarification"},
        )

    # 2) Wire the runtime.
    if as_of is None:
        raise ValueError("as_of is required; the host must supply the run timestamp")
    as_of_dt = _to_iso(as_of)
    source_list = list(sources) if sources is not None else default_sources()
    factory = adapter_factory or default_adapter_factory
    if raw_output:
        from ..artifacts import recording_factory
        factory = recording_factory(factory, raw_output)
    research = ResearchPipeline(
        config=PipelineConfig(as_of=as_of_dt.isoformat(), cache=retrieval_cache),
        adapter_factory=factory,
    )
    ctx = OrchestrationContext(
        research=research,
        model=model,
        as_of=as_of_dt,
        ledger=ledger if ledger is not None else EvidenceLedger(":memory:"),
        semantic_cache=semantic_cache,
    )

    from ..pipeline.adaptive import AdaptiveResearch, ResearchBudget
    plan = parsed.to_plan()
    if "start" in plan["time_window"]:
        cutoff = as_of_dt.replace(tzinfo=timezone.utc) if as_of_dt.tzinfo is None else as_of_dt.astimezone(timezone.utc)
        if _to_iso(plan["time_window"]["start"]) > cutoff:
            raise ValueError("research range starts after as_of")
        plan["time_window"]["end"] = min(_to_iso(plan["time_window"]["end"]), cutoff).isoformat()
    if adaptive and len(ctx.ledger):
        raise ValueError("adaptive research requires a fresh evidence ledger")
    budget = ResearchBudget(research_rounds, research_timeout_seconds) if adaptive else None
    started = monotonic()
    run_deadline = started + budget.timeout_seconds + 45 if budget else None
    # Research must not consume the whole wall clock: synthesis (signals,
    # insights, brief) needs model calls of its own. Reserve a bounded share
    # instead of letting the last retrieval round run into the final seconds.
    research_reserve = 0.0
    research_deadline = None
    reserve_complexity = 0
    reserve_target = 0.0
    reserve_subquestions = len(plan.get("subquestions") or ())
    estimated_subquestions = reserve_subquestions or _DEFAULT_EXPECTED_SUBQUESTIONS
    short_budget = False
    if run_deadline is not None:
        total_seconds = run_deadline - started
        research_reserve, reserve_complexity = _synthesis_reserve(
            total_seconds,
            entities=len(parsed.entities),
            languages=len(parsed.languages),
            mode=parsed.mode,
            subquestions=estimated_subquestions,
        )
        reserve_target = 40.0 + 11.0 * reserve_complexity
        if parsed.mode in _DECISION_HEAVY_MODES:
            reserve_target += 8.0
        # Research gets exactly what synthesis does not reserve. The two phases
        # can never claim overlapping time, and the window is never negative.
        research_seconds = max(0.0, total_seconds - research_reserve)
        short_budget = research_seconds < _RESEARCH_FLOOR_SECONDS
        research_deadline = started + research_seconds
    adaptive_run = AdaptiveResearch(
        model, plan, source_list, budget=budget, opportunities=opportunities,
        deadline=research_deadline,
    ) if budget else None

    # 3) Run the full engine.
    orchestrate_started = monotonic()
    with deadline_scope(run_deadline):
        outcome = orchestrate(
            parsed,
            plan=plan,
            sources=source_list,
            ctx=ctx,
            target_entity=target or parsed.target,
            include_recommendations=decision_support,
            adaptive=adaptive_run,
        )
    orchestrate_seconds = monotonic() - orchestrate_started

    # 4) Package.
    package_started = monotonic()
    diagnostics: dict[str, Any] = {
        "evidence_count": outcome.evidence_count,
        "signal_count": outcome.signal_count,
        "insight_count": outcome.insight_count,
        "recommendation_count": outcome.recommendation_count,
    }
    if outcome.delivery_level:
        diagnostics["delivery_level"] = outcome.delivery_level
    if outcome.synthesis:
        diagnostics["synthesis"] = dict(outcome.synthesis)
    fact_support = [
        {
            "insight_id": row.get("insight_id"),
            "status": row.get("support_status"),
            "semantic": row.get("semantic_verification"),
            "origins": row.get("independent_origins"),
            "claims": row.get("support_claims") or [],
            "reasons": row.get("support_reasons") or [],
        }
        for row in (outcome.insight_diagnostics or {}).values()
        if isinstance(row, Mapping) and str(row.get("type")) == "FACT"
    ]
    if fact_support:
        diagnostics["fact_support"] = fact_support
    if getattr(ctx.ledger, "path", None) is not None:
        diagnostics["evidence_ledger"] = str(ctx.ledger.path)
    if raw_output:
        from pathlib import Path
        if Path(raw_output).exists():
            diagnostics["raw_source_archive"] = str(raw_output)
    if outcome.coverage is not None:
        coverage = outcome.coverage.to_dict()
        diagnostics["coverage"] = coverage
        research = coverage.get("adaptive_research") or {}
        rounds = research.get("rounds") or []
        retrieval_seconds = float(research.get("retrieval_seconds") or 0.0)
        assessment_seconds = float(research.get("assessment_seconds") or 0.0)
        planning_seconds = float(research.get("planning_seconds") or 0.0)
        synthesis_seconds = max(0.0, orchestrate_seconds - retrieval_seconds
                                - assessment_seconds - planning_seconds)
        diagnostics["performance"] = {
            "elapsed_seconds": round(monotonic() - started, 2),
            "budget_seconds": round(run_deadline - started, 1) if run_deadline else None,
            "research_budget_seconds": round(research_deadline - started, 1) if research_deadline else None,
            "synthesis_reserve_seconds": round(research_reserve, 1) if research_reserve else None,
            "synthesis_reserve_basis": {
                "complexity": reserve_complexity,
                "subquestions": reserve_subquestions,
                "estimated_subquestions": estimated_subquestions,
                "target_seconds": round(reserve_target, 1),
                "min_seconds": _SYNTHESIS_RESERVE_MIN,
                "max_seconds": _SYNTHESIS_RESERVE_MAX,
                "share_cap": _SYNTHESIS_RESERVE_SHARE_CAP,
                "research_floor_seconds": _RESEARCH_FLOOR_SECONDS,
                "short_budget": short_budget,
            },
            "phases": {
                "planning": round(planning_seconds, 2),
                "retrieval": round(retrieval_seconds, 2),
                "assessment": round(assessment_seconds, 2),
                "synthesis": round(synthesis_seconds, 2),
                "orchestrate_total": round(orchestrate_seconds, 2),
            },
            "research_rounds": len(rounds),
            "routes_executed": sum(row.get("executed_routes", 0) for row in rounds),
            "routes_empty": sum(row.get("empty_routes", 0) for row in rounds),
            "routes_failed": sum(row.get("failed_routes", 0) for row in rounds),
            "research_model_calls": research.get("planning_model_calls"),
            "retained_evidence": outcome.evidence_count,
            # Each phase reports its own outcome, so a late or failed stage is
            # visible without inferring it from the final status.
            "phase_status": {
                "planning": research.get("planning_status", "not_used"),
                "research": research.get("stop_reason"),
                "synthesis": outcome.status,
            },
        }
    brief = outcome.markdown
    status = Status(outcome.status)
    if opportunities:
        from ..recommendations.opportunities import discover_opportunities, render_opportunities
        opportunity_started = monotonic()
        opportunity_meter = MeteredModel(model, SynthesisBudget(deadline=run_deadline))
        with deadline_scope(run_deadline):
            hypotheses, state = discover_opportunities(
                opportunity_meter, parsed.query, outcome.insights, ctx.ledger,
                research_assessments=adaptive_run.assessments if adaptive_run else (),
            )
        diagnostics["opportunity_discovery"] = {"status": state, "hypotheses": hypotheses}
        if status == Status.SUCCESS and state == "model_unavailable":
            status = Status.PARTIAL
        if brief:
            brief += render_opportunities(hypotheses, ctx.ledger, state)
        if "performance" in diagnostics:
            diagnostics["performance"]["opportunity_model_calls"] = sum(
                opportunity_meter.budget.calls_by_task.values()
            )
            phases = diagnostics["performance"]["phases"]
            phases["opportunity"] = round(monotonic() - opportunity_started, 2)
            diagnostics["performance"]["phase_status"]["opportunity"] = state
    if "performance" in diagnostics:
        diagnostics["performance"]["elapsed_seconds"] = round(monotonic() - started, 2)
        phases = diagnostics["performance"]["phases"]
        phases["report"] = round(max(0.0, monotonic() - package_started
                                    - phases.get("opportunity", 0.0)), 2)
    return SkillResult(
        status=status,
        brief_markdown=brief,
        request=parsed,
        research_plan=adaptive_run.plan if adaptive_run else plan,
        warnings=outcome.warnings,
        stage_statuses=outcome.stage_statuses,
        diagnostics=diagnostics,
        delivery_level=outcome.delivery_level,
    )
