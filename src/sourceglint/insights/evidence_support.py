"""Claim → Evidence → Source Excerpt support contract.

A citation id being valid is not the same as the citation supporting the
claim. This module checks the support relationship deterministically:

  * the cited evidence exists in the ledger;
  * the quoted excerpt literally occurs in that evidence's own text;
  * the excerpt is contiguous (a pasted-together quote fails);
  * the claim and the excerpt share enough content to be about the same
    thing (a lexical gate, not a claim of semantic entailment);
  * a vendor announcement only supports "the vendor states X" — it never
    proves an independent test;
  * copies from one origin do not become multiple independent sources.

Semantic entailment is verified by an explicit, separately budgeted model
stage (``claim_support_verification``). When that stage is unavailable the
fact is reported as ``supported``/unverified, never as ``verified``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

#: Minimum normalized excerpt length accepted as a real quotation.
MIN_EXCERPT_CHARS = 20
#: Content-token overlap needed for a deterministic "direct" / "partial" read.
DIRECT_OVERLAP = 0.6
PARTIAL_OVERLAP = 0.3
#: How many characters of either side of a quote are relevant for locality.
_EXCERPT_WINDOW = 240

_STOPWORDS = frozenset(
    """a an and are as at be been being but by for from had has have how in
    into is it its may more most not of on or other our over such than that
    the their them then there these they this those to under up was were
    what when where which while who will with would you your""".split()
)
_CJK = re.compile(r"[\u3400-\u9fff]")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#-]*")
_SENTENCE = re.compile(r"[^.!?。！？\n]+[.!?。！？]?")
_VENDOR_HINTS = (
    "independent test", "independently tested", "third-party test",
    "benchmark result", "we measured", "we tested", "our test",
    "独立测试", "第三方测试", "实测",
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def content_tokens(text: str) -> set[str]:
    """Latin word tokens plus CJK bigrams (no model, no locale)."""
    lowered = (text or "").lower()
    tokens = {
        word for word in _WORD.findall(lowered)
        if len(word) >= 3 and word not in _STOPWORDS
    }
    cjk = "".join(_CJK.findall(lowered))
    for index in range(len(cjk) - 1):
        tokens.add(cjk[index:index + 2])
    return tokens


def overlap_ratio(claim: str, excerpt: str) -> float:
    claim_tokens = content_tokens(claim)
    if not claim_tokens:
        return 0.0
    excerpt_tokens = content_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0
    return len(claim_tokens & excerpt_tokens) / len(claim_tokens)


def evidence_text(ev: Mapping[str, Any] | None) -> str:
    if not ev:
        return ""
    parts = [str(ev.get(key) or "") for key in ("title", "snippet", "content")]
    return "\n".join(part for part in parts if part)


def is_vendor_material(ev: Mapping[str, Any] | None) -> bool:
    """True when the item is published by the vendor itself."""
    if not ev:
        return False
    metadata = ev.get("raw_metadata")
    if isinstance(metadata, Mapping) and bool(metadata.get("official")):
        return True
    if str(ev.get("source") or "") == "official_web":
        return True
    role = str(ev.get("source_role") or "")
    return role in {"vendor_claim_verified", "vendor_claim_unverified"}


def _origin(ev: Mapping[str, Any] | None) -> str:
    if not ev:
        return ""
    url = str(ev.get("url") or "")
    if url:
        match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/]+)", url)
        if match:
            return match.group(1).lower()
        return url.lower()
    return str(ev.get("source") or "").lower()


def independent_origin_count(
    evidence_ids: Sequence[str],
    evidence_by_id: Mapping[str, Any],
) -> int:
    origins = {
        _origin(evidence_by_id.get(eid))
        for eid in evidence_ids
        if eid in evidence_by_id and not is_vendor_material(evidence_by_id.get(eid))
    }
    origins.discard("")
    return len(origins)


@dataclass(frozen=True)
class ClaimSupport:
    claim: str
    evidence_id: str
    excerpt: str
    verdict: str  # direct | partial | conflicting | unrelated | unverifiable
    reasons: tuple[str, ...] = ()
    independent: bool = True

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "evidence_id": self.evidence_id,
            "excerpt": self.excerpt,
            "verdict": self.verdict,
            "independent": self.independent,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class FactSupport:
    status: str  # verified | supported | partial | vendor_only | unverified | conflicting
    claims: tuple[ClaimSupport, ...] = ()
    reasons: tuple[str, ...] = ()
    independent_origins: int = 0
    semantic_status: str = "not_run"
    rejected: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "claims": [claim.to_dict() for claim in self.claims],
            "reasons": list(self.reasons),
            "independent_origins": self.independent_origins,
            "semantic_status": self.semantic_status,
            "rejected": self.rejected,
        }


def _best_excerpt(claim: str, text: str) -> str:
    """Pick the contiguous sentence-ish window with the best token overlap."""
    normalized = normalize(text)
    best = ""
    best_ratio = 0.0
    for sentence in _SENTENCE.findall(normalized):
        candidate = sentence.strip()
        if len(candidate) < MIN_EXCERPT_CHARS:
            continue
        ratio = overlap_ratio(claim, candidate)
        if ratio > best_ratio:
            best, best_ratio = candidate, ratio
    if best:
        return best[:_EXCERPT_WINDOW]
    return normalized[:_EXCERPT_WINDOW]


def _claim_support(
    claim: str,
    evidence_id: str,
    excerpt: str,
    evidence_by_id: Mapping[str, Any],
) -> ClaimSupport:
    ev = evidence_by_id.get(evidence_id)
    independent = not is_vendor_material(ev)
    if ev is None:
        return ClaimSupport(claim, evidence_id, excerpt, "unverifiable",
                            ("evidence id is not in the ledger",), independent)
    source = normalize(evidence_text(ev))
    quote = normalize(excerpt)
    if not quote:
        return ClaimSupport(claim, evidence_id, excerpt, "unverifiable",
                            ("no excerpt was supplied",), independent)
    if len(quote) < MIN_EXCERPT_CHARS:
        return ClaimSupport(claim, evidence_id, excerpt, "unverifiable",
                            ("excerpt is too short to locate",), independent)
    if quote not in source:
        # Catches paraphrased quotes and two unrelated passages pasted together.
        return ClaimSupport(claim, evidence_id, excerpt, "unverifiable",
                            ("excerpt does not occur verbatim in the cited evidence",),
                            independent)
    ratio = overlap_ratio(claim, quote)
    if ratio >= DIRECT_OVERLAP:
        return ClaimSupport(claim, evidence_id, excerpt, "direct", (), independent)
    if ratio >= PARTIAL_OVERLAP:
        return ClaimSupport(claim, evidence_id, excerpt, "partial",
                            (f"claims more than the excerpt states (overlap {ratio:.2f})",),
                            independent)
    return ClaimSupport(claim, evidence_id, excerpt, "unrelated",
                        (f"excerpt is about something else (overlap {ratio:.2f})",),
                        independent)


def verify_fact_support(
    statement: str,
    evidence_ids: Sequence[str],
    claims: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Any],
) -> FactSupport:
    """Deterministic verification of one fact's claim/excerpt/citation chain."""
    evidence_ids = tuple(dict.fromkeys(str(eid) for eid in evidence_ids))
    supports: list[ClaimSupport] = []
    explicit = [
        row for row in claims
        if isinstance(row, Mapping) and str(row.get("evidence_id") or "")
    ]
    if explicit:
        for row in explicit:
            supports.append(_claim_support(
                str(row.get("claim") or statement),
                str(row.get("evidence_id")),
                str(row.get("excerpt") or ""),
                evidence_by_id,
            ))
    else:
        # Legacy host: no claim breakdown was supplied. Code selects a
        # contiguous excerpt itself, which can establish a structural match
        # but is never reported as fully verified on its own.
        union_text = "\n".join(evidence_text(evidence_by_id.get(eid)) for eid in evidence_ids)
        composite_overlap = overlap_ratio(statement, union_text)
        for eid in evidence_ids:
            ev = evidence_by_id.get(eid)
            text = evidence_text(ev)
            if not text:
                continue
            excerpt = _best_excerpt(statement, text)
            support = _claim_support(statement, eid, excerpt, evidence_by_id)
            if support.verdict in {"direct", "partial"}:
                support = ClaimSupport(
                    support.claim, support.evidence_id, support.excerpt, "partial",
                    (*support.reasons, "claim-level excerpt was not supplied by the host"),
                    support.independent,
                )
            elif support.verdict == "unrelated" and composite_overlap:
                # One excerpt often supports only part of a cross-source
                # statement; the fact as a whole is judged on the union.
                support = ClaimSupport(
                    support.claim, support.evidence_id, support.excerpt, "partial",
                    (*support.reasons, "supports part of the aggregated statement"),
                    support.independent,
                )
            supports.append(support)
        if composite_overlap == 0.0:
            supports = [
                ClaimSupport(s.claim, s.evidence_id, s.excerpt, "unrelated", s.reasons, s.independent)
                for s in supports
            ]

    origins = independent_origin_count(evidence_ids, evidence_by_id)
    vendor_only = bool(evidence_ids) and all(
        is_vendor_material(evidence_by_id.get(eid)) for eid in evidence_ids
    )
    reasons: list[str] = []

    if not supports:
        return FactSupport("unverified", (), ("no usable excerpt for the cited evidence",), origins, rejected=True)

    if any(s.verdict == "unrelated" for s in supports):
        return FactSupport(
            "unverified", tuple(supports),
            ("a cited evidence item does not support the statement",), origins,
            rejected=True,
        )
    if any(s.verdict == "unverifiable" for s in supports):
        return FactSupport(
            "unverified", tuple(supports),
            tuple(dict.fromkeys(r for s in supports if s.verdict == "unverifiable" for r in s.reasons)),
            origins, rejected=True,
        )

    if vendor_only:
        lowered = (statement or "").lower()
        if any(hint in lowered for hint in _VENDOR_HINTS):
            return FactSupport(
                "unverified", tuple(supports),
                ("vendor material cannot establish an independent test",), origins,
                rejected=True,
            )
        return FactSupport(
            "vendor_only", tuple(supports),
            ("only vendor-published material supports this statement",), origins,
        )

    if all(s.verdict == "partial" for s in supports):
        return FactSupport("partial", tuple(supports), reasons, origins)
    corroboration_claim = any(
        hint in (statement or "").lower()
        for hint in ("independent source", "multiple source", "several source",
                     "cross-source", "independently confirmed", "多源", "多方")
    )
    if origins < 2 and corroboration_claim:
        reasons.append("claims independent corroboration but cites a single origin")
        return FactSupport("partial", tuple(supports), tuple(reasons), origins)
    return FactSupport("supported", tuple(supports), tuple(reasons), origins)


