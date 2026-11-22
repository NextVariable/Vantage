"""Regression tests for the real GitHub release miss (Research Quality Sprint P0).

Baseline defect: the engine searched repositories only, so
``Azx8788/opencode-plus`` (three releases inside the window) was reported
as having no dated release artifact. These fixtures replay the real
payload shape and assert release evidence is retrieved with correct time
semantics and that zero-release answers are scoped observations.
"""
from __future__ import annotations

import json

from sourceglint.connectors._http import (
    HttpResponse,
    HttpPermanentError,
    HttpTimeoutError,
    HttpTransientError,
)
from sourceglint.connectors._github_release import (
    fetch_releases,
    license_intent,
    release_intent,
)
from sourceglint.connectors.github import GitHubAdapter


class _ScriptedHttpClient:
    def __init__(self, script):
        self._script = list(script)
        self._idx = 0
        self.calls: list[str] = []

    @property
    def user_agent(self):
        return "sourceglint/test"

    def request(self, url, *, headers=None, timeout=15.0):
        self.calls.append(url)
        if self._idx >= len(self._script):
            raise AssertionError(f"unexpected extra HTTP call to {url}")
        op, payload, status = self._script[self._idx]
        self._idx += 1
        if op == "json":
            return HttpResponse(
                status=status or 200,
                body=json.dumps(payload).encode("utf-8"),
                url=url,
            )
        if op == "raise":
            raise payload
        raise AssertionError(f"unknown op {op}")


def _repo(full_name: str, *, created: str, pushed: str, stars: int = 10) -> dict:
    return {
        "id": abs(hash(full_name)) % 100000,
        "full_name": full_name,
        "description": "Open coding agent",
        "html_url": f"https://github.com/{full_name}",
        "owner": {"login": full_name.split("/")[0]},
        "created_at": created,
        "pushed_at": pushed,
        "updated_at": pushed,
        "stargazers_count": stars,
        "forks_count": 1,
        "language": "TypeScript",
        "license": {"spdx_id": "MIT", "name": "MIT License"},
    }


REPOS = [
    _repo("Azx8788/opencode-plus", created="2026-11-01T00:00:00Z", pushed="2026-11-21T00:00:00Z", stars=300),
    _repo("acme/autopilot-codewhale", created="2026-10-20T00:00:00Z", pushed="2026-11-20T00:00:00Z", stars=80),
    _repo("acme/gitoodo", created="2026-10-15T00:00:00Z", pushed="2026-11-19T00:00:00Z", stars=40),
]

OPENCODE_RELEASES = [
    {
        "id": 9003,
        "tag_name": "v0.3.27",
        "name": "v0.3.27",
        "body": "Adds sandboxed tool execution.",
        "html_url": "https://github.com/Azx8788/opencode-plus/releases/tag/v0.3.27",
        "published_at": "2026-11-21T08:00:00Z",
        "created_at": "2026-11-21T07:00:00Z",
        "draft": False,
        "prerelease": False,
    },
    {
        "id": 9002,
        "tag_name": "v0.3.26",
        "name": "v0.3.26",
        "body": "Fixes release automation.",
        "html_url": "https://github.com/Azx8788/opencode-plus/releases/tag/v0.3.26",
        "published_at": "2026-11-21T06:00:00Z",
        "created_at": "2026-11-21T05:00:00Z",
        "draft": False,
        "prerelease": False,
    },
    {
        "id": 9001,
        "tag_name": "v0.3.25",
        "name": "v0.3.25",
        "body": "First public build.",
        "html_url": "https://github.com/Azx8788/opencode-plus/releases/tag/v0.3.25",
        "published_at": "2026-11-17T09:00:00Z",
        "created_at": "2026-11-17T08:00:00Z",
        "draft": False,
        "prerelease": False,
    },
]

PLAN = {
    "topic": "open-source coding agents",
    "mode": "industry",
    "time_window": {"days": 30},
    "subquestions": [
        {"question": "Which coding agents released a new version inside the window?"}
    ],
}
REQUEST = {
    "query": "open coding agent released recently",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-22T00:00:00Z",
}


class TestIntent:
    def test_release_question_detected(self):
        assert release_intent(PLAN, REQUEST) is True

    def test_plain_question_not_release_intent(self):
        assert release_intent({"topic": "pricing"}, {"query": "meeting notes"}) is False

    def test_license_intent(self):
        assert license_intent({"topic": "license terms"}, {"query": "x"}) is True


