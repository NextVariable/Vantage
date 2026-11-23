"""full-stack application orchestrator (compose only).

Composes Phase 3 → Phase 6C into one canonical run. Pure composition:
no scoring, clustering, insight, recommendation or rendering logic lives
here — each stage is an existing module call with validated hand-off.

Stage failure semantics (§19):
  * research all-sources-failed -> structured FAILED (no silent empty)
  * research partial           -> continue, PARTIAL
  * no usable evidence         -> NO_EVIDENCE result (brief still says so)
  * signals empty              -> brief degrades (no signals note)
  * insights empty             -> signals + coverage still render
  * recommendations empty      -> FACT/INFERENCE still render
A downstream stage NEVER discards upstream results.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from ..brief.dtos import BriefContext, BriefInput
from ..brief.pipeline import run_brief_pipeline
from ..deadline import remaining_time
from ..insights.pipeline import run_insight_pipeline
from ..intelligence.dtos import ResearchContext
from ..intelligence.model import IntelligencePipelineError
from ..intelligence.pipeline import run_intelligence_pipeline
from ..ledger import EvidenceLedger, EvidenceView
from ..pipeline.adaptive import AdaptiveResearch
from ..pipeline.degradation import AllSourcesFailedError
from ..pipeline.orchestrator import ResearchPipeline, ResearchPipelineResult
from ..recommendations.pipeline import run_recommendation_pipeline
from ..synthesis_budget import MeteredModel, SynthesisBudget

STAGE_OK = "ok"
STAGE_NONE = "none"
STAGE_DEGRADED = "degraded"
STAGE_FAILED = "failed"
STAGE_SKIPPED = "skipped"


def _stage(value: str) -> str:
    return value


def _synthesis_degraded(budget: SynthesisBudget, *, include_gtm: bool) -> bool:
    required = ("clustering", "contradiction", "fact_synthesis",
                "inference_synthesis", "semantic_factors")
    if include_gtm:
        required += ("gtm_implications", "recommendations")
    return any(budget.stages[name].status != "ok" for name in required)


def _delivery_level(
    insights: Sequence[Mapping[str, Any]],
    budget: SynthesisBudget | None,
    *,
    include_gtm: bool,
) -> str:
    if not any(row.get("type") == "FACT" for row in insights):
        return "evidence_only_report"
    if budget is not None and _synthesis_degraded(budget, include_gtm=include_gtm):
        return "evidence_backed_brief"
    return "full_brief"


def _execution_status(
    research_degraded: bool, budget: SynthesisBudget, *, include_gtm: bool,
) -> str:
    degraded = research_degraded or _synthesis_degraded(budget, include_gtm=include_gtm)
    return "PARTIAL" if degraded else "SUCCESS"


def _mark_brief(budget: SynthesisBudget | None) -> None:
    if budget is not None:
        budget.mark_stage("brief", "ok")


def _synthesis_payload(
    budget: SynthesisBudget | None,
    metered: MeteredModel | None,
) -> dict[str, Any] | None:
    if budget is None:
        return None
    if metered is not None:
        metered.finalize()
    return budget.to_dict()


@dataclass(frozen=True)
class ApplicationResult:
    """One full engine run's outcome (pre-SkillResult packaging)."""

    status: str  # SUCCESS | PARTIAL | NO_EVIDENCE | FAILED  (see interface.Status)
    brief: Any = None  # RenderedBrief | None
    evidence_count: int = 0
    signal_count: int = 0
    insight_count: int = 0
    recommendation_count: int = 0
    coverage: Any = None
    warnings: tuple[str, ...] = ()
    stage_statuses: Mapping[str, str] = field(default_factory=dict)
    signals: tuple[dict, ...] = ()
    insights: tuple[dict, ...] = ()
    recommendations: tuple[dict, ...] = ()
    delivery_level: str = ""
    synthesis: Mapping[str, Any] | None = None
    insight_diagnostics: Mapping[str, dict] = field(default_factory=dict)

    @property
    def markdown(self) -> str:
        return self.brief.markdown if self.brief is not None else ""


