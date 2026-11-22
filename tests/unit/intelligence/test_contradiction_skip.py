"""Deterministic skip for single-member contradiction clusters."""
from __future__ import annotations

from sourceglint.intelligence import contradiction
from sourceglint.intelligence.dtos import PreparedEvidence, ValidatedCluster
from sourceglint.intelligence.ids import derive_cluster_id
from sourceglint.intelligence.model import FakeIntelligenceModel


def _ev(eid: str) -> PreparedEvidence:
    return PreparedEvidence(
        evidence_id=eid,
        source="reddit",
        source_type="comment",
        window="current",
        title=f"t {eid}",
        snippet=f"s {eid}",
        published_at="2026-09-01",
        market="global",
        language="en",
        source_tier=2,
        url=f"https://example.com/{eid}",
        has_text=True,
    )


def test_single_member_cluster_skips_model():
    cluster = ValidatedCluster(
        cluster_id=derive_cluster_id(("ev_1",)),
        label="L",
        claim="c",
        evidence_ids=("ev_1",),
        confidence=0.8,
    )
    model = FakeIntelligenceModel(scripts=())
    outcome = contradiction.analyze_contradictions(
        [cluster],
        model,
        evidence_by_id={"ev_1": _ev("ev_1")},
    )
    assert model.calls == []
    assert len(outcome.assessments) == 1
    assessment = outcome.assessments[0]
    assert assessment.supporting_evidence_ids == ("ev_1",)
    assert assessment.counter_evidence_ids == ()
    assert "single-member" in assessment.rationale
    assert assessment.degraded is False
