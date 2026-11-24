"""GitLab public-project connector.

Only anonymous public projects are read. Releases are fetched for a small
number of verified projects; the ``next`` link is never followed blindly.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import AdapterError, AdapterInvalidResponse, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import _integer, _json, _limit, _query, _rfc3339

_TAG = re.compile(r"<[^>]+>")
_RELEASE_PROJECTS = 2


def _plain(value: object) -> str:
    text = html.unescape(_TAG.sub(" ", str(value or "")))
    return " ".join(text.split())


@dataclass(frozen=True)
class GitLabAdapter:
    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "gitlab"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = {
            "search": query,
            "order_by": "last_activity_at",
            "sort": "desc",
            "per_page": min(limit, 20),
            "visibility": "public",
        }
        payload = _json(self.http_client, self.source_name, f"https://gitlab.com/api/v4/projects?{urlencode(params)}")
        if not isinstance(payload, list):
            raise AdapterInvalidResponse(self.source_name, "payload was not a list")
        projects = [item for item in payload if isinstance(item, Mapping)]
        out: list[RawSourceResult] = []
        for project in projects:
            project_id = str(project.get("id") or "").strip()
            web_url = str(project.get("web_url") or "").strip()
            name = str(project.get("name") or project.get("path_with_namespace") or "").strip()
            if not project_id or not web_url or not name:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"gitlab:{project_id}",
                url=web_url,
                title=name,
                text=_plain(project.get("description")) or name,
                author=str(project.get("namespace", {}).get("name") if isinstance(project.get("namespace"), Mapping) else ""),
                published_at=_rfc3339(project.get("created_at")),
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                engagement={"points": _integer(project.get("star_count")), "comments": _integer(project.get("forks_count"))},
                raw_metadata={
                    "project_id": project_id,
                    "path_with_namespace": str(project.get("path_with_namespace") or ""),
                    "last_activity_at": _rfc3339(project.get("last_activity_at")),
                    "forks_count": _integer(project.get("forks_count")),
                    "visibility": str(project.get("visibility") or "public"),
                    "date_semantics": "project_created",
                },
            ))
            if len(out) == limit:
                return out
        for project in projects[:_RELEASE_PROJECTS]:
            project_id = str(project.get("id") or "").strip()
            web_url = str(project.get("web_url") or "").strip()
            name = str(project.get("name") or project.get("path_with_namespace") or "").strip()
            if not project_id or not web_url:
                continue
            try:
                releases = _json(
                    self.http_client,
                    self.source_name,
                    f"https://gitlab.com/api/v4/projects/{project_id}/releases?{urlencode({'per_page': 3})}",
                )
            except AdapterError:
                continue
            if not isinstance(releases, list):
                continue
            for release in releases:
                if not isinstance(release, Mapping):
                    continue
                tag = str(release.get("tag_name") or release.get("name") or "").strip()
                if not tag:
                    continue
                links = release.get("_links") if isinstance(release.get("_links"), Mapping) else {}
                url = str(links.get("self") or f"{web_url}/-/releases/{tag}")
                out.append(RawSourceResult(
                    source=self.source_name,
                    source_type="release",
                    source_native_id=f"gitlab:{project_id}:release:{tag}",
                    url=url,
                    title=f"{name} {tag}",
                    text=_plain(release.get("description")) or f"{name} {tag}",
                    author=str(release.get("author", {}).get("name") if isinstance(release.get("author"), Mapping) else ""),
                    published_at=_rfc3339(release.get("released_at") or release.get("created_at")),
                    market=str(request.get("market") or "global"),
                    language=str(request.get("query_language") or "en"),
                    query=query,
                    query_language=str(request.get("query_language") or "en"),
                    raw_metadata={
                        "project_id": project_id,
                        "tag_name": tag,
                        "created_at": _rfc3339(release.get("created_at")),
                        "date_semantics": "release_published",
                    },
                ))
                if len(out) == limit:
                    return out
        return out


@dataclass(frozen=True)
class LemmyAdapter:
    """Federated Lemmy post search on a public instance (key-free)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    instance: str = "lemmy.world"
    source_name: str = "lemmy"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params = urlencode({"q": query, "type_": "Posts", "sort": "New", "limit": min(limit, 50)})
        payload = _json(self.http_client, self.source_name,
                        f"https://{self.instance}/api/v3/search?{params}")
        posts = payload.get("posts") if isinstance(payload, Mapping) else None
        if not isinstance(posts, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing posts")
        out: list[RawSourceResult] = []
        for wrapper in posts:
            post = wrapper.get("post") if isinstance(wrapper, Mapping) else None
            if not isinstance(post, Mapping):
                continue
            title = " ".join(str(post.get("name") or "").split())
            published = _rfc3339(post.get("published"))
            url = str(post.get("ap_id") or "").strip()
            if not title or not published or not url:
                continue
            creator = wrapper.get("creator") if isinstance(wrapper.get("creator"), Mapping) else {}
            community = wrapper.get("community") if isinstance(wrapper.get("community"), Mapping) else {}
            counts = wrapper.get("counts") if isinstance(wrapper.get("counts"), Mapping) else {}
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="post",
                source_native_id=f"lemmy:{post.get('id')}",
                url=url,
                title=title,
                text=_plain(post.get("body")) or title,
                author=str(creator.get("name") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                engagement={
                    "points": _integer(counts.get("score")),
                    "comments": _integer(counts.get("comments")),
                },
                raw_metadata={
                    "instance": self.instance,
                    "community": str(community.get("name") or ""),
                    "community_actor": str(community.get("actor_id") or ""),
                    "external_url": str(post.get("url") or ""),
                    "date_semantics": "post_published",
                },
            ))
            if len(out) == limit:
                break
        return out
