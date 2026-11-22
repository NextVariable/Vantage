"""Audit completed host runs and prepare blinded packets for separate review.

Machine checks establish only ledger consistency, workflow completion and
reported source outcomes. Semantic quality labels are supplied separately by
a reviewer who did not generate the report.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from random import Random
import re
from statistics import median
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CITATION = re.compile(r"\]\((https?://[^\s)]+)\) · (\d{4}-\d{2}-\d{2}) `(ev_[a-z2-7]+)`")
EVIDENCE_ID = re.compile(r"`(ev_[a-z2-7]+)`")


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def jsonl(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def span(window, metadata):
    if "days" in window:
        end = timestamp(metadata["as_of"])
        return end - timedelta(days=window["days"]), end
    return timestamp(window["start"]), timestamp(window["end"])


def audit_case(folder):
    metadata = load(folder / "run.json", {})
    if not metadata:
        return None, None
    status = load(folder / "status.json", {})
    result = load(folder / "result.json", {})
    report = result.get("brief_markdown", "")
    ledger = {row["evidence_id"]: row for row in jsonl(folder / "evidence.jsonl")}
    diagnostics = result.get("diagnostics", {})
    coverage = diagnostics.get("coverage", {})
    adaptive = coverage.get("adaptive_research", {})
    rounds = adaptive.get("rounds", [])
    assessments = adaptive.get("subquestions", [])
    ids = set(EVIDENCE_ID.findall(report))
    cited_rows = {(url, date, eid) for url, date, eid in CITATION.findall(report)}
    consistent = set()
    for url, date, eid in cited_rows:
        row = ledger.get(eid)
        if row and (url == row["url"] or unquote(url) == unquote(row["url"])) and row["published_at"][:10] == date:
            consistent.add((url, date, eid))
    plan = result.get("research_plan") or {}
    in_window = None
    if "time_window" in plan:
        lower, upper = span(plan["time_window"], metadata)
        in_window = sum(lower <= timestamp(row["published_at"]) <= upper for row in ledger.values())
    frames = sorted(folder.glob("request-*.json"))
    replies = {path.stem.removeprefix("reply-"): load(path) for path in folder.glob("reply-*.json")}
    source_frames = [load(path) for path in frames if load(path).get("type") == "source_request"]
    invalid_source = sum(
        isinstance(reply, dict) and reply.get("type") == "source_response"
        and "error" not in reply and not isinstance(reply.get("results"), list)
        for reply in replies.values()
    )
    row = {
        "case": metadata["case"]["id"], "focus": metadata["case"]["focus"], "language": metadata["case"]["language"],
        "commit_sha": metadata["commit_sha"], "dirty": metadata["dirty"], "complete_record": bool(status and result),
        "status": result.get("status"), "failure": status.get("failure"), "planned_by_host": adaptive.get("planning_status") == "planned",
        "had_actual_online_route": any(r.get("executed_routes", 0) for r in rounds),
        "retained_evidence": len(ledger), "in_window": in_window,
        "synthesis_evidence": adaptive.get("synthesis_evidence_count"),
        "displayed_ids": len(ids), "linked_displayed_ids": len({eid for _, _, eid in consistent}),
        "citation_occurrences_distinct": len(cited_rows), "citation_occurrences_matching_ledger": len(consistent),
        "unrecognized_ids": sorted(ids - ledger.keys()),
        "rounds": len(rounds), "stop_reason": adaptive.get("stop_reason"),
        "adapter_requests": sum(r.get("executed_routes", 0) for r in rounds),
        "followup_with_new_retained_candidates": sum(bool(r.get("new_evidence")) for r in rounds[1:]),
        "failed_sources": coverage.get("failed_sources", []), "host_unavailable_targets": coverage.get("unavailable_targets", []),
        "host_source_frames": len(source_frames), "host_invalid_source_reply": invalid_source,
        "model_frames": len(frames) - len(source_frames), "elapsed_seconds": status.get("elapsed_seconds"),
        "host_events": status.get("host_event_types"), "reported_tokens": status.get("reported_tokens"),
        "self_reported_questions": len(assessments), "self_reported_covered": sum(x["status"] == "covered" for x in assessments),
        "hypotheses": len(diagnostics.get("opportunity_discovery", {}).get("hypotheses", [])),
    }
    review = None
    if report:
        review = {
            "question": metadata["case"]["question"], "focus": row["focus"],
            "cutoff_utc": metadata["as_of"], "time_window": plan.get("time_window"),
            "brief": report, "evidence_for_displayed_ids": {eid: ledger[eid] for eid in sorted(ids & ledger.keys())},
        }
    return row, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "runs"):
        parser.error("audit artifacts must stay below ignored runs/")
    out.mkdir(parents=True, exist_ok=True)
    packets, summaries = [], {}
    for directory in args.runs:
        cases = []
        for folder in sorted(p for p in directory.iterdir() if p.is_dir()):
            row, review = audit_case(folder)
            if row:
                cases.append(row)
                if review:
                    packets.append((directory.name, row["case"], review))
        elapsed = [x["elapsed_seconds"] for x in cases if x["elapsed_seconds"] is not None]
        summaries[directory.name] = {
            "cases": cases, "run_records": len(cases), "complete": sum(x["complete_record"] for x in cases),
            "recorded_median_seconds": median(elapsed) if elapsed else None,
            "semantic_quality": "requires separate review",
        }
    Random(125233).shuffle(packets)
    key = {}
    for index, (arm, case, packet) in enumerate(packets, 1):
        name = f"packet-{index:03}"
        key[name] = {"arm": arm, "case": case}
        (out / f"{name}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "private-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "machine-audit.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
