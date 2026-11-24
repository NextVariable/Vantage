"""Claim → Evidence → Excerpt support contract regressions."""
from __future__ import annotations

from dataclasses import dataclass

from sourceglint.insights.claim_verification import verify_claims
from sourceglint.insights.evidence_support import (
    apply_semantic_verdicts,
    independent_origin_count,
    verify_fact_support,
)
from sourceglint.intelligence.model import ModelResponse, ModelStatus


def ev(
    evidence_id: str,
    text: str,
    *,
    url: str = "https://example.com/a",
    source: str = "hacker_news",
    official: bool = False,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "title": "Source item",
        "snippet": text,
        "url": url,
        "source": source,
        "raw_metadata": {"official": official},
    }


def claim(text: str, evidence_id: str, excerpt: str) -> dict:
    return {"claim": text, "evidence_id": evidence_id, "excerpt": excerpt}


def test_a_valid_but_unrelated_evidence_id_is_rejected():
    evidence = {"ev1": ev("ev1", "The toolbar color changed from blue to green.")}
    support = verify_fact_support(
        "The tool runs fully offline without any network access.",
        ("ev1",), (), evidence,
    )
    assert support.rejected
    assert support.status == "unverified"
    assert any("unrelated" in reason or "does not support" in reason
               for reason in support.reasons)


def test_offline_claim_citing_a_toolbar_change_is_rejected():
    evidence = {"ev1": ev("ev1", "Version 4 changes the toolbar color to blue.")}
    support = verify_fact_support(
        "The product works completely offline and never phones home.",
        ("ev1",),
        [claim("The product works completely offline.",
               "ev1", "Version 4 changes the toolbar color to blue.")],
        evidence,
    )
    assert support.rejected
    assert support.status == "unverified"


def test_real_quote_that_overstates_its_scope_is_only_partial():
    text = "The new interpreter is sub-second for Japanese in our staging test."
    evidence = {"ev1": ev("ev1", text)}
    support = verify_fact_support(
        "The new interpreter has sub-second latency for all users worldwide.",
        ("ev1",),
        [claim("The new interpreter has sub-second latency for all users worldwide.",
               "ev1", text)],
        evidence,
    )
    assert not support.rejected
    assert support.status == "partial"
    assert support.claims[0].verdict == "partial"
    assert any("claims more" in reason for reason in support.claims[0].reasons)


def test_two_unrelated_passages_pasted_together_are_detected():
    text = ("Alpha beta gamma delta. A separate paragraph about pricing. "
            "Zeta eta theta iota.")
    evidence = {"ev1": ev("ev1", text)}
    support = verify_fact_support(
        "The release is fast and cheap.",
        ("ev1",),
        [claim("The release is fast and cheap.", "ev1",
               "Alpha beta gamma delta. Zeta eta theta iota.")],
        evidence,
    )
    assert support.rejected
    assert any("verbatim" in reason for reason in support.reasons)


def test_vendor_announcement_cannot_pose_as_an_independent_test():
    text = "Our new tool achieves 3x faster builds in our internal tests."
    evidence = {"ev1": ev("ev1", text, official=True)}
    support = verify_fact_support(
        "The tool was independently tested and achieved 3x faster builds.",
        ("ev1",),
        [claim("The tool was independently tested and achieved 3x faster builds.",
               "ev1", text)],
        evidence,
    )
    assert support.rejected
    assert any("independent test" in reason for reason in support.reasons)


def test_vendor_statement_is_reported_as_a_vendor_claim_only():
    text = "Our new tool achieves 3x faster builds in our internal tests."
    evidence = {"ev1": ev("ev1", text, official=True)}
    support = verify_fact_support(
        "The vendor states the tool is 3x faster at builds.",
        ("ev1",),
        [claim("The vendor states the tool is 3x faster at builds.", "ev1", text)],
        evidence,
    )
    assert not support.rejected
    assert support.status == "vendor_only"
    assert support.independent_origins == 0


def test_multiple_vendor_announcements_are_not_independent_sources():
    text = "Our platform now supports offline mode."
    evidence = {
        "ev1": ev("ev1", text, url="https://vendor.example/news/1", official=True),
        "ev2": ev("ev2", text, url="https://vendor.example/news/2", official=True),
    }
    support = verify_fact_support(
        "Two independent sources confirm the platform supports offline mode.",
        ("ev1", "ev2"),
        [claim("Two independent sources confirm the platform supports offline mode.",
               "ev1", text),
         claim("A second source confirms offline mode.", "ev2", text)],
        evidence,
    )
    assert support.rejected or support.status in {"vendor_only", "partial"}
    assert support.independent_origins == 0
    assert independent_origin_count(("ev1", "ev2"), evidence) == 0


def test_same_origin_repost_is_not_counted_twice():
    text = "The release notes mention a new offline mode."
    evidence = {
        "ev1": ev("ev1", text, url="https://blog.example/post"),
        "ev2": ev("ev2", text, url="https://blog.example/mirror"),
    }
    assert independent_origin_count(("ev1", "ev2"), evidence) == 1
    support = verify_fact_support(
        "The release notes mention a new offline mode.",
        ("ev1", "ev2"), (), evidence,
    )
    assert support.status in {"supported", "partial"}
    assert support.independent_origins == 1


def test_direct_sufficient_citation_passes():
    text = "OpenCode Plus shipped release v1.2 on 2026-10-01."
    evidence = {"ev1": ev("ev1", text, url="https://github.com/opencode/releases")}
    support = verify_fact_support(
        "OpenCode Plus shipped release v1.2 on 2026-10-01.",
        ("ev1",),
        [claim("OpenCode Plus shipped release v1.2 on 2026-10-01.", "ev1", text)],
        evidence,
    )
    assert not support.rejected
    assert support.status == "supported"
    assert support.claims[0].verdict == "direct"


