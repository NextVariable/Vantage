"""API, host and deadline regression coverage for the 1.0 research path."""
import io
from dataclasses import replace
from threading import Event
from time import monotonic

import pytest

from sourceglint.cli import vantage_main
from sourceglint.deadline import deadline_scope
from sourceglint.host_stdio import StdioHostModel
from sourceglint.intelligence.model import ModelStatus
from sourceglint.interface.parser import parse_query, requests_opportunities

from test_adaptive_research import ScriptedModel, execute, followup, observation, source


def test_useful_new_citation_unlocks_a_third_round():
    def assess(payload):
        count = len(payload["already_planned"])
        if count == 3:
            return {}
        return {"status": "partial", "gap": "Still need stronger evidence.",
                "followup": {**followup("reddit", f"AI user review variant {count}"), "gain": "high"}}

    model = ScriptedModel(assess=assess)
    def replies(name, request):
        key = str(len(request["query"])) if name == "hacker_news" else request["query"][-1]
        return [replace(observation(name, native_id=key),
                        text=f"A user provides a distinct review observation for query {request['query']}.")]

    result, report, calls, ledger = execute(model, replies, research_rounds=3)
    assert len(calls) == len(report["rounds"]) == len(ledger) == 3
    assert result.research_plan["budget"]["max_queries"] == 12
    assert report["stop_reason"] == "criteria_met"


def test_unrelated_hits_and_low_gain_do_not_extend_research():
    def assess(payload):
        count = len(payload["already_planned"])
        return {"status": "partial", "gap": "Open",
                "evidence_ids": [item["id"] for item in payload["evidence"] if item["platform"] == "Hacker News"],
                "followup": followup("reddit", f"alternative query {count}")}

    _, report, calls, _ = execute(ScriptedModel(assess=assess), lambda name, _: [observation(name)],
                                  research_rounds=3)
    assert len(calls) == 2 and report["stop_reason"] == "no_material_gain"

    _, report, calls, _ = execute(ScriptedModel(assess=lambda p: {
        "status": "partial", "followup": {**followup("reddit"), "gain": "low"},
    }), lambda *_: [])
    assert len(calls) == 1 and report["stop_reason"] == "no_eligible_followup"


def test_a_grounded_verification_can_follow_a_covered_question():
    def assess(payload):
        ids = [row["id"] for row in payload["evidence"]]
        return {"followup": {**followup("reddit"), "kind": "verification",
                             "gain": "high", "lead_ids": ids[:1]}}
    _, report, calls, _ = execute(ScriptedModel(assess=assess), lambda name, _: [observation(name)])
    assert len(calls) == 2
    assert report["rounds"][0]["subquestions"][0]["followup_kind"] == "verification"


def test_host_timeout_does_not_accept_a_late_reply_as_a_new_message():
    resume = Event()

    class SilentPipe(io.StringIO):
        def readline(self, *args):
            resume.wait(1)
            return super().readline(*args)

    text = '{"type":"model_response","task":"coverage","payload":{}}\n'
    pipe = SilentPipe(text)
    model = StdioHostModel(input_stream=pipe, output_stream=io.StringIO())
    try:
        with deadline_scope(monotonic() + 0.02):
            first = model.complete_structured(task="coverage", payload={}, response_schema={})
        assert first.status is ModelStatus.TIMEOUT
        resume.set()
        second = model.complete_structured(task="coverage", payload={}, response_schema={})
        assert second.status is ModelStatus.TIMEOUT
        assert len(model.output_stream.getvalue().splitlines()) == 1
    finally:
        resume.set()


def test_custom_window_excludes_following_day_and_future():
    def replies(*_):
        return [observation(native_id="start", published="2026-09-08T00:00:00Z"),
                observation(native_id="end", published="2026-09-08T23:59:59Z"),
                observation(native_id="future", published="2026-09-09T01:00:00Z")]
    result, _, _, ledger = execute(ScriptedModel(), replies, start_date="2026-09-08", end_date="2026-09-09",
                                  sources=[source("hacker_news")])
    assert len(ledger) == 2
    assert result.research_plan["time_window"]["end"] == "2026-09-09T00:00:00+00:00"
    assert parse_query("研究 2026-09-01 至 2026-09-02 的进展").time_window["start"] == "2026-09-01T00:00:00Z"
    with pytest.raises(ValueError, match="must precede"):
        parse_query("Research 2026-09-04 through 2026-09-02")


@pytest.mark.parametrize(("query", "is_requested"), [
    ("What opportunities could we validate in offline transcription?", True),
    ("Find recent transcription updates without suggesting opportunities.", False),
    ("研究最近有哪些创业机会，怎么验证？", True),
    ("研究产品变化，不需要提出创业机会。", False),
    ("ローカル翻訳の事業機会を探す", True),
    ("事業機会は不要。更新情報を調べる", False),
    ("Summarize recent industry changes and user complaints.", False),
])
def test_natural_opportunity_opt_in(query, is_requested):
    assert requests_opportunities(query) is is_requested


def test_branded_cli_has_a_compatible_model_boundary(capsys):
    with pytest.raises(SystemExit) as exc:
        vantage_main(["--help"])
    assert exc.value.code == 0
    assert "usage: vantage" in capsys.readouterr().out


