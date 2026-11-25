from __future__ import annotations

from sourceglint.application.api import _apply_platform_scope
from sourceglint.interface.parser import parse_query
from sourceglint.interface.platforms import split_platform_intent
from sourceglint.provenance import known_platform, platform_label

SOURCES = [
    {"name": "reddit"},
    {"name": "github"},
    {"name": "x"},
    {"name": "host_web_search"},
]


def test_focus_mentions_become_soft_preferences():
    parsed = parse_query("重点研究 X、Reddit 和 GitHub 上的 agent 反馈")
    assert parsed.platform_only is False
    assert set(parsed.source_preferences) >= {"x", "reddit", "github"}
    assert "host_web_search" not in parsed.source_preferences


def test_only_phrase_is_a_hard_scope():
    parsed = parse_query("only Reddit and GitHub discuss this launch")
    assert parsed.platform_only is True
    assert set(parsed.source_preferences) == {"reddit", "github"}


def test_exclusion_removes_platform_but_keeps_others():
    parsed = parse_query("compare Reddit, X and GitHub, exclude X")
    assert "x" in parsed.excluded_sources
    assert "reddit" in parsed.source_preferences
    assert "github" in parsed.source_preferences


def test_official_exclusion_is_detected_bilingually():
    parsed = parse_query("排除官方宣传，只看一手体验")
    assert parsed.exclude_official is True
    assert parsed.to_plan().get("exclude_official") is True
    assert parse_query("exclude official marketing, first-hand users only").exclude_official is True
    assert parse_query("compare pricing pages").exclude_official is False


def test_platform_names_do_not_match_inside_words():
    parsed = parse_query("take note of the next section")
    assert "note" not in parsed.source_preferences


def test_split_platform_intent_reports_only_flag():
    requested, excluded, only = split_platform_intent("只研究 Reddit")
    assert requested == ["reddit"]
    assert excluded == []
    assert only is True


def test_hard_scope_filters_registry_and_exclusion_wins():
    scoped = _apply_platform_scope(SOURCES, ("reddit", "github"), ("github",))
    assert [s["name"] for s in scoped] == ["reddit"]


def test_hard_scope_errors_when_platform_is_unregistered():
    try:
        _apply_platform_scope(SOURCES, ("TikTok",), ())
    except ValueError as exc:
        assert "TikTok" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError for an unregistered platform")


def test_platform_attribution_keeps_route_and_original_platform():
    assert known_platform("https://www.reddit.com/r/a/comments/1") == "Reddit"
    assert known_platform("https://unknown.example/a") == ""
    assert platform_label("https://www.reddit.com/r/a/comments/1", "host_web_search") == (
        "Reddit via host_web_search"
    )
    assert platform_label("https://www.reddit.com/r/a/comments/1", "reddit") == "Reddit"
    assert platform_label("https://unknown.example/a", "official_web") == "official_web"
