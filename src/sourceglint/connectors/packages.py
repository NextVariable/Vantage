"""Package-registry connectors: PyPI and crates.io.

PyPI has no public full-text search endpoint, so the query must name a package.
crates.io supports keyword discovery; the exact version date is read from the
per-crate document rather than the search result's ``updated_at``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import AdapterError, AdapterInvalidResponse, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import _integer, _json, _limit, _query, _rfc3339

_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")
_CRATE_DOC_LOOKUPS = 3


def _plain_summary(value: object, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    return text or fallback


@dataclass(frozen=True)
class PyPIAdapter:
    """Named-package lookup against the public PyPI JSON API."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "pypi"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        candidate = str(request.get("package") or "").strip() or _query(request, self.source_name)
        if not _PACKAGE_NAME.match(candidate):
            raise AdapterInvalidResponse(
                self.source_name,
                "PyPI exposes no full-text search; provide a package name via request.package",
            )
        payload = _json(self.http_client, self.source_name, f"https://pypi.org/pypi/{candidate}/json")
        if not isinstance(payload, Mapping):
            raise AdapterInvalidResponse(self.source_name, "payload was not an object")
        info = payload.get("info") if isinstance(payload.get("info"), Mapping) else {}
        version = str(info.get("version") or "").strip()
        name = str(info.get("name") or candidate).strip()
        if not version or not name:
            raise AdapterInvalidResponse(self.source_name, "payload missing package version")
        releases = payload.get("releases") if isinstance(payload.get("releases"), Mapping) else {}
        files = releases.get(version) if isinstance(releases.get(version), list) else []
        uploads = [
            _rfc3339(item.get("upload_time_iso_8601") or item.get("upload_time"))
            for item in files
            if isinstance(item, Mapping)
        ]
        uploads = [value for value in uploads if value]
        published = min(uploads) if uploads else ""
        yanked = bool(files) and all(bool(item.get("yanked")) for item in files if isinstance(item, Mapping))
        summary = _plain_summary(info.get("summary"), name)
        description = " ".join(str(info.get("description") or "").split())
        text = summary if not description else f"{summary}. {description[:1200]}"
        return [RawSourceResult(
            source=self.source_name,
            source_type="release",
            source_native_id=f"pypi:{name}@{version}",
            url=f"https://pypi.org/project/{name}/{version}/",
            title=f"{name} {version}",
            text=text,
            author=str(info.get("author") or ""),
            published_at=published,
            market=str(request.get("market") or "global"),
            language=str(request.get("query_language") or "en"),
            query=candidate,
            query_language=str(request.get("query_language") or "en"),
            raw_metadata={
                "package": name,
                "version": version,
                "file_count": len(files),
                "upload_times": sorted(uploads),
                "requires_python": str(info.get("requires_python") or ""),
                "license": str(info.get("license") or ""),
                "yanked": yanked,
                "publish_time": "release_file_upload" if published else "unresolved",
                "date_semantics": "release_upload",
            },
        )]


@dataclass(frozen=True)
class CratesIoAdapter:
    """Keyword discovery plus exact newest-version date from crates.io."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "crates_io"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def _version_date(self, name: str, version_hint: str) -> tuple[str, str, str]:
        """Return (version, created_at, description) for the newest version."""
        try:
            payload = _json(self.http_client, self.source_name, f"https://crates.io/api/v1/crates/{name}")
        except AdapterError:
            return version_hint, "", ""
        if not isinstance(payload, Mapping):
            return version_hint, "", ""
        crate = payload.get("crate") if isinstance(payload.get("crate"), Mapping) else {}
        versions = payload.get("versions") if isinstance(payload.get("versions"), list) else []
        chosen = None
        for item in versions:
            if isinstance(item, Mapping) and str(item.get("num") or "") == version_hint:
                chosen = item
                break
        if chosen is None:
            for item in versions:
                if isinstance(item, Mapping):
                    chosen = item
                    break
        if chosen is None:
            return version_hint, "", str(crate.get("description") or "")
        return (
            str(chosen.get("num") or version_hint),
            _rfc3339(chosen.get("created_at")),
            str(crate.get("description") or ""),
        )

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = {"q": query, "per_page": min(limit, 20)}
        payload = _json(self.http_client, self.source_name, f"https://crates.io/api/v1/crates?{urlencode(params)}")
        crates = payload.get("crates") if isinstance(payload, Mapping) else None
        if not isinstance(crates, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing crates")
        out: list[RawSourceResult] = []
        lookups = 0
        for crate in crates:
            if not isinstance(crate, Mapping):
                continue
            name = str(crate.get("id") or crate.get("name") or "").strip()
            if not name:
                continue
            hint = str(crate.get("newest_version") or crate.get("max_version") or "").strip()
            version, published, description = hint, "", ""
            if lookups < _CRATE_DOC_LOOKUPS:
                version, published, description = self._version_date(name, hint)
                lookups += 1
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="release",
                source_native_id=f"crates:{name}@{version or hint}",
                url=f"https://crates.io/crates/{name}",
                title=f"{name} {version or hint}".strip(),
                text=str(description or crate.get("description") or name),
                author="",
                published_at=published,
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                raw_metadata={
                    "crate": name,
                    "version": version or hint,
                    "downloads": _integer(crate.get("downloads")),
                    "crate_created_at": _rfc3339(crate.get("created_at")),
                    # Search metadata only: it is a discovery/update marker.
                    "search_updated_at": _rfc3339(crate.get("updated_at")),
                    "publish_time": "version_created_at" if published else "unresolved",
                    "date_semantics": "version_release",
                },
            ))
            if len(out) == limit:
                break
        return out
