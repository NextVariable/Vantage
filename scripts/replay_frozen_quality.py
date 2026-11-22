"""Replay the FACT support contract over one frozen research run.

The replay reads the Evidence Ledger captured by a previous real run and
re-evaluates facts against it. It performs no retrieval and spends no host
budget, so its output is an engineering regression over historical data —
never a new web-research result and never release evidence for research
quality.

For every fact it reports both policies side by side:

  * ``legacy`` — the pre-contract check: every cited evidence id exists.
  * ``contract`` — claim → evidence id → verbatim excerpt support.

Usage:
    python3 scripts/replay_frozen_quality.py --run runs/rc/<case>/
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sourceglint.insights.evidence_support import (  # noqa: E402
    MIN_EXCERPT_CHARS, evidence_text, is_vendor_material, verify_fact_support,
)

LABEL = "frozen replay over historical evidence — engineering regression, not a new web-research result"


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_sentence(row: dict) -> str:
    text = evidence_text(row).replace("\n", " ")
    for piece in text.replace("。", ".").replace("！", ".").replace("？", ".").split("."):
        piece = piece.strip()
        if len(piece) >= MIN_EXCERPT_CHARS:
            return piece
    return ""


def _frozen_probes(rows: list[dict]) -> list[dict]:
    """Structural probes over the frozen ledger (no retrieval, no new claims).

    A positive probe quotes a real sentence with its own id; a cross-wired
    probe quotes one item's sentence but cites a different valid id.
    """
    if len(rows) < 2:
        return []
    first, second = rows[0], rows[1]
    quote = _first_sentence(first)
    other = _first_sentence(second)
    if not quote or not other:
        return []
    return [
        {
            "label": "positive: verbatim excerpt under its own id",
            "synthetic": True,
            "statement": quote,
            "evidence_ids": [first["evidence_id"]],
            "claims": [{"claim": quote, "evidence_id": first["evidence_id"], "excerpt": quote}],
        },
        {
            "label": "negative: valid id, excerpt belongs to another item",
            "synthetic": True,
            "statement": other,
            "evidence_ids": [first["evidence_id"]],
            "claims": [{"claim": other, "evidence_id": first["evidence_id"], "excerpt": other}],
        },
    ]


def _fact_probes(result: dict) -> list[dict]:
    probes = []
    for row in result.get("insights") or []:
        if str(row.get("type") or "").upper() != "FACT":
            continue
        probes.append({
            "label": "real: FACT captured in the frozen run",
            "synthetic": False,
            "statement": str(row.get("statement") or row.get("text") or ""),
            "evidence_ids": list(row.get("evidence_ids") or ()),
            "claims": list(row.get("claims") or ()),
        })
    return probes


def _legacy_accepts(probe: dict, evidence_by_id: dict) -> bool:
    """The pre-contract gate: cite at least one existing id, text non-empty."""
    ids = [str(eid) for eid in probe["evidence_ids"]]
    return bool(probe["statement"].strip()) and bool(ids) and all(
        eid in evidence_by_id for eid in ids
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="frozen run directory")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--probes", type=Path, default=None,
                        help="optional JSON array of {statement, evidence_ids, claims}")
    args = parser.parse_args()

    run = args.run.resolve()
    if not run.is_dir():
        parser.error(f"not a run directory: {run}")
    evidence_path = run / "evidence.jsonl"
    rows = _jsonl(evidence_path)
    evidence_by_id = {str(row.get("evidence_id")): row for row in rows if row.get("evidence_id")}
    result = {}
    if (run / "result.json").exists():
        result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    run_meta = json.loads((run / "run.json").read_text(encoding="utf-8")) if (run / "run.json").exists() else {}
    provenance = (json.loads((run / "provenance.json").read_text(encoding="utf-8"))
                  if (run / "provenance.json").exists() else {})

    if args.probes is not None:
        probes = json.loads(args.probes.resolve().read_text(encoding="utf-8"))
        for probe in probes:
            probe.setdefault("synthetic", True)
            probe.setdefault("label", "supplied replay probe")
    else:
        probes = _fact_probes(result)
        if not probes:
            probes = _frozen_probes(rows)

    evaluated = []
    for probe in probes:
        support = verify_fact_support(
            str(probe.get("statement") or ""),
            tuple(str(eid) for eid in probe.get("evidence_ids") or ()),
            tuple(probe.get("claims") or ()),
            evidence_by_id,
        )
        cited = [str(eid) for eid in probe.get("evidence_ids") or ()]
        evaluated.append({
            **probe,
            "legacy": "accepted" if _legacy_accepts(probe, evidence_by_id) else "rejected",
            "contract": support.status,
            "contract_rejected": support.rejected,
            "independent_origins": support.independent_origins,
            "reasons": list(support.reasons),
            "claims": [claim.to_dict() for claim in support.claims],
            "vendor_material": [eid for eid in cited if is_vendor_material(evidence_by_id.get(eid))],
        })

    summary = {
        "label": LABEL,
        "kind": "frozen_replay",
        "not_a_new_research_result": True,
        "release_evidence": False,
        "run": str(run.relative_to(ROOT) if run.is_relative_to(ROOT) else run),
        "frozen": {
            "evidence_sha256": _sha256(evidence_path),
            "evidence_rows": len(rows),
            "result_sha256": _sha256(run / "result.json"),
            "status": result.get("status"),
            "commit_sha": run_meta.get("commit_sha"),
            "provenance_kind": run_meta.get("provenance_kind"),
            "as_of": run_meta.get("as_of"),
            "model": run_meta.get("host"),
            "provenance": provenance.get("provenance") or {},
        },
        "totals": {
            "facts": len(evaluated),
            "legacy_accepted": sum(1 for row in evaluated if row["legacy"] == "accepted"),
            "contract_rejected": sum(1 for row in evaluated if row["contract_rejected"]),
            "contract_by_status": {
                status: sum(1 for row in evaluated if row["contract"] == status)
                for status in sorted({row["contract"] for row in evaluated})
            },
            "synthetic_probes": sum(1 for row in evaluated if row["synthetic"]),
        },
        "facts": evaluated,
    }
    target = args.output.resolve() if args.output is not None else run / "replay.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["totals"], ensure_ascii=False))
    print(f"replay written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
