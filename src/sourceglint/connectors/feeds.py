"""RSS/Atom feed connectors for publisher and community feeds.

A feed is an official, publicly subscribable publication channel: the item link
is the original article URL and the feed's own date field is the publication
anchor.  Feeds that cannot be queried server-side are filtered locally by the
researcher's topic terms; an empty match is reported as zero results rather
than as unrelated "latest" content.

Engagement counters are never synthesized for feeds — the payload has none.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import urlencode
from xml.etree import ElementTree

from ..pipeline.adapters import AdapterInvalidResponse, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import _get, _limit, _query

_ATOM = "{http://www.w3.org/2005/Atom}"
_DC = "{http://purl.org/dc/elements/1.1/}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
_TAG = re.compile(r"<[^>]+>")
_TERM = re.compile(r"[0-9A-Za-z\u00c0-\u024f\u0400-\u04ff\u3040-\u30ff\u4e00-\u9fff]+")


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG.sub(" ", text)
    text = " ".join(text.split())
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def _first_text(node: ElementTree.Element, *tags: str) -> str:
    for tag in tags:
        child = node.find(tag)
        if child is not None and (child.text or "").strip():
            return str(child.text).strip()
    return ""


def _atom_link(node: ElementTree.Element) -> str:
    fallback = ""
    for child in node.findall(f"{_ATOM}link"):
        href = str(child.get("href") or "").strip()
        if not href:
            continue
        if str(child.get("rel") or "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _atom_author(node: ElementTree.Element) -> str:
    author = node.find(f"{_ATOM}author")
    if author is None:
        return ""
    return _plain(_first_text(author, f"{_ATOM}name"))


def _rss_date(value: str) -> str:
    from email.utils import parsedate_to_datetime

    raw = " ".join(str(value or "").split())
    if not raw:
        return ""
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_feed(body: bytes, source: str) -> list[dict[str, str]]:
    """Parse an RSS 2.0/RSS 1.0/Atom body into neutral item dicts."""
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise AdapterInvalidResponse(source, "feed body was not XML") from exc
    items = root.findall(".//item")
    is_atom = False
    if not items:
        items = root.findall(f".//{_ATOM}entry")
        is_atom = bool(items)
    out: list[dict[str, str]] = []
    for node in items[:200]:
        if is_atom:
            title = _plain(_first_text(node, f"{_ATOM}title"))
            link = _atom_link(node)
            published = _rss_date(_first_text(node, f"{_ATOM}published"))
            updated = _rss_date(_first_text(node, f"{_ATOM}updated"))
            summary = _plain(_first_text(node, f"{_ATOM}summary", f"{_ATOM}content"))
            author = _atom_author(node)
            guid = _first_text(node, f"{_ATOM}id")
            tags = [str(c.get("term") or "") for c in node.findall(f"{_ATOM}category")]
        else:
            title = _plain(_first_text(node, "title"))
            link = _first_text(node, "link")
            published = _rss_date(_first_text(node, "pubDate", f"{_DC}date"))
            updated = ""
            summary = _plain(_first_text(node, "description", f"{_CONTENT}encoded"))
            author = _plain(_first_text(node, f"{_DC}creator", "author"))
            guid = _first_text(node, "guid")
            tags = [str(c.text or "") for c in node.findall("category")]
        out.append({
            "title": title,
            "link": link,
            "summary": summary,
            "published": published,
            "updated": updated,
            "author": author,
            "guid": guid,
            "tags": " ".join(tag for tag in tags if tag),
        })
    return out


def _terms(query: str) -> list[str]:
    return [term.casefold() for term in _TERM.findall(query) if len(term) >= 2]


def _matches(item: Mapping[str, str], terms: list[str]) -> bool:
    if not terms:
        return False
    haystack = " ".join(
        (item.get("title") or "", item.get("summary") or "", item.get("tags") or "")
    ).casefold()
    hits = sum(1 for term in terms if term in haystack)
    return hits >= min(2, len(terms))


@dataclass(frozen=True)
class FeedAdapter:
    """A configured RSS/Atom publication feed.

    ``query_param`` must be set only when the publisher documents a server-side
    search parameter.  Otherwise the feed's recent window is filtered locally.
    """

    feed_url: str
    source_name: str
    market: str = "global"
    language: str = "en"
    source_type: str = "post"
    query_param: str | None = None
    local_filter: bool = True
    max_items: int = 20
    http_client: HttpClient | None = None

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def _url(self, query: str, request: Mapping[str, object]) -> str:
        if not self.query_param:
            return self.feed_url
        params: dict[str, object] = {self.query_param: query}
        language = str(request.get("query_language") or "").strip()
        if language and self.language == "en" and language != "en":
            params["hl"] = language
        return f"{self.feed_url}?{urlencode(params)}"

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_items)
        response = _get(self.http_client, self.source_name, self._url(query, request))
        if response.status != 200:
            raise AdapterInvalidResponse(
                self.source_name, f"upstream returned {response.status}"
            )
        items = parse_feed(response.body, self.source_name)
        terms = _terms(query)
        out: list[RawSourceResult] = []
        for item in items:
            title = item["title"]
            url = item["link"]
            published = item["published"]
            if not title or not url or not published:
                continue
            if self.local_filter and not _matches(item, terms):
                continue
            native_id = item["guid"] or url
            out.append(RawSourceResult(
                source=self.source_name,
                source_type=self.source_type,
                source_native_id=f"{self.source_name}:{native_id}",
                url=url,
                title=title,
                text=item["summary"] or title,
                author=item["author"],
                published_at=published,
                market=str(request.get("market") or self.market),
                language=self.language,
                query=query,
                query_language=str(request.get("query_language") or self.language),
                raw_metadata={
                    "feed_url": self.feed_url,
                    "guid": item["guid"],
                    "updated": item["updated"],
                    "tags": item["tags"],
                    "filter": "server_query" if self.query_param else "local_topic_terms",
                    "date_semantics": "feed_item_published",
                },
            ))
            if len(out) == limit:
                break
        return out
