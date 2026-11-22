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


# --- research-quality sprint regressions ---------------------------------


def test_planned_query_syntax_is_stripped_but_cjk_is_preserved():
    from sourceglint.pipeline.query_expansion import normalize_planned_query

    assert normalize_planned_query(
        '"open source" "coding agent" released November 2026'
    ) == "open source coding agent"
    assert normalize_planned_query("VS Code AND Copilot 日本語 2026") == "VS Code Copilot"
    original = "日本で過去7日間に出たツールは？"
    assert normalize_planned_query(original) == original


def test_research_deadline_never_exceeds_the_reserved_budget():
    from time import monotonic

    from sourceglint.pipeline.adaptive import AdaptiveResearch, ResearchBudget

    run = AdaptiveResearch(None, {"topic": "AI", "languages": ["en"]}, [],
                           budget=ResearchBudget(3, 100), deadline=monotonic() + 10)
    assert run.deadline <= monotonic() + 10.01


def test_no_request_starts_without_enough_time_left():
    from time import monotonic

    from sourceglint.deadline import deadline_scope
    from sourceglint.pipeline.orchestrator import _time_available

    with deadline_scope(monotonic() + 5):
        assert _time_available() is False
    assert _time_available() is True


def test_spacing_variant_of_a_planned_route_is_rejected_as_duplicate():
    model = ScriptedModel(
        initial="VS Code review",
        assess=lambda _: {"status": "partial", "gap": "Open",
                          "followup": followup("hacker_news", "VSCode  review")},
    )
    _, report, calls, _ = execute(model, lambda *_: [], sources=[source("hacker_news")])
    assert len(calls) == 1
    assert report["rejected_routes"] == 1
    assert report["stop_reason"] == "no_eligible_followup"


def test_three_round_multi_question_run_uses_local_source_breadth():
    class TwoQuestions(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Understand AI products", research_objects=["AI products"],
                              subquestions=[
                                  {"question": "What did users experience?", "priority": 1,
                                   "evidence_types": ["T2_community"], "preferred_sources": ["hacker_news"],
                                   "completion_criterion": "A recent report.", "minimum_origins": 1,
                                   "query": "AI product discussion", "language": "en"},
                                  {"question": "What alternatives exist?", "priority": 2,
                                   "evidence_types": ["T2_community"], "preferred_sources": ["reddit"],
                                   "completion_criterion": "A recent report.", "minimum_origins": 1,
                                   "query": "AI product alternatives", "language": "en"},
                              ])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    _, report, calls, _ = execute(
        TwoQuestions(assess=lambda _: {"status": "unanswered", "gap": "Open"}),
        lambda *_: [], sources=[source("hacker_news"), source("reddit")], research_rounds=3,
    )
    assert report["rounds"][0]["planned_routes"] == 4
    assert {call[0] for call in calls} == {"hacker_news", "reddit"}


def test_diagnostics_record_runtime_and_route_coverage():
    result, _, _, _ = execute(ScriptedModel(), lambda *_: [observation()])
    performance = result.diagnostics["performance"]
    assert performance["research_rounds"] == 1
    assert performance["routes_executed"] == 1
    assert performance["elapsed_seconds"] >= 0
    assert performance["synthesis_reserve_seconds"] > 0
    assert performance["retained_evidence"] == 1


def test_search_qualifiers_are_not_sent_as_subject_matter():
    from sourceglint.pipeline.query_expansion import normalize_planned_query

    assert normalize_planned_query(
        "代码智能体 开源 发布 after:2026-09-23 before:2026-11-23"
    ) == "代码智能体 开源 发布"


def test_a_plan_cannot_require_the_whole_evidence_tier_menu():
    class FourTiers(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Understand AI products", research_objects=["AI products"],
                              subquestions=[{
                                  "question": "What did users experience?", "priority": 1,
                                  "evidence_types": ["T1_official", "T2_community",
                                                     "T3_marketplace", "T4_secondary"],
                                  "preferred_sources": ["hacker_news"],
                                  "completion_criterion": "A recent report.", "minimum_origins": 1,
                                  "query": "AI product discussion", "language": "en",
                              }])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    result, _, _, _ = execute(FourTiers(), lambda *_: [observation()])
    question = result.research_plan["subquestions"][0]
    # All four useful tiers are retained; only the derived required set blocks
    # coverage, so a broad plan does not make "covered" unreachable.
    assert question["evidence_types"] == [
        "T1_official", "T2_community", "T3_marketplace", "T4_secondary",
    ]
    assert question["required_evidence"] == ["T1_official", "T2_community"]
    assert question["supporting_evidence"] == ["T3_marketplace", "T4_secondary"]


def test_maker_post_listed_as_both_vendor_and_feedback_counts_only_as_vendor():
    model = ScriptedModel(planned_source="reddit", assess=lambda payload: {
        "feedback_ids": [payload["evidence"][0]["id"]],
        "vendor_claim_ids": [payload["evidence"][0]["id"]],
    })
    _, report, _, ledger = execute(
        model, lambda *_: [observation("reddit")], sources=[source("reddit")],
    )
    row = report["subquestions"][0]
    assert row["feedback_ids"] == []
    assert row["vendor_claim_ids"] == [next(iter(ledger)).evidence_id]


