"""Scholarly metadata connectors: Crossref and OpenAlex.

Both services expose public, key-free JSON for works.  These adapters keep the
upstream publication date separate from deposit/index update timestamps and
never rebuild an abstract unless the upstream provides one in reconstructable
form.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date as date_type
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import (
    _as_of,
    _date_start,
    _integer,
    _json,
    _limit,
    _query,
    _rfc3339,
)

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(?:p|div|br|li|jats:p|jats:sec|jats:title)\b[^>]*>", re.IGNORECASE)


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _BLOCK.sub(" ", text)
    text = _TAG.sub("", text)
    return " ".join(text.split())


def _full_date_parts(parts: object) -> str:
    if not isinstance(parts, list) or not parts:
        return ""
    values = parts[0]
    if not isinstance(values, list) or len(values) < 3:
        return ""
    try:
        return date_type(int(values[0]), int(values[1]), int(values[2])).isoformat()
    except (TypeError, ValueError):
        return ""


def _date_filter(start: object, end: object) -> str:
    parts = []
    if start is not None:
        parts.append(f"from-pub-date:{start.strftime('%Y-%m-%d')}")
    if end is not None:
        parts.append(f"until-pub-date:{end.strftime('%Y-%m-%d')}")
    return ",".join(parts)


@dataclass(frozen=True)
class CrossrefAdapter:
    """Crossref Works REST search.

    Only records with a complete issued year-month-day are accepted.  A DOI is
    the stable identity and the canonical landing page.
    """

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "crossref"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        start = _date_start(plan, request)
        end = _as_of(request)
        params: dict[str, object] = {
            "query.bibliographic": query,
            "rows": limit,
            "select": "DOI,title,abstract,issued,deposited,indexed,author,publisher,container-title,type,license,URL",
        }
        date_filter = _date_filter(start, end)
        if date_filter:
            params["filter"] = date_filter
        payload = _json(self.http_client, self.source_name, f"https://api.crossref.org/works?{urlencode(params)}")
        message = payload.get("message") if isinstance(payload, Mapping) else None
        items = message.get("items") if isinstance(message, Mapping) else None
        if not isinstance(items, list):
            from ..pipeline.adapters import AdapterInvalidResponse

            raise AdapterInvalidResponse(self.source_name, "payload missing message.items")
        out: list[RawSourceResult] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            doi = str(item.get("DOI") or "").strip()
            issued = _full_date_parts(item.get("issued", {}).get("date-parts") if isinstance(item.get("issued"), Mapping) else None)
            if not doi or not issued:
                continue
            titles = item.get("title") if isinstance(item.get("title"), list) else []
            title = _plain(titles[0]) if titles else ""
            if not title:
                continue
            abstract = _plain(item.get("abstract"))
            authors = item.get("author") if isinstance(item.get("author"), list) else []
            names = []
            for author in authors[:4]:
                if not isinstance(author, Mapping):
                    continue
                given = str(author.get("given") or "").strip()
                family = str(author.get("family") or "").strip()
                name = " ".join(x for x in (given, family) if x).strip()
                if name:
                    names.append(name)
            containers = item.get("container-title") if isinstance(item.get("container-title"), list) else []
            licenses = item.get("license") if isinstance(item.get("license"), list) else []
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"doi:{doi}",
                url=str(item.get("URL") or f"https://doi.org/{doi}"),
                title=title,
                text=abstract or title,
                author=", ".join(names),
                published_at=_rfc3339(issued),
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                raw_metadata={
                    "doi": doi,
                    "type": str(item.get("type") or ""),
                    "publisher": str(item.get("publisher") or ""),
                    "container_title": _plain(containers[0]) if containers else "",
                    "deposited": _rfc3339(item.get("deposited", {}).get("date-time") if isinstance(item.get("deposited"), Mapping) else ""),
                    "indexed": _rfc3339(item.get("indexed", {}).get("date-time") if isinstance(item.get("indexed"), Mapping) else ""),
                    "license_urls": [str(x.get("URL")) for x in licenses if isinstance(x, Mapping) and x.get("URL")],
                    "date_semantics": "issued",
                },
            ))
            if len(out) == limit:
                break
        return out


def _reconstruct_abstract(index: object) -> str:
    """Rebuild OpenAlex's inverted index without adding or reordering words."""
    if not isinstance(index, Mapping):
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            if isinstance(offset, int):
                positions.append((offset, str(word)))
    positions.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positions)


