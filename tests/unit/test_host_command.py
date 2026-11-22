"""Contract tests for the provider-neutral command host runtime."""
import json
import sys

import pytest

from sourceglint.host_command import CommandHostModel, _extract_json
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
    from sourceglint.host_command import build_model

    monkeypatch.delenv("SOURCEGLINT_HOST_CMD", raising=False)
    with pytest.raises(ValueError, match="SOURCEGLINT_HOST_CMD"):
        build_model()
    monkeypatch.setenv("SOURCEGLINT_HOST_CMD", f"{sys.executable} -c pass")
    monkeypatch.setenv("SOURCEGLINT_HOST_TIMEOUT", "33")
    model = build_model()
    assert model.command[:1] == [sys.executable] and model.timeout == 33


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


def test_task_budget_fails_only_that_task(tmp_path):
    counter = tmp_path / "spawns.txt"
    model = CommandHostModel(command=envelope_command(counter, 0.02),
                             output_mode="json_envelope", task_budget_usd=0.01)
    assert call(model, task="assessment").status is ModelStatus.SUCCESS
    second = call(model, task="assessment")
    assert second.status is ModelStatus.UNAVAILABLE and "task budget" in second.error
    assert model.blocked is None
    assert call(model, task="synthesis").status is ModelStatus.SUCCESS
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
    # Unknown cost must not be treated as a spend of zero that permits or
    # blocks later calls on the strength of a fabricated number.
    assert call(model).status is ModelStatus.SUCCESS
    assert spawn_count(counter) == 2
