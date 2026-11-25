"""Parity connectors: upstream lanes that are not covered by phase-1/2 modules.

Everything here is bounded and honest about its gate:

* ScrapeCreators-backed platforms (Instagram, Threads, Pinterest, LinkedIn)
  need ``SCRAPECREATORS_API_KEY`` (paid third-party API, small free allowance).
* Truth Social and Meta Ad Library need a user token/approval.
* StockTwits, Polymarket and Xiaohongshu are keyless but were unreachable or
  require a local service in the audit environment, so they are not counted as
  verified until a real round-trip succeeds.
* Digg shells out to an optional local CLI and is reported as missing when the
  binary is absent.

No adapter fabricates a date or engagement value. Items without a usable
publication anchor are dropped.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import (
    AdapterAuthMissing,
    AdapterError,
    AdapterInvalidResponse,
    AdapterRateLimited,
    AdapterTimeout,
    AdapterUnavailable,
    RawSourceResult,
)
from ._http import (
    HttpClient,
    HttpPermanentError,
    HttpTimeoutError,
    HttpTransientError,
    StdlibHttpClient,
)
from ._command import run_command


def _limit(request: Mapping[str, object], maximum: int = 20) -> int:
    try:
        value = int(request.get("limit") or maximum)
    except (TypeError, ValueError):
        value = maximum
    return max(1, min(value, maximum))


def _query(request: Mapping[str, object], source: str = "") -> str:
    value = str(request.get("query") or "").strip()
    if not value:
        raise AdapterInvalidResponse(source or "source", "a nonempty query is required")
    return value


def _iso(value: object) -> str:
    """Parse an ISO-8601 string or epoch seconds/ms; empty when unusable."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(value).strip()
    if re.fullmatch(r"\d{10,13}", text):
        return _iso(int(text))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", text):
        return f"{text}T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _day(value: object) -> tuple[str, str]:
    iso = _iso(value)
    if not iso:
        return "", ""
    precision = "day" if iso.endswith("T00:00:00Z") else "second"
    return iso, precision


