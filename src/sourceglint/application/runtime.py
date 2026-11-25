"""default runtime wiring for the canonical API/CLI.

The core engine is host-neutral; a host injects the model and (usually)
its own adapters. This module provides the *defaults* used when a caller
does not inject anything:

* ``default_sources``       — raw source-registry entries from
  ``config/sources.yaml`` (repository layout) with credential-NAME-only
  contract; absent file → empty registry (no crash).
* ``default_adapter_factory`` — maps a registry source name onto its
  connector adapter. Credentials are read from the environment as NAMES
  only inside the adapters; this factory never logs a value (§25).
  Sources without a concrete connector resolve to None (skipped with a
  coverage note — capability discovery at runtime, never hardcoded in
  prompts, §26).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping
from ..resources import data_path

_REPO_CONFIG = data_path("config", "sources.yaml")
_ENV_CONFIG = os.environ.get("GTM_INTELLIGENCE_SOURCES_YAML", "")


def default_sources() -> list[dict[str, Any]]:
    """Raw registry entries for default runs. Empty list when the config
    file cannot be resolved (package-relative fallback honored).

    A disabled entry whose *entire* credential list is configured is enabled
    for this process (``VANTAGE_AUTO_ENABLE_KEYED=0`` opts out). That is what
    makes one configured provider key unlock its platforms without asking the
    user to edit YAML. A missing credential never enables anything.
    """
    import yaml

    candidates = [_ENV_CONFIG, str(_REPO_CONFIG)]
    for cand in candidates:
        if not cand:
            continue
        path = Path(cand)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, list):
            return _auto_enable(data)
    return []


def _auto_enable(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if os.environ.get("VANTAGE_AUTO_ENABLE_KEYED", "1").strip().lower() in (
        "0", "false", "no", "off",
    ):
        return entries
    import shutil

    from .. import credentials

    output: list[dict[str, Any]] = []
    for entry in entries:
        row = dict(entry)
        needed = [str(item) for item in (row.get("credentials") or [])]
        tools = [str(item) for item in (row.get("tools") or [])]
        if row.get("enabled"):
            output.append(row)
            continue
        if needed and all(credentials.has(item) for item in needed):
            row["enabled"] = True
        elif tools and all(shutil.which(item) for item in tools) and not needed:
            row["enabled"] = True
        output.append(row)
    return output


def _env(*names: str) -> str:
    from .. import credentials

    for name in names:
        value = os.environ.get(name, "") or credentials.resolve(name)
        if value:
            return value
    return ""


def default_adapter_factory(
    name: str, plan: Mapping[str, Any], *, allow_credentials: bool = True
) -> Any | None:
    """Map registry source name → connector adapter instance.

    Returns None for sources with no concrete connector in this repo or
    no host-provided capability — the ResearchPipeline records them as
    UNAVAILABLE with a credential-name-only warning (§25, §26).
    """
    from ..connectors.github import GitHubAdapter
    from ..connectors.hacker_news import HackerNewsAdapter
    from ..connectors.reddit import RedditAdapter
    from ..connectors.bluesky import BlueskyAdapter
    from ..connectors.youtube import YouTubeAdapter
    from ..connectors.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter
    from ..connectors.devplatforms import GitLabAdapter, LemmyAdapter
    from ..connectors.feeds import FeedAdapter
    from ..connectors.publishers import NoteSearchAdapter, ZennSearchAdapter
    from ..connectors.packages import (
        CratesIoAdapter,
        DockerHubAdapter,
        MavenCentralAdapter,
        NuGetAdapter,
        PyPIAdapter,
        RubyGemsAdapter,
    )
    from ..connectors.reviews import ITunesAppStoreAdapter, SteamAdapter
    from ..connectors.scholarly import (
        ClinicalTrialsAdapter,
        CrossrefAdapter,
        DataCiteAdapter,
        DoajAdapter,
        InternetArchiveAdapter,
        OpenAlexAdapter,
        OpenLibraryAdapter,
        PubMedAdapter,
        ZenodoAdapter,
    )
    from ..connectors.open_sources import (
        ArxivAdapter,
        DevToAdapter,
        HuggingFaceAdapter,
        PackageRegistriesAdapter,
        QiitaAdapter,
        SemanticScholarAdapter,
        StackOverflowAdapter,
    )
    from ..connectors.authorized_sources import (
        ProductHuntAdapter,
        ScrapeCreatorsTikTokAdapter,
        XAdapter,
    )

    if not allow_credentials and name in {
        "bluesky", "x", "product_hunt", "semantic_scholar", "tiktok",
        "instagram", "threads", "pinterest", "linkedin", "truthsocial",
        "meta_ad_library", "xiaohongshu", "telegram", "amazon",
    }:
        return None
    if name == "tiktok":
        from ..connectors.fallback import FallbackAdapter, Route
        from ..connectors.parity_sources import PublicLinkYtDlpAdapter

        key = _env("SCRAPECREATORS_API_KEY") or None
        routes = [Route("public_link_ytdlp", PublicLinkYtDlpAdapter(platform="tiktok"))]
        if key:
            routes.append(Route(
                "scrapecreators_tiktok",
                ScrapeCreatorsTikTokAdapter(api_key=key), paid=True,
            ))
        return FallbackAdapter("tiktok", tuple(routes))
    if name in {"instagram", "threads", "pinterest", "linkedin"}:
        from ..connectors.fallback import FallbackAdapter, Route
        from ..connectors.parity_sources import (
            PublicLinkYtDlpAdapter,
            ScrapeCreatorsPlatformAdapter,
        )

        key = _env("SCRAPECREATORS_API_KEY") or None
        endpoint = {
            "instagram": "https://api.scrapecreators.com/v2/instagram/reels/search",
            "threads": "https://api.scrapecreators.com/v1/threads/search",
            "pinterest": "https://api.scrapecreators.com/v1/pinterest/search",
            "linkedin": "https://api.scrapecreators.com/v1/linkedin/search/posts",
        }[name]
        sc = ScrapeCreatorsPlatformAdapter(platform=name, endpoint=endpoint, api_key=key)
        if name == "instagram":
            routes = [Route("public_link_ytdlp", PublicLinkYtDlpAdapter(platform="instagram"))]
            if key:
                routes.append(Route("scrapecreators_instagram", sc, paid=True))
            return FallbackAdapter("instagram", tuple(routes))
        return sc
    if name == "telegram":
        from ..connectors.parity_sources import ScrapeCreatorsTelegramAdapter

        return ScrapeCreatorsTelegramAdapter(
            api_key=_env("SCRAPECREATORS_API_KEY") or None,
            channels=_env("TELEGRAM_SOURCES"),
        )
    if name == "trustpilot":
        from ..connectors.parity_sources import TrustpilotCliAdapter

        return TrustpilotCliAdapter()
    if name == "amazon":
        from ..connectors.parity_sources import AmazonBrightDataAdapter

        return AmazonBrightDataAdapter(api_key=_env("BRIGHTDATA_API_KEY") or None)
    if name == "patents":
        from ..connectors.parity_sources import UsptoPatentAdapter

        return UsptoPatentAdapter()
    if name == "truthsocial":
        from ..connectors.parity_sources import TruthSocialAdapter

        return TruthSocialAdapter(token=_env("TRUTHSOCIAL_TOKEN") or None)
    if name == "meta_ad_library":
        from ..connectors.fallback import FallbackAdapter, Route
        from ..connectors.parity_sources import (
            MetaAdLibraryAdapter,
            ScrapeCreatorsMetaAdsAdapter,
        )

        token = _env("META_ACCESS_TOKEN") or None
        key = _env("SCRAPECREATORS_API_KEY") or None
        routes = [Route("meta_ads_archive", MetaAdLibraryAdapter(token=token))]
        if key:
            routes.append(Route(
                "scrapecreators_meta_ads",
                ScrapeCreatorsMetaAdsAdapter(api_key=key), paid=True,
            ))
        return FallbackAdapter("meta_ad_library", tuple(routes))
    if name == "stocktwits":
        from ..connectors.parity_sources import StockTwitsAdapter

        return StockTwitsAdapter()
    if name == "polymarket":
        from ..connectors.parity_sources import PolymarketAdapter

        return PolymarketAdapter()
    if name == "digg":
        from ..connectors.parity_sources import DiggCliAdapter

        return DiggCliAdapter()
    if name == "xiaohongshu":
        from ..connectors.parity_sources import XiaohongshuMcpAdapter

        return XiaohongshuMcpAdapter(base_url=_env("XHS_MCP_URL") or None)
    if name == "bluesky":
        return BlueskyAdapter(
            handle=_env("BSKY_HANDLE") or None,
            app_password=_env("BSKY_APP_PASSWORD") or None,
        )
    if name == "youtube":
        from ..connectors.parity_sources import ScrapeCreatorsYouTubeAdapter

        key = _env("SCRAPECREATORS_API_KEY") if allow_credentials else ""
        base = YouTubeAdapter(include_transcripts=True)
        if not key:
            return base
        from ..connectors.fallback import FallbackAdapter, Route

        return FallbackAdapter("youtube", (
            Route("yt_dlp", base),
            Route("scrapecreators_youtube", ScrapeCreatorsYouTubeAdapter(api_key=key), paid=True),
        ))
    if name == "hacker_news":
        return HackerNewsAdapter(require_topic_match=True)
    if name == "github":
        token = _env("GITHUB_TOKEN") if allow_credentials else ""
        if not token and allow_credentials:
            # Reuse the user's existing public-GitHub CLI authentication only.
            # Never log, serialize or place the credential in an argv string.
            import shutil
            import subprocess
            from ..connectors._command import run_command
            if shutil.which("gh"):
                try:
                    result = run_command(["gh", "auth", "token", "--hostname", "github.com"], 5)
                    if result.returncode == 0:
                        token = result.stdout.strip()
                except (OSError, subprocess.TimeoutExpired):
                    pass
        return GitHubAdapter(token=token or None, include_discussions=True)
    if name == "reddit":
        from ..connectors.parity_sources import ScrapeCreatorsRedditAdapter

        key = _env("SCRAPECREATORS_API_KEY") if allow_credentials else ""
        base = RedditAdapter(
            client_id=(_env("REDDIT_CLIENT_ID") or None) if allow_credentials else None,
            client_secret=(_env("REDDIT_CLIENT_SECRET") or None) if allow_credentials else None,
            allow_keyless_rss=True,
            include_archive=True,
        )
        if not key:
            return base
        from ..connectors.fallback import FallbackAdapter, Route

        return FallbackAdapter("reddit", (
            Route("reddit_public", base),
            Route("scrapecreators_reddit", ScrapeCreatorsRedditAdapter(api_key=key), paid=True),
        ))
    if name == "devto":
        return DevToAdapter(require_topic_match=True)
    if name == "qiita":
        return QiitaAdapter(require_topic_match=True)
    public_adapters = {
        "arxiv": ArxivAdapter,
        "hugging_face": HuggingFaceAdapter,
        "package_registries": PackageRegistriesAdapter,
        "stack_overflow": StackOverflowAdapter,
    }
    adapter_type = public_adapters.get(name)
    if adapter_type is not None:
        return adapter_type()
    if name == "semantic_scholar":
        return SemanticScholarAdapter(
            api_key=_env("SEMANTIC_SCHOLAR_API_KEY") or None,
        )
    if name == "x":
        return XAdapter(bearer_token=_env("X_BEARER_TOKEN") or None)
    if name == "product_hunt":
        return ProductHuntAdapter(token=_env("PRODUCT_HUNT_TOKEN") or None)
    if name == "openalex":
        return OpenAlexAdapter(
            api_key=(_env("OPENALEX_API_KEY") or None) if allow_credentials else None,
        )
    if name == "crossref":
        return CrossrefAdapter()
    if name == "pypi":
        return PyPIAdapter()
    if name == "crates_io":
        return CratesIoAdapter()
    if name == "gitlab":
        return GitLabAdapter()
    if name == "lever":
        return LeverAdapter()
    if name == "greenhouse":
        return GreenhouseAdapter()
    if name == "ashby":
        return AshbyAdapter()
    if name == "steam":
        return SteamAdapter()
    if name == "app_store":
        return ITunesAppStoreAdapter()
    if name == "lemmy":
        return LemmyAdapter()

    # Key-free public registries, datasets and app stores (1.1 phase 2).
    public_registry_adapters = {
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
    }
    registry_adapter = public_registry_adapters.get(name)
    if registry_adapter is not None:
        return registry_adapter()

    if name == "zenn":
        return ZennSearchAdapter()
    if name == "note":
        return NoteSearchAdapter()

    # Publisher and community feeds. Each feed is a distinct platform entry;
    # feeds without a documented search parameter are topic-filtered locally.
    feed_configs = {
        "itmedia": dict(source_name="itmedia",
                        feed_url="https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
                        language="ja", market="global", source_type="page"),
        "sspai": dict(source_name="sspai", feed_url="https://sspai.com/feed",
                      language="zh", market="cn", source_type="post"),
        "makuake": dict(source_name="makuake", feed_url="https://www.makuake.com/rss/",
                        language="ja", market="jp", source_type="page"),
        "techmeme": dict(source_name="techmeme",
                         feed_url="https://www.techmeme.com/feed.xml",
                         language="en", market="global", source_type="page"),
    }
    feed_config = feed_configs.get(name)
    if feed_config is not None:
        return FeedAdapter(**feed_config)

    if name in {"world_bank", "sec_edgar", "polymarket"}:
        from ..connectors.open_data import build_open_data_adapter

        return build_open_data_adapter(name)
    # official_web and host_web_search need a host search/fetch capability
    # or an official-fetch connector — not present standalone in this repo.
    return None
