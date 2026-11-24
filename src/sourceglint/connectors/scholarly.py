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


# ---------------------------------------------------------------------------
# Public research registries and datasets (key-free JSON endpoints)
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _month_number(value: object) -> int:
    raw = str(value or "").strip().casefold()
    if raw.isdigit():
        number = int(raw)
        return number if 1 <= number <= 12 else 0
    return _MONTHS.get(raw[:3], 0)


def _year_month_day(year: object, month: object = None, day: object = None) -> tuple[str, str]:
    """Return (ISO timestamp, precision) without inventing finer precision."""
    try:
        year_number = int(str(year).strip()[:4])
    except (TypeError, ValueError):
        return "", ""
    month_number = _month_number(month)
    try:
        day_number = int(day) if day not in (None, "") else 0
    except (TypeError, ValueError):
        day_number = 0
    if 1 <= month_number <= 12 and 1 <= day_number <= 31:
        try:
            return date_type(year_number, month_number, day_number).isoformat() + "T00:00:00Z", "day"
        except ValueError:
            pass
    if 1 <= month_number <= 12:
        return date_type(year_number, month_number, 1).isoformat() + "T00:00:00Z", "month"
    if 1800 <= year_number <= 2200:
        return date_type(year_number, 1, 1).isoformat() + "T00:00:00Z", "year"
    return "", ""


def _trim(value: object, limit: int = 1200) -> str:
    return _plain(value)[:limit].rstrip()


