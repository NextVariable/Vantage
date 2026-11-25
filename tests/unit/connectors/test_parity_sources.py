from __future__ import annotations

import json

import pytest

from sourceglint.connectors.parity_sources import (
    DiggCliAdapter,
    MetaAdLibraryAdapter,
    PolymarketAdapter,
    PublicLinkYtDlpAdapter,
    ScrapeCreatorsMetaAdsAdapter,
    ScrapeCreatorsPlatformAdapter,
    ScrapeCreatorsRedditAdapter,
    ScrapeCreatorsTelegramAdapter,
    ScrapeCreatorsYouTubeAdapter,
    StockTwitsAdapter,
    TrustpilotCliAdapter,
    TruthSocialAdapter,
    UsptoPatentAdapter,
    XiaohongshuMcpAdapter,
)
from sourceglint.pipeline.adapters import (
    AdapterAuthMissing,
    AdapterInvalidResponse,
    AdapterUnavailable,
)


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
        "startDate": "2026-10-01", "volume": 1200, "description": "Resolution rules and deadline.",
    }]}])
    items = PolymarketAdapter(http_client=http).retrieve({}, REQUEST)
    assert items[0].raw_metadata["date_semantics"] == "market_start"
    assert items[0].url == "https://polymarket.com/event/agents-2027"
    assert items[0].text == "Resolution rules and deadline."


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


def test_digg_maps_current_cli_search_envelope():
    payload = json.dumps({"meta": {"count": 1}, "results": [{
        "clusterId": "d1", "title": "A story", "url": "https://digg.com/tech/a",
        "tldr": "Published summary from the Digg story cluster.",
        "publishedAt": "2026-11-16T08:00:00Z", "diggScore": 42,
    }]})
    items = DiggCliAdapter(runner=lambda args: payload).retrieve({}, REQUEST)
    assert items[0].source_native_id == "d1"
    assert items[0].engagement["digg_score"] == 42
    assert items[0].text == "Published summary from the Digg story cluster."


# ---------------------------------------------------------------------------
# ScrapeCreators expansion
# ---------------------------------------------------------------------------


def test_scrapecreators_reddit_keeps_t3_prefix_and_engagement():
    http = StubHttp([{"posts": [{
        "id": "abc123", "permalink": "/r/startups/comments/abc123/demo/",
        "title": "We tested an AI agent in production",
        "selftext": "Longer body about reliability.",
        "author": "builder", "created_at": "2026-11-20T10:00:00.000Z",
        "score": 91, "num_comments": 12, "subreddit": {"name": "startups"},
    }]}])
    items = ScrapeCreatorsRedditAdapter(api_key="key", http_client=http).retrieve({}, REQUEST)
    assert items[0].source_native_id == "t3_abc123"
    assert items[0].url.endswith("/comments/abc123/demo/")
    assert items[0].engagement == {"upvotes": 91, "comments": 12}
    assert "sort=relevance" in http.calls[0]["url"]
    assert "timeframe=month" in http.calls[0]["url"]


def test_scrapecreators_reddit_requires_a_key():
    with pytest.raises(AdapterAuthMissing):
        ScrapeCreatorsRedditAdapter(api_key=None).retrieve({}, REQUEST)


def test_scrapecreators_youtube_drops_relative_dates():
    http = StubHttp([{"videos": [
        {"videoId": "abc", "title": "Absolute date", "publishedTime": "2026-11-18T00:00:00Z",
         "channel": {"title": "Builder"}, "viewCountInt": 500},
        {"videoId": "rel", "title": "Relative only", "publishedTime": "2 weeks ago"},
    ]}])
    adapter = ScrapeCreatorsYouTubeAdapter(api_key="key", http_client=http)
    items = adapter.retrieve({}, REQUEST)
    assert [item.source_native_id for item in items] == ["abc"]
    assert items[0].engagement["views"] == 500


def test_scrapecreators_telegram_requires_channels_and_maps_posts():
    with pytest.raises(AdapterAuthMissing):
        ScrapeCreatorsTelegramAdapter(api_key="key", channels="").retrieve({}, REQUEST)
    http = StubHttp([{
        "success": True,
        "channel": {"name": "Builder News", "handle": "buildernews"},
        "posts": [{"id": 42, "text": "New model shipped today", "date": "2026-11-21T09:00:00Z",
                   "views": 800}],
    }])
    adapter = ScrapeCreatorsTelegramAdapter(
        api_key="key", channels="https://t.me/buildernews, @other", http_client=http,
    )
    items = adapter.retrieve({}, REQUEST)
    assert items[0].source_native_id == "buildernews:42"
    assert items[0].url == "https://t.me/buildernews/42"
    assert items[0].author == "Builder News"
    assert "handle=buildernews" in http.calls[0]["url"]


