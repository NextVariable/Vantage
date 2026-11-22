"""Absence (negative-claim) status model.

A research answer often needs to state that something does *not* exist:
no release, no public license, no independent user feedback, no
competitor. Such a claim is only defensible when a deterministic check
actually covered the object. This module separates five states:

  VERIFIED_ABSENT   a check covered the object and found nothing
  OUT_OF_WINDOW     the object exists but not inside the research window
  NOT_RETRIEVED     sources were searched but returned no such object
  SOURCE_UNAVAILABLE the source needed for the check failed
  UNVERIFIED        no check was performed

Only ``VERIFIED_ABSENT`` may be rendered as a definite absence. Every
other state is qualified in place (prefix/suffix) instead of deleting
the model's sentence, so information is preserved but not overstated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

VERIFIED_ABSENT = "verified_absent"
NOT_RETRIEVED = "not_retrieved"
SOURCE_UNAVAILABLE = "source_unavailable"
OUT_OF_WINDOW = "out_of_window"
UNVERIFIED = "unverified"

ALL_STATUSES = (
    VERIFIED_ABSENT,
    OUT_OF_WINDOW,
    NOT_RETRIEVED,
    SOURCE_UNAVAILABLE,
    UNVERIFIED,
)

#: Canonical object -> surface terms the model may use.
_OBJECT_TERMS: dict[str, tuple[str, ...]] = {
    "release": (
        "release", "releases", "released", "artifact", "artifacts",
        "version", "versions", "tag", "tags", "changelog", "publish",
        "published", "发布", "版本", "发行", "更新日志", "发布物",
    ),
    "license": (
        "license", "licence", "licenses", "licences",
        "许可证", "许可协议",
    ),
    "feedback": (
        "feedback", "user feedback", "review", "reviews",
        "user report", "user reports", "用户反馈", "反馈", "评价",
    ),
    "competitor": (
        "competitor", "competitors", "alternative", "alternatives",
        "竞品", "竞争对手",
    ),
}

_TERM_TO_OBJECT: dict[str, str] = {
    term: obj for obj, terms in _OBJECT_TERMS.items() for term in terms
}

#: Terms that look like object nouns but carry no absence meaning here.
_EXCLUSION_PATTERNS = (
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\bno doubt\b", re.IGNORECASE),
    re.compile(r"\bno (?:fewer|less) than\b", re.IGNORECASE),
    re.compile(r"\bnot only\b", re.IGNORECASE),
    re.compile(r"\b(?:cannot|can not|could not|unable to|not verified|unverified)\b", re.IGNORECASE),
)

_NEGATION_PATTERN = re.compile(
    r"\b(?:no|none|never|zero|without)\b"
    r"|\bthere (?:is|are|was|were)\s+no\b"
    r"|没有|并无|无任何|未发现|尚未|未有",
    re.IGNORECASE,
)

#: Sentence boundary that keeps the terminator on the preceding sentence.
_SENTENCE_RE = re.compile(r"[^.!?。！？;；]+[.!?。！？;；]?")

_TERMINATORS = ".!?;:。！？；："


@dataclass(frozen=True)
class AbsenceClaim:
    """One sentence-level absence assertion found in model text."""

    text: str
    object: str
    term: str


@dataclass(frozen=True)
class AbsenceContext:
    """What the engine deterministically knows about each object."""

    verified_objects: frozenset[str] = frozenset()
    source_unavailable: bool = False
    window_checked: bool = False
    searched: bool = True
    basis: tuple[str, ...] = ()

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[Mapping[str, object]],
        *,
        searched: bool = True,
    ) -> "AbsenceContext":
        """Build context from GitHub release/license observations.

        ``verified_absent`` is object-scoped: one repository returning
        zero releases cannot prove a market-wide absence, so callers
        should only pass observations whose scope matches the claim.
        """
        verified: set[str] = set()
        present: set[str] = set()
        checked: dict[str, int] = {}
        unavailable = False
        window_checked = False
        basis: list[str] = []
        for obs in observations:
            kind = str(obs.get("kind") or "")
            status = str(obs.get("status") or "")
            obj = "release" if kind == "releases" else "license" if kind == "license" else ""
            if not obj:
                continue
            checked[obj] = checked.get(obj, 0) + 1
            if status == "present":
                present.add(obj)
                continue
            if status == VERIFIED_ABSENT:
                verified.add(obj)
                basis.append(str(obs.get("detail") or f"{kind}: verified absent"))
            elif status == "only_outside_window":
                window_checked = True
                basis.append(str(obs.get("detail") or f"{kind}: only outside window"))
            elif status in {
                "rate_limited", "auth_missing", "timeout", "unavailable",
                "invalid_response", "forbidden", "not_found",
            }:
                unavailable = True
                basis.append(str(obs.get("detail") or f"{kind}: {status}"))
        # A per-repository zero count is not market-wide absence. Only call
        # the object verified when every checked candidate was absent and
        # the sample covers more than a single repository.
        verified = {
            obj for obj in verified
            if obj not in present and checked.get(obj, 0) >= 2
        }
        return cls(
            verified_objects=frozenset(verified),
            source_unavailable=unavailable,
            window_checked=window_checked,
            searched=searched,
            basis=tuple(basis),
        )

    def for_object(self, obj: str) -> "AbsenceContext":
        """Scope a run-level context to one object.

        A verified absence only applies to the object it covers. Failure
        and window flags stay global because they block every check.
        """
        return AbsenceContext(
            verified_objects=frozenset({obj}) if obj in self.verified_objects else frozenset(),
            source_unavailable=self.source_unavailable,
            window_checked=self.window_checked,
            searched=self.searched,
            basis=self.basis,
        )


def _sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


def _excluded(sentence: str) -> bool:
    return any(p.search(sentence) for p in _EXCLUSION_PATTERNS)


def detect_absence_claims(text: str) -> tuple[AbsenceClaim, ...]:
    """Return sentence-level absence assertions, excluding false friends."""
    claims: list[AbsenceClaim] = []
    value = str(text or "")
    for sentence in _sentences(value):
        if _excluded(sentence):
            continue
        if not _NEGATION_PATTERN.search(sentence):
            continue
        lowered = sentence.lower()
        seen_objects: set[str] = set()
        for term, obj in _TERM_TO_OBJECT.items():
            if obj in seen_objects:
                continue
            if re.search(rf"\b{re.escape(term)}\b", lowered) or term in sentence:
                claims.append(AbsenceClaim(text=sentence, object=obj, term=term))
                seen_objects.add(obj)
    return tuple(claims)


def classify_absence(
    obj: str,
    *,
    verified_absent: bool,
    source_unavailable: bool,
    window_checked: bool,
    searched: bool,
) -> str:
    """Map known facts about one object onto the five-state vocabulary."""
    if verified_absent:
        return VERIFIED_ABSENT
    if source_unavailable:
        return SOURCE_UNAVAILABLE
    if window_checked:
        return OUT_OF_WINDOW
    if searched:
        return NOT_RETRIEVED
    return UNVERIFIED


def _prefix_for(status: str) -> str:
    if status == OUT_OF_WINDOW:
        return "Within the research window: "
    if status == SOURCE_UNAVAILABLE:
        return "Absence not verified (source unavailable): "
    return "Unverified absence: "


def _suffix_for(status: str) -> str:
    if status in (NOT_RETRIEVED, UNVERIFIED):
        return " (absence not established; scoped to retrieved evidence)"
    return ""


def qualify_text(
    text: str,
    *,
    context: AbsenceContext,
) -> tuple[str, tuple[dict, ...]]:
    """Qualify unverified absence claims without deleting their content.

    Returns the rewritten text and machine-readable checks. A sentence
    containing only verified absences is left untouched.
    """
    value = str(text or "")
    claims = detect_absence_claims(value)
    if not claims:
        return value, ()

    checks: list[dict] = []
    status_by_sentence: dict[str, str] = {}
    for claim in claims:
        scoped = context.for_object(claim.object)
        status = classify_absence(
            claim.object,
            verified_absent=claim.object in scoped.verified_objects,
            source_unavailable=scoped.source_unavailable,
            window_checked=scoped.window_checked,
            searched=scoped.searched,
        )
        checks.append(
            {
                "object": claim.object,
                "status": status,
                "claim": claim.text,
                "basis": list(scoped.basis),
            }
        )
        if status != VERIFIED_ABSENT:
            status_by_sentence.setdefault(claim.text, status)

    if not status_by_sentence:
        return value, tuple(checks)

    rewritten: list[str] = []
    for sentence in _sentences(value):
        status = status_by_sentence.get(sentence)
        if status is None:
            rewritten.append(sentence)
            continue
        body = sentence.rstrip()
        if body and body[-1] in _TERMINATORS:
            body = body[:-1]
        body = f"{_prefix_for(status)}{body}{_suffix_for(status)}"
        if sentence and sentence[-1] in _TERMINATORS:
            body += sentence[-1]
        rewritten.append(body)
    return " ".join(rewritten), tuple(checks)


def summary_line(checks: Sequence[Mapping[str, object]]) -> str:
    """Compact deterministic summary for brief/coverage rendering."""
    if not checks:
        return ""
    parts = [f"{c.get('object')}: {c.get('status')}" for c in checks]
    return "; ".join(parts)


def has_unverified_absence(text: str) -> bool:
    """True when text contains an absence assertion (for regression tests)."""
    return bool(detect_absence_claims(text))


__all__ = [
    "VERIFIED_ABSENT",
    "NOT_RETRIEVED",
    "SOURCE_UNAVAILABLE",
    "OUT_OF_WINDOW",
    "UNVERIFIED",
    "ALL_STATUSES",
    "AbsenceClaim",
    "AbsenceContext",
    "detect_absence_claims",
    "classify_absence",
    "qualify_text",
    "summary_line",
    "has_unverified_absence",
]
