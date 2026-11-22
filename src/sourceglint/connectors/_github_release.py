"""Evidence-directed GitHub release/tag retrieval.

A repository search proves a repository exists; it does not prove release
state. When a subquestion asks for release or version artifacts, query the
Releases endpoint for the repositories already returned by the current
search and record each release as evidence with its own tag, publication
time and URL.

Time semantics are explicit: repository ``created_at`` is discovery
metadata, a release uses ``published_at`` (falling back to the release's
``created_at``, never the repository creation date), and a tag has no date
in this response and is therefore reported as an observation only.

Failure classification is exact: 404 → not_found, 401 → auth_missing,
403 → forbidden (or rate_limited when GitHub flags abuse), 429 →
rate_limited, timeout → timeout, malformed JSON → invalid_response.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from ..pipeline.adapters import RawSourceResult
from ._http import (
    HttpClient,
    HttpPermanentError,
    HttpTimeoutError,
    HttpTransientError,
)

SOURCE_NAME = "github"
RELEASES_URL = "https://api.github.com/repos/{full_name}/releases"
TAGS_URL = "https://api.github.com/repos/{full_name}/tags"

DEFAULT_PER_REPO = 10
DEFAULT_MAX_REPOS = 5
DEFAULT_MAX_TAG_REPOS = 3
MAX_RELEASE_PAGES = 3

_RELEASE_INTENT = (
    "release", "released", "releases", "version", "versions", "changelog",
    "tag", "tags", "artifact", "artifacts", "ship", "shipped", "publish",
    "published", "发布", "版本", "发行", "更新日志",
)
_LICENSE_INTENT = ("license", "licence", "许可证", "许可协议")


class _InvalidBody(ValueError):
    """The endpoint answered 200 but the payload was not usable."""


@dataclass(frozen=True)
class ReleaseOutcome:
    """Release evidence plus non-evidence observations."""

    results: list[RawSourceResult] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _texts(plan: Mapping[str, object], request: Mapping[str, object]) -> Iterable[str]:
    yield str(request.get("query") or "")
    goals = request.get("evidence_goals")
    if isinstance(goals, (list, tuple)):
        for goal in goals:
            yield str(goal or "")
    else:
        yield str(goals or "")
    yield str(plan.get("topic") or "")
    for sub in plan.get("subquestions") or ():
        if isinstance(sub, Mapping):
            for key in ("question", "objective", "label", "gap"):
                yield str(sub.get(key) or "")
        else:
            yield str(sub or "")


def _matches(plan: Mapping[str, object], request: Mapping[str, object], terms: Sequence[str]) -> bool:
    blob = " ".join(_texts(plan, request)).lower()
    return any(term in blob for term in terms)


def release_intent(plan: Mapping[str, object], request: Mapping[str, object]) -> bool:
    """True when the research asks about release/version artifacts."""
    return _matches(plan, request, _RELEASE_INTENT)


def license_intent(plan: Mapping[str, object], request: Mapping[str, object]) -> bool:
    """True when the research asks about licensing."""
    return _matches(plan, request, _LICENSE_INTENT)


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _in_window(value: str, window: tuple[datetime, datetime] | None) -> bool:
    if window is None:
        return True
    parsed = _parse(value)
    if parsed is None:
        return False
    start, end = window
    return start <= parsed <= end


def _classify_failure(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, HttpTimeoutError):
        return "timeout", str(exc)
    if isinstance(exc, HttpTransientError):
        if exc.status in (403, 429):
            return "rate_limited", f"http {exc.status}"
        return "unavailable", f"http {exc.status}"
    if isinstance(exc, HttpPermanentError):
        if exc.status == 401:
            return "auth_missing", "http 401"
        if exc.status == 403:
            return "forbidden", "http 403"
        if exc.status == 404:
            return "not_found", "http 404"
        if exc.status == 429:
            return "rate_limited", "http 429"
        return "unavailable", f"http {exc.status}"
    if isinstance(exc, _InvalidBody):
        return "invalid_response", str(exc)
    return "unavailable", f"{type(exc).__name__}: {exc}"


def _get_json(
    http_client: HttpClient,
    url: str,
    headers: Mapping[str, str],
) -> Any:
    response = http_client.request(url, headers=dict(headers))
    if response.status != 200:
        if response.status in (401, 403, 404, 429) or response.status >= 500:
            raise HttpPermanentError(status=response.status, url=url)
        raise _InvalidBody(f"unexpected status {response.status}")
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001 - classified below
        raise _InvalidBody(f"body not JSON: {exc}") from exc


def _get_json_page(
    http_client: HttpClient,
    url: str,
    headers: Mapping[str, str],
) -> tuple[Any, Mapping[str, str]]:
    """Like `_get_json`, but keep response headers for Link pagination."""
    response = http_client.request(url, headers=dict(headers))
    if response.status != 200:
        if response.status in (401, 403, 404, 429) or response.status >= 500:
            raise HttpPermanentError(status=response.status, url=url)
        raise _InvalidBody(f"unexpected status {response.status}")
    try:
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - classified by caller
        raise _InvalidBody(f"body not JSON: {exc}") from exc
    return payload, dict(getattr(response, "headers", {}) or {})


def _next_link(headers: Mapping[str, str]) -> str:
    """Return the rel="next" URL from a GitHub Link header, if present."""
    value = ""
    for key, header_value in headers.items():
        if str(key).lower() == "link":
            value = str(header_value)
            break
    for part in value.split(","):
        if 'rel="next"' not in part.replace(" ", ""):
            continue
        match = re.search(r"<([^>]+)>", part)
        if match:
            return match.group(1)
    return ""


def _observation(
    *,
    kind: str,
    repository: str,
    status: str,
    count: int,
    checked_at: str,
    detail: str,
    in_window_count: int | None = None,
) -> dict:
    payload: dict[str, object] = {
        "source": SOURCE_NAME,
        "kind": kind,
        "repository": repository,
        "status": status,
        "count": count,
        "checked_at": checked_at,
        "detail": detail,
    }
    if in_window_count is not None:
        payload["in_window_count"] = in_window_count
    return payload


def _release_results(
    full_name: str,
    repo: Mapping[str, object],
    releases: Any,
    *,
    window: tuple[datetime, datetime] | None,
    checked_at: str,
    query: str,
    language: str,
    market: str,
    limitations: list[str],
) -> tuple[list[RawSourceResult], int, int]:
    if not isinstance(releases, list):
        raise _InvalidBody("releases payload is not a list")
    repo_created_at = str(repo.get("created_at") or "")
    public: list[Mapping[str, object]] = [
        rel for rel in releases
        if isinstance(rel, Mapping) and not bool(rel.get("draft"))
    ]
    results: list[RawSourceResult] = []
    in_window = 0
    for rel in public:
        tag_name = str(rel.get("tag_name") or "")
        published = str(rel.get("published_at") or "")
        created = str(rel.get("created_at") or "")
        published_at = published or created
        if not published_at:
            limitations.append(
                f"github releases: {full_name} {tag_name or '?'} has no publication date; skipped"
            )
            continue
        if not _in_window(published_at, window):
            continue
        in_window += 1
        release_id = rel.get("id")
        url = str(rel.get("html_url") or "")
        if not url and tag_name:
            url = f"https://github.com/{full_name}/releases/tag/{tag_name}"
        body = str(rel.get("body") or "").strip()
        name = str(rel.get("name") or "").strip()
        results.append(
            RawSourceResult(
                source=SOURCE_NAME,
                source_type="release",
                source_native_id=f"release:{full_name}:{release_id or tag_name}",
                url=url or f"https://github.com/{full_name}/releases",
                title=f"{full_name} {tag_name or name}".strip(),
                text=body or name or tag_name,
                author=full_name.split("/")[0],
                published_at=published_at,
                retrieved_at=checked_at,
                language=language or "en",
                market=market or "global",
                query=query,
                query_language=language,
                raw_metadata={
                    "github_full_name": full_name,
                    "github_kind": "release",
                    "github_repo_id": repo.get("id"),
                    "github_release_id": release_id,
                    "github_tag_name": tag_name,
                    "github_release_published_at": published,
                    "github_release_created_at": created,
                    "github_repo_created_at": repo_created_at,
                    "github_prerelease": bool(rel.get("prerelease")),
                    "github_draft": False,
                    "version_source": "release_published_at" if published else "release_created_at",
                },
            )
        )
    return results, len(public), in_window


def fetch_releases(
    http_client: HttpClient,
    repos: Sequence[Mapping[str, object]],
    *,
    headers: Mapping[str, str],
    per_repo: int = DEFAULT_PER_REPO,
    max_repos: int = DEFAULT_MAX_REPOS,
    max_tag_repos: int = DEFAULT_MAX_TAG_REPOS,
    window: tuple[datetime, datetime] | None = None,
    checked_at: str = "",
    query: str = "",
    language: str = "",
    market: str = "",
) -> ReleaseOutcome:
    """Fetch release evidence for the first ``max_repos`` repositories."""
    results: list[RawSourceResult] = []
    observations: list[dict] = []
    limitations: list[str] = []
    tag_budget = max(0, max_tag_repos)

    for repo in list(repos)[:max(0, max_repos)]:
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            continue
        page_url = f"{RELEASES_URL.format(full_name=full_name)}?per_page={max(1, per_repo)}"
        repo_results: list[RawSourceResult] = []
        public_count = 0
        in_window = 0
        pages_fetched = 0
        pagination_complete = True
        try:
            while True:
                payload, page_headers = _get_json_page(http_client, page_url, headers)
                pages_fetched += 1
                page_results, page_public, page_in_window = _release_results(
                    full_name, repo, payload,
                    window=window,
                    checked_at=checked_at,
                    query=query,
                    language=language,
                    market=market,
                    limitations=limitations,
                )
                repo_results.extend(page_results)
                public_count += page_public
                in_window += page_in_window
                next_url = _next_link(page_headers)
                # Releases are newest-first; stop as soon as the window is
                # covered, or when the page cap is reached.
                if in_window > 0 or not next_url or pages_fetched >= MAX_RELEASE_PAGES:
                    pagination_complete = not next_url
                    break
                page_url = next_url
        except Exception as exc:  # classified, never raised to caller
            status, detail = _classify_failure(exc)
            observations.append(
                _observation(
                    kind="releases",
                    repository=full_name,
                    status=status,
                    count=0,
                    checked_at=checked_at,
                    detail=f"{full_name}: {detail}",
                )
            )
            limitations.append(f"github releases unavailable for {full_name}: {detail}")
            continue

        results.extend(repo_results)
        if public_count == 0:
            status = "verified_absent"
        elif in_window == 0 and pagination_complete:
            status = "only_outside_window"
        elif in_window == 0:
            status = "pagination_incomplete"
        else:
            status = "present"
        observations.append(
            _observation(
                kind="releases",
                repository=full_name,
                status=status,
                count=public_count,
                in_window_count=in_window,
                checked_at=checked_at,
                detail=(
                    f"{full_name}: Releases API returned {public_count} release(s) "
                    f"across {pages_fetched} page(s), {in_window} inside the research "
                    f"window"
                    + ("" if pagination_complete else "; pagination incomplete")
                ),
            )
        )

        if public_count == 0 and pagination_complete and tag_budget > 0:
            tag_budget -= 1
            observations.append(
                _tag_observation(
                    http_client, full_name, headers=headers,
                    checked_at=checked_at, limitations=limitations,
                )
            )
    return ReleaseOutcome(results=results, observations=observations, limitations=limitations)


def _tag_observation(
    http_client: HttpClient,
    full_name: str,
    *,
    headers: Mapping[str, str],
    checked_at: str,
    limitations: list[str],
) -> dict:
    url = f"{TAGS_URL.format(full_name=full_name)}?per_page=10"
    try:
        payload = _get_json(http_client, url, headers)
        count = len(payload) if isinstance(payload, list) else 0
        status = "present" if count else "verified_absent"
    except Exception as exc:  # classified, observation only
        status, detail = _classify_failure(exc)
        limitations.append(f"github tags unavailable for {full_name}: {detail}")
        return _observation(
            kind="tags", repository=full_name, status=status, count=0,
            checked_at=checked_at, detail=f"{full_name}: tags {detail}",
        )
    return _observation(
        kind="tags",
        repository=full_name,
        status=status,
        count=count,
        checked_at=checked_at,
        detail=f"{full_name}: Tags API returned {count} tag(s) without dated releases",
    )


__all__ = [
    "ReleaseOutcome",
    "release_intent",
    "license_intent",
    "fetch_releases",
    "RELEASES_URL",
    "TAGS_URL",
    "DEFAULT_MAX_REPOS",
    "DEFAULT_PER_REPO",
]
