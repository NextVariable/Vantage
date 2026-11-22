"""Live acceptance: default STDIO host recovers after a real timeout.

This harness uses a real model host over two OS pipes and a real, controllable
delay — the first request's deadline is deliberately far shorter than the
host's latency. It proves the behaviour that unit tests only simulate:

  1. ``clustering`` succeeds and negotiates ``request_id`` correlation;
  2. ``contradiction`` times out while the host is still working;
  3. the late contradiction reply is skipped, never accepted;
  4. ``fact_synthesis`` is dispatched with its own request id;
  5. the FACT reply is matched to that id and returned intact.

``--serve`` turns the script into a line-framed host process that answers each
frame with the locally installed, already-authorized Codex CLI. No credentials
are read or written here and no USD amount is claimed.

Usage:
    python3 scripts/stdio_recovery_acceptance.py --output runs/rc/stdio-recovery-<name>
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sourceglint.deadline import deadline_scope  # noqa: E402
from sourceglint.host_stdio import PROTOCOL_VERSION, StdioHostModel  # noqa: E402
from sourceglint.intelligence.model import ModelStatus  # noqa: E402

CODEX = os.environ.get(
    "CODEX_BIN",
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex",
)
MODEL = os.environ.get("SOURCEGLINT_HOST_CODEX_MODEL", "gpt-6.1-sol")
SCHEMA = {
    "type": "object",
    "required": ["marker"],
    "properties": {"marker": {"type": "string"}},
    "additionalProperties": False,
}
# The late reply must still be in flight when the next request is dispatched.
TIMEOUT_SECONDS = 0.05
REPLY_BUDGET_SECONDS = 180.0


def _prompt(frame: dict) -> str:
    return (
        "You are a protocol acceptance host. Reply with exactly one JSON object, "
        "no prose and no code fence. The object must validate against:\n"
        + json.dumps(frame.get("response_schema") or SCHEMA)
        + "\nThe marker value must be the literal task name: "
        + json.dumps(frame.get("task") or "")
        + "\n"
    )


def _parse(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def serve(argv: list[str]) -> int:
    import tempfile

    usage_path = os.environ.get("SOURCEGLINT_HOST_USAGE", "").strip()
    for line in sys.stdin:
        if not line.strip():
            continue
        frame = json.loads(line)
        started = monotonic()
        reply: dict = {
            "type": "model_response",
            "task": frame.get("task"),
            "request_id": frame.get("request_id"),
        }
        payload = None
        error = ""
        usage = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
        with tempfile.TemporaryDirectory() as scratch:
            last = os.path.join(scratch, "last.txt")
            try:
                proc = subprocess.run(
                    [argv[0], "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                     "--ignore-user-config", "-m", argv[1], "--json", "--color", "never",
                     "-o", last, "-"],
                    input=_prompt(frame), text=True, encoding="utf-8", capture_output=True,
                    timeout=REPLY_BUDGET_SECONDS,
                )
                text = ""
                if os.path.exists(last):
                    with open(last, encoding="utf-8") as handle:
                        text = handle.read()
                if proc.returncode == 0 and text.strip():
                    payload = _parse(text)
                else:
                    for event in proc.stdout.splitlines():
                        try:
                            parsed = json.loads(event)
                        except ValueError:
                            continue
                        if parsed.get("type") == "turn.completed":
                            raw = parsed.get("usage") or {}
                            for key in usage:
                                usage[key] += int(raw.get(key) or 0)
                    tail = [row for row in (proc.stderr or "").strip().splitlines()
                            if row and " INFO " not in row and " WARN " not in row]
                    error = (" | ".join(tail[-2:]) or f"exit {proc.returncode} without a reply")[:300]
                if payload is None and not error:
                    error = "host reply contained no JSON object"
            except subprocess.TimeoutExpired:
                error = "codex host timed out"
            except OSError as exc:
                error = f"{type(exc).__name__}: {exc}"
        if usage_path:
            with open(usage_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "task": frame.get("task"),
                    "request_id": frame.get("request_id"),
                    "status": "success" if payload is not None else "unavailable",
                    "seconds": round(monotonic() - started, 3),
                    "usage": usage,
                    "error": error,
                }) + "\n")
        if payload is None:
            reply["error"] = error or "host produced no JSON object"
        else:
            reply["payload"] = payload
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


class Tee:
    """Forward engine frames to the host and keep them for the report."""

    def __init__(self, stream):
        self.stream = stream
        self.frames: list[dict] = []

    def write(self, text: str) -> int:
        for line in text.splitlines():
            if line.strip():
                self.frames.append(json.loads(line))
        self.stream.write(text)
        self.stream.flush()
        return len(text)

    def flush(self) -> None:
        self.stream.flush()


def _call(model: StdioHostModel, task: str, deadline: float) -> dict:
    started = monotonic()
    with deadline_scope(monotonic() + deadline):
        response = model.complete_structured(task=task, payload={"probe": task},
                                            response_schema=SCHEMA)
    return {
        "task": task,
        "status": response.status.value,
        "payload": dict(response.payload or {}),
        "error": response.error,
        "seconds": round(monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--codex", default=CODEX)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--serve", nargs=2, metavar=("CODEX", "MODEL"))
    args = parser.parse_args()
    if args.serve:
        return serve(args.serve)

    if args.output is None:
        parser.error("--output is required")
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    usage_path = target / "host.usage.jsonl"
    env = {**os.environ, "SOURCEGLINT_HOST_USAGE": str(usage_path)}
    with (target / "host.stderr").open("wb") as err:
        host = subprocess.Popen(
            [sys.executable, str(Path(__file__)), "--serve", args.codex, args.model],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
            text=True, encoding="utf-8", bufsize=1, env=env,
        )
    tee = Tee(host.stdin)
    model = StdioHostModel(input_stream=host.stdout, output_stream=tee)
    steps: list[dict] = []
    try:
        steps.append(_call(model, "clustering", REPLY_BUDGET_SECONDS))
        steps.append(_call(model, "contradiction", TIMEOUT_SECONDS))
        steps.append(_call(model, "fact_synthesis", REPLY_BUDGET_SECONDS))
    finally:
        try:
            host.stdin.close()
        except OSError:
            pass
        try:
            host.wait(timeout=20)
        except subprocess.TimeoutExpired:
            host.kill()
            host.wait(timeout=10)

    ids = [frame.get("request_id") for frame in tee.frames if frame.get("type") == "model_request"]
    fact = steps[-1]
    checks = {
        "protocol": all(frame.get("protocol") == PROTOCOL_VERSION for frame in tee.frames),
        "clustering_succeeded": steps[0]["status"] == ModelStatus.SUCCESS.value,
        "contradiction_timed_out": steps[1]["status"] == ModelStatus.TIMEOUT.value,
        "fact_dispatched_with_own_id": len(ids) == 3 and ids[2] not in ids[:2],
        "fact_succeeded": fact["status"] == ModelStatus.SUCCESS.value,
        "no_cross_framing": fact["payload"].get("marker") == "fact_synthesis",
        "late_reply_not_accepted": fact["payload"].get("marker") != "contradiction",
    }
    report = {
        "label": "real host stdio recovery acceptance — protocol behaviour, not a research result",
        "kind": "stdio_recovery_acceptance",
        "codex": args.codex,
        "model": args.model,
        "timeout_seconds": TIMEOUT_SECONDS,
        "requests": tee.frames,
        "request_ids": ids,
        "steps": steps,
        "checks": checks,
        "passed": all(checks.values()),
        "usage": [
            json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ] if usage_path.exists() else [],
    }
    (target / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": report["passed"], "checks": checks,
                      "request_ids": ids}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
