from __future__ import annotations

import json
from typing import Mapping
from urllib.parse import unquote

import pytest

from sourceglint.connectors._http import HttpResponse, HttpTransientError
from sourceglint.connectors.scholarly import CrossrefAdapter, OpenAlexAdapter
from sourceglint.pipeline.adapters import AdapterRateLimited

REQUEST = {
    "query": "agentic AI",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 3,
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, payload=None, *, raises=None):
        self.payload = payload
        self.raises = raises
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, timeout=15.0, method="GET", json_data=None, **kwargs):
        self.calls.append(url)
        if self.raises:
            raise self.raises
        return HttpResponse(status=200, body=json.dumps(self.payload).encode(), url=url)


def test_crossref_maps_full_issued_date_and_keeps_deposit_separate():
    http = StubHttp({"message": {"items": [{
        "DOI": "10.1234/example",
        "title": ["Agentic <i>AI</i>"],
        "abstract": "<jats:p>Hello <jats:italic>world</jats:italic>.</jats:p>",
        "issued": {"date-parts": [[2026, 9, 12]]},
        "deposited": {"date-time": "2026-09-20T10:00:00Z"},
        "URL": "https://doi.org/10.1234/example",
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "type": "journal-article",
        "container-title": ["Journal of Agents"],
    }]}})
    out = CrossrefAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "doi:10.1234/example"
    assert out[0].title == "Agentic AI"
    assert out[0].text == "Hello world."
    assert out[0].published_at == "2026-09-12T00:00:00Z"
    assert out[0].raw_metadata["deposited"] == "2026-09-20T10:00:00Z"
    assert out[0].author == "Ada Lovelace"
    assert "from-pub-date:2026-08-30" in unquote(http.calls[0])


def test_crossref_skips_records_without_a_full_publication_date():
    http = StubHttp({"message": {"items": [{
        "DOI": "10.1234/partial",
        "title": ["Partial"],
        "issued": {"date-parts": [[2026, 9]]},
        "URL": "https://doi.org/10.1234/partial",
    }]}})
    assert CrossrefAdapter(http_client=http).retrieve(PLAN, REQUEST) == []


def test_crossref_rate_limit_is_classified():
    http = StubHttp(raises=HttpTransientError(429, "https://api.crossref.org/works"))
    with pytest.raises(AdapterRateLimited):
        CrossrefAdapter(http_client=http).retrieve(PLAN, REQUEST)


def test_openalex_reconstructs_abstract_in_word_order():
    http = StubHttp({"results": [{
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1234/example",
        "title": "Agentic AI",
        "publication_date": "2026-09-12",
        "updated_date": "2026-09-13",
        "abstract_inverted_index": {"world": [1], "Hello": [0]},
        "primary_location": {"landing_page_url": "https://example.org/paper"},
        "cited_by_count": 4,
        "open_access": {"is_oa": True, "oa_url": "https://example.org/paper.pdf"},
    }]})
    out = OpenAlexAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "openalex:W1"
    assert out[0].url == "https://doi.org/10.1234/example"
    assert out[0].text == "Hello world"
    assert out[0].raw_metadata["updated_date"] == "2026-09-13"
    assert out[0].raw_metadata["cited_by_count"] == 4
    assert "from_publication_date:2026-08-30" in unquote(http.calls[0])


def test_openalex_anonymous_call_does_not_paginate_or_send_a_key():
    http = StubHttp({"results": [], "meta": {"next_cursor": "abc"}})
    OpenAlexAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert len(http.calls) == 1
    assert "api_key" not in http.calls[0]
    assert "cursor" not in http.calls[0]