def build_research_context(
    plan: Mapping[str, Any],
    *,
    languages: tuple[str, ...] = (),
) -> ResearchContext:
    """Map a research_plan dict onto the Phase 5 ResearchContext DTO."""
    return ResearchContext(
        mode=str(plan.get("mode") or "general"),
        entities=tuple(str(e) for e in (plan.get("entities") or [])),
        market=str(plan.get("market") or "global"),
        decision_context=str(plan.get("decision_context") or ""),
        languages=tuple(languages or (plan.get("languages") or ["en"])),
        topic=str(plan.get("topic") or ""),
        subquestions=tuple(row["question"] for row in plan.get("subquestions", ())),
    )


def _evidence_by_id(ledger: EvidenceLedger | EvidenceView) -> dict[str, Mapping[str, Any]]:
    """eid -> full payload map for the 6A/6B evidence contracts."""
    return {r.evidence_id: r.to_payload() for r in ledger}


def _weak_signal_ids(signal_diagnostics: Sequence[Any]) -> set[str]:
    """Signal ids whose Phase 5 assessment flags a weak candidate."""
    out: set[str] = set()
    for d in signal_diagnostics:
        weak = getattr(d, "weak_signal", None)
        if weak is not None and bool(getattr(weak, "is_weak_candidate", False)):
            out.add(str(getattr(d, "signal_id", "")))
    return out


def _run_insights(
    signals: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    model: Any,
    *,
    research_context: ResearchContext,
    cache: Any,
    weak_signal_ids: set[str],
    include_gtm_implications: bool = True,
    budget: SynthesisBudget | None = None,
) -> tuple[Any, list[str]]:
    """Phase 6A. Raises nothing for ordinary emptiness (pipeline returns
    an empty result with warnings)."""
    warnings: list[str] = []
    result = run_insight_pipeline(
        signals,
        evidence_by_id,
        model,
        research_context=research_context,
        cache=cache,
        weak_signal_ids=weak_signal_ids,
        include_gtm_implications=include_gtm_implications,
        budget=budget,
    )
    warnings.extend(f"insights: {w}" for w in result.warnings)
    return result, warnings


def _run_recommendations(
    insights: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    model: Any,
    *,
    research_context: ResearchContext,
    cache: Any,
    insight_diagnostics: Sequence[Any],
    target_entity: str,
) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    result = run_recommendation_pipeline(
        insights,
        evidence_by_id,
        model,
        research_context=research_context,
        cache=cache,
        insight_diagnostics=insight_diagnostics,
        target_entity=target_entity,
    )
    warnings.extend(f"recommendations: {w}" for w in result.warnings)
    return result, warnings


@dataclass(frozen=True)
class OrchestrationContext:
    """Injected runtime wiring for one application run (§15, §45)."""

    research: ResearchPipeline  # Phase 3 orchestrator (adapters + config + cache)
    model: Any  # host-injected union model (Phase 5 / 6A / 6B boundary)
    as_of: datetime
    ledger: EvidenceLedger | EvidenceView = field(default_factory=lambda: EvidenceLedger(":memory:"))
    semantic_cache: Any = None
    drop_baseline_only: bool = True


