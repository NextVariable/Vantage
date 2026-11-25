"""Map natural-language platform names to registry source names.

This is deliberately a small, explicit table rather than an LLM call: a
platform request must be predictable and testable. Unsupported platforms are
returned as canonical labels so the runtime can report them honestly instead of
silently pretending they were searched.
"""
from __future__ import annotations

import re

# alias (lowercase) -> registry source name
ALIASES: dict[str, str] = {
    "x": "x",
    "twitter": "x",
    "推特": "x",
    "reddit": "reddit",
    "youtube": "youtube",
    "yt": "youtube",
    "hacker news": "hacker_news",
    "hackernews": "hacker_news",
    "hn": "hacker_news",
    "github": "github",
    "gitlab": "gitlab",
    "bluesky": "bluesky",
    "bsky": "bluesky",
    "product hunt": "product_hunt",
    "producthunt": "product_hunt",
    "dev.to": "devto",
    "devto": "devto",
    "stack overflow": "stack_overflow",
    "stackoverflow": "stack_overflow",
    "hugging face": "hugging_face",
    "huggingface": "hugging_face",
    "qiita": "qiita",
    "arxiv": "arxiv",
    "crossref": "crossref",
    "openalex": "openalex",
    "pubmed": "pubmed",
    "doaj": "doaj",
    "zenodo": "zenodo",
    "datacite": "datacite",
    "open library": "open_library",
    "internet archive": "internet_archive",
    "clinicaltrials": "clinicaltrials",
    "clinical trials": "clinicaltrials",
    "pypi": "pypi",
    "npm": "package_registries",
    "crates": "crates_io",
    "crates.io": "crates_io",
    "maven": "maven_central",
    "maven central": "maven_central",
    "nuget": "nuget",
    "rubygems": "rubygems",
    "docker hub": "docker_hub",
    "dockerhub": "docker_hub",
    "app store": "app_store",
    "lemmy": "lemmy",
    "zenn": "zenn",
    "note.com": "note",
    "itmedia": "itmedia",
    "sspai": "sspai",
    "少数派": "sspai",
    "makuake": "makuake",
    "techmeme": "techmeme",
    "lever": "lever",
    "greenhouse": "greenhouse",
    "ashby": "ashby",
    "world bank": "world_bank",
    "sec edgar": "sec_edgar",
    "steam": "steam",
    "polymarket": "polymarket",
    # Recognised upstream platforms that this build does not register yet.
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "threads": "Threads",
    "linkedin": "LinkedIn",
    "pinterest": "Pinterest",
    "telegram": "Telegram",
    "truth social": "Truth Social",
    "truthsocial": "Truth Social",
    "digg": "Digg",
    "stocktwits": "StockTwits",
    "trustpilot": "Trustpilot",
    "amazon": "Amazon",
    "meta ad library": "Meta Ad Library",
    "facebook ads": "Meta Ad Library",
    "xiaohongshu": "Xiaohongshu",
    "小红书": "Xiaohongshu",
    "zhihu": "Zhihu",
    "知乎": "Zhihu",
    "bilibili": "Bilibili",
    "b站": "Bilibili",
    "weibo": "Weibo",
    "微博": "Weibo",
    "jike": "Jike",
    "即刻": "Jike",
    "wechat": "WeChat",
    "微信公众号": "WeChat",
    "douyin": "Douyin",
    "抖音": "Douyin",
    "36kr": "36Kr",
    "36氪": "36Kr",
    "huxiu": "Huxiu",
    "虎嗅": "Huxiu",
    "pr times": "PR Times",
    "yahoo finance": "Yahoo Finance",
    "patents": "Patents",
    "专利": "Patents",
}

_ALL_ALIASES = tuple(sorted(ALIASES, key=len, reverse=True))

_EXCLUDE_CUE = re.compile(
    r"(?:\bexclude\b|\bwithout\b|\bavoid\b|\bskip\b|\bnot\s+from\b|"
    r"排除|不要|不使用|不看|剔除|除了)",
    re.IGNORECASE,
)
_ONLY_CUE = re.compile(
    r"(?:\bonly\b|\bjust\b|\bexclusively\b|只看|仅看|只要|仅限于|只研究|仅研究)",
    re.IGNORECASE,
)
_OFFICIAL_CUE = re.compile(
    r"(?:\bexclude\s+official\b|\bno\s+official\b|\bnon[- ]official\b|"
    r"\bfirst[- ]hand\b|\bactual\s+users?\b|\breal\s+user\b|"
    r"排除官方|不要官方|非官方|一手体验|一手反馈|真实用户|用户真实反馈)",
    re.IGNORECASE,
)


def _mentions(text: str) -> list[tuple[int, str]]:
    """(position, canonical name) for every recognised platform alias."""
    lowered = text.casefold()
    found: list[tuple[int, str]] = []
    occupied: list[tuple[int, int]] = []
    for alias in _ALL_ALIASES:
        pattern = re.escape(alias)
        if alias[:1].isascii() and alias[:1].isalnum():
            pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
        for match in re.finditer(pattern, lowered):
            span = match.span()
            if any(start <= span[0] < end for start, end in occupied):
                continue
            occupied.append(span)
            found.append((span[0], ALIASES[alias]))
    return sorted(found)


def detect_platforms(text: str) -> list[str]:
    """Canonical platform names mentioned, in first-appearance order."""
    seen: set[str] = set()
    out: list[str] = []
    for _, name in _mentions(text):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def split_platform_intent(text: str) -> tuple[list[str], list[str], bool]:
    """Return (requested, excluded, platform_only).

    A platform mentioned inside an exclusion clause is excluded; all other
    mentions are requested. ``platform_only`` is true when the query contains
    an explicit "only" cue, which lets the runtime treat requested platforms as
    a hard filter instead of a soft priority.
    """
    requested: list[str] = []
    excluded: list[str] = []
    for pos, name in _mentions(text):
        before = text[:pos]
        clause_start = max(before.rfind("。"), before.rfind(". "), before.rfind(";"), before.rfind("；"))
        clause = before[clause_start + 1:] if clause_start >= 0 else before
        # Look back a short span so "排除官方宣传，只分析 X" does not exclude X.
        window = clause[-40:]
        if _EXCLUDE_CUE.search(window):
            if name not in excluded:
                excluded.append(name)
        elif name not in requested:
            requested.append(name)
    requested = [n for n in requested if n not in excluded]
    return requested, excluded, bool(_ONLY_CUE.search(text))


def canonical_platform(name: str) -> str:
    """Resolve a user-supplied platform token to its registry name."""
    return ALIASES.get(name.strip().casefold(), name.strip())


def exclude_official(text: str) -> bool:
    return bool(_OFFICIAL_CUE.search(text))


__all__ = [
    "ALIASES", "canonical_platform", "detect_platforms",
    "split_platform_intent", "exclude_official",
]
