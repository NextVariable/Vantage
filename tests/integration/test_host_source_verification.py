"""Frozen original-page samples from the Phase 3 Host audit."""

import io
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

from sourceglint.application.api import run_sourceglint
from sourceglint.host_stdio import StdioHostSource
from sourceglint.ids import canonicalize_url
from sourceglint.intelligence.model import ModelResponse, ModelStatus
from sourceglint.ledger import EvidenceLedger
from sourceglint.source_catalog import load_source_catalog, select_host_search_targets

ROOT = Path(__file__).resolve().parents[2]
PACK = json.loads((ROOT / "docs/host-web-verification-tasks.json").read_text(encoding="utf-8"))
CATALOG = {row.name: row for row in load_source_catalog()}
ROWS = PACK["tasks"] + PACK["supplemental_tasks"]
VERIFIED = [row for row in ROWS if row["status"] == "verified"]


class UnavailableModel:
    def complete_structured(self, *, task, **kwargs):
        return ModelResponse(task=task, status=ModelStatus.UNAVAILABLE)


def replay(row):
    sample = row["sample"]
    name = row["platform"]
    context = row["vantage"]["replay_context"]
    profile = context["profile"]
    entries = yaml.safe_load((ROOT / f"config/sources-{profile}.yaml").read_text(encoding="utf-8"))
    host_entry = next(source for source in entries if source["name"] == "host_web_search")
    published_at = date.fromisoformat(sample["published_at"])
    as_of = published_at + timedelta(days=1)
    reply = {
        "type": "source_response",
        "source": "host_web_search",
        "results": [{
            "source_type": sample["source_type"],
            "source_native_id": f"{name}:{published_at}",
            "title": sample["title"],
            "text": sample["excerpt"],
            "url": sample["final_url"],
            "published_at": f"{published_at}T00:00:00Z",
            "language": context["language"],
            "market": context["market"],
        }],
        "searched_targets": [{"name": name, "status": "success"}],
        "limitations": ["Frozen original-page sample; date has calendar-day precision."],
    }
    frames = io.StringIO()
    host = StdioHostSource(
        "host_web_search",
        input_stream=io.StringIO(json.dumps(reply) + "\n"),
        output_stream=frames,
    )
    ledger = EvidenceLedger(":memory:")
    result = run_sourceglint(
        sample["title"], model=UnavailableModel(),
        as_of=f"{as_of}T11:30:00Z",
        window_days=30,
        mode=context["mode"], market=context["market"], languages=[context["language"]],
        adapter_factory=lambda *_: host, sources=[host_entry], ledger=ledger,
    )
    return result, ledger, [json.loads(line) for line in frames.getvalue().splitlines()]


def test_audit_attempts_all_phase3_tasks_and_preserves_catalog_scope():
    assert PACK["task_count"] == len(PACK["tasks"]) == 65
    assert len({row["platform"] for row in ROWS}) == len(ROWS)
    for row in ROWS:
        assert row["probe_query"] and row["capabilities"]["search"] != "unconfirmed"
        assert set(row["capabilities"]) == {"search", "body", "comments", "engagement"}
        assert row["status"] != "pending_host"
        if "sample" not in row:
            assert row["reason"]
    for key, budget, mode, market, language in [
        ("g2", 3, "voc", "global", "en"),
        ("pr_times", 3, "launch", "jp", "ja"),
    ]:
        routed = select_host_search_targets(
            tuple(CATALOG.values()), budget=budget, mode=mode, market=market, language=language,
        )
        assert len(routed) <= budget
        assert key in {target.name for target in routed}


@pytest.mark.parametrize("row", VERIFIED, ids=lambda row: row["platform"])
def test_dated_original_survives_host_ledger_and_evidence_report(row):
    name = row["platform"]
    sample = row["sample"]
    target = CATALOG[name]
    url = sample["final_url"]
    hostname = urlsplit(url).hostname
    assert hostname and any(hostname == d or hostname.endswith("." + d) for d in target.domains)
    context = row["vantage"]["replay_context"]
    assert "host_web_search" in target.routes
    assert target.availability != "unavailable"
    assert context["mode"] in target.modes

    result, ledger, frames = replay(row)
    assert len(ledger) == 1
    record = next(iter(ledger))
    assert record.url == canonicalize_url(url) and record.snippet == sample["excerpt"]
    assert record.published_at.startswith(sample["published_at"])
    assert result.delivery_level == "evidence_only_report"
    assert record.url in result.brief_markdown and record.evidence_id in result.brief_markdown
    assert name in result.diagnostics["coverage"]["searched_targets"]
    assert frames and all(len(frame.get("targets", [])) <= 10 for frame in frames)