def orchestrate(
    parsed: Any,
    *,
    plan: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    ctx: OrchestrationContext,
    target_entity: str = "",
    include_recommendations: bool = True,
    adaptive: AdaptiveResearch | None = None,
) -> ApplicationResult:
    """Run the canonical full pipeline for one parsed request.

    ``sources`` is the source-registry payload (list of entries) that the
    ResearchPipeline validates and the adapter factory resolves.
    """
    warnings: list[str] = []
    stage: dict[str, str] = {}

    # ---- Phase 3: research (evidence + coverage) -------------------------
    try:
        research_result: ResearchPipelineResult = ctx.research.run(
            plan=plan,
            sources=sources,
            ledger=ctx.ledger,
            **({"adaptive": adaptive, "target": target_entity} if adaptive is not None else {}),
        )
    except AllSourcesFailedError as exc:
        stage["research"] = STAGE_FAILED
        warnings.append(
            "research: all sources failed — no usable evidence retrieved"
        )
        for rep in exc.per_source.values():  # pragma: no cover - defensive
            for w in getattr(rep, "warnings", []):
                warnings.append(f"research:{rep.source}: {w}")
        return ApplicationResult(
            status="FAILED",
            evidence_count=0,
            warnings=tuple(warnings),
            stage_statuses=stage,
        )

    research_ctx = build_research_context(
        adaptive.plan if adaptive else plan, languages=tuple(parsed.languages),
    )
    evidence_count = research_result.coverage.final_evidence_count
    if adaptive:
        screened_ids = frozenset(
            eid for row in adaptive.assessments
            for key in ("evidence_ids", "feedback_ids", "vendor_claim_ids", "counterevidence_ids")
            for eid in row.get(key, ())
            if ctx.ledger.exists(eid)
        )
        n_retained = evidence_count
        screening_fallback = not screened_ids and n_retained > 0
        if screening_fallback:
            # Do not discard a completed retrieval because the screening step
            # returned nothing (an unavailable or partial assessment).
            screened_ids = frozenset(record.evidence_id for record in ctx.ledger)
            warnings.append(
                "adaptive: screening selected no evidence; analysis used the full retained corpus"
            )
        evidence_count = len(screened_ids)
        adaptive_coverage = dict(research_result.coverage.adaptive_research or {})
        adaptive_coverage["synthesis_evidence_count"] = evidence_count
        adaptive_coverage["screening_fallback"] = screening_fallback
        if screening_fallback:
            additional_gap = (
                f"Coverage screening selected no evidence; analysis used all {n_retained} retained items."
            )
        else:
            additional_gap = (
                f"Coverage screening selected {evidence_count} of {n_retained} retained items. "
                "Use the ledger for the full retrieval corpus."
            )
        coverage = replace(
            research_result.coverage,
            adaptive_research=adaptive_coverage,
            gaps=(*research_result.coverage.gaps, additional_gap) if evidence_count < n_retained
                 else research_result.coverage.gaps,
        )
        research_result = replace(research_result, coverage=coverage)
        ctx = replace(ctx, ledger=EvidenceView(ctx.ledger, screened_ids))
    adaptive_state = research_result.coverage.adaptive_research or {}
    research_degraded = bool(research_result.coverage.failed_sources) or (
        adaptive_state.get("stop_reason") in {"deadline_exceeded", "assessment_unavailable"}
        or adaptive_state.get("planning_status") in {"fallback", "fallback_routes", "unavailable"}
    )
    stage["research"] = STAGE_DEGRADED if research_degraded else STAGE_OK
    warnings.extend(f"research: {w}" for w in research_result.warnings)
    warnings.extend(
        f"research:{name}: {w}"
        for name, rep in research_result.source_statuses.items()
        for w in rep.warnings
    )

    # No-evidence guard (§19, §20): report cleanly, do not fabricate.
    if evidence_count == 0:
        brief = _render_empty_brief(
            parsed, research_result, ctx.ledger, ctx.as_of,
            discovery_only=not include_recommendations,
        )
        all_failed = bool(research_result.coverage.attempted_sources and not research_result.coverage.successful_sources)
        return ApplicationResult(
            status="FAILED" if all_failed else "NO_EVIDENCE",
            brief=brief,
            evidence_count=0,
            coverage=research_result.coverage,
            warnings=tuple(warnings),
            delivery_level="no_evidence",
            stage_statuses={
                "research": STAGE_FAILED if all_failed else stage["research"],
                "signals": STAGE_SKIPPED,
                "insights": STAGE_SKIPPED,
                "recommendations": STAGE_SKIPPED,
                "brief": STAGE_OK,
            },
        )

    # ---- Phase 5: signals -------------------------------------------------
    remaining = remaining_time()
    synthesis_budget = (
        SynthesisBudget.from_remaining(remaining)
        if remaining is not None else SynthesisBudget(deadline=None)
    )
    metered = MeteredModel(ctx.model, synthesis_budget)
    ctx = replace(ctx, model=metered)
    try:
        signal_result = run_intelligence_pipeline(
            [rec.to_payload() for rec in ctx.ledger] if adaptive else ctx.ledger,
            ctx.model,
            as_of=ctx.as_of,
            research_context=research_ctx,
            cache=ctx.semantic_cache,
            drop_baseline_only=ctx.drop_baseline_only,
            budget=synthesis_budget,
        )
    except IntelligencePipelineError as exc:
        warnings.append(f"signals: {exc}")
        brief = _render_without_signals(
            parsed, research_result, ctx.ledger, ctx.as_of,
            discovery_only=not include_recommendations,
            delivery_level="evidence_only_report",
        )
        _mark_brief(synthesis_budget)
        return ApplicationResult(
            status="PARTIAL",
            brief=brief,
            evidence_count=evidence_count,
            coverage=research_result.coverage,
            warnings=tuple(warnings),
            delivery_level="evidence_only_report",
            synthesis=_synthesis_payload(synthesis_budget, metered),
            stage_statuses={
                **stage,
                "signals": STAGE_FAILED,
                "insights": STAGE_SKIPPED,
                "recommendations": STAGE_SKIPPED,
                "brief": STAGE_OK,
            },
        )
    warnings.extend(f"signals: {w}" for w in signal_result.warnings)
    signals = signal_result.signals
    stage["signals"] = (
        STAGE_DEGRADED if not signals or any(
            state != "success" for state in signal_result.model_status.values()
        ) else STAGE_OK
    )

    if not signals:
        brief = _render_without_signals(
            parsed, research_result, ctx.ledger, ctx.as_of,
            discovery_only=not include_recommendations,
            delivery_level="evidence_only_report",
        )
        _mark_brief(synthesis_budget)
        return ApplicationResult(
            status="PARTIAL",
            brief=brief,
            evidence_count=evidence_count,
            signal_count=0,
            coverage=research_result.coverage,
            warnings=tuple(warnings),
            delivery_level="evidence_only_report",
            synthesis=_synthesis_payload(synthesis_budget, metered),
            stage_statuses={
                **stage,
                "insights": STAGE_SKIPPED,
                "recommendations": STAGE_SKIPPED,
                "brief": STAGE_OK,
            },
        )

    # ---- Phase 6A: FACT / INFERENCE insights ------------------------------
    evidence_by_id = _evidence_by_id(ctx.ledger)
    weak_ids = _weak_signal_ids(signal_result.diagnostics)
    insight_result, ins_warnings = _run_insights(
        signals,
        evidence_by_id,
        ctx.model,
        research_context=research_ctx,
        cache=ctx.semantic_cache,
        weak_signal_ids=weak_ids,
        include_gtm_implications=include_recommendations,
        budget=synthesis_budget,
    )
    warnings.extend(ins_warnings)
    insights = insight_result.insights
    stage["insights"] = (
        STAGE_DEGRADED if not insights or any(
            state != "success" for state in insight_result.model_status.values()
        ) else STAGE_OK
    )
    delivery = _delivery_level(
        insights, synthesis_budget, include_gtm=include_recommendations
    )

    # ---- Phase 6B: recommendations ----------------------------------------
    if not insights:
        brief = _render_insights_only(
            parsed, research_result, ctx.ledger, ctx.as_of, signals, (),
            discovery_only=not include_recommendations,
            delivery_level="evidence_only_report",
        )
        _mark_brief(synthesis_budget)
        return ApplicationResult(
            status="PARTIAL",
            brief=brief,
            evidence_count=evidence_count,
            signal_count=len(signals),
            insight_count=0,
            coverage=research_result.coverage,
            warnings=tuple(warnings),
            delivery_level="evidence_only_report",
            synthesis=_synthesis_payload(synthesis_budget, metered),
            stage_statuses={
                **stage,
                "recommendations": STAGE_SKIPPED,
                "brief": STAGE_OK,
            },
        )

    if not include_recommendations:
        insight_diags = {
            d.insight_id: d.to_dict()
            for d in insight_result.diagnostics
            if hasattr(d, "to_dict")
        }
        brief = _compose_brief(
            parsed, research_result, ctx.ledger, ctx.as_of,
            signals, insights, (), insight_diags, {}, (),
            discovery_only=True,
            delivery_level=delivery,
        )
        stage["recommendations"] = STAGE_SKIPPED
        stage["brief"] = STAGE_OK
        if synthesis_budget is not None:
            synthesis_budget.mark_stage(
                "recommendations", "skipped", "not requested"
            )
        _mark_brief(synthesis_budget)
        return ApplicationResult(
            status=_execution_status(research_degraded, synthesis_budget, include_gtm=False),
            brief=brief,
            evidence_count=evidence_count,
            signal_count=len(signals),
            insight_count=len(insights),
            recommendation_count=0,
            coverage=research_result.coverage,
            warnings=tuple(warnings),
            delivery_level=delivery,
            synthesis=_synthesis_payload(synthesis_budget, metered),
            stage_statuses=stage,
            signals=tuple(signals),
            insights=tuple(insights),
            insight_diagnostics=insight_diags,
        )

    rec_result, rec_warnings = _run_recommendations(
        insights,
        evidence_by_id,
        ctx.model,
        research_context=research_ctx,
        cache=ctx.semantic_cache,
        insight_diagnostics=insight_result.diagnostics,
        target_entity=target_entity,
    )
    warnings.extend(rec_warnings)
    recommendations = rec_result.recommendations
    rec_degraded = any(
        state != "success" for state in rec_result.model_status.values()
    )
    stage["recommendations"] = STAGE_DEGRADED if rec_degraded else STAGE_OK
    synthesis_budget.mark_stage("recommendations", stage["recommendations"])
    delivery = _delivery_level(insights, synthesis_budget, include_gtm=True)

    # ---- Phase 6C: brief ----------------------------------------------------
    diag_by_id = {
        d.insight_id: d.to_dict()
        for d in insight_result.diagnostics
        if hasattr(d, "to_dict")
    }
    rec_diag_by_id = {
        d.insight_id: d.to_dict()
        for d in rec_result.diagnostics
        if hasattr(d, "to_dict")
    }
    brief = _compose_brief(
        parsed,
        research_result,
        ctx.ledger,
        ctx.as_of,
        signals,
        insights,
        recommendations,
        diag_by_id,
        rec_diag_by_id,
        rec_result.conflicts,
        delivery_level=delivery,
    )

    status = _execution_status(research_degraded, synthesis_budget, include_gtm=True)
    stage["brief"] = STAGE_OK
    _mark_brief(synthesis_budget)
    return ApplicationResult(
        status=status,
        brief=brief,
        evidence_count=evidence_count,
        signal_count=len(signals),
        insight_count=len(insights),
        recommendation_count=len(recommendations),
        coverage=research_result.coverage,
        warnings=tuple(warnings),
        delivery_level=delivery,
        synthesis=_synthesis_payload(synthesis_budget, metered),
        stage_statuses=stage,
        signals=tuple(signals),
        insights=tuple(insights),
        recommendations=tuple(recommendations),
        insight_diagnostics=diag_by_id,
    )


