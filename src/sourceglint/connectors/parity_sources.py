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
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import (
    AdapterAuthMissing,
    AdapterInvalidResponse,
    AdapterRateLimited,
    AdapterTimeout,
    AdapterUnavailable,
    RawSourceResult,
)
from ._http import (
    HttpClient,
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
                          published=published, engagement=engagement, source_type="video")

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
                          published=published, engagement=engagement, source_type="pin")

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
            "access_token": self.token,
        })
        payload = _get_json(self.http_client, url, source=self.source_name)
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
                source=self.source_name, source_type="ad", source_native_id=native_id,
                url=str(ad.get("ad_snapshot_url") or f"https://www.facebook.com/ads/library/?id={native_id}"),
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
        url = "https://gamma-api.polymarket.com/public-search?" + urlencode({"q": query, "limit": _limit(request)})
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
                source=self.source_name, source_type="market", source_native_id=native_id,
                url=f"https://polymarket.com/event/{slug}", title=title[:120], text=title,
                author="Polymarket", published_at=start, market="global", language="en",
                query=query, query_language="en",
                engagement={"volume": _count(event.get("volume"))},
                raw_metadata={"route": "polymarket_gamma", "date_semantics": "market_start",
                              "date_precision": precision},
            ))
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
        items = payload.get("stories") if isinstance(payload, Mapping) else payload
        output: list[RawSourceResult] = []
        for story in items or []:
            if not isinstance(story, Mapping):
                continue
            title = str(story.get("title") or "").strip()
            url = str(story.get("url") or "").strip()
            native_id = str(story.get("uuid") or story.get("id") or url)
            published = _iso(story.get("publishedAt") or story.get("published_at"))
            if not title or not url or not published:
                continue
            output.append(RawSourceResult(
                source=self.source_name, source_type="story", source_native_id=native_id,
                url=url, title=title[:120], text=str(story.get("description") or title),
                author=str(story.get("publisher") or ""), published_at=published,
                market="us", language="en", query=query, query_language="en",
                engagement={"digg_score": _count(story.get("diggScore"))},
                raw_metadata={"route": "digg_cli"},
            ))
        return output


__all__ = [
    "DiggCliAdapter",
    "MetaAdLibraryAdapter",
    "PolymarketAdapter",
    "ScrapeCreatorsPlatformAdapter",
    "StockTwitsAdapter",
    "TruthSocialAdapter",
    "XiaohongshuMcpAdapter",
]
