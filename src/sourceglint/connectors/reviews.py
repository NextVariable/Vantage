"""Steam public review connector.

The official ``appreviews`` endpoint is read-only and needs no key.  It requires
a verified numeric app id; reviews are mapped with their own recommendation id,
canonical community URL, creation time and helpfulness votes.  The update time
is kept separate and never substituted for the creation time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from ..pipeline.adapters import AdapterInvalidResponse, AdapterUnavailable, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from .open_sources import _get, _integer, _json, _limit, _query, _rfc3339

_LANGUAGES = {
    "en": "english",
    "zh": "schinese",
    "zh-cn": "schinese",
    "ja": "japanese",
    "ko": "korean",
    "de": "german",
    "fr": "french",
    "es": "spanish",
    "ru": "russian",
}
_DEFAULT_APP_ID = ""


def _app_id(plan: Mapping[str, object], request: Mapping[str, object]) -> str:
    raw = str(request.get("appid") or plan.get("appid") or _DEFAULT_APP_ID).strip()
    return raw if raw.isdigit() else ""


@dataclass(frozen=True)
class SteamAdapter:
    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "steam"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        appid = _app_id(plan, request)
        if not appid:
            raise AdapterInvalidResponse(
                self.source_name,
                "a verified numeric Steam appid is required; pass appid on the request or plan",
            )
        language = str(request.get("query_language") or "en").lower()
        params = {
            "json": 1,
            "language": _LANGUAGES.get(language, "all"),
            "purchase_type": str(request.get("purchase_type") or "all"),
            "num_per_page": min(limit, 100),
            "filter": "recent",
            "review_type": "all",
            "cursor": str(request.get("cursor") or "*"),
        }
        response = _get(
            self.http_client,
            self.source_name,
            f"https://store.steampowered.com/appreviews/{appid}?{urlencode(params)}",
        )
        if response.status != 200:
            raise AdapterInvalidResponse(
                self.source_name, f"Steam returned status {response.status}"
            )
        content_type = str(response.headers.get("content-type") or "").lower()
        if "json" not in content_type:
            # The review endpoint answers a regional/anti-bot gate with a 302 to
            # the store home page. Record that as bounded unavailability rather
            # than a malformed review payload or a fabricated sample.
            raise AdapterUnavailable(
                self.source_name,
                "Steam redirected the review endpoint to a non-JSON page "
                "(regional or anti-bot gate)",
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise AdapterInvalidResponse(
                self.source_name, "Steam review body was not JSON"
            ) from exc
        if not isinstance(payload, Mapping) or payload.get("success") != 1:
            raise AdapterInvalidResponse(self.source_name, "Steam returned no review payload")
        reviews = payload.get("reviews")
        if not isinstance(reviews, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing reviews")
        out: list[RawSourceResult] = []
        for review in reviews:
            if not isinstance(review, Mapping):
                continue
            review_id = str(review.get("recommendationid") or "").strip()
            body = str(review.get("review") or "").strip()
            author = review.get("author") if isinstance(review.get("author"), Mapping) else {}
            steamid = str(author.get("steamid") or "").strip()
            if not review_id or not body:
                continue
            url = (
                f"https://steamcommunity.com/profiles/{steamid}/recommended/{appid}/"
                if steamid
                else f"https://store.steampowered.com/app/{appid}/#app_reviews_hash"
            )
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="review",
                source_native_id=f"steam:{appid}:{review_id}",
                url=url,
                title=f"Steam review for app {appid}",
                text=body,
                author=steamid,
                published_at=_rfc3339(review.get("timestamp_created")),
                market=str(request.get("market") or "global"),
                language=language,
                query=query,
                query_language=language,
                engagement={
                    "points": _integer(review.get("votes_up")),
                    "comments": _integer(review.get("comment_count")),
                },
                raw_metadata={
                    "appid": appid,
                    "timestamp_updated": _rfc3339(review.get("timestamp_updated")),
                    "votes_helpful": _integer(review.get("votes_helpful")),
                    "weighted_vote_score": str(review.get("weighted_vote_score") or ""),
                    "voted_up": bool(review.get("voted_up")),
                    "purchase_type": str(review.get("steam_purchase") and "steam" or "other"),
                    "next_cursor": str(payload.get("cursor") or ""),
                    "date_semantics": "review_created",
                },
            ))
            if len(out) == limit:
                break
        return out


_STORE_COUNTRY = {
    "us": "us", "gb": "gb", "jp": "jp", "de": "de", "fr": "fr",
    "kr": "kr", "cn": "cn", "in": "in", "br": "br",
}


def _label(value: object) -> str:
    """iTunes RSS nests every field as {"label": ...}."""
    if isinstance(value, Mapping):
        return str(value.get("label") or "").strip()
    return str(value or "").strip()


@dataclass(frozen=True)
class ITunesAppStoreAdapter:
    """Apple App Store keyword search via the public iTunes Search API.

    The app listing date is the store's ``releaseDate``; the latest version
    date is kept separately.  Aggregate ratings are reported as engagement,
    not as review text.  When the caller supplies a numeric app id, the public
    customer-review RSS feed adds individually dated reviews.
    """

    http_client: HttpClient | None = None
    max_per_query: int = 20
    max_reviews: int = 10
    source_name: str = "app_store"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def _country(self, request: Mapping[str, object]) -> str:
        market = str(request.get("market") or "us").lower()
        return _STORE_COUNTRY.get(market, "us")

    def _reviews(self, app_id: str, country: str, request: Mapping[str, object], query: str) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterError

        try:
            payload = _json(
                self.http_client, self.source_name,
                f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json",
            )
        except AdapterError:
            return []
        feed = payload.get("feed") if isinstance(payload, Mapping) else None
        entries = feed.get("entry") if isinstance(feed, Mapping) else None
        if not isinstance(entries, list):
            return []
        out: list[RawSourceResult] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            body = _label(entry.get("content"))
            rating = _label(entry.get("im:rating"))
            review_id = _label(entry.get("id"))
            published = _rfc3339(_label(entry.get("updated")))
            if not body or not review_id or not published:
                continue
            link = entry.get("link") if isinstance(entry.get("link"), Mapping) else {}
            attributes = link.get("attributes") if isinstance(link.get("attributes"), Mapping) else {}
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="review",
                source_native_id=f"appstore_review:{review_id}",
                url=review_id if review_id.startswith("http") else str(attributes.get("href") or ""),
                title=f"App Store review {rating or ''}".strip(),
                text=body,
                author=_label(entry.get("author")),
                published_at=published,
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                engagement={
                    "points": _integer(_label(entry.get("im:voteSum"))),
                    "votes": _integer(_label(entry.get("im:voteCount"))),
                },
                raw_metadata={
                    "app_id": app_id,
                    "rating": rating,
                    "version": _label(entry.get("im:version")),
                    "date_semantics": "review_updated",
                },
            ))
            if len(out) == self.max_reviews:
                break
        return out

    def retrieve(self, plan: Mapping[str, object], request: Mapping[str, object]) -> list[RawSourceResult]:
        from ..pipeline.adapters import AdapterInvalidResponse

        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        country = self._country(request)
        # The public search API returns zero rows for limit < 3; request a
        # small floor and still slice the mapped output to the caller's limit.
        params = urlencode({
            "term": query, "entity": "software", "limit": max(3, min(limit, 50)),
            "country": country,
        })
        payload = _json(self.http_client, self.source_name,
                        f"https://itunes.apple.com/search?{params}")
        results = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(results, list):
            raise AdapterInvalidResponse(self.source_name, "payload missing results")
        out: list[RawSourceResult] = []
        for item in results:
            if not isinstance(item, Mapping):
                continue
            track_id = str(item.get("trackId") or "").strip()
            name = str(item.get("trackName") or "").strip()
            url = str(item.get("trackViewUrl") or "").strip()
            published = _rfc3339(item.get("releaseDate"))
            if not track_id or not name or not url or not published:
                continue
            out.append(RawSourceResult(
                source=self.source_name,
                source_type="page",
                source_native_id=f"appstore:{track_id}",
                url=url,
                title=name,
                text=" ".join(str(item.get("description") or "").split())[:1200] or name,
                author=str(item.get("sellerName") or item.get("artistName") or ""),
                published_at=published,
                market=str(request.get("market") or "global"),
                language=str(request.get("query_language") or "en"),
                query=query,
                query_language=str(request.get("query_language") or "en"),
                engagement={
                    "rating": round(float(item.get("averageUserRating") or 0), 2),
                    "ratings": _integer(item.get("userRatingCount")),
                },
                raw_metadata={
                    "app_id": track_id,
                    "bundle_id": str(item.get("bundleId") or ""),
                    "version": str(item.get("version") or ""),
                    "current_version_release_date": _rfc3339(item.get("currentVersionReleaseDate")),
                    "genre": str(item.get("primaryGenreName") or ""),
                    "price": str(item.get("formattedPrice") or ""),
                    "country": country,
                    "date_semantics": "app_first_released",
                },
            ))
            if len(out) == limit:
                break
        app_id = str(request.get("appid") or request.get("app_id") or "").strip()
        if app_id.isdigit():
            out.extend(self._reviews(app_id, country, request, query))
        return out
