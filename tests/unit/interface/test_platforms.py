from __future__ import annotations

from sourceglint.application.api import _resolve_platform_scope
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
    scoped, scope = _resolve_platform_scope(SOURCES, ("Reddit", "GitHub"), ("github",))
    assert [s["name"] for s in scoped] == ["reddit"]
    assert scope["exclude_platforms"] == ["github"]


def test_hard_scope_on_host_only_platform_enables_host_and_domains():
    scoped, scope = _resolve_platform_scope(SOURCES, ("LinkedIn",), ())
    assert [s["name"] for s in scoped] == ["host_web_search"]
    assert scope["include_platforms"] == ["LinkedIn"]
    assert "linkedin.com" in scope["include_domains"]


def test_host_only_scope_errors_when_host_is_disabled():
    try:
        _resolve_platform_scope([{"name": "reddit"}], ("LinkedIn",), ())
    except ValueError as exc:
        assert "Host Web Search" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError when host search is unavailable")


def test_excluding_a_platform_keeps_host_scope_domains():
    scoped, scope = _resolve_platform_scope(SOURCES, (), ("X",))
    assert "x" not in [s["name"] for s in scoped]
    assert scope["exclude_platforms"] == ["x"]
    assert "x.com" in scope["exclude_domains"]


def test_hard_scope_errors_when_platform_is_unregistered():
    try:
        _resolve_platform_scope(SOURCES, ("UnknownSite",), ())
    except ValueError as exc:
        assert "UnknownSite" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError for an unregistered platform")


def test_hard_scope_errors_when_requested_direct_platform_is_disabled():
    sources = [{"name": "reddit"}, {"name": "instagram", "enabled": False}]
    try:
        _resolve_platform_scope(sources, ("Instagram",), ())
    except ValueError as exc:
        message = str(exc).casefold()
        assert "disabled" in message and "instagram" in message
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError for a disabled requested platform")


def test_platform_attribution_keeps_route_and_original_platform():
    assert known_platform("https://www.reddit.com/r/a/comments/1") == "Reddit"
    assert known_platform("https://unknown.example/a") == ""
    assert platform_label("https://www.reddit.com/r/a/comments/1", "host_web_search") == (
        "Reddit via host_web_search"
    )
    assert platform_label("https://www.reddit.com/r/a/comments/1", "reddit") == "Reddit"
    assert platform_label("https://unknown.example/a", "host_web_search") == (
        "Web page (unknown.example)"
    )
    assert platform_label("https://unknown.example/a", "official_web") == (
        "Web page (unknown.example)"
    )