def _count(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _get_json(
    http_client: HttpClient,
    url: str,
    *,
    source: str,
    headers: Mapping[str, str] | None = None,
) -> object:
    try:
        response = http_client.request(url, headers=dict(headers or {}))
    except HttpTransientError as exc:
        if exc.status in (401, 403):
            raise AdapterAuthMissing(source, f"{source} rejected the credential or request") from exc
        if exc.status == 429:
            raise AdapterRateLimited(source, f"{source} rate limit") from exc
        raise AdapterUnavailable(source, f"{source} transient {exc.status}") from exc
    except HttpTimeoutError as exc:
        raise AdapterTimeout(source, str(exc)) from exc
    try:
        return response.json()
    except Exception as exc:
        raise AdapterInvalidResponse(source, f"{source} body was not JSON") from exc


# --------------------------------------------------------------------------
# ScrapeCreators: Instagram, Threads, Pinterest, LinkedIn
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScrapeCreatorsPlatformAdapter:
    platform: str
    endpoint: str
    api_key: str | None = None
    http_client: HttpClient | None = None
    max_per_query: int = 15

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.platform

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key:
            raise AdapterAuthMissing(self.platform, "SCRAPECREATORS_API_KEY is required")
        query = _query(request, self.platform)
        limit = _limit(request, self.max_per_query)
        url = f"{self.endpoint}?{urlencode({'query': query})}"
        payload = _get_json(
            self.http_client, url,
            source=self.platform,
            headers={"x-api-key": self.api_key, "Accept": "application/json"},
        )
        if not isinstance(payload, Mapping):
            raise AdapterInvalidResponse(self.platform, "ScrapeCreators payload was not an object")
        raw_items = self._items(payload)
        output: list[RawSourceResult] = []
        for raw in raw_items:
            item = self._parse(raw)
            if item is not None:
                output.append(item)
            if len(output) >= limit:
                break
        return output

    def _items(self, payload: Mapping[str, object]) -> list[object]:
        for key in ("reels", "posts", "items", "data", "pins"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def _parse(self, raw: object) -> RawSourceResult | None:
        if not isinstance(raw, Mapping):
            return None
        parser = getattr(self, f"_parse_{self.platform}", None)
        if parser is None:
            return None
        return parser(raw)

    def _base(self, *, native_id: str, url: str, text: str, author: str,
              published: str, engagement: Mapping[str, int],
              source_type: str, extra: Mapping[str, object] | None = None) -> RawSourceResult | None:
        if not native_id or not text or not published:
            return None
        return RawSourceResult(
            source=self.platform,
            source_type=source_type,
            source_native_id=native_id,
            url=url,
            title=text[:120],
            text=text,
            author=author,
            published_at=published,
            market="global",
            language="en",
            query="",
            query_language="en",
            engagement=dict(engagement),
            raw_metadata={"route": "scrapecreators", **(extra or {})},
        )

    def _parse_instagram(self, raw: Mapping[str, object]) -> RawSourceResult | None:
        native_id = str(raw.get("id") or raw.get("pk") or "")
        caption = raw.get("caption")
        text = str(
            (caption.get("text") if isinstance(caption, Mapping) else caption)
            or raw.get("desc") or raw.get("text") or ""
        ).strip()
        owner = raw.get("owner") or raw.get("user")
        author = str(owner.get("username") or "") if isinstance(owner, Mapping) else str(owner or "")
        code = str(raw.get("shortcode") or raw.get("code") or "")
        url = f"https://www.instagram.com/reel/{code}/" if code else ""
        published, _ = _day(raw.get("taken_at"))
        engagement = {
            "views": _count(raw.get("video_play_count") or raw.get("video_view_count") or raw.get("play_count")),
            "likes": _count(raw.get("like_count")),
            "comments": _count(raw.get("comment_count")),
        }
        return self._base(native_id=native_id, url=url, text=text, author=author,
                          published=published, engagement=engagement, source_type="post")

    def _parse_threads(self, raw: Mapping[str, object]) -> RawSourceResult | None:
        native_id = str(raw.get("id") or raw.get("pk") or raw.get("code") or "")
        text = str(raw.get("text") or raw.get("caption") or raw.get("content") or "").strip()
        user = raw.get("user") or raw.get("author") or {}
        author = str(user.get("username") or user.get("handle") or "") if isinstance(user, Mapping) else str(user or "")
        code = str(raw.get("code") or raw.get("shortcode") or "")
        url = str(raw.get("url") or raw.get("share_url") or "")
        if not url and code:
            url = f"https://www.threads.net/post/{code}"
        published = ""
        for key in ("taken_at", "create_time", "created_at", "published_at", "date"):
            published = _iso(raw.get(key))
            if published:
                break
        engagement = {
            "likes": _count(raw.get("like_count") or raw.get("likes")),
            "replies": _count(raw.get("reply_count") or raw.get("replies")),
            "reposts": _count(raw.get("repost_count") or raw.get("reposts")),
        }
        return self._base(native_id=native_id, url=url, text=text, author=author,
                          published=published, engagement=engagement, source_type="post")

    def _parse_pinterest(self, raw: Mapping[str, object]) -> RawSourceResult | None:
        native_id = str(raw.get("id") or raw.get("pin_id") or "")
        text = str(raw.get("description") or raw.get("title") or "").strip()
        pinner = raw.get("pinner") or raw.get("creator") or raw.get("user") or {}
        author = str(pinner.get("username") or pinner.get("full_name") or "") if isinstance(pinner, Mapping) else str(pinner or "")
        url = str(raw.get("link") or raw.get("url") or "")
        if not url and native_id:
            url = f"https://www.pinterest.com/pin/{native_id}/"
        published = ""
        for key in ("created_at", "createdAt", "published_at", "date"):
            published = _iso(raw.get(key))
            if published:
                break
        engagement = {
            "saves": _count(raw.get("save_count") or raw.get("saves") or raw.get("repin_count")),
            "comments": _count(raw.get("comment_count") or raw.get("comments")),
        }
        return self._base(native_id=native_id, url=url, text=text, author=author,
                          published=published, engagement=engagement, source_type="post")

    def _parse_linkedin(self, raw: Mapping[str, object]) -> RawSourceResult | None:
        native_id = str(raw.get("urn") or raw.get("id") or raw.get("postId") or "")
        text = str(raw.get("description") or raw.get("text") or raw.get("content") or raw.get("body") or "").strip()
        author_raw = raw.get("author") or raw.get("authorName") or raw.get("author_name") or ""
        author = str(author_raw.get("name") or author_raw.get("full_name") or "") if isinstance(author_raw, Mapping) else str(author_raw)
        url = str(raw.get("url") or raw.get("postUrl") or raw.get("post_url") or "")
        published = ""
        for key in ("datePublished", "date", "postedAt", "posted_at", "createdAt", "created_at"):
            published = _iso(raw.get(key))
            if published:
                break
        engagement = {
            "likes": _count(raw.get("likes") or raw.get("likesCount") or raw.get("likeCount")),
            "comments": _count(raw.get("comments") or raw.get("commentsCount") or raw.get("commentCount")),
            "reposts": _count(raw.get("reposts") or raw.get("reshares")),
        }
        return self._base(native_id=native_id, url=url, text=text, author=author,
                          published=published, engagement=engagement, source_type="post")


# --------------------------------------------------------------------------
# Token or approval gated
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TruthSocialAdapter:
    token: str | None = None
    http_client: HttpClient | None = None
    source_name: str = "truthsocial"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.token:
            raise AdapterAuthMissing(self.source_name, "TRUTHSOCIAL_TOKEN is required")
        query = _query(request, self.source_name)
        url = "https://truthsocial.com/api/v2/search?" + urlencode(
            {"q": query, "type": "statuses", "limit": _limit(request)}
        )
        payload = _get_json(self.http_client, url, source=self.source_name,
                            headers={"Authorization": f"Bearer {self.token}"})
        statuses = payload.get("statuses") if isinstance(payload, Mapping) else None
        output: list[RawSourceResult] = []
        for status in statuses or []:
            if not isinstance(status, Mapping):
                continue
            text = str(status.get("content") or "").strip()
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            native_id = str(status.get("id") or "")
            account = status.get("account") if isinstance(status.get("account"), Mapping) else {}
            published = _iso(status.get("created_at"))
            url_value = str(status.get("url") or (f"https://truthsocial.com/@{account.get('acct')}/posts/{native_id}" if account.get("acct") else ""))
            if not native_id or not text or not published or not url_value:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="post", source_native_id=native_id,
                url=url_value, title=text[:120], text=text,
                author=str(account.get("acct") or ""), published_at=published,
                market="us", language="en", query=query, query_language="en",
                engagement={
                    "replies": _count(status.get("replies_count")),
                    "reblogs": _count(status.get("reblogs_count")),
                    "favourites": _count(status.get("favourites_count")),
                },
                raw_metadata={"route": "truthsocial_api"},
            ))
        return output


@dataclass(frozen=True)
class MetaAdLibraryAdapter:
    token: str | None = None
    http_client: HttpClient | None = None
    source_name: str = "meta_ad_library"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.token:
            raise AdapterAuthMissing(self.source_name, "META_ACCESS_TOKEN is required")
        query = _query(request, self.source_name)
        market = str(request.get("market") or "US").upper()
        url = "https://graph.facebook.com/v20.0/ads_archive?" + urlencode({
            "search_terms": query,
            "ad_reached_countries": json.dumps([market if len(market) == 2 else "US"]),
            "fields": "id,page_name,ad_creative_body,ad_delivery_start_time,ad_snapshot_url",
            "limit": _limit(request, 10),
        })
        payload = _get_json(
            self.http_client, url, source=self.source_name,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        data = payload.get("data") if isinstance(payload, Mapping) else None
        output: list[RawSourceResult] = []
        for ad in data or []:
            if not isinstance(ad, Mapping):
                continue
            body = str(ad.get("ad_creative_body") or "").strip()
            native_id = str(ad.get("id") or "")
            published, precision = _day(ad.get("ad_delivery_start_time"))
            page = str(ad.get("page_name") or "")
            if not native_id or not body or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=native_id,
                url=f"https://www.facebook.com/ads/library/?{urlencode({'id': native_id})}",
                title=body[:120], text=body, author=page, published_at=published,
                market=market, language="en", query=query, query_language="en",
                engagement={},
                raw_metadata={"route": "meta_ads_archive", "date_precision": precision},
            ))
        return output