@dataclass(frozen=True)
class OpenAlexAdapter:
    """OpenAlex Works search.

    Anonymous callers get the first page.  Cursor pagination is enabled only
    when the caller explicitly supplies a key; no key is read from the
    environment by this adapter.
    """

    http_client: HttpClient | None = None
    api_key: str | None = None
    max_per_query: int = 20
    source_name: str = "openalex"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        start = _date_start(plan, request)
        end = _as_of(request)
        filters = []
        if start is not None:
            filters.append(f"from_publication_date:{start.strftime('%Y-%m-%d')}")
        if end is not None:
            filters.append(f"to_publication_date:{end.strftime('%Y-%m-%d')}")
        out: list[RawSourceResult] = []
        cursor = "*"
        pages = 2 if self.api_key else 1
        for _page in range(pages):
            params: dict[str, object] = {
                "search": query,
                "per-page": min(limit, 50),
                "sort": "publication_date:desc",
            }
            if filters:
                params["filter"] = ",".join(filters)
            if self.api_key:
                params["api_key"] = self.api_key
                params["cursor"] = cursor
            payload = _json(self.http_client, self.source_name, f"https://api.openalex.org/works?{urlencode(params)}")
            items = payload.get("results") if isinstance(payload, Mapping) else None
            if not isinstance(items, list):
                from ..pipeline.adapters import AdapterInvalidResponse

                raise AdapterInvalidResponse(self.source_name, "payload missing results")
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                published = str(item.get("publication_date") or "").strip()
                if len(published) != 10:
                    continue
                title = _plain(item.get("title") or item.get("display_name"))
                if not title:
                    continue
                openalex_id = str(item.get("id") or "").strip()
                doi_url = str(item.get("doi") or "").strip()
                location = item.get("primary_location") if isinstance(item.get("primary_location"), Mapping) else {}
                landing = str(location.get("landing_page_url") or "").strip()
                oa = item.get("open_access") if isinstance(item.get("open_access"), Mapping) else {}
                url = doi_url or landing or str(oa.get("oa_url") or "").strip() or openalex_id
                if not url:
                    continue
                abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
                authorships = item.get("authorships") if isinstance(item.get("authorships"), list) else []
                names = []
                for authorship in authorships[:4]:
                    author = authorship.get("author") if isinstance(authorship, Mapping) else None
                    if isinstance(author, Mapping) and author.get("display_name"):
                        names.append(str(author["display_name"]))
                out.append(RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"openalex:{openalex_id.rsplit('/', 1)[-1]}" if openalex_id else f"openalex:{published}:{title[:40]}",
                    url=url,
                    title=title,
                    text=abstract or title,
                    author=", ".join(names),
                    published_at=_rfc3339(published),
                    market=str(request.get("market") or "global"),
                    language=str(request.get("query_language") or "en"),
                    query=query,
                    query_language=str(request.get("query_language") or "en"),
                    raw_metadata={
                        "openalex_id": openalex_id,
                        "doi": doi_url,
                        "updated_date": str(item.get("updated_date") or ""),
                        "type": str(item.get("type") or ""),
                        "cited_by_count": _integer(item.get("cited_by_count")),
                        "is_oa": bool(oa.get("is_oa")),
                        "date_semantics": "publication_date",
                    },
                ))
                if len(out) == limit:
                    return out
            meta = payload.get("meta") if isinstance(payload, Mapping) else {}
            cursor = str(meta.get("next_cursor") or "") if isinstance(meta, Mapping) else ""
            if not self.api_key or not cursor:
                break
        return out
