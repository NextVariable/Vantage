from __future__ import annotations

import json
from typing import Mapping

import pytest

from sourceglint.connectors._http import HttpResponse, HttpPermanentError
from sourceglint.connectors.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter
from sourceglint.pipeline.adapters import AdapterInvalidResponse

REQUEST = {
    "query": "backend engineer",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 5,
    "boards": ["acme"],
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, payload=None, *, raises=None):
        self.payload = payload
        self.raises = raises
        self.calls: list[tuple[str, dict]] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, timeout=15.0, method="GET", json_data=None, **kwargs):
        self.calls.append((url, kwargs))
        if self.raises:
            raise self.raises
        return HttpResponse(status=200, body=json.dumps(self.payload).encode(), url=url)


def test_every_ats_requires_a_named_board():
    for adapter in (LeverAdapter(), GreenhouseAdapter(), AshbyAdapter()):
        with pytest.raises(AdapterInvalidResponse, match="named public board"):
            adapter.retrieve(PLAN, {**REQUEST, "boards": []})


def test_lever_maps_postings_and_millisecond_creation_time():
    http = StubHttp([{
        "id": "abc", "text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/acme/abc",
        "descriptionPlain": "Build agents", "createdAt": 1780000000000,
        "categories": {"team": "Engineering", "location": "Remote", "commitment": "Full-time"},
    }])
    out = LeverAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "lever:acme:abc"
    assert out[0].url == "https://jobs.lever.co/acme/abc"
    assert out[0].published_at.startswith("2026-05-28")
    assert out[0].raw_metadata["location"] == "Remote"


def test_greenhouse_keeps_first_published_separate_from_updated_at():
    http = StubHttp({"jobs": [{
        "id": 42, "title": "Backend Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
        "content": "&lt;p&gt;Build &lt;b&gt;agents&lt;/b&gt;&lt;/p&gt;",
        "first_published": "2026-09-10T00:00:00Z",
        "updated_at": "2026-09-28T00:00:00Z",
        "location": {"name": "Remote"},
    }]})
    out = GreenhouseAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2026-09-10T00:00:00Z"
    assert out[0].raw_metadata["updated_at"] == "2026-09-28T00:00:00Z"
    assert out[0].text == "Build agents"


def test_ashby_applies_the_response_size_cap_and_maps_published_at():
    http = StubHttp({"jobs": [{
        "id": "job-1", "title": "Backend Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/job-1",
        "descriptionPlain": "Build agents", "publishedAt": "2026-09-15T00:00:00Z",
        "isListed": True, "location": "Remote",
    }]})
    out = AshbyAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "ashby:acme:job-1"
    assert out[0].published_at == "2026-09-15T00:00:00Z"
    assert http.calls[0][1]["max_bytes"] == 2_000_000


def test_ashby_oversized_response_is_a_bounded_invalid_response():
    http = StubHttp(raises=HttpPermanentError(413, "https://api.ashbyhq.com/posting-api/job-board/acme"))
    with pytest.raises(AdapterInvalidResponse, match="exceeded"):
        AshbyAdapter(http_client=http).retrieve(PLAN, REQUEST)
