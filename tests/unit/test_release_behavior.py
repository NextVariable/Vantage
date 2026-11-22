import io
import json

from sourceglint.host_stdio import StdioHostSource
from sourceglint.pipeline.coverage import build_coverage_report
from sourceglint.brief.sections import _ref
from sourceglint.brief.selection import _coverage_lines


def test_bridge_reports_execution_without_treating_routed_targets_as_searched():
    answer = {"type": "source_response", "source": "host_web_search", "results": [],
              "searched_targets": [{"name": "reddit", "status": "no_results"}],
              "unanswered_parts": ["user complaints"], "limitations": ["No dated complaints found."]}
    output = io.StringIO()
    source = StdioHostSource("host_web_search", io.StringIO(json.dumps(answer)+"\n"), output)
    source.retrieve({"mode": "general"}, {"query": "AI agents", "query_language": "en"})
    assert source.coverage_reported
    assert source.searched_targets == [{"name": "reddit", "status": "no_results"}]
    assert source.unanswered_parts == ["user complaints"]
    assert "hacker_news" in {x["name"] for x in json.loads(output.getvalue())["targets"]}


def test_single_platform_and_unanswered_aspects_are_visible_in_coverage():
    records = [{"url": "https://www.producthunt.com/products/a", "window": "current"},
               {"url": "https://www.producthunt.com/products/b", "window": "current"}]
    report = build_coverage_report(
        requested_sources=["host_web_search"], attempted_sources=["host_web_search"],
        source_statuses={}, expanded_queries=[], raw_results=records,
        normalized_evidence=records, deduplicated_dropped=0, dropped_by_time_filter=0,
        kept_evidence=records, host_observations=[{"coverage_reported": True,
            "searched_targets": [{"name": "reddit", "status": "no_results"}],
            "unanswered_parts": ["user complaints"]}],
    )
    assert report.original_platforms == ("Product Hunt",)
    assert report.to_dict()["research_quality"] == "LIMITED"
    display = "\n".join(_coverage_lines(report))
    assert "user complaints" in display and "no independent cross-platform" in display
    assert "reddit" in display


def test_public_citation_preserves_original_platform_and_publication_date():
    citation = _ref({"ev1": {"source": "host_web_search", "url": "https://www.reddit.com/r/a/comments/1", "published_at": "2026-10-01T00:00:00Z"}}, "ev1")
    assert "[Reddit]" in citation
    assert "2026-10-01" in citation
    assert "host_web_search" not in citation


def test_synthesis_reserve_scales_with_complexity_and_stays_bounded():
    from sourceglint.application.api import _synthesis_reserve

    low, low_complexity = _synthesis_reserve(345, entities=0, languages=1, mode="market")
    high, high_complexity = _synthesis_reserve(345, entities=4, languages=3, mode="competitor")
    assert low_complexity < high_complexity
    assert 60 <= low < high <= 130
    tiny, _ = _synthesis_reserve(60, entities=4, languages=3, mode="competitor")
    assert tiny == 60


def test_answer_states_never_count_disclosure_as_an_answer():
    from sourceglint.pipeline.adaptive import answer_state

    assert answer_state("covered", missing_required=(), origin_shortfall=False,
                        gap="", unavailable=False) == "fully_answered"
    assert answer_state("partial", missing_required=("T1_official",), origin_shortfall=False,
                        gap="", unavailable=False) == "partially_answered"
    assert answer_state("unanswered", missing_required=("T1_official",), origin_shortfall=False,
                        gap="Named gap.", unavailable=False) == "explicitly_disclosed"
    assert answer_state("unanswered", missing_required=(), origin_shortfall=False,
                        gap="", unavailable=False) == "unanswered"


def test_required_and_supporting_evidence_are_split_by_focus():
    from sourceglint.pipeline.adaptive import split_evidence_requirements

    required, supporting = split_evidence_requirements({
        "focus": "competition",
        "evidence_types": ["T1_official", "T2_community", "T3_marketplace", "T4_secondary"],
    })
    assert required == ["T1_official", "T3_marketplace"]
    assert supporting == ["T2_community", "T4_secondary"]

    # An explicit plan requirement is never widened or relaxed.
    required, supporting = split_evidence_requirements({
        "focus": "competition", "required_evidence": ["T4_secondary"],
        "evidence_types": ["T1_official", "T4_secondary"],
    })
    assert required == ["T4_secondary"]
    assert supporting == ["T1_official"]
