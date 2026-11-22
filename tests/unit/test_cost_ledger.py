"""Invariants for the shared cost ledger and its budget decisions."""
from __future__ import annotations

import threading

from sourceglint.cost_ledger import CostLedger, budget_enforcement


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


def test_reservation_is_atomic_across_threads(tmp_path):
    """Eight contenders, one shared file, a cap that fits exactly two."""
    path = tmp_path / "cost.jsonl"
    barrier = threading.Barrier(8)
    grants: list[dict] = []

    def worker():
        book = CostLedger(path)
        barrier.wait()
        grants.append(book.reserve(run_id="case", task="assessment", ceiling_usd=0.02,
                                   batch_budget_usd=0.05))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    granted = [grant for grant in grants if grant["granted"]]
    assert len(granted) == 2
    totals = CostLedger(path).totals()
    assert totals["in_flight_calls"] == 2
    assert totals["committed_usd"] == 0.04
    assert totals["unknown_calls"] == 0


def test_in_flight_reservation_counts_against_the_cap(tmp_path):
    book = ledger(tmp_path)
    first = book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                         batch_budget_usd=0.05)
    assert first["granted"] is True
    second = book.reserve(run_id="b", task="assessment", ceiling_usd=0.03,
                          batch_budget_usd=0.05)
    assert second["granted"] is False and second["category"] == "budget_exceeded"
    totals = book.totals()
    assert totals["spent_usd"] == 0.0 and totals["in_flight_usd"] == 0.03
    assert totals["committed_usd"] == 0.03


def test_settlement_releases_the_unused_reservation(tmp_path):
    book = ledger(tmp_path)
    reservation = book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                               batch_budget_usd=0.05)
    book.settle(reservation["call_id"], run_id="a", task="assessment", status="success",
                cost_usd=0.01, cost_known=True, cost_state="known")
    assert book.totals()["committed_usd"] == 0.01
    assert book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                        batch_budget_usd=0.05)["granted"] is True
    refused = book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                           batch_budget_usd=0.05)
    assert refused["granted"] is False


def test_unknown_settlement_charges_the_ceiling_and_blocks_the_next_call(tmp_path):
    book = ledger(tmp_path)
    reservation = book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                               batch_budget_usd=1.0)
    result = book.settle(reservation["call_id"], run_id="a", task="assessment",
                         status="timeout", cost_usd=0.03, cost_known=False,
                         cost_state="unknown", basis="ceiling")
    assert result["charged_usd"] == 0.03
    totals = book.totals()
    assert totals["spent_usd"] == 0.03 and totals["unknown_calls"] == 1
    assert totals["cost_known"] is False
    refused = book.reserve(run_id="b", task="assessment", ceiling_usd=0.03,
                           batch_budget_usd=1.0)
    assert refused["granted"] is False and refused["category"] == "cost_unknown"


def test_unbilled_settlement_is_zero_and_does_not_block(tmp_path):
    book = ledger(tmp_path)
    reservation = book.reserve(run_id="a", task="assessment", ceiling_usd=0.03,
                               batch_budget_usd=0.05)
    book.settle(reservation["call_id"], run_id="a", task="assessment", status="auth_failed",
                cost_usd=0.0, cost_known=True, cost_state="unbilled", basis="no_charge")
    totals = book.totals()
    assert totals["spent_usd"] == 0.0 and totals["unknown_calls"] == 0
    assert totals["states"] == {"unbilled": 1}
    assert book.reserve(run_id="b", task="assessment", ceiling_usd=0.03,
                        batch_budget_usd=0.05)["granted"] is True


def test_a_bill_above_the_ceiling_is_reported_as_overshoot(tmp_path):
    book = ledger(tmp_path)
    reservation = book.reserve(run_id="a", task="assessment", ceiling_usd=0.02,
                               batch_budget_usd=1.0)
    result = book.settle(reservation["call_id"], run_id="a", task="assessment",
                         status="success", cost_usd=0.025, cost_known=True)
    assert result["overshoot_usd"] == 0.005
    assert book.totals()["overshoot_usd"] == 0.005


def test_enforcement_is_strict_only_with_a_known_call_ceiling():
    assert budget_enforcement(mode="hard", batch_budget_usd=1.0, max_call_usd=0.05) == "strict"
    assert budget_enforcement(mode="hard", batch_budget_usd=1.0, max_call_usd=None) == "guarded"
    assert budget_enforcement(mode="observe", batch_budget_usd=1.0, max_call_usd=0.05) == "observe"
    assert budget_enforcement(mode="hard", batch_budget_usd=None, max_call_usd=0.05) == "none"

