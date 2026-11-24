"""Structured public-data connectors for economic and regulatory evidence.

Two credential-free routes are implemented after live probes passed during the
1.1 expansion round:

* World Bank indicators (``api.worldbank.org``) — a named country/indicator
  series.  The observation period is a year, so it is recorded as
  ``observation_period`` and never substituted for a publication timestamp.
* SEC EDGAR full-text search (``efts.sec.gov``) — filing metadata for public
  companies.  ``file_date`` is the filing date; the filing body is not fetched,
  so ``content_kind`` stays ``filing_metadata`` instead of claiming full text.

Polymarket's public endpoint was unreachable from the probe environment, so it
stays catalog-only and is not exposed by the factory.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import quote_plus, urlencode

from ..pipeline.adapters import AdapterInvalidResponse, RawSourceResult
from ._http import HttpClient, StdlibHttpClient
from ._recency import search_bounds
from .open_sources import _get, _limit, _query, _rfc3339

_SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
_SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data"


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(text.split())


def _date_window(plan: Mapping[str, object], request: Mapping[str, object]) -> tuple[str, str]:
    bounds = search_bounds(plan, request)
    if not bounds:
        return "", ""
    start, end = bounds
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class WorldBankAdapter:
    """Named World Bank indicator series (country + indicator required)."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "world_bank"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(
        self, plan: Mapping[str, object], request: Mapping[str, object]
    ) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        country = str(request.get("country") or plan.get("country") or "").strip().upper()
        indicator = str(request.get("indicator") or plan.get("indicator") or "").strip().upper()
        if not country or not indicator:
            raise AdapterInvalidResponse(
                self.source_name,
                "World Bank needs a country code and an indicator code; "
                "pass country and indicator on the request or plan",
            )
        params: dict[str, object] = {"format": "json", "per_page": limit}
        start, end = _date_window(plan, request)
        if start and end:
            params["date"] = f"{start[:4]}:{end[:4]}"
        url = (
            f"https://api.worldbank.org/v2/country/{quote_plus(country)}"
            f"/indicator/{quote_plus(indicator)}?{urlencode(params)}"
        )
        response = _get(self.http_client, self.source_name, url)
        if response.status != 200:
            raise AdapterInvalidResponse(
                self.source_name, f"World Bank returned {response.status}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise AdapterInvalidResponse(
                self.source_name, "World Bank body was not JSON"
            ) from exc
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            raise AdapterInvalidResponse(
                self.source_name, "World Bank payload shape was not [meta, rows]"
            )
        meta = payload[0] if isinstance(payload[0], Mapping) else {}
        dataset_updated = _rfc3339(meta.get("lastupdated"))
        country_name = ""
        indicator_name = ""
        rows = payload[1]
        out: list[RawSourceResult] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            value = row.get("value")
            period = str(row.get("date") or "").strip()
            if value is None or not period:
                continue
            country_obj = row.get("country") if isinstance(row.get("country"), Mapping) else {}
            indicator_obj = row.get("indicator") if isinstance(row.get("indicator"), Mapping) else {}
            country_name = country_name or str(country_obj.get("value") or "")
            indicator_name = indicator_name or str(indicator_obj.get("value") or "")
            out.append(
                RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"world_bank:{country}:{indicator}:{period}",
                    url=f"https://data.worldbank.org/indicator/{indicator}?locations={country}",
                    title=f"{country_name or country} {indicator_name or indicator} ({period})",
                    text=(
                        f"{indicator_name or indicator}: {value} for "
                        f"{country_name or country} in {period}"
                    ),
                    author="World Bank",
                    published_at="",
                    market=country,
                    language="en",
                    query=query,
                    query_language="en",
                    raw_metadata={
                        "country": country,
                        "indicator": indicator,
                        "period": period,
                        "value": value,
                        "unit": str(row.get("unit") or ""),
                        "obs_status": str(row.get("obs_status") or ""),
                        "dataset_last_updated": dataset_updated,
                        "date_semantics": "observation_period",
                    },
                )
            )
            if len(out) == limit:
                break
        return out


