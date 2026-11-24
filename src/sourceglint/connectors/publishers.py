"""Publisher-platform connectors for Japanese/Chinese content sites.

Both sites expose their own public, unauthenticated JSON search endpoints
(the same ones their web clients use) plus an official RSS feed.  The JSON
route is used here because the RSS window is a fixed "latest 10" list that
cannot answer a topic query.  No cookies, tokens or undocumented private
routes are involved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import AdapterInvalidResponse, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import _integer, _json, _limit, _query, _rfc3339


@dataclass(frozen=True)
class ZennSearchAdapter:
    """Zenn article search (public JSON search endpoint)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "zenn"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"q": query, "source": "articles"})
        payload = _json(self.http_client, self.source_name,
                        f"https://zenn.dev/api/search?{params}")
        articles = payload.get("articles") if isinstance(payload, Mapping) else None
        if not isinstance(articles, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing articles")
        out: list[RawSourceResult] = []
        for item in articles:
            if not isinstance(item, Mapping):
                continue
            title = " ".join(str(item.get("title") or "").split())
            path = str(item.get("path") or "").strip()
            published = _rfc3339(item.get("published_at"))
            if not title or not path or not published:
                continue
            user = item.get("user") if isinstance(item.get("user"), Mapping) else {}
            topics = item.get("topics") if isinstance(item.get("topics"), list) else []
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="post",
                source_native_id=f"zenn:{item.get('id')}",
                url=f"https://zenn.dev{path}",
                title=title,
                text=title,
                author=str(user.get("name") or user.get("username") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="ja",
                query=query,
                query_language=str(request.get("query_language") or "ja"),
                engagement={
                    "points": _integer(item.get("liked_count")),
                    "comments": _integer(item.get("comments_count")),
                    "bookmarks": _integer(item.get("bookmarked_count")),
                },
                raw_metadata={
                    "article_type": str(item.get("article_type") or ""),
                    "topics": [str(t.get("name")) for t in topics if isinstance(t, Mapping)],
                    "updated": _rfc3339(item.get("body_updated_at")),
                    "feed_url": "https://zenn.dev/feed",
                    "date_semantics": "article_published",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class NoteSearchAdapter:
    """note.com article search (public JSON search endpoint)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "note"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"q": query, "size": min(limit, 20)})
        payload = _json(self.http_client, self.source_name,
                        f"https://note.com/api/v3/searches?{params}")
        data = payload.get("data") if isinstance(payload, Mapping) else None
        notes = data.get("notes") if isinstance(data, Mapping) else None
        contents = notes.get("contents") if isinstance(notes, Mapping) else None
        if not isinstance(contents, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing notes.contents")
        out: list[RawSourceResult] = []
        for item in contents:
            if not isinstance(item, Mapping):
                continue
            user = item.get("user") if isinstance(item.get("user"), Mapping) else {}
            urlname = str(user.get("urlname") or "").strip()
            key = str(item.get("key") or "").strip()
            title = " ".join(str(item.get("name") or "").split())
            published = _rfc3339(item.get("publish_at"))
            if not title or not urlname or not key or not published:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="post",
                source_native_id=f"note:{item.get('id')}",
                url=f"https://note.com/{urlname}/n/{key}",
                title=title,
                text=" ".join(str(item.get("description") or "").split()) or title,
                author=str(user.get("nickname") or user.get("name") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="ja",
                query=query,
                query_language=str(request.get("query_language") or "ja"),
                engagement={
                    "points": _integer(item.get("like_count")),
                    "comments": _integer(item.get("comment_count")),
                },
                raw_metadata={
                    "note_type": str(item.get("type") or ""),
                    "price": _integer(item.get("price")),
                    "feed_url": "https://note.com/rss",
                    "date_semantics": "note_published",
                },
            ))
            if len(out) == limit:
                break
        return out