# --------------------------------------------------------------------------
# Keyless / local-service routes
# --------------------------------------------------------------------------

_SYMBOL = re.compile(r"\$([A-Za-z]{1,5})\b")


def _symbol(request: Mapping[str, object], source: str) -> str:
    explicit = str(request.get("ticker") or request.get("symbol") or "").strip().upper()
    if explicit:
        return explicit.lstrip("$")
    match = _SYMBOL.search(str(request.get("query") or ""))
    if match:
        return match.group(1).upper()
    raise AdapterInvalidResponse(source, "StockTwits requires a ticker such as $NVDA or request.ticker")


@dataclass(frozen=True)
class StockTwitsAdapter:
    http_client: HttpClient | None = None
    source_name: str = "stocktwits"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        symbol = _symbol(request, self.source_name)
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
        payload = _get_json(self.http_client, url, source=self.source_name)
        messages = payload.get("messages") if isinstance(payload, Mapping) else None
        output: list[RawSourceResult] = []
        for message in messages or []:
            if not isinstance(message, Mapping):
                continue
            body = str(message.get("body") or "").strip()
            native_id = str(message.get("id") or "")
            published = _iso(message.get("created_at"))
            user = message.get("user") if isinstance(message.get("user"), Mapping) else {}
            if not native_id or not body or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="post", source_native_id=native_id,
                url=f"https://stocktwits.com/{user.get('username') or 'message'}/message/{native_id}",
                title=body[:120], text=body, author=str(user.get("username") or ""),
                published_at=published, market="us", language="en",
                query=symbol, query_language="en",
                engagement={
                    "likes": _count((message.get("likes") or {}).get("total") if isinstance(message.get("likes"), Mapping) else 0),
                    "reshares": _count((message.get("reshares") or {}).get("reshared_count") if isinstance(message.get("reshares"), Mapping) else 0),
                },
                raw_metadata={"route": "stocktwits_public", "symbol": symbol,
                              "sentiment": ((message.get("entities") or {}).get("sentiment") or {}).get("basic")},
            ))
        return output


@dataclass(frozen=True)
class PolymarketAdapter:
    http_client: HttpClient | None = None
    source_name: str = "polymarket"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request)
        url = "https://gamma-api.polymarket.com/public-search?" + urlencode({
            "q": query, "limit_per_type": limit, "search_tags": "false", "search_profiles": "false",
        })
        payload = _get_json(self.http_client, url, source=self.source_name)
        events = payload.get("events") if isinstance(payload, Mapping) else payload
        output: list[RawSourceResult] = []
        for event in events or []:
            if not isinstance(event, Mapping):
                continue
            title = str(event.get("title") or event.get("question") or "").strip()
            slug = str(event.get("slug") or "")
            native_id = str(event.get("id") or slug)
            start, precision = _day(event.get("startDate") or event.get("createdAt"))
            if not native_id or not title or not start or not slug:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=native_id,
                url=f"https://polymarket.com/event/{slug}", title=title[:120],
                text=_strip_html(event.get("description")) or title,
                author="Polymarket", published_at=start, market="global", language="en",
                query=query, query_language="en",
                engagement={"volume": _count(event.get("volume"))},
                raw_metadata={"route": "polymarket_gamma", "date_semantics": "market_start",
                              "date_precision": precision},
            ))
            if len(output) >= limit:
                break
        return output


@dataclass(frozen=True)
class XiaohongshuMcpAdapter:
    base_url: str | None = None
    http_client: HttpClient | None = None
    source_name: str = "xiaohongshu"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.base_url:
            raise AdapterAuthMissing(self.source_name, "XHS_MCP_URL is required (user-authorized local service)")
        base = self.base_url.rstrip("/")
        query = _query(request, self.source_name)
        status = _get_json(self.http_client, f"{base}/api/v1/login/status", source=self.source_name)
        data = status.get("data") if isinstance(status, Mapping) else None
        if not isinstance(data, Mapping) or not data.get("is_logged_in"):
            raise AdapterAuthMissing(self.source_name, "Xiaohongshu service is reachable but not logged in")
        payload = {
            "keyword": query,
            "filters": {"sort_by": "综合", "note_type": "不限", "publish_time": "一周内",
                        "search_scope": "不限", "location": "不限"},
        }
        try:
            response = self.http_client.request(
                f"{base}/api/v1/feeds/search", method="POST", json_data=payload,
            )
            body = response.json()
        except HttpTimeoutError as exc:
            raise AdapterTimeout(self.source_name, str(exc)) from exc
        except HttpTransientError as exc:
            raise AdapterUnavailable(self.source_name, f"local MCP transient {exc.status}") from exc
        except Exception as exc:
            raise AdapterInvalidResponse(self.source_name, "local MCP body was not JSON") from exc
        feeds = ((body.get("data") or {}).get("feeds") if isinstance(body, Mapping) else None) or []
        output: list[RawSourceResult] = []
        for feed in feeds:
            if not isinstance(feed, Mapping):
                continue
            note = feed.get("noteCard") if isinstance(feed.get("noteCard"), Mapping) else {}
            interact = note.get("interactInfo") if isinstance(note.get("interactInfo"), Mapping) else {}
            native_id = str(feed.get("id") or note.get("noteId") or "")
            title = str(note.get("displayTitle") or note.get("title") or "").strip()
            text = str(note.get("desc") or note.get("displayDesc") or title).strip()
            token = str(feed.get("xsecToken") or note.get("xsecToken") or "")
            published = _iso(note.get("time"))
            if not native_id or not text or not published:
                continue
            url = f"https://www.xiaohongshu.com/explore/{native_id}" + (f"?xsec_token={token}" if token else "")
            output.append(RawSourceResult(
                source=self.source_name, source_type="post", source_native_id=native_id,
                url=url, title=(title or text)[:120], text=text, author="",
                published_at=published, market="cn", language="zh",
                query=query, query_language="zh",
                engagement={
                    "likes": _count(interact.get("likedCount")),
                    "comments": _count(interact.get("commentCount")),
                    "favorites": _count(interact.get("collectedCount")),
                },
                raw_metadata={"route": "xiaohongshu_mcp"},
            ))
        return output


