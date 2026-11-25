"""Offline capability inspection. Readiness is not a live-source verdict."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from typing import Sequence

import yaml

from .resources import data_path
from .source_catalog import load_source_catalog

CONNECTORS = {
    "app_store", "arxiv", "ashby", "bluesky", "clinicaltrials", "crates_io",
    "crossref", "datacite", "devto", "digg", "docker_hub", "doaj", "github",
    "gitlab", "greenhouse", "hacker_news", "hugging_face", "instagram",
    "internet_archive", "itmedia", "lemmy", "lever", "linkedin", "makuake",
    "maven_central", "meta_ad_library", "note", "nuget", "open_library",
    "openalex", "package_registries", "pinterest", "polymarket", "pypi",
    "pubmed", "qiita", "reddit", "rubygems", "sec_edgar", "semantic_scholar",
    "sspai", "steam", "stocktwits", "techmeme", "threads", "tiktok",
    "truthsocial", "world_bank", "product_hunt", "stack_overflow", "x",
    "xiaohongshu", "youtube", "zenodo", "zenn",
}


def build_report() -> dict:
    registry = yaml.safe_load(data_path("config", "sources.yaml").read_text())
    snapshot_path = data_path("docs", "source-live-status.json")
    snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else {}
    sources = []
    for entry in registry:
        name = entry["name"]
        missing = [key for key in entry.get("credentials", []) if not os.environ.get(key)]
        tool = "yt-dlp" if name == "youtube" else "digg-pp-cli" if name == "digg" else None
        tool_ready = bool(shutil.which(tool)) if tool else None
        if not entry.get("enabled"):
            state = "DISABLED"
        elif name not in CONNECTORS:
            state = "HOST_REQUIRED"
        elif missing:
            state = "MISSING_CREDENTIALS"
        elif tool and not tool_ready:
            state = "MISSING_TOOL"
        else:
            state = "READY_UNVERIFIED"
        sources.append({
            "source": name, "state": state,
            "connector_implemented": name in CONNECTORS,
            "missing_credentials": missing, "local_tool": tool,
            "local_tool_available": tool_ready,
            "historical_live_pass": name in snapshot.get("passed", []),
            "historical_verified_at": snapshot.get("verified_at"),
        })
    return {
        "schema_version": 1, "network_probed": False,
        "catalog_sources": len(load_source_catalog()), "sources": sources,
        "note": "Readiness and historical tests do not certify current upstream availability. Host search and reasoning must be supplied by the agent.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sourceglint doctor", description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Vantage capability check (offline)")
        for item in report["sources"]:
            detail = ", ".join(item["missing_credentials"])
            if item["state"] == "MISSING_TOOL":
                detail = item["local_tool"]
            print(f"{item['source']}: {item['state']}" + (f" ({detail})" if detail else ""))
        print(report["note"])
    return 0
