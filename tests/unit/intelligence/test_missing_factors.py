"""Missing factors must not be scored as real zeros."""
from __future__ import annotations

from sourceglint.intelligence.weak_signal import assess
from sourceglint.scoring import DEFAULT_FACTORS, ScoringConfig, compute_score


def base(**overrides):
    factors = {
        "decision_relevance": 0.8,
        "evidence_quality": 0.8,
        "recency": 0.8,
        "market_signal": 0.8,
        "novelty": 0.8,
    }
    factors.update(overrides)
    return factors


def test_unassessed_relevance_is_excluded_not_zeroed():
    measured = compute_score(base())
    unknown = compute_score(base(decision_relevance=0.0),
                            unassessed=("decision_relevance",))
    zeroed = compute_score(base(decision_relevance=0.0))

    assert unknown.components.keys() == measured.components.keys() - {"decision_relevance"}
    assert unknown.score > zeroed.score
    assert abs(unknown.score - measured.score) < 1e-9
    assert unknown.coverage == 0.65
    assert zeroed.coverage == 1.0
    assert unknown.completeness == "partial"
    assert unknown.to_dict()["unassessed"] == ["decision_relevance"]


def test_input_order_does_not_change_the_ranking():
    strong = base(evidence_quality=0.9)
    weak = base(evidence_quality=0.2)
    forward = [compute_score(strong), compute_score(weak)]
    backward = [compute_score(weak), compute_score(strong)][::-1]
    assert [row.score for row in forward] == [row.score for row in backward]
    assert forward[0].score > forward[1].score


def test_missing_and_present_scores_are_disclosed_as_not_comparable():
    full = compute_score(base())
    partial = compute_score(base(), unassessed=("recency", "novelty"))
    assert full.completeness == "complete"
    assert partial.completeness == "partial"
    assert partial.coverage < full.coverage
    assert set(partial.to_dict()["components"]) == set(DEFAULT_FACTORS) - {"recency", "novelty"}


def test_weights_are_renormalised_over_assessed_factors():
    cfg = ScoringConfig.default()
    partial = compute_score(
        {"evidence_quality": 1.0, "recency": 1.0, "market_signal": 1.0},
        cfg=cfg,
        unassessed=("decision_relevance", "novelty"),
    )
    # All assessed factors are 1.0, so the renormalised mean is 1.0, not a
    # floor-dragged 0.4-ish score caused by two phantom zeros.
    assert abs(partial.score - 1.0) < 1e-9


def test_weak_signal_does_not_use_an_unassessed_relevance_as_novelty():
    features = type("F", (), {
        "evidence_count": 1,
        "engagement_total": 0,
        "appeared_only_current": False,
    })()
    skipped = assess(features=features, decision_relevance=0.0,
                     relevance_assessed=False)
    assessed = assess(features=features, decision_relevance=0.9,
                      relevance_assessed=True)
    assert not skipped.is_weak_candidate
    assert assessed.is_weak_candidate
    assert any("relevance" in reason for reason in assessed.reasons)
    assert all("relevance" not in reason for reason in skipped.reasons)
