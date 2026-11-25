from __future__ import annotations

import pytest

from sourceglint.connectors.fallback import FallbackAdapter, Route
from sourceglint.pipeline.adapters import AdapterTimeout, RawSourceResult


class _Adapter:
    def __init__(self, items=None, exc=None, name="route"):
        self.items = items or []
        self.exc = exc
        self.calls = 0
        self.name = name

    def retrieve(self, plan, request):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return list(self.items)


def _item(native: str, route: str = "raw") -> RawSourceResult:
    return RawSourceResult(
        source="reddit", source_type="post", source_native_id=native,
        url=f"https://www.reddit.com/comments/{native}", title="t", text="body",
        published_at="2026-11-20T00:00:00Z", raw_metadata={"route": route},
    )


def test_free_route_success_does_not_call_paid_route():
    free = _Adapter([_item("t3_abc")])
    paid = _Adapter([_item("t3_zzz")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ), paid_call_budget=5)
    items = adapter.retrieve({}, {})
    assert [item.source_native_id for item in items] == ["t3_abc"]
    assert items[0].raw_metadata["access_route"] == "public"
    assert paid.calls == 0


def test_empty_free_route_falls_back_to_paid_once():
    free = _Adapter([])
    paid = _Adapter([_item("t3_zzz")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ), paid_call_budget=5)
    items = adapter.retrieve({}, {})
    assert len(items) == 1
    assert paid.calls == 1
    assert items[0].raw_metadata["access_route"] == "paid"
    assert any("routes:" in note for note in adapter.limitations)


def test_paid_route_is_skipped_when_disabled():
    free = _Adapter([])
    paid = _Adapter([_item("t3_zzz")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ), paid_enabled=False)
    assert adapter.retrieve({}, {}) == []
    assert paid.calls == 0


def test_failed_free_route_preserves_nothing_but_records_state():
    free = _Adapter(exc=AdapterTimeout("reddit", "timed out"))
    paid = _Adapter([_item("t3_zzz")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ))
    items = adapter.retrieve({}, {})
    assert len(items) == 1
    assert any("route public failed" in note for note in adapter.limitations)


def test_same_native_id_from_two_routes_is_counted_once():
    free = _Adapter([_item("t3_same")])
    paid = _Adapter([_item("t3_same")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ), minimum_results=2)
    items = adapter.retrieve({}, {})
    assert len(items) == 1
    assert paid.calls == 1  # the fallback ran, but the duplicate was collapsed


def test_paid_call_budget_is_enforced():
    free = _Adapter([])
    paid = _Adapter([_item("t3_zzz")])
    adapter = FallbackAdapter("reddit", (
        Route("public", free), Route("paid", paid, paid=True),
    ), paid_call_budget=0)
    assert adapter.retrieve({}, {}) == []
    assert paid.calls == 0
    assert any("budget" in note for note in adapter.limitations)
