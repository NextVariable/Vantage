"""Hard platform scope must constrain host evidence, not just the registry."""
from __future__ import annotations

from sourceglint.pipeline.adapters import RawSourceResult
from sourceglint.pipeline.orchestrator import _platform_scope_filter


def _row(source: str, url: str) -> RawSourceResult:
    return RawSourceResult(
        source=source,
        source_type="post",
        source_native_id=url,
        url=url,
        title="t",
        text="body",
    )


def test_excluded_platform_drops_host_evidence_even_when_host_returns_it():
    rows = [
        _row("host_web_search", "https://www.linkedin.com/posts/acme_123"),
        _row("host_web_search", "https://example.com/post"),
    ]
    kept, dropped = _platform_scope_filter(
        rows, {"exclude_platforms": ["linkedin"], "exclude_domains": ["linkedin.com"]}
    )
    assert dropped == 1
    assert [row.url for row in kept] == ["https://example.com/post"]


def test_include_platform_keeps_only_matching_host_targets():
    rows = [
        _row("host_web_search", "https://www.threads.net/@acme/post/1"),
        _row("host_web_search", "https://www.pinterest.com/pin/1"),
        _row("host_web_search", "https://example.com/blog"),
    ]
    kept, dropped = _platform_scope_filter(
        rows,
        {"include_platforms": ["threads"], "include_domains": ["threads.net"]},
    )
    assert dropped == 2
    assert [row.url for row in kept] == ["https://www.threads.net/@acme/post/1"]


def test_include_domains_keeps_unknown_hosts_only_when_they_match():
    rows = [
        _row("host_web_search", "https://m.facebook.com/ads/library/?id=1"),
        _row("host_web_search", "https://unrelated.example/item"),
    ]
    kept, dropped = _platform_scope_filter(
        rows, {"include_platforms": ["meta ad library"], "include_domains": ["facebook.com"]}
    )
    assert dropped == 1
    assert kept and kept[0].url.startswith("https://m.facebook.com/")


def test_direct_source_rows_are_not_removed_by_include_scope():
    rows = [_row("reddit", "https://www.reddit.com/r/x/1")]
    kept, dropped = _platform_scope_filter(
        rows, {"include_platforms": ["threads"], "include_domains": ["threads.net"]}
    )
    assert dropped == 0
    assert len(kept) == 1


def test_empty_scope_is_a_noop():
    rows = [_row("host_web_search", "https://example.com/x")]
    kept, dropped = _platform_scope_filter(rows, {})
    assert kept == rows and dropped == 0
