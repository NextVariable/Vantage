"""Bounded, extractive coverage for explicitly named competitors."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

DIMENSIONS = ("Product updates and availability", "Positioning and intended workflows",
              "Firsthand use and counterexamples")
_POSITIONING = re.compile(r"\b(?:designed for|built for|aimed at|targeted at|positioned as)\b", re.I)
_FIRSTHAND = re.compile(
    r"\b(?:i|we)\s+(?:used|use|tried|tested|installed|switched|stopped|found|experienced)\b|"
    r"\b(?:i've|we've)\s+(?:used|tried|tested|installed|switched)\b|実際に使|使ってみ|我用|我试",
    re.I,
)
_GENERIC = {"ai", "app", "tool", "assistant", "editor", "platform", "software"}


def _words(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[^\W_]+", value.casefold()))


def _contains(text: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    return bool(phrase) and any(text[i:i + len(phrase)] == phrase for i in range(len(text)))


def collect_comparison(query, plan, ledger) -> tuple[tuple[str, ...], list[dict]]:
    """Select literal, product-attributable observations without assigning new FACTs."""
    question = _words(query)
    products = []
    names = set()
    for product in (*(plan.get("research_objects") or ()), *(plan.get("entities") or ())):
        if not isinstance(product, str):
            continue
        name = _words(product)
        specific = tuple(word for word in name if word not in _GENERIC)
        if specific and specific not in names and _contains(question, name):
            products.append(product)
            names.add(specific)
    products = products[:4]
    if len(products) < 2:
        return (), []

    rows = []
    for item in ledger:
        row = item.to_payload()
        title = _words(item.title)
        excerpt = str(row.get("snippet") or row.get("content") or "").strip()
        if not excerpt or not item.url or not item.published_at or row.get("window") == "baseline":
            continue
        location = urlsplit(item.url)
        host = (location.hostname or "").split(".")[:-1]
        shared_hosting = location.hostname in {"github.com", "gitlab.com", "codeberg.org", "medium.com", "substack.com"}
        kind = row.get("source_type")
        publisher_owner = (
            location.path.split("/")[1].casefold()
            if shared_hosting and "/releases/" in location.path else ""
        )

        for product in products:
            name = _words(product)
            brand = name[0]
            specific = tuple(word for word in name if word not in _GENERIC)
            if not specific:
                continue
            title_matches = _contains(title, name) or _contains(title, specific)
            site_matches = brand in host and not shared_hosting or publisher_owner == brand
            description_matches = len(specific) == 1 or any(word in title or word in host for word in specific[1:])
            if kind in {"release", "page"} and (
                (site_matches and description_matches and (kind == "release" or
                 any(part in location.path.lower() for part in ("/changelog", "/release-notes", "/releases"))))
                or (row.get("source") == "official_web" and title_matches)
            ):
                rows.append({"product": product, "dimension": DIMENSIONS[0],
                             "id": item.evidence_id, "label": "Publisher excerpt",
                             "text": excerpt})
                if _POSITIONING.search(excerpt):
                    rows.append({"product": product, "dimension": DIMENSIONS[1],
                                 "id": item.evidence_id, "label": "Publisher excerpt",
                                 "text": excerpt})
            elif kind in {"post", "comment", "review", "page"} and (
                any(
                    _FIRSTHAND.search(sentence) and _contains(_words(sentence), specific)
                    for sentence in re.split(r"[.!?。！？\n]", excerpt)
                )
            ):
                rows.append({"product": product, "dimension": DIMENSIONS[2],
                             "id": item.evidence_id, "label": "First-person account",
                             "text": excerpt})
    return tuple(products), rows
