from __future__ import annotations

import json
from typing import Mapping

import pytest

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.packages import CratesIoAdapter, PyPIAdapter
from sourceglint.pipeline.adapters import AdapterInvalidResponse

REQUEST = {
    "query": "agent-kit",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 3,
}
PLAN = {"time_window": {"days": 30}}


class RoutedHttp:
    user_agent = "test"

    def __init__(self, routes: Mapping[str, object]):
        self.routes = routes
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, timeout=15.0, method="GET", json_data=None, **kwargs):
        self.calls.append(url)
        for needle, payload in self.routes.items():
            if needle in url:
                return HttpResponse(status=200, body=json.dumps(payload).encode(), url=url)
        return HttpResponse(status=404, body=b"{}", url=url)


def test_pypi_uses_earliest_release_file_upload_time():
    http = RoutedHttp({"/pypi/agent-kit/json": {
        "info": {
            "name": "agent-kit", "version": "1.2.3", "summary": "Agent toolkit",
            "description": "A long description", "author": "Ada",
            "requires_python": ">=3.10", "license": "MIT",
        },
        "releases": {"1.2.3": [
            {"upload_time_iso_8601": "2026-09-28T00:00:00Z"},
            {"upload_time_iso_8601": "2026-09-27T00:00:00Z"},
        ]},
    }})
    out = PyPIAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "pypi:agent-kit@1.2.3"
    assert out[0].url == "https://pypi.org/project/agent-kit/1.2.3/"
    assert out[0].published_at == "2026-09-27T00:00:00Z"
    assert out[0].raw_metadata["file_count"] == 2
    assert out[0].raw_metadata["publish_time"] == "release_file_upload"


def test_pypi_requires_a_named_package():
    http = RoutedHttp({})
    with pytest.raises(AdapterInvalidResponse, match="no full-text search"):
        PyPIAdapter(http_client=http).retrieve(PLAN, {**REQUEST, "query": "how do agents work"})
    assert http.calls == []


def test_crates_uses_version_created_at_not_search_updated_at():
    http = RoutedHttp({
        "/api/v1/crates?": {"crates": [{
            "id": "agent-kit", "newest_version": "1.2.3",
            "description": "Agent toolkit", "downloads": 500,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2026-09-28T00:00:00Z",
        }]},
        "/api/v1/crates/agent-kit": {
            "crate": {"description": "Agent toolkit"},
            "versions": [
                {"num": "1.2.3", "created_at": "2026-09-20T00:00:00Z"},
                {"num": "1.2.2", "created_at": "2026-08-01T00:00:00Z"},
            ],
        },
    })
    out = CratesIoAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "crates:agent-kit@1.2.3"
    assert out[0].published_at == "2026-09-20T00:00:00Z"
    assert out[0].raw_metadata["search_updated_at"] == "2026-09-28T00:00:00Z"
    assert out[0].raw_metadata["crate_created_at"] == "2024-01-01T00:00:00Z"


def test_crates_document_failure_does_not_invent_a_publish_date():
    http = RoutedHttp({"/api/v1/crates?": {"crates": [{
        "id": "agent-kit", "newest_version": "1.2.3", "updated_at": "2026-09-28T00:00:00Z",
    }]}})
    out = CratesIoAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == ""
    assert out[0].raw_metadata["publish_time"] == "unresolved"
