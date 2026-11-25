"""Bounded multi-route retrieval for one platform.

A platform can be reachable through several legal routes (a free public
endpoint, a local CLI, and an authorized provider). ``FallbackAdapter`` tries
them in a fixed order and stops as soon as the free route has produced enough
evidence.

Rules:

* the free route is always tried first;
* a paid route runs only when its adapter was constructed (a credential is
  configured), the budget allows it, and the free route produced too little;
* failures are recorded, never retried in a loop;
* items already retrieved are kept when a later route fails;
* the same physical item reached through two routes is returned once — the
  dedupe key is the platform-native id (with ``t3_``/``t1_`` prefixes
  normalised) or the canonical URL;
* every item records the actual route in ``raw_metadata['access_route']``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Mapping

from ..ids import canonicalize_url
from ._paid import paid_available
from ..pipeline.adapters import AdapterError, RawSourceResult


def _paid_call_budget() -> int:
    raw = os.environ.get("VANTAGE_PAID_FALLBACK_CALLS", "10").strip()
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 10


def _paid_enabled() -> bool:
    return os.environ.get("VANTAGE_DISABLE_PAID_FALLBACK", "").strip().lower() not in (
        "1", "true", "yes", "on",
    )


@dataclass(frozen=True)
class Route:
    name: str
    adapter: object
    paid: bool = False


def _native_key(item: RawSourceResult) -> str:
    native = item.source_native_id.strip()
    if native.startswith(("t3_", "t1_")):
        native = native[3:]
    if native:
        return f"native:{native}"
    return f"url:{canonicalize_url(item.url)}"


@dataclass
class FallbackAdapter:
    source_name: str
    routes: tuple[Route, ...]
    minimum_results: int = 1
    paid_call_budget: int = field(default_factory=_paid_call_budget)
    paid_enabled: bool = field(default_factory=_paid_enabled)
    limitations: list[str] = field(default_factory=list, compare=False)
    route_history: list[dict[str, object]] = field(default_factory=list, compare=False)
    _paid_calls: int = field(default=0, init=False, repr=False)

    @property
    def name(self) -> str:
        return self.source_name

    def _note(self, message: str) -> None:
        if message not in self.limitations:
            self.limitations.append(message)

    def retrieve(
        self, plan: Mapping[str, object], request: Mapping[str, object]
    ) -> list[RawSourceResult]:
        collected: list[RawSourceResult] = []
        seen: set[str] = set()
        self.route_history = []
        for route in self.routes:
            if route.paid:
                if not self.paid_enabled or not paid_available():
                    self._note(f"route {route.name} skipped: paid fallback disabled")
                    continue
                if self._paid_calls >= self.paid_call_budget:
                    self._note(f"route {route.name} skipped: paid call budget reached")
                    continue
            if route.paid:
                self._paid_calls += 1
            try:
                out = list(route.adapter.retrieve(plan=plan, request=request))  # type: ignore[attr-defined]
            except AdapterError as exc:
                self.route_history.append({
                    "route": route.name, "status": "failed",
                    "reason": type(exc).__name__, "paid": route.paid,
                })
                self._note(f"route {route.name} failed: {type(exc).__name__}")
                continue
            kept = 0
            for item in out:
                key = _native_key(item)
                if key in seen:
                    continue
                seen.add(key)
                metadata = dict(item.raw_metadata)
                metadata["access_route"] = route.name
                metadata.setdefault("route", route.name)
                collected.append(replace(item, raw_metadata=metadata))
                kept += 1
            self.route_history.append({
                "route": route.name, "status": "returned",
                "items": kept, "paid": route.paid,
            })
            if len(collected) >= self.minimum_results:
                break
        summary = ", ".join(
            f"{row['route']}:{row['status']}"
            + (f"({row.get('items')})" if row["status"] == "returned" else "")
            for row in self.route_history
        )
        if summary:
            self._note(f"source {self.source_name} routes: {summary}")
        return collected


__all__ = ["FallbackAdapter", "Route"]