@dataclass(frozen=True)
class PubMedAdapter:
    """PubMed E-utilities search + summary (no key, 3 req/s policy)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "pubmed"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params: dict[str, object] = {
            "db": "pubmed", "term": query, "retmode": "json",
            "retmax": min(limit, 50), "sort": "date",
        }
        start = _date_start(plan, request)
        if start is not None:
            params.update({
                "datetype": "pdat",
                "mindate": start.strftime("%Y-%m-%d"),
                "maxdate": date_type.today().strftime("%Y-%m-%d"),
            })
        search = _json(self.http_client, self.source_name,
                       f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urlencode(params)}")
        result = search.get("esearchresult") if isinstance(search, Mapping) else None
        ids = result.get("idlist") if isinstance(result, Mapping) else None
        if not isinstance(ids, list):
            raise AdapterInvalidResponse(self.source_name, "search payload missing idlist")
        ids = [str(value) for value in ids if str(value).strip()]
        if not ids:
            return []
        summary = _json(
            self.http_client, self.source_name,
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
            f"{urlencode({'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json'})}",
        )
        records = summary.get("result") if isinstance(summary, Mapping) else None
        if not isinstance(records, Mapping):
            raise AdapterInvalidResponse(self.source_name, "summary payload missing result")
        out: list[RawSourceResult] = []
        for pmid in ids:
            item = records.get(pmid)
            if not isinstance(item, Mapping):
                continue
            title = _plain(item.get("title"))
            if not title:
                continue
            published, precision = _year_month_day(
                *str(item.get("pubdate") or "").split()[:3]
            ) if str(item.get("pubdate") or "").strip() else ("", "")
            if not published:
                published, precision = _year_month_day(*str(item.get("sortpubdate") or "").split("/")[:3])
            authors = item.get("authors") if isinstance(item.get("authors"), list) else []
            names = [str(a.get("name")) for a in authors[:4] if isinstance(a, Mapping) and a.get("name")]
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"pmid:{pmid}",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                title=title,
                text=title,
                author=", ".join(names),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "pmid": pmid,
                    "journal": str(item.get("source") or ""),
                    "volume": str(item.get("volume") or ""),
                    "issue": str(item.get("issue") or ""),
                    "epubdate": str(item.get("epubdate") or ""),
                    "date_precision": precision,
                    "date_semantics": "journal_publication_date",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class DoajAdapter:
    """DOAJ open-access article search."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "doaj"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse
        from urllib.parse import quote

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        url = (
            f"https://doaj.org/api/search/articles/{quote(query)}"
            f"?{urlencode({'pageSize': min(limit, 50), 'sort': 'created_date:desc'})}"
        )
        payload = _json(self.http_client, self.source_name, url)
        results = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(results, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing results")
        out: list[RawSourceResult] = []
        for item in results:
            bib = item.get("bibjson") if isinstance(item, Mapping) else None
            if not isinstance(bib, Mapping):
                continue
            title = _plain(bib.get("title"))
            links = bib.get("link") if isinstance(bib.get("link"), list) else []
            target = next(
                (str(link.get("url")) for link in links
                 if isinstance(link, Mapping) and link.get("url")),
                "",
            )
            identifier = str(item.get("id") or "").strip()
            url_value = target or (f"https://doaj.org/article/{identifier}" if identifier else "")
            published, precision = _year_month_day(bib.get("year"), bib.get("month"))
            if not title or not url_value or not published:
                continue
            journal = bib.get("journal") if isinstance(bib.get("journal"), Mapping) else {}
            authors = bib.get("author") if isinstance(bib.get("author"), list) else []
            names = [str(a.get("name")) for a in authors[:4] if isinstance(a, Mapping) and a.get("name")]
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"doaj:{identifier or url_value}",
                url=url_value,
                title=title,
                text=_trim(bib.get("abstract")) or title,
                author=", ".join(names),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "journal": str(journal.get("title") or ""),
                    "issn": list(journal.get("issns") or []),
                    "year": str(bib.get("year") or ""),
                    "month": str(bib.get("month") or ""),
                    "index_created": _rfc3339(item.get("created_date")),
                    "index_updated": _rfc3339(item.get("last_updated")),
                    "date_precision": precision,
                    "date_semantics": "journal_publication_month",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class ZenodoAdapter:
    """Zenodo record search (public, key-free)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "zenodo"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        payload = _json(
            self.http_client, self.source_name,
            f"https://zenodo.org/api/records?{urlencode({'q': query, 'size': min(limit, 25), 'sort': 'newest'})}",
        )
        hits = payload.get("hits") if isinstance(payload, Mapping) else None
        items = hits.get("hits") if isinstance(hits, Mapping) else None
        if not isinstance(items, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing hits.hits")
        out: list[RawSourceResult] = []
        for item in items:
            meta = item.get("metadata") if isinstance(item, Mapping) else None
            if not isinstance(meta, Mapping):
                continue
            title = _plain(meta.get("title"))
            doi = str(item.get("doi") or "").strip()
            links = item.get("links") if isinstance(item.get("links"), Mapping) else {}
            url = (
                str(item.get("doi_url") or "").strip()
                or str(links.get("self_html") or "").strip()
                or (f"https://doi.org/{doi}" if doi else "")
            )
            published = _rfc3339(meta.get("publication_date"))
            semantics = "record_publication_date"
            if not published:
                published = _rfc3339(item.get("created"))
                semantics = "record_created"
            if not title or not url or not published:
                continue
            creators = meta.get("creators") if isinstance(meta.get("creators"), list) else []
            names = [str(c.get("name")) for c in creators[:4] if isinstance(c, Mapping) and c.get("name")]
            resource = meta.get("resource_type") if isinstance(meta.get("resource_type"), Mapping) else {}
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"zenodo:{item.get('id') or doi}",
                url=url,
                title=title,
                text=_trim(meta.get("description")) or title,
                author=", ".join(names),
                published_at=published,
                market=str(request.get("market") or "global"),
                language=str(meta.get("language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                raw_metadata={
                    "doi": doi,
                    "record_id": str(item.get("id") or ""),
                    "resource_type": str(resource.get("title") or resource.get("type") or ""),
                    "updated": _rfc3339(item.get("updated") or item.get("modified")),
                    "date_semantics": semantics,
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class DataCiteAdapter:
    """DataCite DOI metadata search across repositories."""

    http_client: HttpClient | None = None
    max_per_query: int = 10
    source_name: str = "datacite"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"query": query, "page[size]": min(limit, 10), "sort": "-created"})
        payload = _json(self.http_client, self.source_name, f"https://api.datacite.org/dois?{params}")
        records = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(records, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing data")
        out: list[RawSourceResult] = []
        for record in records:
            attrs = record.get("attributes") if isinstance(record, Mapping) else None
            if not isinstance(attrs, Mapping):
                continue
            titles = attrs.get("titles") if isinstance(attrs.get("titles"), list) else []
            title = _plain(titles[0].get("title") if titles and isinstance(titles[0], Mapping) else "")
            doi = str(attrs.get("doi") or record.get("id") or "").strip()
            url = str(attrs.get("url") or "").strip() or (f"https://doi.org/{doi}" if doi else "")
            published = _rfc3339(attrs.get("published")) or _rfc3339(attrs.get("issued"))
            semantics = "resource_published"
            if not published:
                published = _rfc3339(attrs.get("created"))
                semantics = "doi_created"
            if not title or not url or not published:
                continue
            creators = attrs.get("creators") if isinstance(attrs.get("creators"), list) else []
            names = [str(c.get("name")) for c in creators[:4] if isinstance(c, Mapping) and c.get("name")]
            descriptions = attrs.get("descriptions") if isinstance(attrs.get("descriptions"), list) else []
            abstract = ""
            for entry in descriptions:
                if isinstance(entry, Mapping) and str(entry.get("descriptionType") or "") == "Abstract":
                    abstract = _trim(entry.get("description"))
                    break
            types = attrs.get("types") if isinstance(attrs.get("types"), Mapping) else {}
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"datacite:{doi}",
                url=url,
                title=title,
                text=abstract or title,
                author=", ".join(names),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "doi": doi,
                    "publisher": str(attrs.get("publisher") or ""),
                    "resource_type": str(types.get("resourceTypeGeneral") or ""),
                    "registered": _rfc3339(attrs.get("registered")),
                    "date_semantics": semantics,
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class OpenLibraryAdapter:
    """Open Library work search; dates are year-precision by design."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "open_library"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({
            "q": query, "limit": min(limit, 50),
            "fields": "key,title,first_publish_year,author_name,subject",
        })
        payload = _json(self.http_client, self.source_name, f"https://openlibrary.org/search.json?{params}")
        docs = payload.get("docs") if isinstance(payload, Mapping) else None
        if not isinstance(docs, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing docs")
        out: list[RawSourceResult] = []
        for doc in docs:
            if not isinstance(doc, Mapping):
                continue
            key = str(doc.get("key") or "").strip()
            title = _plain(doc.get("title"))
            published, precision = _year_month_day(doc.get("first_publish_year"))
            if not key or not title or not published:
                continue
            authors = doc.get("author_name") if isinstance(doc.get("author_name"), list) else []
            subjects = doc.get("subject") if isinstance(doc.get("subject"), list) else []
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"openlibrary:{key}",
                url=f"https://openlibrary.org{key}",
                title=title,
                text=title,
                author=", ".join(str(a) for a in authors[:4]),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "work_key": key,
                    "first_publish_year": int(doc.get("first_publish_year") or 0),
                    "subjects": [str(s) for s in subjects[:8]],
                    "date_precision": precision,
                    "date_semantics": "first_publish_year",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class InternetArchiveAdapter:
    """Internet Archive advanced search over item metadata."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "internet_archive"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = (
            f"q={urlencode({'': query})[1:]}"
            f"&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=date&fl%5B%5D=creator"
            f"&rows={min(limit, 50)}&page=1&output=json"
        )
        payload = _json(self.http_client, self.source_name,
                        f"https://archive.org/advancedsearch.php?{params}")
        response = payload.get("response") if isinstance(payload, Mapping) else None
        docs = response.get("docs") if isinstance(response, Mapping) else None
        if not isinstance(docs, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing response.docs")
        out: list[RawSourceResult] = []
        for doc in docs:
            if not isinstance(doc, Mapping):
                continue
            identifier = str(doc.get("identifier") or "").strip()
            title_value = doc.get("title")
            if isinstance(title_value, list):
                title_value = title_value[0] if title_value else ""
            title = _plain(title_value)
            raw_date = doc.get("date")
            if isinstance(raw_date, list):
                raw_date = raw_date[0] if raw_date else ""
            published = _rfc3339(str(raw_date or "")[:10])
            if not identifier or not title or not published:
                continue
            creator = doc.get("creator")
            if isinstance(creator, list):
                creator = creator[0] if creator else ""
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"archive:{identifier}",
                url=f"https://archive.org/details/{identifier}",
                title=title,
                text=title,
                author=_plain(creator),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "identifier": identifier,
                    "raw_date": str(raw_date),
                    "date_semantics": "archive_item_date",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class ClinicalTrialsAdapter:
    """ClinicalTrials.gov v2 study search."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "clinicaltrials"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({
            "query.term": query,
            "pageSize": min(limit, 100),
            "sort": "LastUpdatePostDate:desc",
        })
        payload = _json(self.http_client, self.source_name,
                        f"https://clinicaltrials.gov/api/v2/studies?{params}")
        studies = payload.get("studies") if isinstance(payload, Mapping) else None
        if not isinstance(studies, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing studies")
        out: list[RawSourceResult] = []
        for study in studies:
            protocol = study.get("protocolSection") if isinstance(study, Mapping) else None
            if not isinstance(protocol, Mapping):
                continue
            ident = protocol.get("identificationModule") if isinstance(protocol.get("identificationModule"), Mapping) else {}
            status = protocol.get("statusModule") if isinstance(protocol.get("statusModule"), Mapping) else {}
            desc = protocol.get("descriptionModule") if isinstance(protocol.get("descriptionModule"), Mapping) else {}
            nct = str(ident.get("nctId") or "").strip()
            title = _plain(ident.get("briefTitle") or ident.get("officialTitle"))
            first_post = status.get("studyFirstPostDateStruct") if isinstance(status.get("studyFirstPostDateStruct"), Mapping) else {}
            published = _rfc3339(first_post.get("date"))
            if not nct or not title or not published:
                continue
            last_update = status.get("lastUpdatePostDateStruct") if isinstance(status.get("lastUpdatePostDateStruct"), Mapping) else {}
            sponsor = protocol.get("sponsorCollaboratorsModule") if isinstance(protocol.get("sponsorCollaboratorsModule"), Mapping) else {}
            lead = sponsor.get("leadSponsor") if isinstance(sponsor.get("leadSponsor"), Mapping) else {}
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"nct:{nct}",
                url=f"https://clinicaltrials.gov/study/{nct}",
                title=title,
                text=_trim(desc.get("briefSummary")) or title,
                author=str(lead.get("name") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                raw_metadata={
                    "nct_id": nct,
                    "overall_status": str(status.get("overallStatus") or ""),
                    "last_update_posted": _rfc3339(last_update.get("date")),
                    "date_semantics": "study_first_posted",
                },
            ))
            if len(out) == limit:
                break
        return out