def test_product_and_version_entities_survive_query_cleanup():
    from sourceglint.pipeline.query_expansion import normalize_planned_query

    cases = {
        ".NET 9 performance": ".NET 9 performance",
        "C++ vs C# benchmark": "C++ vs C# benchmark",
        "C# 13 features": "C# 13 features",
        "Claude Code release notes": "Claude Code release notes",
        "GPT-5 pricing": "GPT-5 pricing",
        "Node.js 22 LTS": "Node.js 22 LTS",
        "open source coding agent released November 2026": "open source coding agent",
    }
    for raw, expected in cases.items():
        assert normalize_planned_query(raw) == expected, raw
    assert normalize_planned_query("May launch notes", protect=["May", "launch"]) == "May launch notes"


def test_required_evidence_follows_focus_and_supporting_does_not_block_coverage():
    class CompetitionPlan(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Compare AI products", research_objects=["AI products"],
                              subquestions=[{
                                  "question": "How do competitors position?", "priority": 1,
                                  "focus": "competition",
                                  "evidence_types": ["T1_official", "T2_community",
                                                     "T3_marketplace", "T4_secondary"],
                                  "preferred_sources": ["hacker_news"],
                                  "completion_criterion": "A recent comparison.",
                                  "minimum_origins": 1, "query": "AI product comparison",
                                  "language": "en",
                              }])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    result, report, _, _ = execute(CompetitionPlan(), lambda *_: [observation()])
    question = result.research_plan["subquestions"][0]
    assert question["required_evidence"] == ["T1_official", "T3_marketplace"]
    assert "T4_secondary" in question["supporting_evidence"]
    row = report["subquestions"][0]
    # The model said "covered" but only third-party community commentary was
    # cited. Competition needs a verified vendor claim, independent test or
    # media report, so the answer is partial. Derived tiers are advisory: no
    # site type is mandatory, but the evidence kind still has to match.
    assert row["missing_required"] == []
    assert row["claim_roles"] == {"third_party_commentary": 1}
    assert row["status"] == "partial"
    assert row["answer_state"] == "partially_answered"
    assert "required kind" in row["gap"]


def test_unanswered_with_a_named_gap_is_disclosed_not_counted_as_answered():
    model = ScriptedModel(planned_source="hacker_news", assess=lambda payload: {
        "status": "unanswered", "evidence_ids": [],
        "gap": "No firsthand report was published in the window.",
    })
    _, report, _, _ = execute(model, lambda *_: [observation()])
    row = report["subquestions"][0]
    assert row["answer_state"] == "explicitly_disclosed"
    assert report["answer_states"]["explicitly_disclosed"] == 1
    assert report["subquestions_covered"] == 0


def test_source_language_mismatch_is_classified_instead_of_silently_dropped():
    _, report, calls, _ = execute(
        ScriptedModel(), lambda *_: [], sources=[source("hacker_news", languages=("ja",))],
    )
    assert calls == []
    assert report["route_rejections"].get("source_language_unsupported") >= 1


def test_plan_records_evidence_priority_routing_and_stop_rule():
    result, _, _, _ = execute(ScriptedModel(), lambda *_: [observation()])
    plan = result.research_plan
    strategy = plan["retrieval_strategy"]
    assert strategy["initial_route_limit"] >= 1
    assert "follow up only" in strategy["followup_rule"].lower()
    assert strategy["source_order"]
    assert plan["subquestions"][0]["required_evidence"]


def test_unverifiable_community_author_is_never_promoted_by_username_matching():
    class MakerPlan(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Understand Acme", research_objects=["Acme"],
                              subquestions=[{
                                  "question": "What did users report?", "priority": 1,
                                  "evidence_types": ["T2_community"],
                                  "preferred_sources": ["reddit"],
                                  "completion_criterion": "A recent report.",
                                  "minimum_origins": 1, "query": "Acme discussion",
                                  "language": "en",
                              }])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    from sourceglint.pipeline.adapters import RawSourceResult

    def maker_post(*_):
        return [RawSourceResult(
            source="reddit", source_type="post", source_native_id="m1",
            url="https://reddit.com/r/a/comments/m1", title="Acme update",
            text="Our team shipped a new Acme release.", author="acme_team",
            published_at="2026-09-08T12:00:00Z",
        )]

    model = MakerPlan(planned_source="reddit", assess=lambda payload: {
        "feedback_ids": [payload["evidence"][0]["id"]],
    })
    _, report, _, _ = execute(model, maker_post, sources=[source("reddit")])
    row = report["subquestions"][0]
    # "acme_team" looks like the vendor, but a username is not identity evidence.
    # The post's own text ("Our team shipped ...") marks it as an unverified
    # vendor claim, not firsthand user feedback.
    assert row["feedback_ids"] == []
    assert len(row["vendor_claim_ids"]) == 1
    assert row["identity_confidence"] == "unverified"
    assert row["claim_roles"] == {"vendor_claim_unverified": 1}


