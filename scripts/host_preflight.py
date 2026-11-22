"""Host preflight for real research runs.

Checks, in order: the configured model factory can build a model, its command
exists, one structured reply validates, billing/credential failures are named,
and the source registry has at least one enabled connector. A blocking result
means real benchmark runs must not start.

Exit codes: 0 pass, 2 blocked (balance/auth/model), 1 other failure.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_factory(spec: str):
    module_name, _, attribute = spec.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attribute or "build_model")


def registry_state(path: Path) -> dict:
    try:
        rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError) as exc:
        return {"ok": False, "path": str(path), "detail": type(exc).__name__}
    enabled = [row.get("name") for row in rows if row.get("enabled", True)]
    return {"ok": bool(enabled), "path": str(path), "enabled": enabled}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="sourceglint.host_command:build_model")
    parser.add_argument("--registry", default=str(ROOT / "config" / "sources-native.yaml"))
    parser.add_argument("--skip-model", action="store_true", help="check configuration only")
    args = parser.parse_args()

    report: dict = {"model_spec": args.model, "registry": registry_state(Path(args.registry))}
    try:
        model = load_factory(args.model)()
    except Exception as exc:  # configuration errors must surface, not be swallowed
        report.update({"status": "fail", "category": "configuration",
                       "detail": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 1
    report["model"] = getattr(model, "model_id", type(model).__name__)
    if args.skip_model:
        report["status"] = "pass" if report["registry"]["ok"] else "fail"
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 0 if report["registry"]["ok"] else 1
    preflight = getattr(model, "preflight", None)
    if preflight is None:
        report.update({"status": "unsupported", "category": "no_preflight",
                       "detail": "model has no preflight method"})
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 1
    result = preflight()
    report.update(result)
    report["status"] = "pass" if result.get("status") == "pass" and report["registry"]["ok"] else "fail"
    if not report["registry"]["ok"]:
        report["category"] = "registry_empty"
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if report["status"] == "pass":
        return 0
    return 2 if result.get("blocked") else 1


if __name__ == "__main__":
    sys.exit(main())