@dataclass(frozen=True)
class DiggCliAdapter:
    cli: str = "digg-pp-cli"
    runner: object | None = None
    source_name: str = "digg"

    @property
    def name(self) -> str:
        return self.source_name

    def _run(self, args: list[str]) -> str:
        if self.runner is not None:
            return self.runner(args)  # type: ignore[operator]
        binary = shutil.which(self.cli)
        if not binary:
            raise AdapterUnavailable(self.source_name, f"{self.cli} is not installed")
        try:
            completed = run_command([binary, *args], timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise AdapterTimeout(self.source_name, f"{self.cli} timed out") from exc
        if completed.returncode != 0:
            raise AdapterUnavailable(self.source_name, f"{self.cli} exited {completed.returncode}")
        return completed.stdout

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        raw = self._run(["search", query, "--since", "30d", "--agent",
                         "--limit", str(_limit(request, 10))])
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AdapterInvalidResponse(self.source_name, "digg JSON was invalid") from exc
        if isinstance(payload, Mapping):
            items = payload.get("results", payload.get("stories"))
        else:
            items = payload
        if not isinstance(items, list):
            raise AdapterInvalidResponse(self.source_name, "digg JSON did not contain a results array")
        output: list[RawSourceResult] = []
        for story in items:
            if not isinstance(story, Mapping):
                continue
            title = str(story.get("title") or "").strip()
            url = str(story.get("url") or "").strip()
            native_id = str(story.get("clusterId") or story.get("uuid") or story.get("id") or url)
            published = _iso(story.get("publishedAt") or story.get("published_at"))
            if not title or not url or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=native_id,
                url=url, title=title[:120], text=str(story.get("tldr") or story.get("description") or title),
                author=str(story.get("publisher") or ""), published_at=published,
                market="us", language="en", query=query, query_language="en",
                engagement={"digg_score": _count(story.get("diggScore"))},
                raw_metadata={"route": "digg_cli"},
            ))
        return output


# --------------------------------------------------------------------------
# ScrapeCreators: Reddit, YouTube, Telegram, Meta Ads
# --------------------------------------------------------------------------

SC_BASE = "https://api.scrapecreators.com"


def _sc_payload(
    http_client: HttpClient,
    path: str,
    params: Mapping[str, object],
    api_key: str,
    source: str,
) -> Mapping[str, object]:
    cleaned = {key: value for key, value in params.items() if value not in (None, "")}
    url = f"{SC_BASE}{path}?{urlencode(cleaned)}"
    payload = _get_json(
        http_client, url, source=source,
        headers={"x-api-key": api_key, "Accept": "application/json"},
    )
    if not isinstance(payload, Mapping):
        raise AdapterInvalidResponse(source, "ScrapeCreators payload was not an object")
    return payload


def _sc_items(payload: Mapping[str, object], keys: tuple[str, ...]) -> list[object]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _timeframe(plan: Mapping[str, object]) -> str:
    """Map the research window onto ScrapeCreators' fixed timeframes."""
    window = plan.get("time_window") if isinstance(plan, Mapping) else None
    days = 30
    if isinstance(window, Mapping):
        if "days" in window:
            try:
                days = max(1, int(window["days"]))
            except (TypeError, ValueError):
                days = 30
        elif "start" in window and "end" in window:
            try:
                start = datetime.fromisoformat(str(window["start"]).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(window["end"]).replace("Z", "+00:00"))
                days = max(1, (end - start).days)
            except (TypeError, ValueError):
                days = 30
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    if days <= 366:
        return "year"
    return "all"


def _first_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item or "").strip()
            if text:
                return text
        return ""
    return str(value or "").strip()


def _strip_html(value: object) -> str:
    text = str(value or "")
    if "<" in text and ">" in text:
        text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


@dataclass(frozen=True)
class ScrapeCreatorsRedditAdapter:
    """Reddit keyword search through the aggregated provider.

    The keyless public route runs first in the runtime; this adapter is the
    authorized fallback. Native ids keep the ``t3_`` prefix so a post reached
    through both routes collapses to one item.
    """

    api_key: str | None = None
    http_client: HttpClient | None = None
    max_per_query: int = 15
    source_name: str = "reddit"
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key:
            raise AdapterAuthMissing(self.source_name, "SCRAPECREATORS_API_KEY is required")
        query = _query(request, self.source_name)
        payload = _sc_payload(
            self.http_client, "/v1/reddit/search",
            {"query": query, "sort": "relevance", "timeframe": _timeframe(plan)},
            self.api_key, self.source_name,
        )
        output: list[RawSourceResult] = []
        for post in _sc_items(payload, ("posts", "results", "data")):
            if not isinstance(post, Mapping):
                continue
            raw_id = str(post.get("id") or "")
            if not raw_id:
                continue
            native_id = raw_id if raw_id.startswith("t3_") else f"t3_{raw_id}"
            permalink = str(post.get("permalink") or "")
            url = f"https://www.reddit.com{permalink}" if permalink else str(post.get("url") or "")
            if "reddit.com" not in url:
                continue
            title = _strip_html(post.get("title"))
            body = _strip_html(post.get("selftext") or post.get("body"))
            text = body if len(body) > len(title) else title
            published = _iso(post.get("created_at") or post.get("created_utc") or post.get("date"))
            if not text or not published:
                continue
            subreddit = post.get("subreddit")
            if isinstance(subreddit, Mapping):
                subreddit = subreddit.get("name") or subreddit.get("display_name")
            output.append(RawSourceResult(
                source=self.source_name, source_type="post", source_native_id=native_id,
                url=url, title=title[:120] or text[:120], text=text,
                author=str(post.get("author") or ""), published_at=published,
                market="global", language="en", query=query, query_language="en",
                engagement={
                    "upvotes": _count(post.get("score") or post.get("ups") or post.get("votes")),
                    "comments": _count(post.get("num_comments")),
                },
                raw_metadata={
                    "route": "scrapecreators_reddit", "provider": "scrapecreators",
                    "subreddit": str(subreddit or ""),
                },
            ))
            if len(output) >= _limit(request, self.max_per_query):
                break
        if not output:
            self.limitations.append("ScrapeCreators Reddit returned no dated posts for this query")
        return output


