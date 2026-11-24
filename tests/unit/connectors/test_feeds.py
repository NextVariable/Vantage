from __future__ import annotations

from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.feeds import FeedAdapter, parse_feed

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>News</title>
<item>
  <title>AI agents reshape developer tooling</title>
  <link>https://example.jp/news/ai-agents</link>
  <description><![CDATA[<p>Agents for <b>developers</b>.</p>]]></description>
  <pubDate>Mon, 23 Nov 2026 09:00:00 +0900</pubDate>
  <guid>https://example.jp/news/ai-agents</guid>
  <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Editor</dc:creator>
</item>
<item>
  <title>Cooking rice at home</title>
  <link>https://example.jp/news/rice</link>
  <description>Not related.</description>
  <pubDate>Sun, 22 Nov 2026 09:00:00 +0900</pubDate>
</item>
<item>
  <title>Undated AI note</title>
  <link>https://example.jp/news/undated</link>
</item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>AI funding round</title>
    <link rel="alternate" href="https://example.jp/blog/funding"/>
    <id>tag:example.jp,2026:1</id>
    <published>2026-11-20T01:00:00Z</published>
    <updated>2026-11-21T01:00:00Z</updated>
    <summary>AI startup raises money.</summary>
    <author><name>Reporter</name></author>
  </entry>
</feed>"""

REQUEST = {
    "query": "AI developers",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 5,
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, body: bytes):
        self.body = body
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, **kwargs):
        self.calls.append(url)
        return HttpResponse(status=200, body=self.body, url=url)


def test_parse_rss_maps_fields_and_separates_updates():
    items = parse_feed(RSS, "test_feed")
    assert items[0]["title"] == "AI agents reshape developer tooling"
    assert items[0]["summary"] == "Agents for developers."
    assert items[0]["published"] == "2026-11-23T00:00:00Z"
    assert items[0]["author"] == "Editor"
    assert items[0]["link"] == "https://example.jp/news/ai-agents"


def test_parse_atom_entry():
    items = parse_feed(ATOM, "test_feed")
    assert items[0]["link"] == "https://example.jp/blog/funding"
    assert items[0]["published"] == "2026-11-20T01:00:00Z"
    assert items[0]["updated"] == "2026-11-21T01:00:00Z"
    assert items[0]["author"] == "Reporter"


def test_feed_adapter_filters_locally_and_skips_undated():
    out = FeedAdapter(
        feed_url="https://example.jp/feed", source_name="jp_news",
        language="ja", http_client=StubHttp(RSS),
    ).retrieve(PLAN, REQUEST)
    assert [item.url for item in out] == ["https://example.jp/news/ai-agents"]
    assert out[0].published_at == "2026-11-23T00:00:00Z"
    assert out[0].raw_metadata["filter"] == "local_topic_terms"
    assert out[0].raw_metadata["date_semantics"] == "feed_item_published"
    assert out[0].engagement == {}


def test_feed_adapter_passes_query_when_documented():
    http = StubHttp(RSS)
    FeedAdapter(
        feed_url="https://example.jp/search", source_name="jp_search",
        query_param="q", local_filter=False, http_client=http,
    ).retrieve(PLAN, REQUEST)
    assert "q=AI+developers" in http.calls[0]


def test_feed_adapter_returns_empty_when_nothing_matches():
    out = FeedAdapter(
        feed_url="https://example.jp/feed", source_name="jp_news",
        http_client=StubHttp(RSS),
    ).retrieve(PLAN, dict(REQUEST, query="quantum"))
    assert out == []
