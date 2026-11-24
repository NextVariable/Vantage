"""Explicit semantic verification of claim support.

This is deliberately a separate stage with its own budget gate: it is the only
place allowed to turn a structurally supported FACT into a ``verified`` FACT.
It is never treated as an unquestionable proof — a failed or unavailable call
leaves the fact unverified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..intelligence.model import ModelResponse
from .model import CLAIM_VERIFICATION_RESPONSE_SCHEMA, TASK_CLAIM_VERIFICATION
from .prompts import get_insight_prompt

_VERDICTS = {"supported", "partial", "conflicting", "unrelated", "unverifiable"}


@dataclass(frozen=True)
class ClaimVerificationResult:
    verdicts: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()
    model_status: str = "unavailable"


def verify_claims(
    rows: Sequence[Mapping[str, Any]],
    model: Any,
) -> ClaimVerificationResult:
    """Ask the verifier for one verdict per prepared claim row.

    ``rows`` carry no URLs, titles or raw metadata: only the claim, the quote
    and whether the publisher is the vendor itself.
    """
    if not rows:
        return ClaimVerificationResult(model_status="skipped")
    payload = {"claims": [dict(row) for row in rows]}
    try:
        prompt = get_insight_prompt(TASK_CLAIM_VERIFICATION)
        payload["prompt"] = prompt.render()
    except (FileNotFoundError, KeyError):
        pass  # prompt is optional for offline hosts

    response: ModelResponse = model.complete_structured(
        task=TASK_CLAIM_VERIFICATION,
        payload=payload,
        response_schema=CLAIM_VERIFICATION_RESPONSE_SCHEMA,
    )
    if not response.ok:
        return ClaimVerificationResult(
            warnings=(f"claim_support_verification: model {response.status.value}: {response.error}",),
            model_status=response.status.value,
        )
    raw = response.rows("verifications")
    if raw is None:
        return ClaimVerificationResult(
            warnings=("claim_support_verification: invalid verifications array",),
            model_status="invalid_output",
        )
    limit = len(rows)
    verdicts: dict[int, dict] = {}
    duplicates: set[int] = set()
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        try:
            index = int(row.get("claim_index", -1))
        except (TypeError, ValueError):
            continue
        verdict = str(row.get("verdict") or "")
        if index < 0 or index >= limit or verdict not in _VERDICTS:
            continue
        if index in verdicts:
            duplicates.add(index)
        verdicts[index] = {
            "claim_index": index,
            "verdict": verdict,
            "rationale": str(row.get("rationale") or ""),
        }
    for index in duplicates:
        verdicts.pop(index)
    status = "success" if len(verdicts) == limit else "partial" if verdicts else "invalid_output"
    return ClaimVerificationResult(
        verdicts=tuple(verdicts.values()),
        warnings=() if status == "success" else ("claim_support_verification: missing or ambiguous verdicts",),
        model_status=status,
    )
