"""The 1.1 connectors must reach the evidence ledger, not just return data."""

from __future__ import annotations

from sourceglint.pipeline.adapters import RawSourceResult

from test_adaptive_research import ScriptedModel, execute, followup, observation, source


def _paper(source_name: str, native_id: str, url: str) -> RawSourceResult:
    return RawSourceResult(
        source=source_name,
        source_type="page",
        source_native_id=native_id,
        url=url,
        title="Large language model evaluation study",
        text="A peer-reviewed study reports that evaluation practice varies across teams.",
        author="Example author",
        published_at="2026-09-01T00:00:00Z",
        language="en",
        market="global",
        query="large language model evaluation",
        query_language="en",
        raw_metadata={"date_semantics": "publication_date"},
    )


def test_new_structured_sources_enter_the_evidence_ledger():
    def replies(name, request):
        if name == "crossref":
            return [_paper("crossref", "doi:10.5555/example", "https://doi.org/10.5555/example")]
        if name == "openalex":
            return [_paper("openalex", "openalex:W123", "https://openalex.org/W123")]
        return [observation(name)]

    def assess(payload):
        if len(payload["already_planned"]) < 2:
            return {
                "status": "partial",
                "gap": "Need bibliographic coverage from a second index.",
                "followup": followup("openalex", "large language model evaluation 2026"),
            }
        return {"status": "covered", "gap": ""}

    result, report, calls, ledger = execute(
        ScriptedModel(planned_source="crossref", assess=assess),
        replies,
        sources=[source("crossref"), source("openalex")],
        research_rounds=3,
    )

    rows = ledger.all()
    sources_seen = {row.source for row in rows}
    assert {"crossref", "openalex"} <= sources_seen
    assert all(row.url.startswith("https://") for row in rows)
    assert all(row.published_at for row in rows)
    assert result.diagnostics["coverage"]["failed_sources"] == []
    assert len(calls) == 2
    assert report["stop_reason"] in {"criteria_met", "covered"}