# ------------------------------------------------------------- brief helpers

def _support_note(insight_diagnostics: Mapping[str, Any] | None) -> str:
    """One sentence describing fact-level citation support (never a verdict)."""
    rows = [
        row for row in (insight_diagnostics or {}).values()
        if isinstance(row, Mapping) and str(row.get("type")) == "FACT"
    ]
    if not rows:
        return ""
    total = len(rows)
    verified = sum(1 for row in rows if row.get("support_status") == "verified")
    supported = sum(
        1 for row in rows if row.get("support_status") in {"verified", "supported"}
    )
    vendor = sum(1 for row in rows if row.get("support_status") == "vendor_only")
    unverified = total - supported - vendor
    parts = [f"{supported} of {total} facts quote a located supporting excerpt"]
    if verified:
        parts.append(f"{verified} passed the semantic check")
    else:
        parts.append("none has been promoted to verified")
    if vendor:
        parts.append(f"{vendor} rest on vendor material only")
    if unverified:
        parts.append(f"{unverified} remain unverified")
    return "; ".join(parts) + "."


def _brief_input(
    parsed: Any,
    *,
    coverage: Any,
    ledger: Any,
    as_of: datetime,
    signals: Sequence[Mapping[str, Any]] = (),
    insights: Sequence[Mapping[str, Any]] = (),
    recommendations: Sequence[Mapping[str, Any]] = (),
    insight_diagnostics: Mapping[str, Any] | None = None,
    recommendation_diagnostics: Mapping[str, Any] | None = None,
    conflicts: Sequence[Any] = (),
    discovery_only: bool = False,
    delivery_level: str = "",
) -> BriefInput:
    return BriefInput(
        context=BriefContext(
            query=parsed.query,
            topic=getattr(parsed, "topic", ""),
            mode=parsed.mode,
            market=parsed.market,
            languages=tuple(parsed.languages),
            time_window=parsed.time_window_text,
            as_of=as_of.date().isoformat() if as_of.tzinfo is not None
            else as_of.isoformat(),
            entities=tuple(parsed.entities),
            decision_context=parsed.decision_context,
            discovery_only=discovery_only,
            delivery_level=delivery_level,
            support_note=_support_note(insight_diagnostics),
        ),
        ledger=ledger,
        signals=tuple(signals),
        insights=tuple(insights),
        recommendations=tuple(recommendations),
        insight_diagnostics=insight_diagnostics or {},
        recommendation_diagnostics=recommendation_diagnostics or {},
        conflicts=tuple(conflicts),
        coverage=coverage,
    )