@dataclass(frozen=True)
class ScrapeCreatorsYouTubeAdapter:
    """YouTube keyword search through the aggregated provider.

    Records without an absolute publication timestamp are dropped: the
    provider's relative strings ("2 weeks ago") are not a date.
    """

    api_key: str | None = None
    http_client: HttpClient | None = None
    max_per_query: int = 10
    source_name: str = "youtube"
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key:
            raise AdapterAuthMissing(self.source_name, "SCRAPECREATORS_API_KEY is required")
        query = _query(request, self.source_name)
        payload = _sc_payload(
            self.http_client, "/v1/youtube/search", {"query": query},
            self.api_key, self.source_name,
        )
        output: list[RawSourceResult] = []
        for video in _sc_items(payload, ("videos", "data", "items")):
            if not isinstance(video, Mapping):
                continue
            video_id = str(video.get("videoId") or video.get("video_id") or video.get("id") or "")
            if not video_id:
                continue
            title = _strip_html(video.get("title"))
            description = _strip_html(video.get("description"))[:500]
            channel = video.get("channel") or video.get("channel_name") or video.get("uploader")
            if isinstance(channel, Mapping):
                channel = channel.get("title") or channel.get("handle") or ""
            published = _iso(
                video.get("upload_date") or video.get("publishedTime")
                or video.get("published_at") or video.get("date")
            )
            if not title or not published:
                continue
            url = str(video.get("url") or f"https://www.youtube.com/watch?v={video_id}")
            output.append(RawSourceResult(
                source=self.source_name, source_type="post", source_native_id=video_id,
                url=url, title=title[:120], text=(description or title),
                author=str(channel or ""), published_at=published,
                market="global", language="en", query=query, query_language="en",
                engagement={
                    "views": _count(video.get("viewCountInt") or video.get("view_count") or video.get("views")),
                    "likes": _count(video.get("like_count") or video.get("likes")),
                    "comments": _count(video.get("comment_count") or video.get("comments")),
                },
                raw_metadata={"route": "scrapecreators_youtube", "provider": "scrapecreators"},
            ))
            if len(output) >= _limit(request, self.max_per_query):
                break
        if not output:
            self.limitations.append("ScrapeCreators YouTube returned no item with an absolute date")
        return output


def _parse_channels(raw: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        values = [str(part).strip() for part in raw]
    cleaned: list[str] = []
    for value in values:
        handle = value.removeprefix("https://t.me/").removeprefix("@").strip("/")
        if handle and handle not in cleaned:
            cleaned.append(handle)
    return tuple(cleaned)


@dataclass(frozen=True)
class ScrapeCreatorsTelegramAdapter:
    """Public Telegram channel posts through the aggregated provider.

    Upstream has no keyword discovery for Telegram: a channel list is required.
    Without both a key and at least one channel the adapter reports the exact
    missing piece instead of returning unrelated content.
    """

    api_key: str | None = None
    channels: object = ""
    http_client: HttpClient | None = None
    max_per_channel: int = 5
    source_name: str = "telegram"
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key:
            raise AdapterAuthMissing(self.source_name, "SCRAPECREATORS_API_KEY is required")
        channels = _parse_channels(self.channels)
        if not channels:
            raise AdapterAuthMissing(self.source_name, "TELEGRAM_SOURCES channel list is required")
        query = str(request.get("query") or "").strip()
        output: list[RawSourceResult] = []
        for handle in channels:
            try:
                payload = _sc_payload(
                    self.http_client, "/v1/telegram/channel/posts", {"handle": handle},
                    self.api_key, self.source_name,
                )
            except (AdapterAuthMissing, AdapterInvalidResponse):
                raise
            except AdapterError as exc:
                self.limitations.append(f"telegram @{handle}: {type(exc).__name__}")
                continue
            channel = payload.get("channel") if isinstance(payload.get("channel"), Mapping) else {}
            kept = 0
            for post in _sc_items(payload, ("posts", "data", "items")):
                if not isinstance(post, Mapping):
                    continue
                post_id = str(post.get("id") or post.get("message_id") or "")
                text = _strip_html(post.get("text") or post.get("message") or post.get("caption"))
                published = _iso(post.get("date") or post.get("published_at") or post.get("created_at"))
                if not post_id or not text or not published:
                    continue
                output.append(RawSourceResult(
                    source=self.source_name, source_type="post",
                    source_native_id=f"{handle}:{post_id}",
                    url=f"https://t.me/{handle}/{post_id}",
                    title=text[:120], text=text,
                    author=str(channel.get("name") or channel.get("handle") or handle),
                    published_at=published, market="global", language="en",
                    query=query, query_language="en",
                    engagement={
                        "views": _count(post.get("views") or post.get("view_count")),
                        "forwards": _count(post.get("forwards") or post.get("forward_count")),
                    },
                    raw_metadata={"route": "scrapecreators_telegram", "provider": "scrapecreators",
                                  "channel": handle},
                ))
                kept += 1
                if kept >= self.max_per_channel:
                    break
            if not kept:
                self.limitations.append(f"telegram @{handle}: no dated post in the returned page")
        return output


@dataclass(frozen=True)
class ScrapeCreatorsMetaAdsAdapter:
    """Meta Ad Library keyword search through the aggregated provider.

    This is the paid-provider alternative to the official Graph API; it does
    not remove Meta's own policy constraints and is only used when a key is
    configured.
    """

    api_key: str | None = None
    http_client: HttpClient | None = None
    max_per_query: int = 10
    source_name: str = "meta_ad_library"
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key:
            raise AdapterAuthMissing(self.source_name, "SCRAPECREATORS_API_KEY is required")
        query = _query(request, self.source_name)
        country = str(request.get("market") or "US").upper()
        payload = _sc_payload(
            self.http_client, "/v1/facebook/adLibrary/search/ads",
            {
                "query": query,
                "country": country if len(country) == 2 else "US",
                "status": "ACTIVE",
                "search_type": "keyword_unordered",
                "trim": "true",
            },
            self.api_key, self.source_name,
        )
        output: list[RawSourceResult] = []
        for row in _sc_items(payload, ("searchResults", "results", "ads", "data")):
            if not isinstance(row, Mapping):
                continue
            snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), Mapping) else {}
            body = snapshot.get("body")
            if isinstance(body, Mapping):
                body = body.get("text")
            text = _strip_html(body or snapshot.get("title"))
            native_id = str(row.get("ad_archive_id") or row.get("collation_id") or "")
            published = _iso(
                row.get("start_date_string") or row.get("start_date")
                or row.get("ad_delivery_start_time")
            )
            page_name = str(snapshot.get("page_name") or row.get("page_name") or "")
            if not text or not native_id or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=native_id,
                url=str(snapshot.get("url") or f"https://www.facebook.com/ads/library/?id={native_id}"),
                title=text[:120], text=text, author=page_name, published_at=published,
                market=country, language="en", query=query, query_language="en",
                engagement={},
                raw_metadata={"route": "scrapecreators_meta_ads", "provider": "scrapecreators"},
            ))
            if len(output) >= _limit(request, self.max_per_query):
                break
        if not output:
            self.limitations.append("ScrapeCreators Meta Ads returned no dated active creative")
        return output


