"""Absence observations survive coverage/brief without becoming false gaps."""
from __future__ import annotations

from sourceglint.brief import sections
from sourceglint.brief.dtos import BriefContext, SelectedBrief
from sourceglint.pipeline.coverage import build_coverage_report


def _coverage(absence):
    return build_coverage_report(
        requested_sources=("github",),
        attempted_sources=("github",),
        source_statuses={},
        expanded_queries=({"query_language": "en", "market": "global"},),
        raw_results=(),
        normalized_evidence=(),
        deduplicated_dropped=0,
        dropped_by_time_filter=0,
        kept_evidence=(),
        absence_observations=absence,
    )


def test_verified_absence_is_recorded_but_not_a_gap():
    report = _coverage(
        [
            {"source": "github", "kind": "releases", "repository": "a/b", "status": "verified_absent", "count": 0},
            {"source": "github", "kind": "releases", "repository": "c/d", "status": "verified_absent", "count": 0},
        ]
    )
    assert len(report.absence_observations) == 2
    assert not any("verified absent" in gap for gap in report.gaps)
    assert len(report.to_dict()["absence_checks"]) == 2


def test_unavailable_release_check_is_a_gap():
    report = _coverage(
        [{"source": "github", "kind": "releases", "repository": "a/b", "status": "rate_limited"}]
    )
    assert any("rate_limited" in gap for gap in report.gaps)


def test_qualified_gap_renders_with_status_and_no_plain_negative():
    brief = SelectedBrief(
        context=BriefContext(query="q"),
        research_assessments=(
            {
                "question": "Which agents released a version?",
                "status": "partial",
                "focus": "industry",
                "gap": (
                    "Unverified absence: no coding-agent candidate has a dated release artifact "
                    "(absence not established; scoped to retrieved evidence)"
                ),
                "absence_checks": [{"object": "release", "status": "not_retrieved"}],
            },
        ),
    )
    md = sections.research_questions(brief, {})
    assert "Unverified absence:" in md
    assert "absence: release → not_retrieved" in md
