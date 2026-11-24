from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.devplatforms import LemmyAdapter

PLAN = {"time_window": {"days": 30}}
REQUEST = {
    "query": "ai",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 3,
}


class StubHttp:
    user_agent = "test"

    def __init__(self, payload: object):
        self.payload = payload
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, **kwargs):
        self.calls.append(url)
        return HttpResponse(status=200, body=json.dumps(self.payload).encode(), url=url)


def test_lemmy_maps_federated_permalink_and_counts():
    out = LemmyAdapter(http_client=StubHttp({"posts": [{
        "post": {
            "id": 99, "name": "Local AI roundup",
            "body": "<p>Links.</p>",
            "published": "2026-11-24T13:48:53.000000Z",
            "ap_id": "https://lemmy.world/post/99",
            "url": "https://example.com/roundup",
        },
        "creator": {"name": "Patnou"},
        "community": {"name": "technology", "actor_id": "https://lemmy.world/c/technology"},
        "counts": {"score": 12, "comments": 4},
    }]})).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://lemmy.world/post/99"
    assert out[0].published_at == "2026-11-24T13:48:53Z"
    assert out[0].engagement == {"points": 12, "comments": 4}
    assert out[0].raw_metadata["external_url"] == "https://example.com/roundup"


def test_lemmy_skips_post_without_permalink():
    out = LemmyAdapter(http_client=StubHttp({"posts": [{
        "post": {"id": 1, "name": "No permalink", "published": "2026-11-24T00:00:00Z"},
    }]})).retrieve(PLAN, REQUEST)
    assert out == []
