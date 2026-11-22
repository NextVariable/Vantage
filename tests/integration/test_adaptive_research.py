"""Exercise the adaptive path through public entry points without network access."""
import io
import json
from dataclasses import replace

import pytest

from scripts.evaluate_adaptive import FIXTURE, replay
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from sourceglint.resources import data_path
from sourceglint.application.api import run_sourceglint
from sourceglint.host_stdio import StdioHostSource
from sourceglint.intelligence.model import ModelResponse, ModelStatus
from sourceglint.interface.parser import parse_query
from sourceglint.interface.result import Status
from sourceglint.ledger import EvidenceLedger
from sourceglint.pipeline.adapters import AdapterRateLimited, RawSourceResult

from test_public_api import AS_OF, SOURCE, OneFactModel


def source(name, *, max_queries=2, market="global", languages=("en",)):
    return {**SOURCE, "name": name, "max_queries_per_run": max_queries,
            "markets": [market], "languages": list(languages)}


def observation(name="hacker_news", *, native_id="1", published="2026-09-08T12:00:00Z"):
    domain = {"hacker_news": "news.ycombinator.com", "reddit": "reddit.com", "github": "github.com"}[name]
    return RawSourceResult(
        source=name, source_type="post", source_native_id=native_id,
        url=f"https://{domain}/posting/{native_id}", title="AI product discussion",
        text="A new AI product was discussed by users.", published_at=published,
    )


def answer(task, **payload):
    return ModelResponse(task=task, status=ModelStatus.SUCCESS, payload=payload)


class ScriptedModel(OneFactModel):
    def __init__(self, *, planned_source="hacker_news", initial="AI product discussion",
                 assess=None, language="en", minimum_origins=1):
        super().__init__()
        self.planned_source = planned_source
        self.initial = initial
        self.assess = assess
        self.language = language
        self.minimum_origins = minimum_origins
        self.tasks = []

    def complete_structured(self, *, task, payload, response_schema):
        self.tasks.append((task, payload))
        if task == "research_planning":
            return answer(task, goal="Understand AI product discussion", research_objects=["AI products"],
                          subquestions=[{
                              "question": "What did users experience?", "priority": 1,
                              "evidence_types": ["T2_community"], "preferred_sources": [self.planned_source],
                              "completion_criterion": "A recent report from distinct sources.",
                              "minimum_origins": self.minimum_origins, "query": self.initial,
                              "language": self.language,
                          }])
        if task == "research_coverage":
            row = {
                "question_id": "q1", "status": "covered",
                "evidence_ids": [ev["id"] for ev in payload["evidence"]], "gap": "",
            }
            if self.assess:
                row.update(self.assess(payload))
            return answer(task, assessments=[row])
        if task == "opportunity_hypotheses":
            return answer(task, hypotheses=[{
                "hypothesis": "A subset of users may need faster review.",
                "validation_test": "Observe whether they reuse a faster review flow.",
                "disconfirming_result": "Users revert to their original flow.",
                "supporting_insight_ids": [payload["insights"][0]["id"]],
            }, {
                "hypothesis": "Unsupported conclusion.",
                "validation_test": "Test unrelated behavior.",
                "disconfirming_result": "No change.",
                "supporting_insight_ids": ["invented-id"],
            }])
        return super().complete_structured(task=task, payload=payload, response_schema=response_schema)


def followup(source_name, query="AI product firsthand user reviews"):
    return {"source": source_name, "query": query, "language": "en",
            "expected_gain": "Find an independently published firsthand example."}


def execute(model, replies, *, sources=None, query="Recent AI products", **options):
    calls = []
    ledger = EvidenceLedger(":memory:")

    class Adapter:
        def __init__(self, name):
            self.name = name

        def retrieve(self, plan, request):
            calls.append((self.name, request["query"], request["query_language"]))
            result = replies(self.name, request)
            if isinstance(result, Exception):
                raise result
            return result

    result = run_sourceglint(
        query, model=model, adaptive=True, as_of=AS_OF, ledger=ledger,
        sources=sources or [source("hacker_news"), source("reddit")],
        adapter_factory=lambda name, plan: Adapter(name), **options,
    )
    return result, result.diagnostics["coverage"]["adaptive_research"], calls, ledger


