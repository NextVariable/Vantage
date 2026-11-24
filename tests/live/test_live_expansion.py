"""Opt-in live checks for the 1.1 structured connectors.

Run only what you mean to:

    RUN_LIVE_TESTS=1 pytest tests/live/test_live_expansion.py -q

These calls hit credential-free public endpoints. A route that is blocked by
the current network is expected to fail in a bounded, classified way; it must
never return invented samples.
"""

import pytest

from sourceglint.connectors.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter
from sourceglint.connectors.devplatforms import GitLabAdapter
from sourceglint.connectors.open_data import SecEdgarAdapter, WorldBankAdapter
from sourceglint.connectors.packages import CratesIoAdapter, PyPIAdapter
from sourceglint.connectors.reviews import SteamAdapter
from sourceglint.connectors.scholarly import CrossrefAdapter, OpenAlexAdapter
from sourceglint.pipeline.adapters import AdapterUnavailable

PLAN = {"time_window": {"days": 365}}
BASE = {
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 2,
}


def _run(adapter, **extra):
    return adapter.retrieve(PLAN, {**BASE, **extra})


def test_crossref_live():
    results = _run(CrossrefAdapter(), query="large language model evaluation")
    assert results
    assert all(item.url.startswith("https://doi.org/") for item in results)
    assert all(item.published_at and len(item.published_at) >= 10 for item in results)


def test_openalex_live():
    results = _run(OpenAlexAdapter(), query="large language model evaluation")
    assert results
    assert all(item.source_native_id.startswith("openalex:W") for item in results)
    assert all(item.published_at for item in results)


def test_pypi_live():
    results = _run(PyPIAdapter(), query="pypi", package="requests")
    assert results
    assert results[0].source_native_id.startswith("pypi:requests@")


def test_crates_io_live():
    results = _run(CratesIoAdapter(), query="serde")
    assert results
    assert all(item.url.startswith("https://crates.io/crates/") for item in results)


def test_gitlab_live():
    results = _run(GitLabAdapter(), query="machine learning")
    assert results
    assert all(item.url.startswith("https://gitlab.com/") for item in results)


def test_lever_live():
    results = LeverAdapter().retrieve(PLAN, {**BASE, "query": "engineer", "boards": ["leverdemo"]})
    assert results
    assert all(item.url.startswith("https://jobs.lever.co/") for item in results)


def test_greenhouse_live():
    results = GreenhouseAdapter().retrieve(PLAN, {**BASE, "query": "engineer", "boards": ["stripe"]})
    assert results
    assert all(item.url.startswith("https://") for item in results)


def test_ashby_live():
    results = AshbyAdapter().retrieve(PLAN, {**BASE, "query": "engineer", "boards": ["linear"]})
    assert results
    assert all(item.url.startswith("https://jobs.ashbyhq.com/") for item in results)


def test_world_bank_live():
    results = _run(WorldBankAdapter(), query="china gdp", country="CN", indicator="NY.GDP.MKTP.CD")
    assert results
    assert all(item.raw_metadata["date_semantics"] == "observation_period" for item in results)


def test_sec_edgar_live():
    results = _run(SecEdgarAdapter(), query="artificial intelligence", forms="8-K", market="us")
    assert results
    assert all(item.url.startswith("https://www.sec.gov/Archives/") for item in results)


def test_steam_live_is_bounded_never_fabricated():
    adapter = SteamAdapter()
    try:
        results = adapter.retrieve(PLAN, {**BASE, "query": "cozy game", "appid": "413150"})
    except AdapterUnavailable as exc:
        assert "redirect" in str(exc).lower() or "anti-bot" in str(exc).lower()
        return
    assert results
    assert all(item.source_native_id.startswith("steam:413150:") for item in results)
    assert all(item.published_at for item in results)


@pytest.mark.parametrize("adapter", [CrossrefAdapter(), OpenAlexAdapter()])
def test_scholarly_requires_a_query(adapter):
    from sourceglint.pipeline.adapters import AdapterInvalidResponse

    with pytest.raises(AdapterInvalidResponse):
        adapter.retrieve(PLAN, {**BASE, "query": ""})
