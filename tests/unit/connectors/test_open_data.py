from __future__ import annotations

import json
from typing import Mapping

import pytest

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.open_data import SecEdgarAdapter, WorldBankAdapter
from sourceglint.pipeline.adapters import AdapterInvalidResponse

PLAN = {"time_window": {"days": 365}}
REQUEST = {
    "query": "china gdp",
    "query_language": "en",
    "market": "cn",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 5,
}


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


def test_world_bank_requires_country_and_indicator():
    with pytest.raises(AdapterInvalidResponse, match="country code and an indicator"):
        WorldBankAdapter(http_client=StubHttp([{}, []])).retrieve(PLAN, REQUEST)


def test_world_bank_records_observation_period_not_a_publish_date():
    payload = [
        {"page": 1, "pages": 1, "lastupdated": "2026-11-11"},
        [{
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "CN", "value": "China"},
            "date": "2025",
            "value": 19498039388042.6,
            "unit": "",
            "obs_status": "",
        }],
    ]
    request = {**REQUEST, "country": "CN", "indicator": "NY.GDP.MKTP.CD"}
    out = WorldBankAdapter(http_client=StubHttp(payload)).retrieve(PLAN, request)
    assert len(out) == 1
    assert out[0].published_at == ""
    assert out[0].raw_metadata["date_semantics"] == "observation_period"
    assert out[0].raw_metadata["period"] == "2025"
    assert out[0].raw_metadata["dataset_last_updated"] == "2026-11-11T00:00:00Z"
    assert out[0].url == "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD?locations=CN"


def test_sec_edgar_maps_filing_metadata_without_claiming_full_text():
    payload = {
        "hits": {
            "hits": [
                {
                    "_id": "0001683168-20-000837:radnet_8k-ex9901.htm",
                    "_source": {
                        "adsh": "0001683168-20-000837",
                        "ciks": ["0000790526"],
                        "display_names": ["RadNet, Inc.  (RDNT)  (CIK 0000790526)"],
                        "file_date": "2020-03-16",
                        "form": "8-K",
                        "items": ["8.01", "9.01"],
                        "period_ending": "2020-03-13",
                        "file_description": "",
                        "biz_locations": ["US-CA"],
                    },
                }
            ]
        }
    }
    out = SecEdgarAdapter(http_client=StubHttp(payload)).retrieve(PLAN, REQUEST)
    assert len(out) == 1
    filing = out[0]
    assert filing.source_type == "page"
    assert filing.published_at == "2020-03-16T00:00:00Z"
    assert filing.raw_metadata["content_kind"] == "filing_metadata"
    assert filing.url == (
        "https://www.sec.gov/Archives/edgar/data/790526/"
        "000168316820000837/radnet_8k-ex9901.htm"
    )
    assert "Form 8-K" in filing.text


def test_sec_edgar_rejects_a_payload_without_hits():
    with pytest.raises(AdapterInvalidResponse, match="missing hits"):
        SecEdgarAdapter(http_client=StubHttp({})).retrieve(PLAN, REQUEST)
