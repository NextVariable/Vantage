"""Applicant-tracking-system connectors: Lever, Greenhouse, Ashby.

All three are public, read-only job-board APIs that require a named company
board.  A board must be supplied by the caller; no board is guessed from the
research query.  Posting dates are used only when the upstream provides a real
publish field; ``updated_at`` is retained as an update marker.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import urlencode

from ..pipeline.adapters import (
    AdapterInvalidResponse,
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
from .open_sources import _json, _limit, _query, _rfc3339

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(?:p|div|br|li|ul|ol)\b[^>]*>", re.IGNORECASE)
_MAX_BOARDS = 2
_ASHBY_MAX_BYTES = 2_000_000


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _BLOCK.sub(" ", text)
    text = _TAG.sub("", text)
    return " ".join(text.split())


def _epoch(value: object) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    if number > 10_000_000_000:  # millisecond timestamps
        number //= 1000
    return _rfc3339(number)


def _boards(
    plan: Mapping[str, object],
    request: Mapping[str, object],
    default: Sequence[str],
) -> list[str]:
    raw = request.get("boards") or plan.get("boards") or default
    if isinstance(raw, str):
        values = re.split(r"[,\s]+", raw)
    elif isinstance(raw, (list, tuple)):
        values = [str(value) for value in raw]
    else:
        values = []
    cleaned = [value.strip() for value in values if value.strip()]
    return cleaned[:_MAX_BOARDS]


def _newest_first(items: list, date_of) -> list:
    """Sort postings newest-first; undated entries go last."""
    return sorted(
        items,
        key=lambda item: date_of(item) if isinstance(item, Mapping) else "",
        reverse=True,
    )


def _require_boards(plan: Mapping[str, object], request: Mapping[str, object], source: str) -> list[str]:
    boards = _boards(plan, request, ())
    if not boards:
        raise AdapterInvalidResponse(
            source,
            "a named public board is required; pass boards=[...] on the request or plan",
        )
    return boards


def _bounded_get(http: HttpClient, source: str, url: str, max_bytes: int):
    try:
        return http.request(url, max_bytes=max_bytes)
    except HttpTransientError as exc:
        from ..pipeline.adapters import AdapterRateLimited

        if exc.status == 429:
            raise AdapterRateLimited(source, "upstream rate limit") from exc
        raise AdapterUnavailable(source, f"upstream transient error {exc.status}") from exc
    except HttpTimeoutError as exc:
        raise AdapterTimeout(source, str(exc)) from exc
    except HttpPermanentError as exc:
        if exc.status == 413:
            raise AdapterInvalidResponse(source, f"response exceeded {max_bytes} byte limit") from exc
        raise AdapterInvalidResponse(source, str(exc)) from exc
    except Exception as exc:
        raise AdapterUnavailable(source, f"{type(exc).__name__}: {exc}") from exc


@dataclass(frozen=True)
class LeverAdapter:
    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "lever"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        out: list[RawSourceResult] = []
        for board in _require_boards(plan, request, self.source_name):
            payload = _json(
                self.http_client,
                self.source_name,
                f"https://api.lever.co/v0/postings/{board}?{urlencode({'mode': 'json'})}",
            )
            if not isinstance(payload, list):
                raise AdapterInvalidResponse(self.source_name, "payload was not a list")
            for posting in _newest_first(payload, lambda item: _epoch(item.get("createdAt"))):
                if not isinstance(posting, Mapping):
                    continue
                posting_id = str(posting.get("id") or "").strip()
                url = str(posting.get("hostedUrl") or posting.get("applyUrl") or "").strip()
                title = str(posting.get("text") or "").strip()
                if not posting_id or not url or not title:
                    continue
                categories = posting.get("categories") if isinstance(posting.get("categories"), Mapping) else {}
                description = posting.get("descriptionPlain") or _plain(posting.get("description"))
                out.append(RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"lever:{board}:{posting_id}",
                    url=url,
                    title=title,
                    text=str(description or title),
                    author=board,
                    published_at=_epoch(posting.get("createdAt")),
                    market=str(request.get("market") or "global"),
                    language=str(request.get("query_language") or "en"),
                    query=query,
                    query_language=str(request.get("query_language") or "en"),
                    raw_metadata={
                        "board": board,
                        "team": str(categories.get("team") or ""),
                        "location": str(categories.get("location") or ""),
                        "commitment": str(categories.get("commitment") or ""),
                        "publish_time": "created_at" if _epoch(posting.get("createdAt")) else "snapshot_only",
                        "date_semantics": "posting_created",
                    },
                ))
                if len(out) == limit:
                    return out
        return out


@dataclass(frozen=True)
class GreenhouseAdapter:
    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "greenhouse"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        out: list[RawSourceResult] = []
        for board in _require_boards(plan, request, self.source_name):
            payload = _json(
                self.http_client,
                self.source_name,
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?{urlencode({'content': 'true'})}",
            )
            jobs = payload.get("jobs") if isinstance(payload, Mapping) else None
            if not isinstance(jobs, list):
                raise AdapterInvalidResponse(self.source_name, "payload missing jobs")
            for job in _newest_first(
                jobs,
                lambda item: _rfc3339(item.get("first_published") or item.get("datePosted") or item.get("updated_at")),
            ):
                if not isinstance(job, Mapping):
                    continue
                job_id = str(job.get("id") or "").strip()
                url = str(job.get("absolute_url") or "").strip()
                title = str(job.get("title") or "").strip()
                if not job_id or not url or not title:
                    continue
                published = _rfc3339(job.get("first_published") or job.get("datePosted"))
                location = job.get("location") if isinstance(job.get("location"), Mapping) else {}
                out.append(RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"greenhouse:{board}:{job_id}",
                    url=url,
                    title=title,
                    text=_plain(job.get("content")) or title,
                    author=board,
                    published_at=published,
                    market=str(request.get("market") or "global"),
                    language=str(request.get("query_language") or "en"),
                    query=query,
                    query_language=str(request.get("query_language") or "en"),
                    raw_metadata={
                        "board": board,
                        "location": str(location.get("name") or ""),
                        "updated_at": _rfc3339(job.get("updated_at")),
                        "publish_time": "first_published" if published else "snapshot_only",
                        "date_semantics": "posting_first_published",
                    },
                ))
                if len(out) == limit:
                    return out
        return out


@dataclass(frozen=True)
class AshbyAdapter:
    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "ashby"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        out: list[RawSourceResult] = []
        for board in _require_boards(plan, request, self.source_name):
            response = _bounded_get(
                self.http_client,
                self.source_name,
                f"https://api.ashbyhq.com/posting-api/job-board/{board}",
                _ASHBY_MAX_BYTES,
            )
            if response.status != 200:
                raise AdapterInvalidResponse(self.source_name, f"upstream returned {response.status}")
            try:
                payload = response.json()
            except Exception as exc:
                raise AdapterInvalidResponse(self.source_name, "upstream body was not JSON") from exc
            jobs = payload.get("jobs") if isinstance(payload, Mapping) else None
            if not isinstance(jobs, list):
                raise AdapterInvalidResponse(self.source_name, "payload missing jobs")
            for job in _newest_first(jobs, lambda item: _rfc3339(item.get("publishedAt"))):
                if not isinstance(job, Mapping) or job.get("isListed") is False:
                    continue
                job_id = str(job.get("id") or "").strip()
                url = str(job.get("jobUrl") or "").strip()
                title = str(job.get("title") or "").strip()
                if not job_id or not url or not title:
                    continue
                out.append(RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"ashby:{board}:{job_id}",
                    url=url,
                    title=title,
                    text=str(job.get("descriptionPlain") or _plain(job.get("descriptionHtml")) or title),
                    author=board,
                    published_at=_rfc3339(job.get("publishedAt")),
                    market=str(request.get("market") or "global"),
                    language=str(request.get("query_language") or "en"),
                    query=query,
                    query_language=str(request.get("query_language") or "en"),
                    raw_metadata={
                        "board": board,
                        "location": str(job.get("location") or ""),
                        "department": str(job.get("department") or ""),
                        "employment_type": str(job.get("employmentType") or ""),
                        "is_listed": True,
                        "publish_time": "published_at" if _rfc3339(job.get("publishedAt")) else "snapshot_only",
                        "date_semantics": "posting_published",
                    },
                ))
                if len(out) == limit:
                    return out
        return out