@dataclass(frozen=True)
class SecEdgarAdapter:
    """SEC EDGAR full-text search over public filing metadata."""

    http_client: HttpClient | None = None
    max_per_query: int = 20
    source_name: str = "sec_edgar"

    def __post_init__(self) -> None:
        if self.http_client is None:
            object.__setattr__(self, "http_client", StdlibHttpClient())

    @property
    def name(self) -> str:
        return self.source_name

    def retrieve(
        self, plan: Mapping[str, object], request: Mapping[str, object]
    ) -> list[RawSourceResult]:
        query = _query(request, self.source_name)
        limit = _limit(request, self.max_per_query)
        params: dict[str, object] = {"q": f'"{query}"'}
        forms = request.get("forms") or plan.get("forms")
        if forms:
            params["forms"] = (
                ",".join(str(form) for form in forms)
                if isinstance(forms, (list, tuple))
                else str(forms)
            )
        start, end = _date_window(plan, request)
        if start and end:
            params.update({"dateRange": "custom", "startdt": start, "enddt": end})
        url = f"{_SEC_SEARCH_URL}?{urlencode(params)}"
        response = _get(self.http_client, self.source_name, url)
        if response.status != 200:
            raise AdapterInvalidResponse(self.source_name, f"SEC EDGAR returned {response.status}")
        try:
            payload = response.json()
        except Exception as exc:
            raise AdapterInvalidResponse(
                self.source_name, "SEC EDGAR body was not JSON"
            ) from exc
        hits = payload.get("hits") if isinstance(payload, Mapping) else None
        rows = hits.get("hits") if isinstance(hits, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterInvalidResponse(self.source_name, "SEC EDGAR payload missing hits")
        out: list[RawSourceResult] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            source = row.get("_source") if isinstance(row.get("_source"), Mapping) else {}
            hit_id = str(row.get("_id") or "")
            accession, _, filename = hit_id.partition(":")
            ciks = source.get("ciks") if isinstance(source.get("ciks"), list) else []
            if not accession or not filename or not ciks:
                continue
            cik = str(ciks[0]).lstrip("0") or str(ciks[0])
            file_date = str(source.get("file_date") or "").strip()
            if not file_date:
                continue
            names = source.get("display_names") if isinstance(source.get("display_names"), list) else []
            company = _plain(names[0] if names else "")
            form = str(source.get("form") or "").strip()
            items = source.get("items") if isinstance(source.get("items"), list) else []
            description = _plain(source.get("file_description"))
            text = " | ".join(
                part
                for part in (
                    company,
                    f"Form {form}" if form else "",
                    f"Items {', '.join(str(i) for i in items)}" if items else "",
                    description,
                )
                if part
            )
            out.append(
                RawSourceResult(
                    source=self.source_name,
                    source_type="page",
                    source_native_id=f"sec:{accession}:{filename}",
                    url=f"{_SEC_ARCHIVE_URL}/{cik}/{accession.replace('-', '')}/{filename}",
                    title=f"{company} {form}".strip() or f"SEC filing {accession}",
                    text=text,
                    author=company,
                    published_at=_rfc3339(file_date),
                    market=str(source.get("biz_locations") and source["biz_locations"][0] or "us"),
                    language="en",
                    query=query,
                    query_language="en",
                    raw_metadata={
                        "accession": accession,
                        "form": form,
                        "items": items,
                        "period_ending": str(source.get("period_ending") or ""),
                        "cik": str(ciks[0]),
                        "content_kind": "filing_metadata",
                        "date_semantics": "filing_date",
                    },
                )
            )
            if len(out) == limit:
                break
        return out


def build_open_data_adapter(name: str):
    """Factory hook for the verified open-data connectors only."""
    if name == "world_bank":
        return WorldBankAdapter()
    if name == "sec_edgar":
        return SecEdgarAdapter()
    if name == "polymarket":
        # Live probe could not reach gamma-api.polymarket.com from the build
        # environment; keep the candidate catalog-only rather than shipping an
        # untested connector.
        return None
    return None


__all__ = [
    "SecEdgarAdapter",
    "WorldBankAdapter",
    "build_open_data_adapter",
]