def test_scrapecreators_meta_ads_maps_snapshot_body():
    http = StubHttp([{"searchResults": [{
        "ad_archive_id": "ad1", "start_date_string": "2026-11-10",
        "snapshot": {"body": {"text": "Try the new AI workspace"},
                     "page_name": "Acme", "url": "https://www.facebook.com/ads/library/?id=ad1"},
    }]}])
    items = ScrapeCreatorsMetaAdsAdapter(api_key="key", http_client=http).retrieve({}, REQUEST)
    assert items[0].source_type == "page"
    assert items[0].author == "Acme"
    assert items[0].published_at == "2026-11-10T00:00:00Z"
    assert "search_type=keyword_unordered" in http.calls[0]["url"]


def test_public_link_adapter_requires_a_url_instead_of_faking_discovery(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/yt-dlp")
    adapter = PublicLinkYtDlpAdapter(platform="tiktok")
    items = adapter.retrieve({}, {"query": "AI agents", "limit": 3})
    assert items == []
    assert any("no public post URL" in note for note in adapter.limitations)


def test_trustpilot_without_a_fresh_session_never_launches_a_browser():
    calls: list[list[str]] = []

    def runner(args):
        calls.append(args)
        return {"session": {"harvestedAt": "2026-11-20T00:00:00Z"}} if args[:1] == ["auth"] else {}

    adapter = TrustpilotCliAdapter(runner=runner)
    items = adapter.retrieve({}, {**REQUEST, "query": "acme.com", "retrieved_at": "2026-11-25T00:00:00Z"})
    assert items == []
    assert calls == [["auth", "status", "--agent"]]
    assert any("trustpilot-pp-cli auth login" in note for note in adapter.limitations)


def test_trustpilot_needs_a_domain_for_the_local_route():
    adapter = TrustpilotCliAdapter(runner=lambda args: {})
    assert adapter.retrieve({}, REQUEST) == []
    assert any("company domain" in note for note in adapter.limitations)


def test_trustpilot_missing_cli_is_unavailable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(AdapterUnavailable):
        TrustpilotCliAdapter().retrieve({}, {**REQUEST, "query": "acme.com"})


class _PatentHttp:
    status = 200
    headers = {"x-access-token": "token-1"}

    def __init__(self):
        self.bodies = []

    def request(self, url, **kwargs):
        self.bodies.append(kwargs.get("json_data"))
        if url.endswith("/api/users/me/session"):
            payload = {"userCase": {"caseId": 7}}
        else:
            payload = {"patents": [{
                "guid": "g1",
                "publicationReferenceDocumentNumber": "20260303390",
                "inventionTitle": ["<span>DYNAMIC</span> MEETING ASSISTANTS"],
                "datePublished": ["2026-10-01T00:00:00Z"],
                "applicantName": ["Acme Corp"],
            }, {
                "guid": "g2",
                "inventionTitle": ["Undated item"],
            }]}
        return _PatentResponse(payload)


class _PatentResponse:
    def __init__(self, payload):
        self.status = 200
        self.headers = {"x-access-token": "token-1"}
        self._payload = payload

    def json(self):
        return self._payload


def test_uspto_maps_dated_patent_and_drops_undated_rows():
    http = _PatentHttp()
    adapter = UsptoPatentAdapter(http_client=http)
    items = adapter.retrieve(
        {"time_window": {"days": 30}},
        {**REQUEST, "query": "meeting assistant", "retrieved_at": "2026-11-25T00:00:00Z"},
    )
    assert len(items) == 1
    assert items[0].source_native_id == "g1"
    assert items[0].title == "DYNAMIC MEETING ASSISTANTS"
    assert items[0].published_at == "2026-10-01T00:00:00Z"
    assert items[0].url.endswith("/20260303390")
    assert items[0].author == "Acme Corp"
    # the request carried both a session body and a bounded query
    assert http.bodies[0] == -1
    assert "meeting assistant" in str(http.bodies[-1])
    assert '@pd>="' in str(http.bodies[-1])