def test_supported_subquestion_stops_after_first_round_and_keeps_feedback_separate():
    model = ScriptedModel(assess=lambda payload: {
        "feedback_ids": [payload["evidence"][0]["id"], "unknown-id"],
        "followup": followup("reddit"),  # unnecessary even if suggested
    })
    result, report, calls, ledger = execute(model, lambda *_: [observation()])
    assert len(calls) == len(report["rounds"]) == len(ledger) == 1
    assert report["stop_reason"] == "criteria_met"
    assert report["subquestions"][0]["feedback_ids"] == [next(iter(ledger)).evidence_id]
    assert "Firsthand user feedback (reported)" in result.brief_markdown
    assert "Opportunity hypotheses" not in result.brief_markdown
    assert "opportunity_hypotheses" not in [task for task, _ in model.tasks]
    assert result.research_plan["time_window"] == {"days": 30}
    assert result.research_plan["subquestions"][0]["id"] == "q1"
    schema = json.loads(data_path("schemas", "research_plan.schema.json").read_text())
    common = json.loads(data_path("schemas", "common.schema.json").read_text())
    registry = Registry().with_resource(common["$id"], Resource.from_contents(common))
    Draft202012Validator(schema, registry=registry).validate(result.research_plan)


def test_followup_retains_first_round_and_recovers_from_platform_failure():
    model = ScriptedModel(assess=lambda payload: {"followup": followup("reddit")})
    result, report, calls, ledger = execute(
        model, lambda name, _: AdapterRateLimited(name) if name == "hacker_news" else [observation(name)],
    )
    assert [row[0] for row in calls] == ["hacker_news", "reddit"]
    assert result.status is Status.PARTIAL
    assert len(ledger) == 1
    assert report["rounds"][0]["failed_routes"] == 1
    assert report["rounds"][1]["new_evidence"] == 1
    assert report["stop_reason"] == "criteria_met"
    assert report["rounds"][0]["subquestions"][0]["expected_gain"]
    assert result.diagnostics["coverage"]["failed_sources"] == ["hacker_news"]


@pytest.mark.parametrize("query", ["ＡＩ PRODUCT discussion!", "AI product discussion"])
def test_normalized_duplicate_route_is_rejected_without_second_call(query):
    model = ScriptedModel(assess=lambda _: {
        "status": "partial", "gap": "No direct evidence.", "followup": followup("hacker_news", query),
    })
    _, report, calls, _ = execute(model, lambda *_: [])
    assert len(calls) == 1 and report["rejected_routes"] == 1
    assert report["stop_reason"] == "no_eligible_followup"


def test_duplicate_evidence_and_out_of_window_hits_do_not_close_gap():
    def assess(payload):
        return {"status": "covered", "evidence_ids": [ev["id"] for ev in payload["evidence"]] + ["invented"],
                "followup": followup("reddit")}
    model = ScriptedModel(assess=assess, minimum_origins=2)
    eligible = observation(published="2026-08-10T00:00:00Z")
    result, report, calls, ledger = execute(model, lambda *_: [
        eligible, observation(native_id="old", published="2026-08-09T23:59:59Z"),
        observation(native_id="future", published="2026-09-09T00:00:01Z"),
        observation(native_id="undated", published=""),
    ])
    assert len(calls) == 2 and len(ledger) == 1
    assert report["stop_reason"] == "no_new_evidence"
    assert report["subquestions"][0]["status"] == "partial"
    assert report["subquestions"][0]["evidence_ids"] == [next(iter(ledger)).evidence_id]
    assert result.diagnostics["coverage"]["time_filter_dropped_count"] == 6


def test_attempt_limit_and_all_failed_are_reported_without_retrying_blocked_source():
    model = ScriptedModel(assess=lambda _: {"followup": followup("hacker_news")})
    result, report, calls, _ = execute(model, lambda name, _: AdapterRateLimited(name))
    assert len(calls) == 1
    assert report["stop_reason"] == "no_eligible_followup"
    assert result.status is Status.FAILED
    assert "Sources unavailable: hacker_news" in result.brief_markdown
    assert "unanswered" in result.brief_markdown