def test_cross_language_verbatim_quote_is_unverified_not_rejected():
    """A Chinese claim over an English quote is genuine but needs semantics."""
    text = "OpenCode Plus shipped release v1.2 on 2026-10-01."
    evidence = {"ev1": ev("ev1", text)}
    statement = "OpenCode Plus 于 2026-10-01 发布了 v1.2 版本。"
    support = verify_fact_support(
        statement, ("ev1",), [claim(statement, "ev1", text)], evidence
    )
    assert not support.rejected
    assert support.status == "unverified"
    assert support.claims[0].verdict == "needs_semantic"

    unavailable = apply_semantic_verdicts(support, ())
    assert unavailable.status == "unverified"

    verified = apply_semantic_verdicts(support, [{"claim_index": 0, "verdict": "supported"}])
    assert verified.status == "verified"


def test_same_language_unrelated_quote_is_still_rejected():
    text = "版本更新把工具栏从蓝色改成了绿色，并新增了三个快捷键。"
    evidence = {"ev1": ev("ev1", text)}
    support = verify_fact_support(
        "该产品完全离线运行，不需要任何网络连接。",
        ("ev1",),
        [claim("该产品完全离线运行，不需要任何网络连接。", "ev1", text)],
        evidence,
    )
    assert support.rejected
    assert support.claims[0].verdict == "unrelated"


def test_semantic_stage_is_the_only_path_to_verified():
    text = "OpenCode Plus shipped release v1.2 on 2026-10-01."
    evidence = {"ev1": ev("ev1", text)}
    support = verify_fact_support(
        "OpenCode Plus shipped release v1.2 on 2026-10-01.",
        ("ev1",),
        [claim("OpenCode Plus shipped release v1.2 on 2026-10-01.", "ev1", text)],
        evidence,
    )
    assert support.status == "supported"

    unavailable = apply_semantic_verdicts(support, ())
    assert unavailable.status == "supported"
    assert unavailable.semantic_status == "unavailable"

    verified = apply_semantic_verdicts(
        support, [{"claim_index": 0, "verdict": "supported"}]
    )
    assert verified.status == "verified"
    assert verified.semantic_status == "supported"


def test_legacy_host_without_claims_can_never_be_fully_verified():
    text = "OpenCode Plus shipped release v1.2 on 2026-10-01."
    evidence = {"ev1": ev("ev1", text)}
    support = verify_fact_support(
        "OpenCode Plus shipped release v1.2 on 2026-10-01.",
        ("ev1",), (), evidence,
    )
    assert not support.rejected
    assert support.status in {"partial", "supported"}
    assert all(
        "claim-level excerpt was not supplied by the host" in claim.reasons
        for claim in support.claims
    )


@dataclass
class VerifierModel:
    payload: dict

    def complete_structured(self, *, task, payload, response_schema):
        return ModelResponse(task=task, status=ModelStatus.SUCCESS, payload=self.payload)


def test_claim_verification_filters_bad_indices_and_verdicts():
    rows = [{"claim_index": 0, "claim": "a", "excerpt": "b", "source_role": "independent"}]
    result = verify_claims(rows, VerifierModel({"verifications": [
        {"claim_index": 0, "verdict": "supported"},
        {"claim_index": 99, "verdict": "supported"},
        {"claim_index": 0, "verdict": "made_up"},
    ]}))
    assert result.model_status == "success"
    assert [row["verdict"] for row in result.verdicts] == ["supported"]


def test_claim_verification_unavailable_never_promotes():
    support = support_for()

    class Down:
        def complete_structured(self, *, task, payload, response_schema):
            return ModelResponse(task=task, status=ModelStatus.UNAVAILABLE, error="no host")

    result = verify_claims(
        [{"claim_index": 0, "claim": "a", "excerpt": "b", "source_role": "independent"}],
        Down(),
    )
    assert result.verdicts == ()
    assert result.model_status == "unavailable"
    assert apply_semantic_verdicts(support, result.verdicts).status != "verified"


def support_for():
    text = "OpenCode Plus shipped release v1.2 on 2026-10-01."
    evidence = {"ev1": ev("ev1", text)}
    return verify_fact_support(
        "OpenCode Plus shipped release v1.2 on 2026-10-01.",
        ("ev1",),
        [claim("OpenCode Plus shipped release v1.2 on 2026-10-01.", "ev1", text)],
        evidence,
    )


def test_supported_subclaim_cannot_hide_an_unsupported_displayed_statement():
    excerpt = "The update changes the color of the browser toolbar."
    result = verify_fact_support(
        "The update changes the color of the browser toolbar and guarantees offline operation.",
        ("ev1",), [claim(excerpt, "ev1", excerpt)], {"ev1": ev("ev1", excerpt)},
    )
    assert result.rejected


def test_claim_must_cover_exactly_the_displayed_citations():
    excerpt = "The update changes the color of the browser toolbar."
    result = verify_fact_support(excerpt, ("ev1", "ev2"), [claim(excerpt, "ev1", excerpt)],
                                 {"ev1": ev("ev1", excerpt), "ev2": ev("ev2", "Unrelated")})
    assert result.rejected


def test_quote_cannot_join_a_title_to_the_body():
    title = "Stable release shipped"
    text = "with a new experimental local API."
    stitched = f"{title} {text}"
    evidence = {"ev1": {**ev("ev1", text), "title": title}}
    result = verify_fact_support(stitched, ("ev1",), [claim(stitched, "ev1", stitched)], evidence)
    assert result.rejected
