from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.packages import (
    DockerHubAdapter,
    MavenCentralAdapter,
    NuGetAdapter,
    RubyGemsAdapter,
)

REQUEST = {
    "query": "vector",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 3,
}
PLAN = {"time_window": {"days": 30}}


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


def test_maven_central_decodes_millisecond_timestamp():
    http = StubHttp({"search.maven.org": {"response": {"docs": [{
        "g": "org.example", "a": "vector", "latestVersion": "1.2.3",
        "timestamp": 1750161562000, "versionCount": 23, "text": "vector",
    }]}}})
    out = MavenCentralAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2025-06-17T11:59:22Z"
    assert out[0].url == "https://central.sonatype.com/artifact/org.example/vector"
    assert out[0].raw_metadata["date_semantics"] == "latest_version_published"


def test_nuget_reads_published_from_registration_entry():
    http = StubHttp({
        "azuresearch-usnc.nuget.org": {"data": [{
            "id": "Vector.Lib", "version": "2.0.0",
            "description": "Vectors.", "authors": ["Dev"], "totalDownloads": 12,
            "verified": True, "projectUrl": "https://example.dev/vector",
        }]},
        "registration5-semver1/vector.lib/index.json": {"items": [{"items": [{
            "catalogEntry": {
                "version": "2.0.0", "published": "2026-03-04T05:06:07Z",
                "listed": True,
            },
        }]}]},
    })
    out = NuGetAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2026-03-04T05:06:07Z"
    assert out[0].url == "https://www.nuget.org/packages/Vector.Lib/2.0.0"
    assert out[0].raw_metadata["date_semantics"] == "version_published"


def test_rubygems_skips_packages_without_resolved_date():
    http = StubHttp({
        "rubygems.org/api/v1/search.json": [
            {"name": "vector", "version": "0.0.6", "info": "Info", "authors": "Z",
             "project_uri": "https://rubygems.org/gems/vector"},
        ],
        "rubygems.org/api/v1/gems/vector.json": {
            "version_created_at": "2015-01-14T21:33:08Z",
        },
    })
    out = RubyGemsAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2015-01-14T21:33:08Z"
    assert out[0].url == "https://rubygems.org/gems/vector"


def test_docker_hub_uses_registration_date_from_detail():
    http = StubHttp({
        "hub.docker.com/v2/search/repositories/": {"results": [{
            "repo_name": "timberio/vector", "short_description": "Telemetry.",
            "star_count": 100, "pull_count": 1000, "is_official": False,
        }]},
        "hub.docker.com/v2/repositories/timberio/vector/": {
            "date_registered": "2019-05-28T22:38:32.000000Z",
            "last_updated": "2026-11-01T00:00:00.000000Z",
        },
    })
    out = DockerHubAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2019-05-28T22:38:32Z"
    assert out[0].raw_metadata["last_updated"] == "2026-11-01T00:00:00Z"
    assert out[0].raw_metadata["date_semantics"] == "repository_registered"
