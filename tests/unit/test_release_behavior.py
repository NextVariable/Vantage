import io
import json

import pytest

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
    assert 0 < tiny <= 60 * 0.45


@pytest.mark.parametrize("total", [0, 1, 5, 20, 45, 60, 90, 120, 180, 345, 3600])
@pytest.mark.parametrize(("entities", "languages", "mode"),
                         [(0, 1, "market"), (4, 3, "competitor"), (2, 2, "opportunity")])
def test_synthesis_reserve_never_exceeds_the_share_cap_or_goes_negative(total, entities, languages, mode):
    from sourceglint.application.api import (
        _SYNTHESIS_RESERVE_MAX,
        _SYNTHESIS_RESERVE_SHARE_CAP,
        _synthesis_reserve,
    )

    reserve, _ = _synthesis_reserve(total, entities=entities, languages=languages, mode=mode)
    assert reserve >= 0
    assert reserve <= total * _SYNTHESIS_RESERVE_SHARE_CAP + 1e-9
    assert reserve <= _SYNTHESIS_RESERVE_MAX
    assert total - reserve >= 0


def test_evidence_role_never_infers_vendor_identity_from_a_username():
    from sourceglint.pipeline.adaptive import classify_evidence_role

    maker_post = {"source_tier": 2, "source_type": "post", "author": "acme_team",
                  "source": "reddit", "content": "Our team shipped Acme 2.0."}
    assert classify_evidence_role(maker_post) == ("third_party_commentary", "unverified_author")
    assert classify_evidence_role(maker_post, feedback=True) == ("firsthand_experience", "self_reported")
    # A platform is not a publisher: a GitHub release page is a platform-hosted
    # account, not a verified vendor statement.
    platform_release = {"source_tier": 1, "source_type": "release", "source": "github"}
    assert classify_evidence_role(platform_release) == ("vendor_claim_unverified", "platform_account")
    # Only an official-site designation or explicit item metadata verifies identity.
    official = {"source_tier": 1, "source_type": "release", "source": "official_web"}
    assert classify_evidence_role(official) == ("vendor_claim_verified", "declared_official")
    flagged = {"source_tier": 1, "source_type": "release", "source": "github",
               "raw_metadata": {"official": True}}
    assert classify_evidence_role(flagged) == ("vendor_claim_verified", "declared_official")
    media = {"source_tier": 4, "source_type": "page", "source": "host_web_search"}
    assert classify_evidence_role(media) == ("media_report", "publisher")


def test_provenance_separates_platform_publisher_and_firsthand_level():
    from sourceglint.pipeline.adaptive import classify_provenance

    github_issue = {"source_tier": 1, "source_type": "issue", "source": "github"}
    provenance = classify_provenance(github_issue, role="vendor_claim_unverified",
                                     identity="platform_account")
    assert provenance["platform"] == "github"
    assert provenance["publisher_identity"] == "platform_account"
    assert provenance["content_type"] == "issue"
    assert provenance["firsthand"] == "direct"
    assert provenance["credibility_prior"] == "high"
    assert provenance["role"] == "vendor_claim_unverified"

    repost = {"source_tier": 4, "source_type": "page", "source": "news"}
    media = classify_provenance(repost, role="media_report", identity="publisher")
    assert media["publisher_identity"] == "independent_publisher"
    assert media["firsthand"] == "secondhand"

    testimony = {"source_tier": 3, "source_type": "post", "source": "forum"}
    self_reported = classify_provenance(testimony, role="firsthand_experience",
                                        identity="self_reported")
    assert self_reported["publisher_identity"] == "community_user"
    assert self_reported["firsthand"] == "self_reported"
    assert self_reported["credibility_prior"] == "medium"


def test_evidence_requirements_are_kind_based_and_do_not_mandate_a_site():
    from sourceglint.pipeline.adaptive import evidence_requirements

    demand = evidence_requirements({"focus": "demand", "evidence_types": ["T2_community", "T4_secondary"],
                                    "minimum_origins": 2})
    assert demand["roles_any_of"] == ["firsthand_experience", "independent_test"]
    assert demand["min_direct_observations"] == 1
    assert demand["min_independent_origins"] == 2
    assert demand["blocking_tiers"] == []  # derived tiers are advisory, not a site requirement
    explicit = evidence_requirements({"focus": "demand", "required_evidence": ["T2_community"],
                                      "evidence_types": ["T2_community"]})
    assert explicit["blocking_tiers"] == ["T2_community"]


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
