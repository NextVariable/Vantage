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


_DETAIL_LOOKUPS = 3


@dataclass(frozen=True)
class MavenCentralAdapter:
    """Maven Central artifact search (Solr endpoint, no key)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "maven_central"

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
        params = urlencode({"q": query, "rows": min(limit, 50), "wt": "json"})
        payload = _json(self.http_client, self.source_name,
                        f"https://search.maven.org/solrsearch/select?{params}")
        response = payload.get("response") if isinstance(payload, Mapping) else None
        docs = response.get("docs") if isinstance(response, Mapping) else None
        if not isinstance(docs, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing response.docs")
        out: list[RawSourceResult] = []
        for doc in docs:
            if not isinstance(doc, Mapping):
                continue
            group = str(doc.get("g") or "").strip()
            artifact = str(doc.get("a") or "").strip()
            version = str(doc.get("latestVersion") or "").strip()
            try:
                published = _rfc3339(int(doc.get("timestamp") or 0) / 1000)
            except (TypeError, ValueError):
                published = ""
            if not group or not artifact or not version or not published:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="release",
                source_native_id=f"maven:{group}:{artifact}",
                url=f"https://central.sonatype.com/artifact/{group}/{artifact}",
                title=f"{group}:{artifact} {version}",
                text=str(doc.get("text") or f"{group}:{artifact}"),
                author=group,
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                engagement={"points": _integer(doc.get("versionCount"))},
                raw_metadata={
                    "group_id": group,
                    "artifact_id": artifact,
                    "latest_version": version,
                    "version_count": _integer(doc.get("versionCount")),
                    "repository_id": str(doc.get("repositoryId") or ""),
                    "date_semantics": "latest_version_published",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class NuGetAdapter:
    """NuGet package search with exact published time from registration."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "nuget"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def _published(self, package_id: str, version: str) -> str:
        from ..pipeline.adapters import AdapterError

        try:
            index = _json(
                self.http_client, self.source_name,
                f"https://api.nuget.org/v3/registration5-semver1/{package_id.lower()}/index.json",
            )
        except AdapterError:
            return ""
        pages = index.get("items") if isinstance(index, Mapping) else None
        if not isinstance(pages, list):
            return ""
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            entries = page.get("items")
            if not isinstance(entries, list) and page.get("@id"):
                try:
                    entries = _json(self.http_client, self.source_name, str(page["@id"])).get("items")
                except AdapterError:
                    continue
            for entry in entries or []:
                catalog = entry.get("catalogEntry") if isinstance(entry, Mapping) else None
                if isinstance(catalog, str):
                    try:
                        catalog = _json(self.http_client, self.source_name, catalog)
                    except AdapterError:
                        continue
                if not isinstance(catalog, Mapping):
                    continue
                if str(catalog.get("version") or "") != version:
                    continue
                return _rfc3339(catalog.get("published") or catalog.get("created"))
        return ""

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"q": query, "take": min(limit, 50), "prerelease": "false"})
        payload = _json(self.http_client, self.source_name,
                        f"https://azuresearch-usnc.nuget.org/query?{params}")
        items = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(items, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing data")
        out: list[RawSourceResult] = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                continue
            package_id = str(item.get("id") or "").strip()
            version = str(item.get("version") or "").strip()
            if not package_id or not version:
                continue
            published = self._published(package_id, version) if index < _DETAIL_LOOKUPS else ""
            if not published:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="release",
                source_native_id=f"nuget:{package_id}@{version}",
                url=f"https://www.nuget.org/packages/{package_id}/{version}",
                title=f"{package_id} {version}",
                text=str(item.get("description") or item.get("summary") or package_id),
                author=str(item.get("authors") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                engagement={"points": _integer(item.get("totalDownloads"))},
                raw_metadata={
                    "package": package_id,
                    "version": version,
                    "verified": bool(item.get("verified")),
                    "total_downloads": _integer(item.get("totalDownloads")),
                    "project_url": str(item.get("projectUrl") or ""),
                    "date_semantics": "version_published",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class RubyGemsAdapter:
    """RubyGems search with exact version creation time."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "rubygems"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterError, AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        payload = _json(
            self.http_client, self.source_name,
            f"https://rubygems.org/api/v1/search.json?{urlencode({'query': query})}",
        )
        if not isinstance(payload, list):
            raise AdapterInvalidResponse(self.source_name, "payload was not a list")
        out: list[RawSourceResult] = []
        for index, item in enumerate(payload):
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "").strip()
            version = str(item.get("version") or "").strip()
            if not name or not version:
                continue
            published = ""
            if index < _DETAIL_LOOKUPS:
                try:
                    detail = _json(self.http_client, self.source_name,
                                   f"https://rubygems.org/api/v1/gems/{name}.json")
                except AdapterError:
                    detail = {}
                if isinstance(detail, Mapping):
                    published = _rfc3339(detail.get("version_created_at") or detail.get("created_at"))
            if not published:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="release",
                source_native_id=f"rubygems:{name}@{version}",
                url=str(item.get("project_uri") or f"https://rubygems.org/gems/{name}"),
                title=f"{name} {version}",
                text=str(item.get("info") or name),
                author=str(item.get("authors") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                engagement={
                    "points": _integer(item.get("downloads")),
                    "version_downloads": _integer(item.get("version_downloads")),
                },
                raw_metadata={
                    "gem": name,
                    "version": version,
                    "licenses": list(item.get("licenses") or []),
                    "date_semantics": "version_created",
                },
            ))
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class DockerHubAdapter:
    """Docker Hub repository search with registration/push dates."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "docker_hub"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterError, AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"query": query, "page_size": min(limit, 50)})
        payload = _json(self.http_client, self.source_name,
                        f"https://hub.docker.com/v2/search/repositories/?{params}")
        results = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(results, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing results")
        out: list[RawSourceResult] = []
        for index, item in enumerate(results):
            if not isinstance(item, Mapping):
                continue
            repo = str(item.get("repo_name") or "").strip()
            if not repo:
                continue
            published = ""
            registered = ""
            last_updated = ""
            if index < _DETAIL_LOOKUPS:
                try:
                    detail = _json(self.http_client, self.source_name,
                                   f"https://hub.docker.com/v2/repositories/{repo}/")
                except AdapterError:
                    detail = {}
                if isinstance(detail, Mapping):
                    registered = _rfc3339(detail.get("date_registered"))
                    last_updated = _rfc3339(detail.get("last_updated"))
                    published = registered
            if not published:
                continue
            description = str(item.get("short_description") or "")
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"dockerhub:{repo}",
                url=f"https://hub.docker.com/r/{repo}",
                title=repo,
                text=description or repo,
                author=str(item.get("repo_owner") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language="en",
                query=query,
                query_language="en",
                engagement={
                    "points": _integer(item.get("star_count")),
                    "pulls": _integer(item.get("pull_count")),
                },
                raw_metadata={
                    "repository": repo,
                    "official": bool(item.get("is_official")),
                    "automated": bool(item.get("is_automated")),
                    "last_updated": last_updated,
                    "date_semantics": "repository_registered",
                },
            ))
            if len(out) == limit:
                break
        return out