def test_source_cap_applies_across_both_rounds():
    model = ScriptedModel(assess=lambda _: {"followup": followup("hacker_news")})
    _, report, calls, _ = execute(model, lambda *_: [], sources=[source("hacker_news", max_queries=1)])
    assert len(calls) == 1 and report["stop_reason"] == "no_eligible_followup"


@pytest.mark.parametrize(("query", "market", "language", "days"), [
    ("中国最近14天的用户反馈", "cn", "zh", 14),
    ("日本で過去7日間に出たツールは？", "jp", "ja", 7),
    ("한국에서 최근 2개월간 신규 도구는?", "kr", "ko", 60),
])
def test_local_language_window_and_route_scope(query, market, language, days):
    assert parse_query(query).query_language == language
    model = ScriptedModel(initial=query, language=language)
    scoped = source("hacker_news", market=market, languages=(language,))
    result, _, calls, _ = execute(model, lambda *_: [], sources=[scoped], query=query)
    assert result.research_plan["market"] == market
    assert result.research_plan["time_window"] == {"days": days}
    assert calls == [("hacker_news", query, language)]


def test_opportunity_opt_in_filters_unresolvable_hypotheses_and_has_a_disconfirming_result():
    result, _, _, _ = execute(ScriptedModel(), lambda *_: [observation()], opportunities=True)
    hypotheses = result.diagnostics["opportunity_discovery"]["hypotheses"]
    assert len(hypotheses) == 1
    assert hypotheses[0]["evidence_ids"]
    assert "Disconfirming result:" in result.brief_markdown
    assert "Unsupported conclusion" not in result.brief_markdown

    model = ScriptedModel()
    result, _, _, _ = execute(model, lambda *_: [], opportunities=True)
    assert result.diagnostics["opportunity_discovery"]["status"] == "insufficient_evidence"
    assert not any(task == "opportunity_hypotheses" for task, _ in model.tasks)


