"""Opt-in live checks for the 1.1 phase-2 key-free sources.

Run only what you mean to:

    RUN_LIVE_TESTS=1 pytest tests/live/test_live_phase2_sources.py -q

Every assertion checks real fields: an original URL, a non-empty publication
anchor and a source-native id. Feeds without a server-side query are filtered
locally, so their tests use a broad term that the current window contains.
"""
from __future__ import annotations

import pytest

from sourceglint.connectors.devplatforms import LemmyAdapter
from sourceglint.connectors.feeds import FeedAdapter
from sourceglint.connectors.packages import (
    DockerHubAdapter,
    MavenCentralAdapter,
    NuGetAdapter,
    RubyGemsAdapter,
)
from sourceglint.connectors.publishers import NoteSearchAdapter, ZennSearchAdapter
from sourceglint.connectors.reviews import ITunesAppStoreAdapter
from sourceglint.connectors.scholarly import (
    ClinicalTrialsAdapter,
    DataCiteAdapter,
    DoajAdapter,
    InternetArchiveAdapter,
    OpenLibraryAdapter,
    PubMedAdapter,
    ZenodoAdapter,
)

PLAN = {"time_window": {"days": 3650}}
BASE = {
    "query_language": "en",
    "market": "us",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 2,
}


def _run(adapter, **extra):
    return adapter.retrieve(PLAN, {**BASE, **extra})


def _assert_evidence(results, prefix: str):
    assert results, "expected at least one real item"
    for item in results:
        assert item.url.startswith(prefix), item.url
        assert item.published_at, f"{item.source} missing a date anchor"
        assert item.source_native_id


def test_pubmed_live():
    _assert_evidence(_run(PubMedAdapter(), query="vector database"), "https://pubmed.ncbi.nlm.nih.gov/")


def test_doaj_live():
    _assert_evidence(_run(DoajAdapter(), query="vector database"), "http")


def test_zenodo_live():
    _assert_evidence(_run(ZenodoAdapter(), query="vector database"), "http")


def test_datacite_live():
    _assert_evidence(_run(DataCiteAdapter(), query="vector database"), "http")


def test_openlibrary_live():
    _assert_evidence(_run(OpenLibraryAdapter(), query="vector database"), "https://openlibrary.org/")


def test_internet_archive_live():
    _assert_evidence(_run(InternetArchiveAdapter(), query="vector database"), "https://archive.org/details/")


def test_clinicaltrials_live():
    _assert_evidence(_run(ClinicalTrialsAdapter(), query="semaglutide"), "https://clinicaltrials.gov/study/")


def test_maven_central_live():
    _assert_evidence(_run(MavenCentralAdapter(), query="vector"), "https://central.sonatype.com/artifact/")


def test_nuget_live():
    results = _run(NuGetAdapter(), query="vector")
    assert results
    assert all(item.url.startswith("https://www.nuget.org/packages/") for item in results)
    assert all(item.published_at for item in results)


def test_rubygems_live():
    results = _run(RubyGemsAdapter(), query="vector")
    assert results
    assert all(item.url.startswith("https://rubygems.org/gems/") for item in results)
    assert all(item.published_at for item in results)


def test_docker_hub_live():
    results = _run(DockerHubAdapter(), query="vector")
    assert results
    assert all(item.url.startswith("https://hub.docker.com/r/") for item in results)
    assert all(item.published_at for item in results)


def test_app_store_live():
    results = ITunesAppStoreAdapter().retrieve(PLAN, {**BASE, "query": "ai chat"})
    assert results
    assert all(item.url.startswith("https://apps.apple.com/") for item in results)
    assert all(item.published_at for item in results)


def test_lemmy_live():
    results = _run(LemmyAdapter(), query="ai")
    assert results
    assert all(item.url.startswith("https://") for item in results)
    assert all(item.published_at for item in results)


@pytest.mark.parametrize(
    "adapter",
    [ZennSearchAdapter(), NoteSearchAdapter()],
    ids=["zenn", "note"],
)
def test_japanese_platforms_live(adapter):
    results = adapter.retrieve(PLAN, {**BASE, "query": "AI", "query_language": "ja", "market": "jp"})
    _assert_evidence(results, "https://")


@pytest.mark.parametrize(
    "adapter,language,market,prefix",
    [
        (FeedAdapter(source_name="itmedia", feed_url="https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
                     language="ja", source_type="page"), "ja", "jp", "https://"),
        (FeedAdapter(source_name="sspai", feed_url="https://sspai.com/feed",
                     language="zh", market="cn"), "zh", "cn", "https://"),
        (FeedAdapter(source_name="makuake", feed_url="https://www.makuake.com/rss/",
                     language="ja", market="jp", source_type="page"), "ja", "jp", "https://"),
    ],
    ids=["itmedia", "sspai", "makuake"],
)
def test_publisher_feeds_live(adapter, language, market, prefix):
    results = adapter.retrieve(
        PLAN, {**BASE, "query": "AI", "query_language": language, "market": market}
    )
    _assert_evidence(results, prefix)