# --------------------------------------------------------------------------
# Public-link extraction with yt-dlp (no provider key)
# --------------------------------------------------------------------------

_PUBLIC_POST_RE = re.compile(
    r"https?://(?:www\.)?(?:tiktok\.com/@[\w.\-]+/video/\d+"
    r"|instagram\.com/(?:reel|reels|p)/[\w\-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PublicLinkYtDlpAdapter:
    """Resolve explicitly supplied public TikTok/Instagram links with yt-dlp.

    Keyword discovery is deliberately not attempted here: without an
    authorized provider or a host web search there is no legal discovery
    route. Given a public post URL, yt-dlp returns metadata, the caption and
    (when the platform exposes it) a transcript, with no cookie read.
    """

    platform: str
    executable: str | None = None
    http_client: HttpClient | None = None
    max_urls: int = 3
    timeout_seconds: float = 60.0
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.executable is None:
            object.__setattr__(self, "executable", shutil.which("yt-dlp"))
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.platform

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        raw_urls: list[str] = []
        explicit = request.get("urls") or request.get("url")
        if isinstance(explicit, str):
            raw_urls.extend(_PUBLIC_POST_RE.findall(explicit))
        elif isinstance(explicit, (list, tuple)):
            for value in explicit:
                raw_urls.extend(_PUBLIC_POST_RE.findall(str(value)))
        raw_urls.extend(_PUBLIC_POST_RE.findall(str(request.get("query") or "")))
        urls = list(dict.fromkeys(raw_urls))[: self.max_urls]
        if not urls:
            self.limitations.append(
                f"{self.platform}: no public post URL supplied; keyword discovery needs an authorized provider"
            )
            return []
        expected = "tiktok.com" if self.platform == "tiktok" else "instagram.com"
        urls = [url for url in urls if expected in url]
        if not urls:
            return []
        if not self.executable:
            raise AdapterUnavailable(self.platform, "yt-dlp is not installed")
        output: list[RawSourceResult] = []
        for url in urls:
            try:
                from ._command import run_command

                completed = run_command(
                    [
                        self.executable, "--ignore-config", "--no-cookies-from-browser",
                        "--dump-json", "--no-warnings", "--no-download", url,
                    ],
                    timeout=self.timeout_seconds,
                    env=_tool_env(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.limitations.append(f"{self.platform}: yt-dlp failed for one link ({type(exc).__name__})")
                continue
            if completed.returncode != 0:
                self.limitations.append(f"{self.platform}: yt-dlp exited {completed.returncode} for one link")
                continue
            payload: object = None
            for line in completed.stdout.splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                break
            if not isinstance(payload, Mapping):
                continue
            native_id = str(payload.get("id") or "")
            text = str(payload.get("description") or payload.get("title") or "").strip()
            published = _iso(payload.get("timestamp") or payload.get("upload_date"))
            if not native_id or not text or not published:
                self.limitations.append(f"{self.platform}: one link had no absolute date")
                continue
            output.append(RawSourceResult(
                source=self.platform, source_type="post", source_native_id=native_id,
                url=str(payload.get("webpage_url") or url),
                title=str(payload.get("title") or text)[:120], text=text,
                author=str(payload.get("uploader") or payload.get("channel") or ""),
                published_at=published, market="global", language="en",
                query=str(request.get("query") or ""), query_language="en",
                engagement={
                    "views": _count(payload.get("view_count")),
                    "likes": _count(payload.get("like_count")),
                    "comments": _count(payload.get("comment_count")),
                },
                raw_metadata={"route": "public_link_ytdlp"},
            ))
        return output


def _tool_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """A small child environment: runtime, locale and proxy settings only."""
    allow = {
        "PATH", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
        "TMPDIR", "TEMP", "TMP", "SSL_CERT_FILE", "SSL_CERT_DIR", "NO_COLOR",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    }
    env = {key: value for key, value in os.environ.items() if key in allow}
    for key, value in (extra or {}).items():
        if value:
            env[key] = value
    return env


# --------------------------------------------------------------------------
# Trustpilot local CLI (no browser, no WAF harvest)
# --------------------------------------------------------------------------

_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9.-]*\.(?:com|io|co|net|org|ai|app|dev|tech|shop|store)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TrustpilotCliAdapter:
    """Trustpilot through ``trustpilot-pp-cli`` when its session is replayable.

    Only local reads are allowed by default. If the CLI has no fresh WAF
    session, the adapter reports how to create one (``trustpilot-pp-cli auth
    login``) instead of launching a browser inside a research run.
    """

    cli: str = "trustpilot-pp-cli"
    runner: object | None = None
    source_name: str = "trustpilot"
    limitations: list[str] = field(default_factory=list, compare=False)

    @property
    def name(self) -> str:
        return self.source_name

    def _run(self, args: list[str], timeout: float) -> dict[str, object]:
        if self.runner is not None:
            return self.runner(args)  # type: ignore[operator]
        binary = shutil.which(self.cli)
        if not binary:
            raise AdapterUnavailable(self.source_name, f"{self.cli} is not installed")
        try:
            completed = run_command([binary, *args], timeout=timeout, env=_tool_env())
        except subprocess.TimeoutExpired as exc:
            raise AdapterTimeout(self.source_name, f"{self.cli} timed out") from exc
        if completed.returncode != 0:
            raise AdapterUnavailable(self.source_name, f"{self.cli} exited {completed.returncode}")
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise AdapterInvalidResponse(self.source_name, f"{self.cli} output was not JSON") from exc
        return payload if isinstance(payload, Mapping) else {}

    def _session_fresh(self, status: Mapping[str, object], now: str) -> bool:
        harvested = ""
        for container in (status, status.get("session")):
            if isinstance(container, Mapping) and container.get("harvestedAt"):
                harvested = str(container["harvestedAt"])
                break
        if not harvested:
            return False
        try:
            harvested_dt = datetime.fromisoformat(harvested.replace("Z", "+00:00"))
            now_dt = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
            age = (now_dt - harvested_dt).total_seconds()
        except ValueError:
            return False
        return 0 <= age <= 180

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        explicit = str(request.get("domain") or "").strip()
        match = _DOMAIN_RE.search(explicit or query)
        if not match:
            self.limitations.append("Trustpilot local route needs a company domain (for example acme.com)")
            return []
        domain = match.group(0).lower()
        status = self._run(["auth", "status", "--agent"], timeout=10)
        if not self._session_fresh(status, str(request.get("retrieved_at") or "")):
            self.limitations.append(
                "Trustpilot session is missing or stale; run `trustpilot-pp-cli auth login`, "
                "then rerun within three minutes"
            )
            return []
        payload = self._run(["info", "--agent", "--", domain], timeout=75)
        records = payload.get("reviews") if isinstance(payload.get("reviews"), list) else []
        output: list[RawSourceResult] = []
        for review in records:
            if not isinstance(review, Mapping):
                continue
            text = _strip_html(review.get("text") or review.get("content") or review.get("title"))
            published = _iso(review.get("publishedAt") or review.get("date") or review.get("createdAt"))
            native_id = str(review.get("id") or review.get("reviewId") or "")
            if not text or not published or not native_id:
                continue
            rating = review.get("rating")
            output.append(RawSourceResult(
                source=self.source_name, source_type="review", source_native_id=native_id,
                url=str(review.get("url") or f"https://www.trustpilot.com/review/{domain}"),
                title=text[:120], text=text,
                author=str(review.get("author") or review.get("authorName") or ""),
                published_at=published, market="global", language="en",
                query=query, query_language="en",
                engagement={"rating": _count(rating)} if rating is not None else {},
                raw_metadata={"route": "trustpilot_cli", "domain": domain},
            ))
            if len(output) >= _limit(request, 10):
                break
        if not output:
            self.limitations.append("Trustpilot cached record carried no dated review")
        return output


# --------------------------------------------------------------------------
# Amazon through the Bright Data CLI (paid dataset, opt-in)
# --------------------------------------------------------------------------

_AMAZON_SEARCH_DATASET = "gd_lwdb4vjm1ehb499uxs"


@dataclass(frozen=True)
class AmazonBrightDataAdapter:
    """Amazon product search through the Bright Data CLI.

    Activation is two-way: the ``brightdata`` binary must be installed and
    either ``BRIGHTDATA_API_KEY`` or the CLI's own login must exist. The
    adapter never buys credits or logs in; it reports what is missing.
    """

    cli: str = "brightdata"
    api_key: str | None = None
    runner: object | None = None
    source_name: str = "amazon"
    limitations: list[str] = field(default_factory=list, compare=False)

    @property
    def name(self) -> str:
        return self.source_name

    def _run(self, args: list[str], timeout: float) -> dict[str, object]:
        if self.runner is not None:
            return self.runner(args)  # type: ignore[operator]
        raise AdapterUnavailable(
            self.source_name, "Bright Data CLI has no enforceable per-request budget",
        )

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        if not self.api_key and not shutil.which(self.cli):
            raise AdapterUnavailable(self.source_name, "brightdata CLI and BRIGHTDATA_API_KEY are absent")
        query = _query(request, self.source_name)
        payload = self._run(
            [
                "pipelines", "run", _AMAZON_SEARCH_DATASET, "collect_by_url",
                "--input", json.dumps([{"keyword": query, "url": "https://www.amazon.com",
                                        "pages_to_search": 1}]),
                "--json", "--timeout", "60",
            ],
            timeout=75,
        )
        records = payload.get("records") or payload.get("results") or payload.get("data") or []
        output: list[RawSourceResult] = []
        for row in records if isinstance(records, list) else []:
            if not isinstance(row, Mapping):
                continue
            title = _strip_html(row.get("title") or row.get("name"))
            asin = str(row.get("asin") or row.get("id") or "")
            url = str(row.get("url") or (f"https://www.amazon.com/dp/{asin}" if asin else ""))
            published = _iso(
                row.get("date_first_available") or row.get("first_available")
                or row.get("published_at")
            )
            if not title or not asin or not url or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=asin,
                url=url, title=title[:120], text=title,
                author=str(row.get("brand") or row.get("seller") or ""),
                published_at=published, market="us", language="en",
                query=query, query_language="en",
                engagement={
                    "rating": _count(row.get("rating") or row.get("stars")),
                    "comments": _count(row.get("reviews_count") or row.get("review_count")),
                },
                raw_metadata={"route": "brightdata_amazon_search"},
            ))
            if len(output) >= _limit(request, 10):
                break
        if not output:
            self.limitations.append("Amazon returned no product with a publication date; listings are usually undated")
        return output