def test_model_flagged_vendor_post_stays_a_vendor_claim():
    class MakerPlan(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Understand Acme", research_objects=["Acme"],
                              subquestions=[{
                                  "question": "What did users report?", "priority": 1,
                                  "evidence_types": ["T2_community"],
                                  "preferred_sources": ["reddit"],
                                  "completion_criterion": "A recent report.",
                                  "minimum_origins": 1, "query": "Acme discussion",
                                  "language": "en",
                              }])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    from sourceglint.pipeline.adapters import RawSourceResult

    def maker_post(*_):
        return [RawSourceResult(
            source="reddit", source_type="post", source_native_id="m1",
            url="https://reddit.com/r/a/comments/m1", title="Acme update",
            text="Our team shipped a new Acme release.", author="acme_team",
            published_at="2026-09-08T12:00:00Z",
        )]

    model = MakerPlan(planned_source="reddit", assess=lambda payload: {
        "feedback_ids": [payload["evidence"][0]["id"]],
        "vendor_claim_ids": [payload["evidence"][0]["id"]],
    })
    _, report, _, _ = execute(model, maker_post, sources=[source("reddit")])
    row = report["subquestions"][0]
    assert row["feedback_ids"] == []
    assert len(row["vendor_claim_ids"]) == 1
    assert row["claim_roles"] == {"vendor_claim_unverified": 1}


def test_platform_release_and_official_designation_report_different_publishers():
    class OfficialPlan(ScriptedModel):
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Understand Acme", research_objects=["Acme"],
                              subquestions=[{
                                  "question": "What did Acme ship?", "priority": 1,
                                  "evidence_types": ["T1_official"],
                                  "preferred_sources": ["github", "official_web"],
                                  "completion_criterion": "An official announcement.",
                                  "minimum_origins": 2, "query": "Acme v1 release",
                                  "language": "en",
                              }])
            return super().complete_structured(task=task, payload=payload, response_schema=response_schema)

    def replies(name, _request):
        if name == "github":
            return [RawSourceResult(
                source="github", source_type="release", source_native_id="r1",
                url="https://github.com/acme/tool/releases/tag/v1", title="Acme v1",
                text="Acme shipped v1 with distributed tracing.",
                published_at="2026-09-08T12:00:00Z",
            )]
        return [RawSourceResult(
            source="official_web", source_type="page", source_native_id="o1",
            url="https://acme.example/blog/v1", title="Acme v1",
            text="Acme announces v1 with distributed tracing.",
            published_at="2026-09-08T13:00:00Z",
        )]

    _, report, _, _ = execute(OfficialPlan(planned_source="github", assess=lambda payload: {
        "followup": followup("official_web"),
    }), replies, sources=[source("github"), source("official_web")],
        query="Acme v1 release")
    row = report["subquestions"][0]
    by_platform = {entry["platform"]: entry for entry in row["provenance"]}
    # A release hosted on GitHub is a platform account, not a verified vendor.
    assert by_platform["github"]["publisher_identity"] == "platform_account"
    assert by_platform["github"]["role"] == "vendor_claim_unverified"
    # The official-site designation is the only thing that verifies identity.
    assert by_platform["official_web"]["publisher_identity"] == "verified_vendor"
    assert by_platform["official_web"]["role"] == "vendor_claim_verified"
    assert row["publisher_identities"] == {"platform_account": 1, "verified_vendor": 1}


def test_self_reported_experience_is_never_upgraded_to_verified_fact():
    model = ScriptedModel(assess=lambda payload: {
        "feedback_ids": [payload["evidence"][0]["id"]],
    })
    _, report, _, _ = execute(model, lambda *_: [observation("reddit")],
                              sources=[source("reddit")], query="AI product discussion")
    row = report["subquestions"][0]
    provenance = row["provenance"][0]
    assert provenance["firsthand"] == "self_reported"
    assert provenance["publisher_identity"] == "community_user"
    assert provenance["role"] == "firsthand_experience"
    assert row["publisher_identities"] == {"community_user": 1}


def test_short_budget_keeps_phases_non_negative_and_never_over_reserves():
    result, _, _, _ = execute(ScriptedModel(), lambda *_: [], research_timeout_seconds=5)
    performance = result.diagnostics["performance"]
    assert performance["synthesis_reserve_seconds"] <= performance["budget_seconds"] * 0.45 + 1e-6
    assert performance["research_budget_seconds"] <= performance["budget_seconds"]
    assert performance["synthesis_reserve_basis"]["short_budget"] is True
    assert all(value >= 0 for value in performance["phases"].values())
    assert set(performance["phases"]) >= {"planning", "retrieval", "assessment", "synthesis", "report"}
    assert set(performance["phase_status"]) >= {"planning", "research", "synthesis"}
