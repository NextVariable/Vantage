"""Deterministic regressions for Synthesis Runtime 2.0.

Covers the real 345 s baseline failure shape: clustering + contradiction +
semantic factors consumed the whole reserve and fact synthesis was refused.
The budget must protect the fact layer and record every degradation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic

import pytest

from sourceglint.application.api import _synthesis_reserve
from sourceglint.application.orchestrator import _delivery_level
from sourceglint.connectors._github_release import fetch_releases
from sourceglint.deadline import deadline_scope, remaining_time
from sourceglint.intelligence.dtos import PreparedEvidence
from sourceglint.intelligence.model import ModelResponse, ModelStatus
from sourceglint.intelligence.preparation import model_payloads
from sourceglint.pipeline.absence import NOT_RETRIEVED, AbsenceContext, qualify_text
from sourceglint.synthesis_budget import MeteredModel, SynthesisBudget


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class InnerModel:
    model_id = "fake-host"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_structured(self, *, task, payload, response_schema):
        self.calls.append(task)
        return ModelResponse(task=task, status=ModelStatus.SUCCESS, payload={})


# ---------------------------------------------------------------------------
# Budget gates
# ---------------------------------------------------------------------------

def test_semantic_gate_protects_the_fact_reserve():
    clock = FakeClock()
    budget = SynthesisBudget.from_remaining(100, clock=clock)
    clock.advance(60)  # 40 s left; fact + inference + brief need more
    allowed, reason = budget.allow("semantic_factors")
    assert allowed is False
    assert "semantic" in reason
    assert budget.allow("fact_synthesis")[0] is True


def test_real_baseline_timings_skip_semantics_but_keep_fact_synthesis():
    clock = FakeClock()
    budget = SynthesisBudget.from_remaining(106, clock=clock)

    clock.advance(49.6)
    budget.record_call("clustering", input_chars=10, seconds=49.6, ok=True)
    clock.advance(15.0)
    budget.record_call("contradiction", input_chars=10, seconds=15.0, ok=True)

    assert budget.allow("semantic_factors")[0] is False
    assert budget.allow("fact_synthesis")[0] is True

    clock.advance(10.0)
    budget.record_call("fact_synthesis", input_chars=10, seconds=10.0, ok=True)
    assert budget.allow("inference_synthesis")[0] is True


def test_semantic_call_cap_uses_observed_latency():
    clock = FakeClock()
    budget = SynthesisBudget.from_remaining(120, clock=clock)
    clock.advance(20)
    budget.record_call("clustering", input_chars=10, seconds=20.0, ok=True)
    # 100 s left, reserves 42 + 14.4 + 1.5 -> ~42 s usable, 20 s per call -> 2
    assert budget.semantic_call_cap == 2


def test_claim_verification_is_admitted_before_inference_and_refused_when_tight():
    clock = FakeClock()
    budget = SynthesisBudget.from_remaining(120, clock=clock)
    clock.advance(20)
    budget.record_call("clustering", input_chars=10, seconds=20.0, ok=True)
    # 100 s left: inference reserve + brief floor + one observed call still fit.
    assert budget.allow("claim_support_verification")[0] is True
    # Late in the run the verification stage must yield to inference and brief.
    clock.advance(80)
    allowed, reason = budget.allow("claim_support_verification")
    assert allowed is False
    assert "claim_verification" in reason
    # The stage is ordered before inference so a refusal is explainable.
    from sourceglint.synthesis_budget import STAGE_ORDER
    assert STAGE_ORDER.index("claim_verification") < STAGE_ORDER.index("inference_synthesis")


def test_host_contract_discloses_cooperative_timeout_and_legacy_limit():
    budget = SynthesisBudget.from_remaining(90)
    contract = budget.to_dict()["host_contract"]
    assert contract["protocol"] == "sourceglint-host/v2"
    assert "request_id" in contract["correlation"]
    assert contract["timeout_enforcement"].startswith("cooperative")
    # A host that cannot correlate must fail closed rather than reuse the stream.
    assert "fail closed" in contract["recovery"]


# ---------------------------------------------------------------------------
# Metered model
# ---------------------------------------------------------------------------

def test_metered_model_records_calls_and_refusals():
    clock = FakeClock()
    budget = SynthesisBudget.from_remaining(100, clock=clock)
    inner = InnerModel()
    meter = MeteredModel(inner, budget)

    meter.complete_structured(task="clustering", payload={"a": "x" * 40}, response_schema={})
    assert budget.calls_by_task["clustering"] == 1
    assert budget.input_chars_by_task["clustering"] > 40

    clock.advance(70)  # only 30 s left, no room for a semantic call
    response = meter.complete_structured(
        task="semantic_factors", payload={"b": 1}, response_schema={}
    )
    assert response.status is ModelStatus.UNAVAILABLE
    assert "synthesis budget" in response.error
    assert inner.calls == ["clustering"]
    assert budget.refusals and budget.refusals[-1]["task"] == "semantic_factors"


def test_metered_model_finalizes_host_usage():
    budget = SynthesisBudget.from_remaining(100, clock=FakeClock())

    class HostWithUsage(InnerModel):
        def usage_summary(self):
            return {"input_tokens": 123, "cached_tokens": 45, "cost_usd": 0.0}

    meter = MeteredModel(HostWithUsage(), budget)
    meter.finalize()
    assert budget.to_dict()["model_io"]["host_usage"]["cached_tokens"] == 45


# ---------------------------------------------------------------------------
# Delivery levels
# ---------------------------------------------------------------------------

def _budget_with(stages: dict[str, str]) -> SynthesisBudget:
    budget = SynthesisBudget.from_remaining(100, clock=FakeClock())
    for name, status in stages.items():
        budget.mark_stage(name, status)
    return budget


def test_delivery_level_requires_facts():
    assert _delivery_level([], None, include_gtm=True) == "evidence_only_report"


def test_delivery_level_evidence_backed_when_inference_skipped():
    budget = _budget_with(
        {
            "clustering": "ok",
            "contradiction": "ok",
            "fact_synthesis": "ok",
            "semantic_factors": "skipped",
            "inference_synthesis": "skipped",
        }
    )
    assert _delivery_level(
        [{"type": "FACT"}], budget, include_gtm=False
    ) == "evidence_backed_brief"


def test_delivery_level_full_when_all_stages_ok():
    budget = _budget_with(
        {
            "clustering": "ok",
            "contradiction": "ok",
            "fact_synthesis": "ok",
            "inference_synthesis": "ok",
            "semantic_factors": "ok",
            "gtm_implications": "ok",
            "recommendations": "ok",
        }
    )
    assert _delivery_level([{"type": "FACT"}], budget, include_gtm=True) == "full_brief"


# ---------------------------------------------------------------------------
# Dynamic reserve
# ---------------------------------------------------------------------------

def test_reserve_scales_with_subquestions_and_share_cap():
    one, _ = _synthesis_reserve(
        345, entities=1, languages=1, mode="industry", subquestions=1
    )
    three, _ = _synthesis_reserve(
        345, entities=1, languages=1, mode="industry", subquestions=3
    )
    assert three > one
    assert three <= min(140.0, 345 * 0.45)


# ---------------------------------------------------------------------------
# Evidence payload budgeting
# ---------------------------------------------------------------------------

def test_content_budget_trims_payload_without_dropping_ids():
    prepared = [
        PreparedEvidence(
            evidence_id=f"ev{i}",
            source="github",
            source_type="repo",
            window="current",
            content="x" * 9000,
            has_text=True,
        )
        for i in range(4)
    ]
    payloads = model_payloads(prepared, content_budget=8000)
    assert [p["evidence_id"] for p in payloads] == ["ev0", "ev1", "ev2", "ev3"]
    total = sum(len(str(p.get("content") or "")) for p in payloads)
    assert total <= 8000 + 400  # per-item floor/rounding


# ---------------------------------------------------------------------------
# GitHub release pagination
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload, headers=None, status=200) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def request(self, url, headers=None):
        self.urls.append(url)
        return self.responses.pop(0)


WINDOW = (
    datetime(2026, 11, 1, tzinfo=timezone.utc),
    datetime(2026, 11, 23, tzinfo=timezone.utc),
)


def _release(tag: str, published: str) -> dict:
    return {
        "id": tag,
        "tag_name": tag,
        "name": tag,
        "published_at": published,
        "html_url": f"https://github.com/a/b/releases/tag/{tag}",
        "body": "body",
    }


def test_release_pagination_finds_an_older_in_window_release():
    http = FakeHttp(
        [
            FakeResponse(
                [_release("v9", "2025-01-01T00:00:00Z")],
                headers={"Link": '<https://api.github.com/repos/a/b/releases?page=2>; rel="next"'},
            ),
            FakeResponse([_release("v1", "2026-11-10T00:00:00Z")]),
        ]
    )
    outcome = fetch_releases(
        http,
        [{"full_name": "a/b"}],
        headers={},
        window=WINDOW,
        checked_at="2026-11-23T00:00:00Z",
    )
    assert outcome.observations[0]["status"] == "present"
    assert outcome.observations[0]["in_window_count"] == 1
    assert len(http.urls) == 2


def test_incomplete_pagination_is_not_only_outside_window():
    def next_header(page):
        return {"Link": f'<https://api.github.com/repos/a/b/releases?page={page}>; rel="next"'}
    http = FakeHttp(
        [
            FakeResponse([_release("v9", "2025-01-01T00:00:00Z")], headers=next_header(2)),
            FakeResponse([_release("v8", "2025-02-01T00:00:00Z")], headers=next_header(3)),
            FakeResponse([_release("v7", "2025-03-01T00:00:00Z")], headers=next_header(4)),
        ]
    )
    outcome = fetch_releases(
        http,
        [{"full_name": "a/b"}],
        headers={},
        window=WINDOW,
        checked_at="2026-11-23T00:00:00Z",
    )
    assert outcome.observations[0]["status"] == "pagination_incomplete"
    ctx = AbsenceContext.from_observations(outcome.observations)
    assert ctx.coverage_incomplete is True
    text, checks = qualify_text("No releases found.", context=ctx)
    assert checks[0]["status"] == NOT_RETRIEVED
    assert "Unverified absence" in text


# ---------------------------------------------------------------------------
# Absence scope
# ---------------------------------------------------------------------------

def test_verified_absence_does_not_cover_a_different_repository():
    ctx = AbsenceContext.from_observations(
        [
            {"kind": "releases", "status": "verified_absent", "repository": "a/b"},
            {"kind": "releases", "status": "verified_absent", "repository": "c/d"},
        ]
    )
    _, checks = qualify_text("x/y has no releases.", context=ctx)
    assert checks[0]["status"] != "verified_absent"


def test_verified_absence_stays_sentence_scoped():
    ctx = AbsenceContext.from_observations(
        [
            {"kind": "releases", "status": "verified_absent", "repository": "a/b"},
            {"kind": "releases", "status": "verified_absent", "repository": "c/d"},
        ]
    )
    text, checks = qualify_text(
        "The project is active. a/b has no releases.", context=ctx
    )
    assert checks[0]["status"] == NOT_RETRIEVED
    assert "Unverified absence" in text
    assert "Within the research window" not in text


def test_parent_deadline_refuses_without_counting_a_dispatch():
    inner = InnerModel()
    budget = SynthesisBudget.from_remaining(100)
    with deadline_scope(monotonic() - 1):
        reply = MeteredModel(inner, budget).complete_structured(
            task="fact_synthesis", payload={}, response_schema={}
        )
    assert reply.status is ModelStatus.UNAVAILABLE
    assert not inner.calls
    assert not budget.calls_by_task
    assert len(budget.refusals) == 1


def test_recommendation_uses_parent_deadline_and_records_timeout_once():
    class TimeoutModel(InnerModel):
        def complete_structured(self, *, task, payload, response_schema):
            assert 0 < remaining_time() <= 3
            raise TimeoutError

    budget = SynthesisBudget.from_remaining(100)
    with deadline_scope(monotonic() + 3):
        reply = MeteredModel(TimeoutModel(), budget).complete_structured(
            task="recommendation_generation", payload={}, response_schema={}
        )
    assert reply.status is ModelStatus.TIMEOUT
    assert budget.calls_by_task == {"recommendation_generation": 1}
    assert budget.stages["recommendations"].calls == 1


def test_zero_budget_refuses_clustering_and_preserves_short_fact_reserve():
    assert not SynthesisBudget.from_remaining(0).allow("clustering")[0]
    short = SynthesisBudget.from_remaining(10)
    assert 0 < short.fact_reserve_seconds < 10
    assert short.stage_deadline("clustering") < short.stage_deadline("fact_synthesis")


def test_empty_unfinished_release_scan_cannot_claim_absence():
    http = FakeHttp([
        FakeResponse([], {"Link": '<https://api.github.com/repos/a/b/releases?page=2>; rel="next"'}),
        FakeResponse([], {"Link": '<https://api.github.com/repos/a/b/releases?page=3>; rel="next"'}),
        FakeResponse([], {"Link": '<https://api.github.com/repos/a/b/releases?page=4>; rel="next"'}),
    ])
    outcome = fetch_releases(http, [{"full_name": "a/b"}], headers={}, window=WINDOW)
    observed = outcome.observations[0]
    assert observed["status"] == "pagination_incomplete"
    assert observed["complete"] is False and observed["pages_fetched"] == 3
    assert observed["endpoint"] == "https://api.github.com/repos/a/b/releases"
    assert observed["window_start"] == WINDOW[0].isoformat()
    assert observed["window_end"] == WINDOW[1].isoformat()
    assert len(http.urls) == 3


def test_untrusted_next_link_is_not_followed_and_bad_date_is_not_absence():
    http = FakeHttp([
        FakeResponse([_release("v1", "invalid")], {"Link": '<https://example.org/page>; rel="next"'}),
    ])
    outcome = fetch_releases(http, [{"full_name": "a/b"}], headers={}, window=WINDOW)
    assert len(http.urls) == 1
    assert not outcome.results
    assert outcome.observations[0]["status"] == "pagination_incomplete"


def test_release_pagination_accepts_github_repository_id_link():
    http = FakeHttp([
        FakeResponse([], {"Link": '<https://api.github.com/repositories/123/releases?page=2>; rel="next"'}),
        FakeResponse([_release("v1", "2026-11-10T00:00:00Z")]),
    ])
    outcome = fetch_releases(http, [{"full_name": "a/b", "id": 123}], headers={}, window=WINDOW)
    assert len(http.urls) == 2
    assert outcome.observations[0]["status"] == "present"


def test_malformed_release_link_and_tag_body_never_certify_absence():
    response = FakeResponse([], {"Link": '; rel="next"'})
    http = FakeHttp([response])
    outcome = fetch_releases(http, [{"full_name": "a/b"}], headers={}, window=WINDOW)
    assert outcome.observations[0]["status"] == "invalid_response"

    http = FakeHttp([FakeResponse([]), FakeResponse({"message": "bad payload"})])
    outcome = fetch_releases(http, [{"full_name": "a/b"}], headers={}, window=WINDOW)
    release, tag = outcome.observations
    assert release["status"] == "verified_absent" and release["complete"] is True
    assert tag["status"] == "invalid_response"