# --------------------------------------------------------------------------
# US patents through the public USPTO search session (no credential)
# --------------------------------------------------------------------------

_USPTO_BASE = "https://ppubs.uspto.gov"
_USPTO_PDF = "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/"
_USPTO_USER_AGENT = "VantageResearch/1.1"


def _patent_phrase(query: str) -> str:
    words = [word for word in re.split(r"\s+", query) if word]
    drop = {"patent", "patents", "filing", "filings", "recent", "latest", "new",
            "company", "startup", "and", "or", "the", "for", "of", "in", "on",
            "about", "market", "research", "analysis", "trend", "trends", "news",
            "landscape", "overview", "competitor", "competitors", "competition",
            "report", "reports", "2025", "2026", "2027"}
    kept = [word for word in words if word.casefold().strip(",.") not in drop]
    phrase = " ".join(kept[:6]) or query
    return phrase.replace('"', "").replace("\\", "")


def _patent_words(phrase: str) -> list[str]:
    words = [word.strip(",.") for word in phrase.split()]
    return [word for word in words if len(word) >= 3][:4]


@dataclass(frozen=True)
class UsptoPatentAdapter:
    """US patent applications/grants through the public USPTO search UI API.

    The legacy PatentsView endpoint is retired. This uses the same anonymous
    session the public Patent Public Search page opens, sends no credential and
    reads one page per database. A refusal is reported, never circumvented.
    """

    http_client: HttpClient | None = None
    source_name: str = "patents"
    max_per_query: int = 10
    timeout_seconds: float = 20.0
    limitations: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def _post(self, url: str, body: object, token: str | None = None) -> tuple[object, Mapping[str, str]]:
        headers = {
            "User-Agent": _USPTO_USER_AGENT,
            "Content-Type": "application/json",
            "Referer": f"{_USPTO_BASE}/pubwebapp/",
            "Origin": _USPTO_BASE,
            "X-Access-Token": token or "null",
        }
        try:
            response = self.http_client.request(
                url, method="POST", json_data=body, headers=headers,
                timeout=self.timeout_seconds, max_bytes=2_000_000,
            )
        except HttpTransientError as exc:
            if exc.status in (401, 403):
                raise AdapterAuthMissing(self.source_name, "USPTO refused an anonymous session") from exc
            if exc.status == 429:
                raise AdapterRateLimited(self.source_name, "USPTO rate limit") from exc
            raise AdapterUnavailable(self.source_name, f"USPTO transient {exc.status}") from exc
        except HttpPermanentError as exc:
            if exc.status in (401, 403):
                raise AdapterAuthMissing(self.source_name, "USPTO refused an anonymous session") from exc
            if exc.status == 429:
                raise AdapterRateLimited(self.source_name, "USPTO rate limit") from exc
            raise AdapterUnavailable(self.source_name, f"USPTO HTTP {exc.status}") from exc
        except HttpTimeoutError as exc:
            raise AdapterTimeout(self.source_name, str(exc)) from exc
        try:
            payload = response.json()
        except Exception as exc:
            raise AdapterInvalidResponse(self.source_name, "USPTO body was not JSON") from exc
        return payload, {k.lower(): v for k, v in response.headers.items()}

    def _session(self) -> tuple[str, object]:
        body, headers = self._post(f"{_USPTO_BASE}/api/users/me/session", -1)
        token = headers.get("x-access-token", "")
        case = body.get("userCase") if isinstance(body, Mapping) else None
        case_id = case.get("caseId") if isinstance(case, Mapping) else None
        if not token or case_id is None:
            raise AdapterAuthMissing(self.source_name, "USPTO gave no anonymous session")
        return str(token), case_id

    def _search(self, token: str, case_id: object, query: str) -> list[Mapping[str, object]]:
        payload, _ = self._post(
            f"{_USPTO_BASE}/api/searches/searchWithBeFamily",
            {
                "start": 0, "pageCount": 50, "sort": "date_publ desc",
                "docFamilyFiltering": "noFiltering", "searchType": 1,
                "familyIdEnglishOnly": True, "familyIdFirstPreferred": "US-PGPUB",
                "familyIdSecondPreferred": "USPAT", "familyIdThirdPreferred": "FPRS",
                "showDocPerFamilyPref": "showEnglish", "queryId": 0, "tagDocSearch": False,
                "query": {
                    "caseId": case_id, "hl_snippets": "2", "op": "OR", "q": query,
                    "queryName": query, "highlights": "0", "qt": "brs",
                    "spellCheck": False, "viewName": "tile", "plurals": True,
                    "britishEquivalents": True,
                    "databaseFilters": [{"databaseName": "US-PGPUB", "countryCodes": []}],
                    "searchType": 1, "ignorePersist": True, "userEnteredQuery": query,
                },
            },
            token,
        )
        rows = payload.get("patents") if isinstance(payload, Mapping) else None
        return [row for row in rows or [] if isinstance(row, Mapping)]

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        phrase = _patent_phrase(query)
        if not phrase:
            return []
        from ._recency import search_bounds

        bounds = search_bounds(plan, request)
        date_clause = ""
        if bounds:
            start, end = bounds
            date_clause = f' AND @pd>="{start:%Y%m%d}"<="{end:%Y%m%d}"'
        words = _patent_words(phrase)
        candidates = [
            f'(("{phrase}").ti. or ("{phrase}").ab.){date_clause}',
        ]
        if len(words) >= 2:
            terms = " AND ".join(f'({word}).ab.' for word in words)
            candidates.append(f"{terms}{date_clause}")
            top_two = " AND ".join(f'({word}).ab.' for word in words[:2])
            candidates.append(f"{top_two}{date_clause}")
        candidates.append(f'("{phrase}").aanm.{date_clause}')
        token, case_id = self._session()
        rows: list[Mapping[str, object]] = []
        for uspto_query in candidates:
            rows = self._search(token, case_id, uspto_query)
            if rows:
                break
        output: list[RawSourceResult] = []
        for row in rows:
            number = str(row.get("publicationReferenceDocumentNumber") or "")
            guid = str(row.get("guid") or "")
            title = _strip_html(_first_text(row.get("inventionTitle")))
            published = _iso(_first_text(row.get("datePublished")))
            applicant = _first_text(row.get("applicantName") or row.get("assigneeName"))
            native_id = guid or number
            if not native_id or not title or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="page", source_native_id=native_id,
                url=f"{_USPTO_PDF}{number}" if number else f"{_USPTO_BASE}/pubwebapp/",
                title=title[:120], text=title, author=applicant,
                published_at=published, market="us", language="en",
                query=query, query_language="en", engagement={},
                raw_metadata={"route": "uspto_public_search", "document_number": number},
            ))
            if len(output) >= _limit(request, self.max_per_query):
                break
        if not output:
            self.limitations.append("USPTO returned no dated application naming this phrase")
        return output


__all__ = [
    "AmazonBrightDataAdapter",
    "DiggCliAdapter",
    "MetaAdLibraryAdapter",
    "PolymarketAdapter",
    "PublicLinkYtDlpAdapter",
    "ScrapeCreatorsMetaAdsAdapter",
    "ScrapeCreatorsPlatformAdapter",
    "ScrapeCreatorsRedditAdapter",
    "ScrapeCreatorsTelegramAdapter",
    "ScrapeCreatorsYouTubeAdapter",
    "StockTwitsAdapter",
    "TrustpilotCliAdapter",
    "TruthSocialAdapter",
    "UsptoPatentAdapter",
    "XiaohongshuMcpAdapter",
]
