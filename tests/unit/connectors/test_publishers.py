from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.publishers import NoteSearchAdapter, ZennSearchAdapter

REQUEST = {
    "query": "AI",
    "query_language": "ja",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 5,
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, payload: object):
        self.payload = payload

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, **kwargs):
        return HttpResponse(status=200, body=json.dumps(self.payload).encode(), url=url)


def test_zenn_maps_original_article_url_and_engagement():
    out = ZennSearchAdapter(http_client=StubHttp({"articles": [{
        "id": 691456, "path": "/karamage/articles/73027ee36796dc",
        "title": "AI にテストを書かせるな",
        "published_at": "2026-11-21T11:12:39.343+09:00",
        "body_updated_at": "2026-11-22T11:56:42.659+09:00",
        "liked_count": 78, "comments_count": 2, "bookmarked_count": 37,
        "article_type": "tech",
        "user": {"username": "karamage", "name": "karamage"},
    }]})).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://zenn.dev/karamage/articles/73027ee36796dc"
    assert out[0].published_at == "2026-11-21T02:12:39Z"
    assert out[0].raw_metadata["updated"] == "2026-11-22T02:56:42Z"
    assert out[0].engagement == {"points": 78, "comments": 2, "bookmarks": 37}


def test_note_builds_canonical_note_url():
    out = NoteSearchAdapter(http_client=StubHttp({"data": {"notes": {"contents": [{
        "id": 192129204, "type": "TextNote", "name": "AI 銘柄",
        "key": "n273c340a02ef", "publish_at": "2026-11-20T06:59:02.000+09:00",
        "description": "説明", "like_count": 543, "comment_count": 0,
        "user": {"urlname": "hirosetakao", "nickname": "広瀬隆雄"},
    }]}}})).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://note.com/hirosetakao/n/n273c340a02ef"
    assert out[0].published_at == "2026-11-19T21:59:02Z"
    assert out[0].author == "広瀬隆雄"
    assert out[0].text == "説明"


def test_note_skips_entries_without_a_canonical_key():
    out = NoteSearchAdapter(http_client=StubHttp({"data": {"notes": {"contents": [{
        "id": 1, "name": "No key", "publish_at": "2026-11-20T00:00:00Z",
        "user": {"urlname": "someone"},
    }]}}})).retrieve(PLAN, REQUEST)
    assert out == []