def apply_semantic_verdicts(
    support: FactSupport,
    verdicts: Sequence[Mapping[str, Any]],
) -> FactSupport:
    """Merge the explicit semantic stage into a deterministic support result.

    Only a ``supported`` verdict can upgrade the fact to ``verified``; a
    missing, partial or conflicting verdict never can.
    """
    by_index = {
        int(row.get("claim_index", -1)): str(row.get("verdict") or "")
        for row in verdicts
        if isinstance(row, Mapping)
    }
    if not by_index:
        return FactSupport(
            support.status, support.claims, (*support.reasons, "semantic verification returned no verdicts"),
            support.independent_origins, "unavailable",
        )
    claims: list[ClaimSupport] = []
    conflicts = False
    unverified = False
    for index, claim in enumerate(support.claims):
        verdict = by_index.get(index, "")
        if verdict == "conflicting":
            conflicts = True
            claims.append(ClaimSupport(claim.claim, claim.evidence_id, claim.excerpt,
                                       "conflicting", (*claim.reasons, "semantic verifier reports conflicting evidence"),
                                       claim.independent))
        elif verdict in {"unrelated", "unverifiable", ""}:
            unverified = True
            claims.append(ClaimSupport(claim.claim, claim.evidence_id, claim.excerpt,
                                       "unverifiable", (*claim.reasons, "semantic verifier did not confirm support"),
                                       claim.independent))
        else:
            claims.append(claim)
    if conflicts:
        return FactSupport("conflicting", tuple(claims), (*support.reasons, "semantic verifier reports a conflict"),
                           support.independent_origins, "conflicting")
    if unverified:
        return FactSupport("partial", tuple(claims), (*support.reasons, "semantic verifier did not confirm every claim"),
                           support.independent_origins, "partial")
    if support.status == "supported":
        return FactSupport("verified", tuple(claims), support.reasons,
                           support.independent_origins, "supported")
    return FactSupport(support.status, tuple(claims), support.reasons,
                       support.independent_origins, "supported")
