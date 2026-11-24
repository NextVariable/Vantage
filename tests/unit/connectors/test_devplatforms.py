from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.devplatforms import GitLabAdapter

REQUEST = {
    "query": "agent framework",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-09-29T00:00:00Z",
    "limit": 5,
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


def test_gitlab_maps_public_projects_and_releases():
    http = RoutedHttp({
        "/api/v4/projects?": [{
            "id": 1, "web_url": "https://gitlab.com/acme/agent-kit", "name": "Agent Kit",
            "description": "An <b>agent</b> framework", "created_at": "2025-01-02T00:00:00Z",
            "last_activity_at": "2026-09-20T00:00:00Z", "star_count": 12, "forks_count": 3,
            "namespace": {"name": "acme"},
        }],
        "/projects/1/releases": [{
            "tag_name": "v1.2.3", "name": "v1.2.3", "released_at": "2026-09-18T00:00:00Z",
            "created_at": "2026-09-17T00:00:00Z", "description": "Release notes",
            "_links": {"self": "https://gitlab.com/acme/agent-kit/-/releases/v1.2.3"},
        }],
    })
    out = GitLabAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].source_native_id == "gitlab:1"
    assert out[0].text == "An agent framework"
    assert out[0].published_at == "2025-01-02T00:00:00Z"
    assert out[0].engagement == {"points": 12, "comments": 3}
    release = [row for row in out if row.source_type == "release"][0]
    assert release.source_native_id == "gitlab:1:release:v1.2.3"
    assert release.url == "https://gitlab.com/acme/agent-kit/-/releases/v1.2.3"
    assert release.published_at == "2026-09-18T00:00:00Z"
