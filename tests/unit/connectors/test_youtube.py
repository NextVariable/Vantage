from __future__ import annotations

import json
import subprocess

import pytest

from sourceglint.connectors._command import CommandResult
from sourceglint.connectors.youtube import YouTubeAdapter
from sourceglint.pipeline.adapters import (
    AdapterInvalidResponse,
    AdapterRateLimited,
    AdapterTimeout,
    AdapterUnavailable,
)


def _request():
    return {"query": "AI video", "query_language": "en", "market": "global"}


def test_maps_metadata_without_cookies_or_downloads():
    calls = []

    def runner(command, timeout):
        calls.append((list(command), timeout))
        return CommandResult(
            0,
            json.dumps({
                "id": "abc123",
                "title": "A new AI workflow",
                "description": "A hands-on review",
                "channel": "Maker Lab",
                "upload_date": "20260920",
                "view_count": 1200,
                "like_count": 42,
                "comment_count": 7,
                "duration": 95,
            }),
            "",
        )

    out = YouTubeAdapter(executable="/opt/yt-dlp", runner=runner).retrieve(
        {}, _request()
    )
    assert len(out) == 1
    assert out[0].url == "https://www.youtube.com/watch?v=abc123"
    assert out[0].published_at == "2026-09-20T00:00:00Z"
    assert out[0].engagement == {"views": 1200, "likes": 42, "comments": 7}
    command = calls[0][0]
    assert command[0] == "/opt/yt-dlp"
    assert "--no-cookies-from-browser" in command
    assert "--no-download" in command
    assert "ytsearch8:AI video" in command


def test_missing_binary_is_explicit():
    with pytest.raises(AdapterUnavailable, match="not installed"):
        YouTubeAdapter(executable="").retrieve({}, _request())


def test_non_json_output_is_rejected():
    adapter = YouTubeAdapter(
        executable="yt-dlp",
        runner=lambda *_: CommandResult(0, "not-json", ""),
    )
    with pytest.raises(AdapterInvalidResponse):
        adapter.retrieve({}, _request())


def test_rate_limit_and_timeout_are_classified():
    blocked = YouTubeAdapter(
        executable="yt-dlp",
        runner=lambda *_: CommandResult(1, "", "HTTP Error 429"),
    )
    with pytest.raises(AdapterRateLimited):
        blocked.retrieve({}, _request())

    def timeout(*_):
        raise subprocess.TimeoutExpired("yt-dlp", 1)

    with pytest.raises(AdapterTimeout):
        YouTubeAdapter(executable="yt-dlp", runner=timeout).retrieve({}, _request())


def test_yt_dlp_timeout_is_capped_by_the_research_deadline(monkeypatch):
    from sourceglint import deadline

    seen = []

    def runner(command, timeout):
        seen.append(timeout)
        raise subprocess.TimeoutExpired(command, timeout)

    adapter = YouTubeAdapter(executable="/opt/yt-dlp", runner=runner, timeout_seconds=120)
    with deadline.deadline_scope(deadline.monotonic() + 4):
        with pytest.raises(AdapterTimeout):
            adapter.retrieve({}, _request())
    assert 0 < seen[0] <= 4


def test_yt_dlp_is_skipped_when_no_research_time_remains():
    adapter = YouTubeAdapter(executable="/opt/yt-dlp", runner=lambda *_: pytest.fail("must not run"))
    with deadline_scoped_now():
        with pytest.raises(AdapterTimeout):
            adapter.retrieve({}, _request())


def deadline_scoped_now():
    from sourceglint import deadline

    return deadline.deadline_scope(deadline.monotonic() - 1)