def test_opportunity_timeout_preserves_brief_but_marks_explicit_request_partial():
    class OpportunityTimeoutModel(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "opportunity_hypotheses":
                return ModelResponse(task=task, status=ModelStatus.TIMEOUT)
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    model = OpportunityTimeoutModel()
    ordinary, _, _, _ = execute(model, lambda *_: [observation()])
    assert ordinary.status == Status.SUCCESS
    result, _, _, _ = execute(model, lambda *_: [observation()], opportunities=True)
    assert result.status == Status.PARTIAL
    assert result.diagnostics["opportunity_discovery"]["status"] == "model_unavailable"
    assert result.brief_markdown.startswith(ordinary.brief_markdown)
    assert "Structured opportunity assessment was unavailable" in result.brief_markdown


def test_stdio_reports_bounded_targets_to_host():
    out = io.StringIO()
    host = StdioHostSource("host_web_search", input_stream=io.StringIO(
        '{"type":"source_response","source":"host_web_search","results":[]}\n'
    ), output_stream=out)
    host.retrieve({"mode": "general", "market": "global"}, {"host_target_budget": 3})
    assert 0 < len(json.loads(out.getvalue())["targets"]) <= 3


@pytest.mark.parametrize("index", range(4))
def test_paired_fixture_cases(index):
    fixture = json.loads(FIXTURE.read_text())
    case = fixture["cases"][index]
    before = replay(case, fixture["as_of"], adaptive=False)
    after = replay(case, fixture["as_of"], adaptive=True)
    assert after["subquestions_with_evidence"] == after["subquestion_count"] == 2
    assert after["subquestions_with_evidence"] > before["subquestions_with_evidence"]
    assert after["unproductive_adapter_calls"] < before["unproductive_adapter_calls"]
    assert after["evidence_support_rate"] == 1.0
    assert after["rounds"] == (1 if index == 0 else 2)
    assert after["opportunity_hypotheses"] == (1 if index == 3 else 0)


def test_cli_stdio_executes_one_followup_and_reports_no_evidence(tmp_path):
    import subprocess
    import sys

    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps([source("host_web_search")]))
    plan = {
        "goal": "Explore current AI product feedback", "research_objects": ["AI products"],
        "subquestions": [{
            "question": "What did users report?", "priority": 1, "evidence_types": ["T2_community"],
            "preferred_sources": ["host_web_search"], "completion_criterion": "Find firsthand feedback.",
            "minimum_origins": 1, "query": "AI product complaints", "language": "en",
        }],
    }
    gap = {"question_id": "q1", "status": "unanswered", "gap": "No firsthand observations.", "evidence_ids": []}
    response = {"type": "source_response", "source": "host_web_search", "results": [],
                "searched_targets": [{"name": "reddit", "status": "no_results"}]}
    replies = [
        {"type": "model_response", "task": "research_planning", "payload": plan},
        response,
        {"type": "model_response", "task": "research_coverage", "payload": {
            "assessments": [{**gap, "followup": followup("host_web_search")}],
        }},
        response,
        {"type": "model_response", "task": "research_coverage", "payload": {"assessments": [gap]}},
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "sourceglint", "Recent AI products", "--adaptive", "--opportunities",
         "--host-sources-stdio", "--model", "sourceglint.host_stdio:build_model",
         "--registry", str(registry), "--as-of", AS_OF.isoformat(), "--json"],
        input="\n".join(json.dumps(msg) for msg in replies) + "\n",
        text=True, capture_output=True, check=True, timeout=30,
    )
    lines = proc.stdout.splitlines()
    messages = [json.loads(line) for line in lines[:5]]
    assert [msg["type"] for msg in messages] == [
        "model_request", "source_request", "model_request", "source_request", "model_request",
    ]
    result = json.loads("\n".join(lines[5:]))
    assert result["status"] == "NO_EVIDENCE"
    assert result["diagnostics"]["coverage"]["adaptive_research"]["stop_reason"] == "no_new_evidence"
    assert result["diagnostics"]["opportunity_discovery"]["hypotheses"] == []


def test_syndicated_text_and_counterevidence_are_not_independent_support():
    def assess(payload):
        ids = [ev["id"] for ev in payload["evidence"]]
        return {"evidence_ids": ids, "counterevidence_ids": ids[-1:] if len(ids) == 3 else [],
                "followup": followup("reddit")}
    model = ScriptedModel(assess=assess, minimum_origins=2)
    copied = "A new AI product was discussed by users. This exact account was syndicated across platforms without independent reporting."
    result, report, _, ledger = execute(model, lambda name, _: (
        [replace(observation(), text=copied)] if name == "hacker_news" else [
            replace(observation(name), text=copied), observation(name, native_id="counter"),
        ]
    ))
    assert len(ledger) == 3
    assert report["subquestions"][0]["status"] == "partial"
    assert report["subquestions"][0]["supporting_origin_count"] == 1
    assert "Counterevidence:" in result.brief_markdown


def test_invalid_planning_or_assessment_discloses_fallback_without_retrying():
    class UnavailablePlanner(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task in ("research_planning", "research_coverage"):
                return answer(task, invalid=True)
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    result, report, calls, _ = execute(UnavailablePlanner(), lambda *_: [],
                                       sources=[source("hacker_news", max_queries=1)])
    assert len(calls) == len(report["rounds"]) == 1
    assert report["planning_status"] == "fallback"
    assert report["stop_reason"] == "assessment_unavailable"
    assert report["subquestions"][0]["status"] == "unassessed"
    assert result.diagnostics["coverage"]["research_quality"] == "LIMITED"


def test_planner_keeps_a_subquestion_when_its_preferred_source_is_ineligible():
    model = ScriptedModel(planned_source="unconfigured_route")
    _, report, calls, _ = execute(model, lambda *_: [observation("reddit")],
                                  sources=[source("reddit")])
    assert [call[0] for call in calls] == ["reddit"]
    assert report["planning_status"] == "planned"
    assert report["subquestions"][0]["status"] == "covered"