class TestRealMissRegression:
    def _run(self):
        client = _ScriptedHttpClient(
            [
                ("json", {"items": REPOS, "total_count": 3}, 200),
                ("json", OPENCODE_RELEASES, 200),
                ("json", [], 200),
                ("json", [{"name": "v1", "commit": {"sha": "abc"}}], 200),
                ("json", [], 200),
                ("json", [], 200),
            ]
        )
        adapter = GitHubAdapter(http_client=client)
        out = adapter.retrieve(plan=PLAN, request=REQUEST)
        return adapter, out

    def test_three_releases_are_retrieved_with_release_dates(self):
        adapter, out = self._run()
        releases = [r for r in out if r.source_type == "release"]
        assert len(releases) == 3
        by_tag = {r.raw_metadata["github_tag_name"]: r for r in releases}
        assert by_tag["v0.3.25"].published_at == "2026-11-17T09:00:00Z"
        assert by_tag["v0.3.26"].published_at == "2026-11-21T06:00:00Z"
        assert by_tag["v0.3.27"].published_at == "2026-11-21T08:00:00Z"
        assert by_tag["v0.3.27"].url.endswith("/releases/tag/v0.3.27")
        meta = by_tag["v0.3.27"].raw_metadata
        assert meta["github_full_name"] == "Azx8788/opencode-plus"
        assert meta["github_kind"] == "release"
        assert meta["github_repo_created_at"] == "2026-11-01T00:00:00Z"
        assert meta["github_release_created_at"] == "2026-11-21T07:00:00Z"
        assert meta["version_source"] == "release_published_at"

    def test_zero_release_repos_are_scoped_verified_absences(self):
        adapter, _ = self._run()
        obs = [o for o in adapter.absence_observations if o["kind"] == "releases"]
        statuses = {o["repository"]: o["status"] for o in obs}
        assert statuses["Azx8788/opencode-plus"] == "present"
        assert statuses["acme/autopilot-codewhale"] == "verified_absent"
        assert statuses["acme/gitoodo"] == "verified_absent"
        # A per-repository absence never becomes a global claim.
        assert all(o.get("repository") for o in obs)

    def test_tags_are_observations_not_dated_evidence(self):
        adapter, out = self._run()
        tags = [o for o in adapter.absence_observations if o["kind"] == "tags"]
        assert tags and tags[0]["status"] == "present"
        assert all(r.source_type != "tag" for r in out)

    def test_release_search_uses_activity_window(self):
        adapter, out = self._run()
        search_url = adapter.http_client.calls[0]
        assert "pushed%3A2026-10-23..2026-11-22" in search_url
        assert "created%3A" not in search_url

    def test_no_release_call_without_intent(self):
        client = _ScriptedHttpClient([("json", {"items": REPOS}, 200)])
        GitHubAdapter(http_client=client).retrieve(
            plan={"topic": "pricing", "time_window": {"days": 30}},
            request={"query": "meeting notes", "retrieved_at": "2026-11-22T00:00:00Z"},
        )
        assert len(client.calls) == 1


class TestFailureClassification:
    def _status(self, exc) -> str:
        client = _ScriptedHttpClient([("raise", exc, None)])
        outcome = fetch_releases(
            client,
            [REPOS[0]],
            headers={},
            window=None,
            checked_at="2026-11-22T00:00:00Z",
        )
        assert outcome.results == []
        return outcome.observations[0]["status"]

    def test_404(self):
        assert self._status(HttpPermanentError(status=404, url="x")) == "not_found"

    def test_401(self):
        assert self._status(HttpPermanentError(status=401, url="x")) == "auth_missing"

    def test_403_forbidden(self):
        assert self._status(HttpPermanentError(status=403, url="x")) == "forbidden"

    def test_403_transient_is_rate_limited(self):
        assert self._status(HttpTransientError(status=403, url="x", body_preview="")) == "rate_limited"

    def test_429(self):
        assert self._status(HttpTransientError(status=429, url="x", body_preview="")) == "rate_limited"

    def test_timeout(self):
        assert self._status(HttpTimeoutError(url="x", timeout=1.0)) == "timeout"


class TestWindowSemantics:
    def test_releases_outside_window_are_not_evidence(self):
        old = dict(OPENCODE_RELEASES[0])
        old["published_at"] = "2025-01-01T00:00:00Z"
        old["created_at"] = "2025-01-01T00:00:00Z"
        from datetime import datetime, timezone

        window = (
            datetime(2026, 10, 23, tzinfo=timezone.utc),
            datetime(2026, 11, 22, tzinfo=timezone.utc),
        )
        outcome = fetch_releases(
            _ScriptedHttpClient([("json", [old], 200)]),
            [REPOS[0]],
            headers={},
            window=window,
            checked_at="2026-11-22T00:00:00Z",
        )
        assert outcome.results == []
        assert outcome.observations[0]["status"] == "only_outside_window"
