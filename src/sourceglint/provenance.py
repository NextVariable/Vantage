"""Display original publishing surfaces separately from retrieval adapters.

A retrieval route is HOW bytes arrived (``host_web_search``, ``reddit``,
``techmeme``). The original platform is WHERE the content was published and is
derived from the final URL, so a Reddit post read through host search still
reports Reddit as its platform.
"""
from urllib.parse import urlsplit

_DOMAINS = {
    "reddit.com": "Reddit",
    "news.ycombinator.com": "Hacker News",
    "github.com": "GitHub",
    "gist.github.com": "GitHub",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "producthunt.com": "Product Hunt",
    "x.com": "X",
    "twitter.com": "X",
    "bsky.app": "Bluesky",
    "dev.to": "DEV",
    "qiita.com": "Qiita",
    "arxiv.org": "arXiv",
    "huggingface.co": "Hugging Face",
    "stackoverflow.com": "Stack Overflow",
    "npmjs.com": "npm",
    "pypi.org": "PyPI",
    "crates.io": "Crates.io",
    "gitlab.com": "GitLab",
    "doi.org": "DOI",
    "openalex.org": "OpenAlex",
    "pubmed.ncbi.nlm.nih.gov": "PubMed",
    "doaj.org": "DOAJ",
    "zenodo.org": "Zenodo",
    "datacite.org": "DataCite",
    "openlibrary.org": "Open Library",
    "archive.org": "Internet Archive",
    "clinicaltrials.gov": "ClinicalTrials.gov",
    "central.sonatype.com": "Maven Central",
    "nuget.org": "NuGet",
    "rubygems.org": "RubyGems",
    "hub.docker.com": "Docker Hub",
    "apps.apple.com": "App Store",
    "lemmy.world": "Lemmy",
    "zenn.dev": "Zenn",
    "note.com": "note",
    "itmedia.co.jp": "ITmedia",
    "sspai.com": "SSPAI",
    "makuake.com": "Makuake",
    "techmeme.com": "Techmeme",
    "polymarket.com": "Polymarket",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "instagram.com": "Instagram",
    "threads.net": "Threads",
    "threads.com": "Threads",
    "pinterest.com": "Pinterest",
    "telegram.me": "Telegram",
    "t.me": "Telegram",
    "truthsocial.com": "Truth Social",
    "stocktwits.com": "StockTwits",
    "trustpilot.com": "Trustpilot",
    "amazon.com": "Amazon",
    "facebook.com": "Meta",
    "xiaohongshu.com": "Xiaohongshu",
    "xhslink.com": "Xiaohongshu",
    "digg.com": "Digg",
    "yahoo.com": "Yahoo Finance",
    "finance.yahoo.com": "Yahoo Finance",
    "uspto.gov": "USPTO",
    "patents.google.com": "Google Patents",
    "sec.gov": "SEC EDGAR",
    "worldbank.org": "World Bank",
    "lever.co": "Lever",
    "greenhouse.io": "Greenhouse",
    "ashbyhq.com": "Ashby",
    "steamcommunity.com": "Steam",
    "store.steampowered.com": "Steam",
}


def original_platform(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for domain, label in _DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return label
    return host or "Unidentified platform"


def known_platform(url: str) -> str:
    """Mapped platform label, or ``""`` when the host is not recognised."""
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for domain, label in _DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return label
    return ""


def platform_label(url: str, route: str) -> str:
    """Human label that keeps the original platform and the retrieval route.

    When the route already names the platform (``reddit`` + reddit.com) the
    label stays short. When they differ, both are shown once:
    ``Reddit via host_web_search``.
    """
    platform = known_platform(url)
    route_name = (route or "").strip()
    if not platform:
        return route_name or "Unidentified platform"
    if not route_name:
        return platform
    route_key = route_name.lower().replace("-", "_")
    if route_key == platform.lower().replace(" ", "_"):
        return platform
    if route_key in {"host_web_search", "official_web"}:
        return f"{platform} via {route_name}"
    return platform if platform.lower() != route_name.lower() else route_name


__all__ = ["known_platform", "original_platform", "platform_label"]
