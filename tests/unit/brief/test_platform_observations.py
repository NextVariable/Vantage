from __future__ import annotations

from sourceglint.brief.dtos import SelectedBrief, SelectedFact
from sourceglint.brief.sections import facts, platform_observations
from sourceglint.pipeline.coverage import _syndicated_copy_count


def _fact(eids: tuple[str, ...]) -> SelectedFact:
    return SelectedFact(
        insight_id="f1", statement="A claim", confidence=0.8, support=0.8,
        evidence_ids=eids,
    )


LOOKUP = {
    "r1": {"source": "host_web_search", "url": "https://www.reddit.com/r/a/comments/1",
           "title": "Reddit thread", "published_at": "2026-10-01T00:00:00Z"},
    "g1": {"source": "github", "url": "https://github.com/o/r/issues/2",
           "title": "GitHub issue", "published_at": "2026-10-02T00:00:00Z"},
    "u1": {"source": "host_web_search", "url": "https://unknown.example/post",
           "title": "Unknown site", "published_at": "2026-10-03T00:00:00Z"},
}


def test_platform_observations_group_by_original_platform():
    sel = SelectedBrief(facts=(_fact(("r1", "g1")),))
    section = platform_observations(sel, LOOKUP)
    assert "## Platform Observations" in section
    assert "**GitHub**" in section and "**Reddit**" in section
    assert "Reddit via host_web_search" in section


def test_platform_observations_skips_a_single_platform():
    sel = SelectedBrief(facts=(_fact(("r1",)),))
    assert platform_observations(sel, LOOKUP) == ""


def test_platform_observations_ignores_unmapped_hosts():
    sel = SelectedBrief(facts=(_fact(("r1", "u1")),))
    assert platform_observations(sel, LOOKUP) == ""


def test_cross_platform_fact_meta_names_platforms():
    sel = SelectedBrief(facts=(_fact(("r1", "g1")),))
    rendered = facts(sel, LOOKUP)
    assert "cross-platform: GitHub, Reddit" in rendered


def test_syndicated_copies_are_counted_once_per_extra_platform():
    kept = [
        {"title": "Acme launches a brand new agent workspace",
         "snippet": "The same press release body appears on both platforms.",
         "url": "https://www.reddit.com/r/a/comments/1"},
        {"title": "Acme launches a brand new agent workspace",
         "snippet": "The same press release body appears on both platforms.",
         "url": "https://www.techmeme.com/251001/p1#a1"},
        {"title": "A different post about a different subject entirely",
         "snippet": "Unique text.",
         "url": "https://github.com/o/r/issues/2"},
    ]
    assert _syndicated_copy_count(kept) == 1
