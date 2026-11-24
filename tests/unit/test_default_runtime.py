from __future__ import annotations

from sourceglint.application.runtime import default_adapter_factory
from sourceglint.connectors.authorized_sources import ProductHuntAdapter, XAdapter
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


def test_phase2_key_free_sources_are_wired_without_credentials():
    expected = {
        "pubmed": PubMedAdapter,
        "doaj": DoajAdapter,
        "zenodo": ZenodoAdapter,
        "datacite": DataCiteAdapter,
        "open_library": OpenLibraryAdapter,
        "internet_archive": InternetArchiveAdapter,
        "clinicaltrials": ClinicalTrialsAdapter,
        "maven_central": MavenCentralAdapter,
        "nuget": NuGetAdapter,
        "rubygems": RubyGemsAdapter,
        "docker_hub": DockerHubAdapter,
        "app_store": ITunesAppStoreAdapter,
        "lemmy": LemmyAdapter,
        "zenn": ZennSearchAdapter,
        "note": NoteSearchAdapter,
    }
    for name, adapter_type in expected.items():
        adapter = default_adapter_factory(name, {}, allow_credentials=False)
        assert isinstance(adapter, adapter_type), name


def test_phase2_feed_sources_are_configured_per_platform():
    for name, language, market in (
        ("itmedia", "ja", "global"),
        ("sspai", "zh", "cn"),
        ("makuake", "ja", "jp"),
    ):
        adapter = default_adapter_factory(name, {}, allow_credentials=False)
        assert isinstance(adapter, FeedAdapter), name
        assert adapter.language == language
        assert adapter.market == market
        assert adapter.local_filter is True


def test_default_runtime_wires_x_token_from_environment(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "x-test-token")
    adapter = default_adapter_factory("x", {})
    assert isinstance(adapter, XAdapter)
    assert adapter.bearer_token == "x-test-token"


def test_default_runtime_wires_product_hunt_token_from_environment(monkeypatch):
    monkeypatch.setenv("PRODUCT_HUNT_TOKEN", "ph-test-token")
    adapter = default_adapter_factory("product_hunt", {})
    assert isinstance(adapter, ProductHuntAdapter)
    assert adapter.token == "ph-test-token"


def test_default_runtime_returns_credential_gated_adapters_without_secrets(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCT_HUNT_TOKEN", raising=False)
    assert isinstance(default_adapter_factory("x", {}), XAdapter)
    assert isinstance(default_adapter_factory("product_hunt", {}), ProductHuntAdapter)


def test_public_sources_factory_never_reads_connector_credentials(monkeypatch):
    import pytest
    from sourceglint.application import runtime
    from sourceglint.connectors import _command

    def forbidden(*args, **kwargs):
        pytest.fail("public-only route attempted to access credentials")

    monkeypatch.setattr(runtime, "_env", forbidden)
    monkeypatch.setattr(_command, "run_command", forbidden)
    assert runtime.default_adapter_factory("github", {}, allow_credentials=False).token is None
    reddit = runtime.default_adapter_factory("reddit", {}, allow_credentials=False)
    assert reddit.client_id is None and reddit.client_secret is None
    for gated in ("x", "bluesky", "product_hunt", "semantic_scholar"):
        assert runtime.default_adapter_factory(gated, {}, allow_credentials=False) is None
