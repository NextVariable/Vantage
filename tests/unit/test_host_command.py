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
    assert summary["billed_cost_usd"] == 0.02


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
