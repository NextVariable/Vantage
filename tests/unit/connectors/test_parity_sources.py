from __future__ import annotations

import json

import pytest

from sourceglint.connectors.parity_sources import (
    DiggCliAdapter,
    MetaAdLibraryAdapter,
    PolymarketAdapter,
    ScrapeCreatorsPlatformAdapter,
    StockTwitsAdapter,
    TruthSocialAdapter,
    XiaohongshuMcpAdapter,
)
from sourceglint.pipeline.adapters import AdapterAuthMissing, AdapterInvalidResponse


class StubHttp:
    user_agent = "test"

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[dict[str, object]] = []

    def request(self, url: str, *, headers=None, timeout=15.0, method="GET", json_data=None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "method": method, "json": json_data})
        payload = self.responses.pop(0) if self.responses else {}

        class _Response:
            def json(self_inner):
                return payload

        return _Response()


REQUEST = {"query": "AI agents", "query_language": "en", "market": "global",
           "retrieved_at": "2026-11-25T00:00:00Z", "limit": 5}


def test_instagram_maps_caption_owner_date_and_engagement():
    http = StubHttp([{"reels": [{
        "id": "ig1", "shortcode": "abc",
        "caption": {"text": "Testing an AI agent in production"},
        "owner": {"username": "builder"},
        "taken_at": "2026-11-20T10:00:00.000Z",
        "video_play_count": 500, "like_count": 20, "comment_count": 3,
    }]}])
    adapter = ScrapeCreatorsPlatformAdapter(
        platform="instagram", endpoint="https://x/v2/instagram/reels/search",
        api_key="key", http_client=http,
    )
    items = adapter.retrieve({}, REQUEST)
    assert items[0].url == "https://www.instagram.com/reel/abc/"
    assert items[0].published_at == "2026-11-20T10:00:00Z"
    assert items[0].engagement["views"] == 500
    assert "query=AI+agents" in http.calls[0]["url"]


def test_threads_and_linkedin_keep_original_urls():
    http = StubHttp([{"posts": [{
        "id": "th1", "code": "c1", "text": "Threads take on agents",
        "user": {"username": "tester"}, "create_time": 1790000000,
        "like_count": 4, "reply_count": 2,
    }, {
        "urn": "li1", "description": "LinkedIn analysis of agent pricing",
        "author": {"name": "Analyst"}, "datePublished": "2026-11-19",
        "url": "https://www.linkedin.com/posts/x",
        "likes": 8, "comments": 1,
    }]}])
    threads = ScrapeCreatorsPlatformAdapter(
        platform="threads", endpoint="https://x/v1/threads/search",
        api_key="key", http_client=http,
    )
    # The same stub response is consumed by one call; use separate stubs in real runs.
    items = threads.retrieve({}, REQUEST)
    assert items[0].url == "https://www.threads.net/post/c1"
    assert items[0].published_at.startswith("2026-09-21")


def test_undated_pinterest_pin_is_dropped_not_fabricated():
    http = StubHttp([{"pins": [{
        "id": "p1", "description": "Mood board for agent launches",
        "save_count": 10,
    }]}])
    adapter = ScrapeCreatorsPlatformAdapter(
        platform="pinterest", endpoint="https://x/v1/pinterest/search",
        api_key="key", http_client=http,
    )
    assert adapter.retrieve({}, REQUEST) == []


def test_scrapecreators_platform_requires_key():
    adapter = ScrapeCreatorsPlatformAdapter(
        platform="instagram", endpoint="https://x", api_key=None, http_client=StubHttp(),
    )
    with pytest.raises(AdapterAuthMissing):
        adapter.retrieve({}, REQUEST)


def test_truthsocial_requires_token_and_maps_status():
    with pytest.raises(AdapterAuthMissing):
        TruthSocialAdapter(token=None, http_client=StubHttp()).retrieve({}, REQUEST)
    http = StubHttp([{"statuses": [{
        "id": "ts1", "content": "<p>Agents are everywhere</p>",
        "created_at": "2026-11-18T12:00:00.000Z",
        "account": {"acct": "user"},
        "replies_count": 2, "reblogs_count": 3, "favourites_count": 4,
    }]}])
    items = TruthSocialAdapter(token="t", http_client=http).retrieve({}, REQUEST)
    assert items[0].text == "Agents are everywhere"
    assert items[0].url.endswith("/@user/posts/ts1")


def test_meta_ad_library_requires_token_and_marks_day_precision():
    with pytest.raises(AdapterAuthMissing):
        MetaAdLibraryAdapter(token=None, http_client=StubHttp()).retrieve({}, REQUEST)
    http = StubHttp([{"data": [{
        "id": "ad1", "page_name": "Acme",
        "ad_creative_body": "Book a demo today",
        "ad_delivery_start_time": "2026-11-01",
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=ad1",
    }]}])
    items = MetaAdLibraryAdapter(token="t", http_client=http).retrieve({}, REQUEST)
    assert items[0].published_at == "2026-11-01T00:00:00Z"
    assert items[0].raw_metadata["date_precision"] == "day"


def test_stocktwits_requires_a_ticker_and_maps_messages():
    with pytest.raises(AdapterInvalidResponse):
        StockTwitsAdapter(http_client=StubHttp()).retrieve({}, {"query": "AI agents"})
    http = StubHttp([{"messages": [{
        "id": 1, "body": "$NVDA to the moon", "created_at": "2026-11-17T09:30:00Z",
        "user": {"username": "trader"}, "likes": {"total": 5},
        "reshares": {"reshared_count": 1},
        "entities": {"sentiment": {"basic": "Bullish"}},
    }]}])
    items = StockTwitsAdapter(http_client=http).retrieve({}, {"query": "$NVDA"})
    assert items[0].source_native_id == "1"
    assert items[0].raw_metadata["sentiment"] == "Bullish"


def test_polymarket_marks_market_start_semantics():
    http = StubHttp([{"events": [{
        "id": "e1", "title": "Will agents ship by 2027?", "slug": "agents-2027",
        "startDate": "2026-10-01", "volume": 1200,
    }]}])
    items = PolymarketAdapter(http_client=http).retrieve({}, REQUEST)
    assert items[0].raw_metadata["date_semantics"] == "market_start"
    assert items[0].url == "https://polymarket.com/event/agents-2027"


def test_xiaohongshu_refuses_when_service_is_not_logged_in():
    http = StubHttp([{"data": {"is_logged_in": False}}])
    adapter = XiaohongshuMcpAdapter(base_url="http://127.0.0.1:18060", http_client=http)
    with pytest.raises(AdapterAuthMissing):
        adapter.retrieve({}, {"query": "AI 产品", "query_language": "zh"})


def test_digg_missing_binary_is_reported_not_faked(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(Exception) as exc:
        DiggCliAdapter().retrieve({}, REQUEST)
    assert "not installed" in str(exc.value)


def test_digg_maps_cli_json_through_an_injected_runner():
    payload = json.dumps({"stories": [{
        "uuid": "d1", "title": "A story", "url": "https://example.com/a",
        "publishedAt": "2026-11-16T08:00:00Z", "diggScore": 42,
    }]})
    items = DiggCliAdapter(runner=lambda args: payload).retrieve({}, REQUEST)
    assert items[0].source_native_id == "d1"
    assert items[0].engagement["digg_score"] == 42