def test_synthesis_and_brief_exclude_unassessed_candidates_but_ledger_keeps_them():
    def assess(payload):
        supported = [e["id"] for e in payload["evidence"] if "Noise candidate" not in e["title"]]
        return {"evidence_ids": supported, "status": "covered"}

    model = ScriptedModel(assess=assess)
    result, report, _, ledger = execute(model, lambda *_: [
        observation(),
        replace(observation(native_id="noise"), title="Noise candidate", text="An unrelated tourism story."),
    ])
    assert len(ledger) == 2 and report["synthesis_evidence_count"] == 1
    clustering = next(payload for task, payload in model.tasks if task == "clustering")
    assert len(clustering["evidence_items"]) == 1
    assert "Noise candidate" not in result.brief_markdown


def test_empty_screening_falls_back_to_the_retained_corpus():
    """A screening step that returns nothing must not erase retrieved evidence."""

    def assess(payload):
        return {"evidence_ids": [], "status": "covered"}

    model = ScriptedModel(assess=assess)
    result, report, _, ledger = execute(model, lambda *_: [observation()])
    assert len(ledger) == 1
    assert report["synthesis_evidence_count"] == 1
    clustering = next(payload for task, payload in model.tasks if task == "clustering")
    assert len(clustering["evidence_items"]) == 1
    assert any("screening selected no evidence" in w for w in result.warnings)


def test_timed_native_request_does_not_touch_network_after_deadline():
    from sourceglint.connectors._http import HttpTimeoutError, StdlibHttpClient

    with deadline_scope(monotonic() - 1), pytest.raises(HttpTimeoutError):
        StdlibHttpClient().request("https://example.invalid")


def test_competition_timeout_keeps_both_sides_and_rejects_frozen_directory_pr():
    from sourceglint.application.api import run_sourceglint
    from sourceglint.intelligence.model import ModelResponse
    from sourceglint.pipeline.adapters import RawSourceResult
    from test_adaptive_research import answer

    rows = [
        RawSourceResult(
            "host_web_search", "release", "cursor-voice", "https://cursor.com/changelog",
            "Voice Chat with Agents",
            "Voice chat works in the Agents Window, the IDE, on web, and in Cursor for iOS.",
            published_at="2026-11-06T00:00:00Z",
        ),
        RawSourceResult(
            "host_web_search", "release", "copilot-ignite",
            "https://github.blog/changelog/2026-11-17-github-copilot-app-microsoft-ignite-releases",
            "GitHub Copilot app, Microsoft Ignite releases",
            "Azure DevOps integration is now in public preview.",
            published_at="2026-11-17T00:00:00Z",
        ),
        RawSourceResult(
            "github", "post", "1951", "https://github.com/jaw9c/awesome-remote-mcp-servers/pull/1951",
            "Add Calven", "Adds Calven under Market Intelligence. Its hosted MCP server gives Cursor and Copilot access.",
            published_at="2026-11-03T19:02:33Z",
        ),
    ]

    class TimeoutModel:
        def complete_structured(self, *, task, payload, response_schema):
            if task == "research_planning":
                return answer(task, goal="Compare the products", research_objects=["Cursor AI editor", "GitHub Copilot"],
                              subquestions=[{
                                  "question": "Which product changes shipped?", "priority": 1,
                                  "evidence_types": ["T1_official"], "preferred_sources": ["host_web_search"],
                                  "completion_criterion": "Dated changes from each vendor.",
                                  "minimum_origins": 2, "query": "release changes", "language": "en",
                              }])
            return ModelResponse(task=task, status=ModelStatus.TIMEOUT)

    class FrozenAdapter:
        def retrieve(self, plan, request):
            return rows

    result = run_sourceglint(
        "How did Cursor AI editor and GitHub Copilot change?", mode="competitor",
        adaptive=True, model=TimeoutModel(), as_of="2026-11-24T08:15:00Z",
        sources=[source("host_web_search")], adapter_factory=lambda *_: FrozenAdapter(),
    )
    body = result.brief_markdown
    assert result.status.value == "PARTIAL"
    assert result.delivery_level == "evidence_only_report"
    assert result.diagnostics["evidence_count"] == 2
    assert result.diagnostics["insight_count"] == 0
    assert "| Dimension | Cursor AI editor | GitHub Copilot |" in body
    assert "Voice chat works" in body and "Azure DevOps integration" in body
    assert "2026-11-06" in body and "2026-11-17" in body
    assert "| Firsthand use and counterexamples | Uncovered in the retained sample" in body
    assert "Calven" not in body and "/pull/1951" not in body


def test_comparison_preserves_firsthand_counterevidence_without_guessing_equivalence():
    from sourceglint.brief import sections
    from sourceglint.brief.competition import collect_comparison
    from sourceglint.ledger import EvidenceRecord

    records = [
        EvidenceRecord("report", "reddit", "post", "https://reddit.com/r/example/01",
                       "2026-11-24", "2026-11-19", title="Nimbus versus Orchard",
                       snippet="I tried Nimbus for two days and stopped using it after sync failed."),
        EvidenceRecord("promo", "github", "post", "https://github.com/someone/directory/pull/5",
                       "2026-11-24", "2026-11-20", title="Add connector",
                       snippet="Connector supports Nimbus and Orchard."),
    ]
    products, observations = collect_comparison(
        "Compare Nimbus and Orchard", {"research_objects": ["Nimbus", "Orchard"]}, records,
    )
    body = sections.comparison({"products": products, "observations": observations},
                               {row.evidence_id: row for row in records})
    assert "First-person account" in body and "sync failed" in body
    assert observations[0]["product"] == "Nimbus" and len(observations) == 1
    assert "Uncovered in the retained sample" in body
    assert "Connector supports" not in body
