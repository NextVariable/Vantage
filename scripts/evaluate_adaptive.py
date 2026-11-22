#!/usr/bin/env python3
"""Paired, offline replay of the legacy and adaptive paths on fixed cases.

No network, no provider billing, and no independent model-quality claim.
"""
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from sourceglint.application.api import run_sourceglint
from sourceglint.intelligence.model import ModelResponse, ModelStatus
from sourceglint.ledger import EvidenceLedger
from sourceglint.pipeline.adapters import RawSourceResult
from sourceglint.recommendations.model import FakeRecommendationModel

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "adaptive-research.json"
PLATFORMS = {"github": "github.com", "reddit": "reddit.com", "hacker_news": "news.ycombinator.com"}


def _response(task, **payload):
    return ModelResponse(task=task, status=ModelStatus.SUCCESS, payload=payload)


class ReplayModel(FakeRecommendationModel):
    def __init__(self, case):
        super().__init__()
        self.case = case
        self.requests = []
        self.claims = []

    def complete_structured(self, *, task, payload, response_schema):
        self.requests.append((task, len(json.dumps(payload, ensure_ascii=False))))
        aspects = self.case["aspects"]
        if task == "research_planning":
            return _response(task, goal=self.case["query"], research_objects=[self.case["subject"]],
                             subquestions=[{
                                 "question": part["question"], "priority": index,
                                 "evidence_types": [part["evidence_type"]],
                                 "preferred_sources": [part["source"]],
                                 "completion_criterion": "Find one dated, directly relevant observation.",
                                 "minimum_origins": 1, "query": part["query"], "language": "en",
                             } for index, part in enumerate(aspects, 1)])
        if task == "research_coverage":
            assessments = []
            for index, part in enumerate(aspects, 1):
                evidence = [row["id"] for row in payload["evidence"] if part["text"] in row["content"]]
                row = {"question_id": f"q{index}", "status": "covered" if evidence else "unanswered",
                       "evidence_ids": evidence, "gap": "" if evidence else "No direct source yet."}
                if part.get("followup") and not evidence and payload["followup_allowed"]:
                    row["followup"] = {"query": part["followup"], "language": "en", "source": part["source"],
                                       "expected_gain": "Find firsthand evidence answering the remaining question."}
                assessments.append(row)
            return _response(task, assessments=assessments)
        if task == "clustering":
            return _response(task, clusters=[
                {"label": item["title"], "claim": part["text"], "evidence_ids": [item["evidence_id"]],
                 "confidence": 0.8}
                for item in payload["evidence_items"] for part in aspects if item["title"] == part["question"]
            ])
        if task == "fact_synthesis":
            statements = {part["question"]: part["text"] for part in aspects}
            self.claims = [{
                "statement": statements[signal["claim"]], "signal_ids": [signal["signal_id"]],
                "evidence_ids": signal["evidence_ids"], "confidence": 0.7,
            } for signal in payload["signals"]]
            return _response(task, facts=self.claims)
        if task == "opportunity_hypotheses":
            return _response(task, hypotheses=[{
                "hypothesis": "Meeting participants who work offline may value export that preserves formatting.",
                "validation_test": "Have offline users export and share a sample, then observe whether they reuse it.",
                "disconfirming_result": "Users continue their existing workflow despite a clean export.",
                "supporting_insight_ids": [row["id"] for row in payload["insights"]],
            }])
        return super().complete_structured(task=task, payload=payload, response_schema=response_schema)


def replay(case, as_of, *, adaptive):
    outcomes: list[bool] = []
    ledger = EvidenceLedger(":memory:")
    model = ReplayModel(case)
    sources = [{
        "name": name, "enabled": True, "type": "official" if name == "github" else "community",
        "cost": "free", "auth_required": False, "credentials": [], "priority": 70,
        "capabilities": ["search"], "markets": ["global"], "languages": ["en"], "cache_ttl": 0,
        "max_queries_per_run": 2,
    } for name in PLATFORMS]

    class Adapter:
        def __init__(self, name):
            self.name = name

        def retrieve(self, plan, request):
            rows = []
            for index, part in enumerate(case["aspects"], 1):
                if part["source"] != self.name:
                    continue
                query = request["query"].casefold()
                if part["term"] in query or (index == 1 and case["subject"].casefold() in query):
                    rows.append(RawSourceResult(
                        source=self.name, source_type="page" if self.name == "github" else "post",
                        source_native_id=f"good-{index}", url=f"https://{PLATFORMS[self.name]}/case/{index}",
                        title=part["question"], text=part["text"], published_at="2026-09-08T12:00:00Z",
                    ))
            if not rows and case["subject"].casefold() in request["query"].casefold():
                rows.append(RawSourceResult(
                    source=self.name, source_type="post", source_native_id="noise",
                    url=f"https://{PLATFORMS[self.name]}/unrelated",
                    title="Unrelated same-name mention", text="Unrelated tourism discussion.",
                    published_at="2026-09-08T12:00:00Z",
                ))
            outcomes.append(any(row.source_native_id.startswith("good-") for row in rows))
            return rows

    start = perf_counter()
    result = run_sourceglint(
        case["query"], model=model, sources=sources, adapter_factory=lambda name, plan: Adapter(name),
        as_of=as_of, ledger=ledger, adaptive=adaptive, opportunities=adaptive and case.get("opportunities", False),
    )
    elapsed_ms = round((perf_counter() - start) * 1000, 2)
    records = {row.evidence_id: row.to_payload() for row in ledger}
    truth = {part["text"] for part in case["aspects"]}
    relevant = {key for key, row in records.items() if row.get("snippet") in truth}
    # Count factual claims presented in the report and compare their cited
    # evidence to the fixed answer key. This does not score fluent paraphrases.
    claims = [row for row in model.claims if row["statement"] in result.brief_markdown]
    supported = sum(bool(row["evidence_ids"]) and all(
        eid in relevant and records[eid]["snippet"] == row["statement"]
        for eid in row["evidence_ids"]
    ) for row in claims)
    coverage = result.diagnostics["coverage"]
    return {
        "status": result.status.value,
        "relevant_retained": len(relevant),
        "retained": len(records),
        "retained_relevance": len(relevant) / len(records) if records else None,
        "supported_factual_claims": supported,
        "factual_claims": len(claims),
        "evidence_support_rate": supported / len(claims) if claims else None,
        "subquestions_with_evidence": len({records[key]["snippet"] for key in relevant}),
        "subquestion_count": len(truth),
        "adapter_calls": len(outcomes),
        "unproductive_adapter_calls": outcomes.count(False),
        "elapsed_ms": elapsed_ms,
        "model_calls": len(model.requests),
        "model_input_characters": sum(size for _, size in model.requests),
        "opportunity_hypotheses": len(result.diagnostics.get("opportunity_discovery", {}).get("hypotheses", [])),
        "rounds": len(coverage.get("adaptive_research", {}).get("rounds", [])) if adaptive else 1,
    }


def main():
    suite = json.loads(FIXTURE.read_text(encoding="utf-8"))
    print(json.dumps({
        "test_kind": "offline scripted replay; call counts and input characters are cost proxies",
        "cases": [{
            "id": case["id"],
            "before": replay(case, suite["as_of"], adaptive=False),
            "after": replay(case, suite["as_of"], adaptive=True),
        } for case in suite["cases"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
