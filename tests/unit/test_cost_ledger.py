"""Invariants for the shared cost ledger and its budget decisions."""
from __future__ import annotations

from sourceglint.cost_ledger import CostLedger


def ledger(tmp_path) -> CostLedger:
    return CostLedger(tmp_path / "cost.jsonl")


def test_hard_budget_blocks_after_reported_spend_reaches_the_cap(tmp_path):
    book = ledger(tmp_path)
    book.record(run_id="a", task="assessment", status="success", cost_usd=0.03, cost_known=True)
    assert book.check(run_id="a", batch_budget_usd=0.05, run_budget_usd=None) is None
    book.record(run_id="b", task="assessment", status="success", cost_usd=0.03, cost_known=True)
    assert book.check(run_id="b", batch_budget_usd=0.05, run_budget_usd=None) == "budget_exceeded"
    assert book.totals()["spent_usd"] == 0.06
    assert book.totals()["cost_known"] is True


def test_unknown_cost_refuses_a_hard_budget_but_observe_mode_proceeds(tmp_path):
    book = ledger(tmp_path)
    book.record(run_id="a", task="assessment", status="success", cost_usd=None, cost_known=False)
    assert book.check(run_id="b", batch_budget_usd=1.0, run_budget_usd=None) == "cost_unknown"
    assert book.check(run_id="b", batch_budget_usd=1.0, run_budget_usd=None,
                      mode="observe") is None
    assert book.totals()["unknown_calls"] == 1
    assert book.totals()["spent_usd"] == 0.0


def test_run_budget_is_scoped_to_run_id_not_model_stage(tmp_path):
    book = ledger(tmp_path)
    book.record(run_id="case-a", task="planning", status="success", cost_usd=0.02, cost_known=True)
    book.record(run_id="case-a", task="assessment", status="success", cost_usd=0.02, cost_known=True)
    assert book.check(run_id="case-a", batch_budget_usd=None,
                      run_budget_usd=0.03) == "run_budget_exceeded"
    assert book.check(run_id="case-b", batch_budget_usd=None, run_budget_usd=0.03) is None
    assert book.totals(run_id="case-a")["run_spent_usd"] == 0.04
    assert book.totals(run_id="case-b")["run_spent_usd"] == 0.0


def test_no_configured_cap_never_blocks_and_malformed_lines_are_ignored(tmp_path):
    book = ledger(tmp_path)
    book.path.write_text("not json\n{\"run_id\": \"a\", \"cost_usd\": 0.01, \"cost_known\": true}\n",
                         encoding="utf-8")
    totals = book.totals()
    assert totals["entries"] == 1 and totals["spent_usd"] == 0.01
    assert book.check(run_id="a", batch_budget_usd=None, run_budget_usd=None) is None
