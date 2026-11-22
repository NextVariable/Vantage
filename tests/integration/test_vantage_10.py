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


def test_timed_native_request_does_not_touch_network_after_deadline():
    from sourceglint.connectors._http import HttpTimeoutError, StdlibHttpClient

    with deadline_scope(monotonic() - 1), pytest.raises(HttpTimeoutError):
        StdlibHttpClient().request("https://example.invalid")
