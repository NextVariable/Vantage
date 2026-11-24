from __future__ import annotations

import json
from typing import Mapping

import pytest

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.reviews import SteamAdapter
from sourceglint.pipeline.adapters import AdapterInvalidResponse, AdapterUnavailable

REQUEST = {
    "query": "cozy farming game feedback",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 3,
    "appid": "413150",
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, payload=None, *, content_type="application/json", raises=None):
        self.payload = payload
        self.content_type = content_type
        self.raises = raises
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, timeout=15.0, method="GET", json_data=None, **kwargs):
        self.calls.append(url)
        if self.raises:
            raise self.raises
        return HttpResponse(
            status=200,
            headers={"content-type": self.content_type},
            body=json.dumps(self.payload).encode(),
            url=url,
        )


def _payload():
    return {
        "success": 1,
        "cursor": "next-token",
        "reviews": [
            {
                "recommendationid": "100",
                "review": "The coop mode is relaxing",
                "timestamp_created": 1750000000,
                "timestamp_updated": 1750500000,
                "votes_helpful": 12,
                "votes_up": 9,
                "comment_count": 2,
                "voted_up": True,
                "steam_purchase": True,
                "author": {"steamid": "7656119"},
            }
        ],
    }


def test_steam_requires_a_numeric_appid():
    with pytest.raises(AdapterInvalidResponse, match="appid"):
        SteamAdapter(http_client=StubHttp(_payload())).retrieve(PLAN, {**REQUEST, "appid": ""})


def test_steam_maps_review_creation_and_keeps_update_separate():
    out = SteamAdapter(http_client=StubHttp(_payload())).retrieve(PLAN, REQUEST)
    assert len(out) == 1
    review = out[0]
    assert review.source_type == "review"
    assert review.source_native_id == "steam:413150:100"
    assert review.url == "https://steamcommunity.com/profiles/7656119/recommended/413150/"
    assert review.published_at.startswith("2025-06-15")
    assert review.raw_metadata["timestamp_updated"].startswith("2025-06-21")
    assert review.raw_metadata["votes_helpful"] == 12
    assert review.raw_metadata["next_cursor"] == "next-token"
    assert review.engagement == {"points": 9, "comments": 2}


def test_steam_rejects_a_success_zero_payload():
    with pytest.raises(AdapterInvalidResponse, match="no review payload"):
        SteamAdapter(http_client=StubHttp({"success": 0, "reviews": []})).retrieve(PLAN, REQUEST)


def test_steam_html_redirect_is_reported_as_bounded_unavailability():
    http = StubHttp(None, content_type="text/html")
    with pytest.raises(AdapterUnavailable, match="redirected"):
        SteamAdapter(http_client=http).retrieve(PLAN, REQUEST)