def _compose_brief(
    parsed: Any,
    research_result: ResearchPipelineResult,
    ledger: Any,
    as_of: datetime,
    signals: Sequence[Mapping[str, Any]],
    insights: Sequence[Mapping[str, Any]],
    recommendations: Sequence[Mapping[str, Any]],
    insight_diagnostics: Mapping[str, Any],
    recommendation_diagnostics: Mapping[str, Any],
    conflicts: Sequence[Any],
    discovery_only: bool = False,
    delivery_level: str = "",
) -> Any:
    brief_input = _brief_input(
        parsed,
        coverage=research_result.coverage,
        ledger=ledger,
        as_of=as_of,
        signals=signals,
        insights=insights,
        recommendations=recommendations,
        insight_diagnostics=insight_diagnostics,
        recommendation_diagnostics=recommendation_diagnostics,
        conflicts=conflicts,
        discovery_only=discovery_only,
        delivery_level=delivery_level,
    )
    return run_brief_pipeline(brief_input)


def _render_empty_brief(
    parsed: Any, research_result: ResearchPipelineResult, ledger: Any, as_of: datetime,
    *, discovery_only: bool = False,
) -> Any:
    return run_brief_pipeline(
        _brief_input(
            parsed, coverage=research_result.coverage, ledger=ledger, as_of=as_of,
            discovery_only=discovery_only,
        )
    )


def _render_without_signals(
    parsed: Any, research_result: ResearchPipelineResult, ledger: Any, as_of: datetime,
    *, discovery_only: bool = False, delivery_level: str = "",
) -> Any:
    return run_brief_pipeline(
        _brief_input(
            parsed, coverage=research_result.coverage, ledger=ledger, as_of=as_of,
            discovery_only=discovery_only, delivery_level=delivery_level,
        )
    )


def _render_insights_only(
    parsed: Any,
    research_result: ResearchPipelineResult,
    ledger: Any,
    as_of: datetime,
    signals: Sequence[Mapping[str, Any]],
    insights: Sequence[Mapping[str, Any]],
    *, discovery_only: bool = False, delivery_level: str = "",
) -> Any:
    return run_brief_pipeline(
        _brief_input(
            parsed,
            coverage=research_result.coverage,
            ledger=ledger,
            as_of=as_of,
            signals=signals,
            insights=insights,
            discovery_only=discovery_only,
            delivery_level=delivery_level,
        )
    )
