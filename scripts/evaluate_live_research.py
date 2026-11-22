"""Opt-in paired evaluation with actual public sources and scripted judgments.

The raw/retained evidence is real when the adapters succeed. The planner,
relevance proxy and structured model are controlled harnesses. Do not interpret
the resulting counts as independent human scores or provider token usage.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from time import perf_counter

from sourceglint.application.api import run_sourceglint
from sourceglint.connectors._http import StdlibHttpClient
from sourceglint.connectors.hacker_news import HackerNewsAdapter
from sourceglint.connectors.open_sources import DevToAdapter, QiitaAdapter
from sourceglint.intelligence.model import ModelResponse, ModelStatus
from sourceglint.ledger import EvidenceLedger
from sourceglint.recommendations.model import FakeRecommendationModel

DATA = Path(__file__).resolve().parents[1] / "evals" / "vantage-1.0-live.json"


def response(task, **payload):
    return ModelResponse(task=task, status=ModelStatus.SUCCESS, payload=payload)


class ControlledModel(FakeRecommendationModel):
    def __init__(self, case, routes, upgraded):
        super().__init__()
        self.case, self.routes, self.upgraded = case, routes, upgraded
        self.requests = []
        self.checked_ids = set()

    def relevant(self, title, body):
        return self.case["literal"].casefold() in (title + " " + body).casefold()

    def complete_structured(self, *, task, payload, response_schema):
        self.requests.append((task, len(json.dumps(payload, ensure_ascii=False))))
        case = self.case
        if task == "research_planning":
            question = {
                "question": case["question"], "priority": 1, "evidence_types": [],
                "preferred_sources": [self.routes[0]],
                "completion_criterion": "Find two dated candidates suitable for independent review.",
                "minimum_origins": 2, "query": case["initial"], "language": case["language"],
            }
            if self.upgraded:
                question["focus"] = case["focus"]
            return response(task, goal=case["question"], research_objects=[case["initial"]],
                            subquestions=[question])
        if task == "research_coverage":
            selected = [row["id"] for row in payload["evidence"]
                        if self.relevant(row["title"], row["content"])][:10]
            self.checked_ids.update(selected)
            row = {"question_id": "q1", "evidence_ids": selected,
                   "status": "covered" if len(selected) >= 2 else "partial",
                   "gap": "" if len(selected) >= 2 else "Too few literal screening matches."}
            k = len(payload["already_planned"])
            if payload["followup_allowed"] and k <= 2:
                row["followup"] = {
                    "source": self.routes[1] if k == 1 else self.routes[0],
                    "query": case["followup"], "language": case["language"],
                    "expected_gain": "Locate an additional report or independent account for review.",
                }
            if payload["followup_allowed"] and k == 1 and len(selected) >= 2:
                # The baseline's origin gate will downgrade one-platform results;
                # the alternative route is still a useful candidate in both arms.
                row["status"] = "partial"
                row["gap"] = "Independent source still needed."
            return response(task, assessments=[row])
        if task == "clustering":
            selected = [r for r in payload["evidence_items"] if r["evidence_id"] in self.checked_ids][:4]
            return response(task, clusters=[
                {"label": row["title"][:160] or "Retrieved candidate", "claim": "A source candidate was retrieved.",
                 "evidence_ids": [row["evidence_id"]], "confidence": 0.6}
                for row in selected
            ])
        if task == "fact_synthesis":
            # A literal term match cannot establish a factual research finding.
            return response(task, facts=[])
        return super().complete_structured(task=task, payload=payload, response_schema=response_schema)


def run(case, args):
    names = ("qiita", "hacker_news") if case["language"] == "ja" else ("hacker_news", "devto")
    transport = StdlibHttpClient(default_timeout=6, max_attempts=1)
    fence = {"require_topic_match": True} if args.upgraded else {}
    adapters = {"hacker_news": HackerNewsAdapter(http_client=transport, max_per_query=5, require_topic_match=True),
                "devto": DevToAdapter(http_client=transport, max_per_query=5, **fence),
                "qiita": QiitaAdapter(http_client=transport, max_per_query=5, **fence)}
    calls = []

    class Trace:
        def __init__(self, name):
            self.name, self.adapter = name, adapters[name]

        def __getattr__(self, name):
            return getattr(self.adapter, name)

        def retrieve(self, plan, request):
            start = perf_counter()
            record = {"source": self.name, "query": request["query"], "outcome": "failed"}
            calls.append(record)
            try:
                rows = self.adapter.retrieve(plan, request)
                record.update(outcome="returned", rows=len(rows),
                              candidate_rows=sum(model.relevant(r.title, r.text) for r in rows))
                return rows
            except Exception as exc:
                record["failure_type"] = type(exc).__name__
                raise
            finally:
                record["ms"] = round((perf_counter() - start) * 1000)

    sources = [{
        "name": name, "enabled": True, "type": "community", "cost": "free",
        "auth_required": False, "credentials": [], "priority": 70, "capabilities": ["search"],
        "markets": ["global"], "languages": [case["language"]], "cache_ttl": 0,
        "max_queries_per_run": 2,
    } for name in names]
    model = ControlledModel(case, names, args.upgraded)
    now = perf_counter()
    ledger = EvidenceLedger(":memory:")
    output = run_sourceglint(
        case["question"], as_of=args.as_of, mode="general", market="global",
        languages=(case["language"],), window_days=case["days"],
        adaptive=True, model=model, sources=sources,
        adapter_factory=lambda name, plan: Trace(name), ledger=ledger,
        opportunities=case["focus"] == "opportunity",
        **({"research_rounds": 3, "research_timeout_seconds": 25} if args.upgraded else {}),
    )
    records = [record.to_payload() for record in ledger]
    coverage = output.diagnostics.get("coverage", {})
    return {
        "case": case["id"], "focus": case["focus"], "language": case["language"], "days": case["days"],
        "status": output.status.value, "report": output.brief_markdown, "coverage": coverage,
        "elapsed_ms": round((perf_counter() - now) * 1000),
        "adapter_calls": calls, "model_calls": len(model.requests),
        "model_input_chars": sum(length for _, length in model.requests),
        "ledger": records, "literal_candidate_ids": sorted(model.checked_ids),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--upgraded", action="store_true")
    p.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    args = p.parse_args()
    cases = json.loads(DATA.read_text(encoding="utf-8"))["cases"]
    with args.output.open("x", encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda case: run(case, args), cases):
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()


if __name__ == "__main__":
    main()
