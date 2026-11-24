from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.reviews import ITunesAppStoreAdapter

PLAN = {"time_window": {"days": 30}}
REQUEST = {
    "query": "ai chat",
    "query_language": "en",
    "market": "us",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 5,
}


class StubHttp:
    user_agent = "test"

    def __init__(self, mapping: Mapping[str, object]):
        self.mapping = mapping
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, **kwargs):
        self.calls.append(url)
        for marker, payload in self.mapping.items():
            if marker in url:
                return HttpResponse(status=200, body=json.dumps(payload).encode(), url=url)
        raise AssertionError(f"unexpected url {url}")


def test_app_store_maps_release_date_and_keeps_version_date_separate():
    http = StubHttp({"itunes.apple.com/search": {"results": [{
        "trackId": 6448311069, "trackName": "ChatGPT",
        "sellerName": "OpenAI", "releaseDate": "2023-05-18T07:00:00Z",
        "currentVersionReleaseDate": "2026-11-01T00:00:00Z",
        "trackViewUrl": "https://apps.apple.com/us/app/chatgpt/id6448311069",
        "averageUserRating": 4.7, "userRatingCount": 1000,
        "version": "1.2.3", "bundleId": "com.openai.chat",
    }]}})
    out = ITunesAppStoreAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2023-05-18T07:00:00Z"
    assert out[0].raw_metadata["current_version_release_date"] == "2026-11-01T00:00:00Z"
    assert out[0].raw_metadata["date_semantics"] == "app_first_released"
    assert out[0].engagement == {"rating": 4.7, "ratings": 1000}


def test_app_store_adds_dated_reviews_only_when_app_id_supplied():
    http = StubHttp({
        "itunes.apple.com/search": {"results": [{
            "trackId": 6448311069, "trackName": "ChatGPT",
            "releaseDate": "2023-05-18T07:00:00Z",
            "trackViewUrl": "https://apps.apple.com/us/app/chatgpt/id6448311069",
        }]},
        "customerreviews": {"feed": {"entry": [{
            "author": {"name": {"label": "reviewer"}},
            "content": {"label": "Great for research."},
            "updated": {"label": "2026-11-20T10:00:00-07:00"},
            "im:rating": {"label": "5"},
            "im:version": {"label": "1.2.3"},
            "id": {"label": "https://itunes.apple.com/us/review?id=123"},
            "im:voteSum": {"label": "7"},
            "im:voteCount": {"label": "9"},
        }]}},
    })
    out = ITunesAppStoreAdapter(http_client=http).retrieve(
        PLAN, dict(REQUEST, appid="6448311069")
    )
    reviews = [item for item in out if item.source_type == "review"]
    assert len(reviews) == 1
    assert reviews[0].published_at == "2026-11-20T17:00:00Z"
    assert reviews[0].raw_metadata["rating"] == "5"
    assert reviews[0].engagement == {"points": 7, "votes": 9}
    assert any("customerreviews/id=6448311069" in url for url in http.calls)


def test_app_store_maps_market_to_storefront():
    http = StubHttp({"itunes.apple.com/search": {"results": []}})
    ITunesAppStoreAdapter(http_client=http).retrieve(PLAN, dict(REQUEST, market="jp"))
    assert "country=jp" in http.calls[0]


def test_app_store_requests_small_limit_floor_but_slices_output():
    results = [{
        "trackId": index, "trackName": f"App {index}",
        "releaseDate": "2024-01-01T00:00:00Z",
        "trackViewUrl": f"https://apps.apple.com/us/app/app-{index}/id{index}",
    } for index in range(3)]
    http = StubHttp({"itunes.apple.com/search": {"results": results}})
    out = ITunesAppStoreAdapter(http_client=http).retrieve(PLAN, dict(REQUEST, limit=1))
    assert "limit=3" in http.calls[0]
    assert len(out) == 1
