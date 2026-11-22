"""Negative-claim propagation into FACT / INFERENCE statements."""
from __future__ import annotations

from sourceglint.insights.dtos import PreparedSignal
from sourceglint.insights.facts import synthesize_facts
from sourceglint.insights.inferences import synthesize_inferences
from sourceglint.insights.model import (
    FakeFactScript,
    FakeInferenceScript,
    FakeInsightModel,
)


def _signal() -> PreparedSignal:
    return PreparedSignal(
        signal_id="sig_a",
        signal_type="cross_source",
        claim="coding agent release activity",
        score=0.7,
        confidence=0.8,
        evidence_ids=("ev_1",),
        supporting_evidence_summaries=("one item",),
        counter_evidence_summaries=(),
        market="global",
        language="en",
        current_count=1,
        baseline_count=0,
        weak_signal=False,
    )


def test_fact_negative_claim_is_qualified():
    model = FakeInsightModel(
        fact_scripts=(
            FakeFactScript(
                signal_ids=("sig_a",),
                statement="No release artifact exists for the candidate.",
                evidence_ids=("ev_1",),
            ),
        )
    )
    result = synthesize_facts([_signal()], model, {"ev_1": {}})
    assert result.validated
    statement = result.validated[0].statement
    assert statement.startswith("Unverified absence:")
    assert "release artifact exists" in statement
    assert any("absence claims qualified" in w for w in result.warnings)


def test_inference_negative_claim_is_qualified():
    model = FakeInsightModel(
        inference_scripts=(
            FakeInferenceScript(
                fact_ids=("fact_1",),
                signal_ids=("sig_a",),
                statement="There are no independent user reviews.",
                evidence_ids=("ev_1",),
            ),
        )
    )
    result = synthesize_inferences(
        facts=[_fact_draft()],
        fact_insight_ids=["fact_1"],
        prepared_signals=[_signal()],
        model=model,
        evidence_by_id={"ev_1": {}},
    )
    assert result.validated
    statement = result.validated[0].statement
    assert statement.startswith("Unverified absence:")
    assert "independent user reviews" in statement


def test_positive_fact_statement_is_untouched():
    model = FakeInsightModel(
        fact_scripts=(
            FakeFactScript(
                signal_ids=("sig_a",),
                statement="One candidate shipped two releases.",
                evidence_ids=("ev_1",),
            ),
        )
    )
    result = synthesize_facts([_signal()], model, {"ev_1": {}})
    assert result.validated[0].statement == "One candidate shipped two releases."


def _fact_draft():
    from sourceglint.insights.dtos import FactDraft

    return FactDraft(
        statement="One candidate shipped two releases.",
        signal_ids=("sig_a",),
        evidence_ids=("ev_1",),
        confidence=0.8,
    )
