"""Contract tests for the provider-neutral command host runtime."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sourceglint.cost_ledger import CostLedger
from sourceglint.host_command import CommandHostModel, _extract_json, build_model
from sourceglint.intelligence.model import ModelStatus

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}


def runner(expression: str, *, exit_code: int = 0, sleep: float = 0.0):
    code = (
        "import json, sys, time\n"
        f"time.sleep({sleep})\n"
        f"print({expression})\n"
        f"sys.exit({exit_code})\n"
    )
    return [sys.executable, "-c", code]


def call(model, task="research_planning"):
    return model.complete_structured(task=task, payload={"request": "x"}, response_schema=SCHEMA)


def test_valid_reply_is_accepted_and_usage_is_recorded_separately(tmp_path):
    log = tmp_path / "usage.jsonl"
    model = CommandHostModel(command=runner("json.dumps({'answer': 'ok'})"), usage_log=log)
    response = call(model)
    assert response.status is ModelStatus.SUCCESS and response.payload == {"answer": "ok"}
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "success" and record["task"] == "research_planning"
    assert "payload" not in record and "request" not in record
    assert model.usage_summary()["calls"] == 1


def test_prose_or_fenced_reply_is_parsed_without_inventing_values():
    model = CommandHostModel(command=runner(
        "'Sure:\\n```json\\n' + json.dumps({'answer': 'ok'}) + '\\n```'"
    ))
    assert call(model).status is ModelStatus.SUCCESS


@pytest.mark.parametrize("expression", ["'not json at all'", "json.dumps({'nope': 1})"])
def test_invalid_reply_maps_to_invalid_output(expression):
    model = CommandHostModel(command=runner(expression))
    response = call(model)
    assert response.status is ModelStatus.INVALID_OUTPUT
    assert response.payload is None


def test_nonzero_exit_maps_to_unavailable_with_error_excerpt():
    model = CommandHostModel(command=runner("'{}'", exit_code=3))
    response = call(model)
    assert response.status is ModelStatus.UNAVAILABLE
    assert "exited 3" in response.error


def test_timeout_maps_to_timeout_and_does_not_raise():
    model = CommandHostModel(command=runner("'{}'", sleep=3), timeout=0.2)
    assert call(model).status is ModelStatus.TIMEOUT


def test_missing_command_is_unavailable():
    model = CommandHostModel(command=["definitely-not-an-installed-model-command"])
    response = call(model)
    assert response.status is ModelStatus.UNAVAILABLE
    assert "could not run" in response.error


def test_json_envelope_separates_model_text_from_usage(tmp_path):
    envelope = {
        "type": "result", "result": json.dumps({"answer": "ok"}),
        "usage": {"input_tokens": 11, "output_tokens": 3}, "total_cost_usd": 0.02,
    }
    model = CommandHostModel(
        command=runner(f"json.dumps({envelope!r})"), output_mode="json_envelope",
        usage_log=tmp_path / "usage.jsonl",
    )
    assert call(model).status is ModelStatus.SUCCESS
    summary = model.usage_summary()
    assert summary["reported_tokens"] == {"input_tokens": 11, "output_tokens": 3,
                                          "cache_read_input_tokens": 0}
    assert summary["spent_usd"] == 0.02
    assert summary["cost_known"] is True


def test_build_model_requires_an_explicit_local_command(monkeypatch):
    monkeypatch.delenv("SOURCEGLINT_HOST_CMD", raising=False)
    with pytest.raises(ValueError, match="SOURCEGLINT_HOST_CMD"):
        build_model()
    monkeypatch.setenv("SOURCEGLINT_HOST_CMD", f"{sys.executable} -c pass")
    monkeypatch.setenv("SOURCEGLINT_HOST_TIMEOUT", "33")
    model = build_model()
    assert model.command[:1] == [sys.executable] and model.timeout == 33


def test_malformed_command_config_never_echoes_its_raw_value(monkeypatch):
    monkeypatch.setenv("SOURCEGLINT_HOST_CMD", "runner --key sk-SECRET123456 'unclosed")
    with pytest.raises(ValueError) as error:
        build_model()
    assert "sk-SECRET123456" not in str(error.value)


def test_argv_prompt_mode_passes_the_prompt_without_a_shell():
    model = CommandHostModel(
        command=[sys.executable, "-c",
                 "import json,sys; print(json.dumps({'answer': sys.argv[1][:4]}))"],
        prompt_mode="argv",
    )
    response = model.complete_structured(task="t", payload={}, response_schema=SCHEMA)
    assert response.status is ModelStatus.SUCCESS
    assert response.payload["answer"] == "You "


def test_extract_json_prefers_the_first_object():
    assert _extract_json('text {"a": 1} {"b": 2}') == {"a": 1}


def counting_failure(counter, message: str, exit_code: int = 1):
    """A runner that records every spawn, then fails with one diagnostic."""
    code = (
        "import sys\n"
        f"open({str(counter)!r}, 'a', encoding='utf-8').write('call\\n')\n"
        f"print({message!r}, file=sys.stderr)\n"
        f"sys.exit({exit_code})\n"
    )
    return [sys.executable, "-c", code]


def spawn_count(counter) -> int:
    return len(counter.read_text(encoding="utf-8").splitlines()) if counter.exists() else 0


def envelope_command(counter, cost):
    payload = {"type": "result", "result": json.dumps({"answer": "ok"}),
               "usage": {"input_tokens": 5, "output_tokens": 1}}
    if cost is not None:
        payload["total_cost_usd"] = cost
    code = (
        "import json\n"
        f"open({str(counter)!r}, 'a', encoding='utf-8').write('call\\n')\n"
        f"print(json.dumps({payload!r}))\n"
    )
    return [sys.executable, "-c", code]


def test_stdin_is_the_default_and_the_prompt_stays_out_of_argv():
    model = CommandHostModel(command=[sys.executable, "-c",
        "import json,sys; sys.stdin.read(); print(json.dumps({'answer': json.dumps(sys.argv[1:])}))"])
    response = call(model)
    assert response.status is ModelStatus.SUCCESS
    assert "You are the host model" not in response.payload["answer"]


def test_preflight_passes_with_a_structured_reply():
    model = CommandHostModel(command=runner("json.dumps({'ok': True})"))
    result = model.preflight()
    assert result["status"] == "pass" and result["command_found"] is True
    assert result["blocked"] is False and result["category"] == "ok"
    assert model.usage_summary()["calls"] == 1


def test_preflight_reports_a_missing_command_without_running():
    model = CommandHostModel(command=["definitely-not-an-installed-model-command"])
    result = model.preflight()
    assert result["status"] == "fail" and result["category"] == "command_missing"
    assert result["command_found"] is False and result["blocked"] is True
    assert model.usage_summary()["calls"] == 0


def test_insufficient_balance_blocks_and_never_spawns_a_second_call(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=counting_failure(
        counter, "API Error: 402 Insufficient Balance"), usage_log=tmp_path / "usage.jsonl")
    first = call(model)
    second = call(model)
    assert first.status is ModelStatus.UNAVAILABLE
    assert second.status is ModelStatus.UNAVAILABLE
    assert "insufficient_balance" in second.error
    assert spawn_count(counter) == 1
    summary = model.usage_summary()
    assert summary["blocked"] == "insufficient_balance" and summary["blocked_calls"] == 1


def test_authentication_failure_latches_auth_failed(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=counting_failure(counter, "401 Unauthorized: invalid api key"))
    call(model)
    call(model)
    assert model.blocked == "auth_failed"
    assert spawn_count(counter) == 1


def test_missing_model_is_a_blocking_category(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=counting_failure(
        counter, "unrecognized_model: no such model deepseek-x"))
    call(model)
    call(model)
    assert model.blocked == "model_not_found"
    assert spawn_count(counter) == 1


def test_schema_mismatch_is_reported_but_does_not_latch():
    model = CommandHostModel(command=[sys.executable, "-c",
                                      "import json,sys; print(json.dumps({'wrong': 1}))"])
    first = call(model)
    second = call(model)
    assert first.status is ModelStatus.INVALID_OUTPUT
    assert second.status is ModelStatus.INVALID_OUTPUT
    assert model.last_category == "schema_mismatch"
    assert model.blocked is None and model.usage_summary()["calls"] == 2


def test_secrets_are_redacted_from_diagnostics(tmp_path):
    counter = tmp_path / "spawns.txt"
    log = tmp_path / "usage.jsonl"
    model = CommandHostModel(
        command=counting_failure(counter, "bad sk-ABCDEF1234567890 bearer abcdefgh12345678"),
        usage_log=log)
    response = call(model)
    assert "sk-ABCDEF" not in response.error
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "sk-ABCDEF" not in record.get("stderr", "")
    assert "[redacted]" in record["stderr"]


def test_batch_budget_latches_once_reported_spend_reaches_the_cap(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=envelope_command(counter, 0.02),
                             output_mode="json_envelope", budget_usd=0.01)
    assert call(model, task="t1").status is ModelStatus.SUCCESS
    second = call(model, task="t2")
    assert second.status is ModelStatus.UNAVAILABLE
    assert model.blocked == "budget_exceeded"
    assert spawn_count(counter) == 1


def test_run_budget_spans_stages_of_one_run_and_not_other_runs(tmp_path):
    counter = tmp_path / "spawns.txt"
    ledger = CostLedger(tmp_path / "cost.jsonl")
    first = CommandHostModel(command=envelope_command(counter, 0.02), output_mode="json_envelope",
                             run_budget_usd=0.01, run_id="case-a", ledger=ledger)
    assert call(first, task="assessment").status is ModelStatus.SUCCESS
    second = call(first, task="synthesis")
    assert second.status is ModelStatus.UNAVAILABLE and "run_budget_exceeded" in second.error
    assert first.blocked is None
    # A different research run has its own run_id and its own share of the cap.
    other = CommandHostModel(command=envelope_command(counter, 0.02), output_mode="json_envelope",
                             run_budget_usd=0.01, run_id="case-b", ledger=ledger)
    assert call(other, task="assessment").status is ModelStatus.SUCCESS
    assert spawn_count(counter) == 2


def test_unreported_cost_is_unknown_not_zero(tmp_path):
    counter = tmp_path / "spawns.txt"
    log = tmp_path / "usage.jsonl"
    model = CommandHostModel(command=envelope_command(counter, None),
                             output_mode="json_envelope", budget_usd=1.0, usage_log=log)
    assert call(model).status is ModelStatus.SUCCESS
    summary = model.usage_summary()
    assert summary["cost_known"] is False
    assert summary["budget_remaining_usd"] is None
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert record["cost_reported"] is False and record["cost_usd"] is None
    # Unknown cost must not be treated as zero: a hard cap refuses the next
    # call because it cannot prove the spend stayed inside the cap.
    blocked = call(model)
    assert blocked.status is ModelStatus.UNAVAILABLE
    assert model.blocked == "cost_unknown"
    assert spawn_count(counter) == 1


def test_observe_mode_records_unknown_cost_without_enforcing(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=envelope_command(counter, None), output_mode="json_envelope",
                             budget_usd=0.01, budget_mode="observe")
    assert call(model).status is ModelStatus.SUCCESS
    assert call(model).status is ModelStatus.SUCCESS
    summary = model.usage_summary()
    assert summary["budget_enforced"] is False
    assert summary["cost_known"] is False
    assert spawn_count(counter) == 2


def test_preflight_cost_is_counted_and_disclosed(tmp_path):
    ledger = CostLedger(tmp_path / "cost.jsonl")
    command = [sys.executable, "-c",
               "import json; print(json.dumps({'type': 'result', 'result': json.dumps({'ok': True}), "
               "'total_cost_usd': 0.02}))"]
    model = CommandHostModel(command=command, output_mode="json_envelope",
                             run_id="preflight", ledger=ledger)
    result = model.preflight()
    assert result["status"] == "pass"
    assert result["cost_usd"] == 0.02 and result["cost_known"] is True
    assert result["batch_spent_usd"] == 0.02 and result["batch_cost_known"] is True
    assert ledger.totals()["entries"] == 1


def test_403_rate_limit_is_transient_not_an_auth_failure(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=counting_failure(counter, "403 Forbidden: rate limit exceeded"))
    first = call(model)
    call(model)
    assert first.status is ModelStatus.UNAVAILABLE
    assert model.last_category == "rate_limited"
    assert model.blocked is None
    assert spawn_count(counter) == 2


def test_403_without_rate_wording_is_an_auth_failure(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=counting_failure(counter, "403 Forbidden: invalid api key"))
    call(model)
    call(model)
    assert model.blocked == "auth_failed"
    assert spawn_count(counter) == 1


def _fake_host(tmp_path, cost):
    price = f", 'total_cost_usd': {cost}" if cost is not None else ""
    path = tmp_path / "fake_host.py"
    path.write_text(
        "import json\n"
        f"print(json.dumps({{'type': 'result', 'result': json.dumps({{'answer': 'ok'}})"
        f"{price}}}))\n",
        encoding="utf-8",
    )
    return path


def _cross_process_spend(tmp_path, *, ledger, budget, run_id, cost, results):
    fake = _fake_host(tmp_path, cost)
    src = Path(__file__).resolve().parents[2] / "src"
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from sourceglint.cost_ledger import CostLedger\n"
        "from sourceglint.host_command import CommandHostModel\n"
        f"model = CommandHostModel(command=[sys.executable, {str(fake)!r}], "
        f"output_mode='json_envelope', budget_usd={budget}, run_id=sys.argv[1], "
        f"ledger=CostLedger(Path({str(ledger)!r})))\n"
        "response = model.complete_structured(task='assessment', payload={'request': 'x'}, "
        "response_schema={'type': 'object'})\n"
        f"Path({str(results)!r}).open('a', encoding='utf-8').write(response.status.value + '\\n')\n"
        "print(model.blocked or '')\n"
    )
    return subprocess.Popen([sys.executable, "-c", code, run_id],
                            env={**os.environ, "PYTHONPATH": str(src)},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_concurrent_processes_share_one_batch_budget(tmp_path):
    ledger = tmp_path / "batch.jsonl"
    results = tmp_path / "results.txt"
    children = [_cross_process_spend(tmp_path, ledger=ledger, budget=0.05,
                                     run_id=f"case-{index}", cost=0.02, results=results)
                for index in range(4)]
    for child in children:
        child.wait(timeout=90)
    statuses = results.read_text(encoding="utf-8").split()
    totals = CostLedger(ledger).totals()
    assert totals["spent_usd"] >= 0.05
    assert totals["unknown_calls"] == 0
    assert totals["entries"] == len(statuses)
    assert totals["spent_usd"] == round(0.02 * statuses.count("success"), 6)
    # A fresh process starts with zero local counters; the shared ledger must
    # still refuse it rather than resetting the cap per process.
    fresh = CommandHostModel(command=[sys.executable, str(_fake_host(tmp_path, 0.02))],
                             output_mode="json_envelope", budget_usd=0.05,
                             run_id="case-new", ledger=CostLedger(ledger))
    assert call(fresh).status is ModelStatus.UNAVAILABLE
    assert fresh.blocked == "budget_exceeded"


def test_unknown_cost_in_one_process_blocks_another_process(tmp_path):
    ledger = tmp_path / "batch.jsonl"
    results = tmp_path / "results.txt"
    child = _cross_process_spend(tmp_path, ledger=ledger, budget=1.0,
                                 run_id="case-a", cost=None, results=results)
    child.wait(timeout=90)
    assert results.read_text(encoding="utf-8").strip() == "success"
    fresh = CommandHostModel(command=[sys.executable, str(_fake_host(tmp_path, 0.02))],
                             output_mode="json_envelope", budget_usd=1.0,
                             run_id="case-b", ledger=CostLedger(ledger))
    assert call(fresh).status is ModelStatus.UNAVAILABLE
    assert fresh.blocked == "cost_unknown"
