"""Offline capability inspection. Readiness is not a live-source verdict."""
from __future__ import annotations

import argparse
import json
import shutil
from typing import Sequence

from . import credentials
from .application.runtime import default_sources
from .source_catalog import load_source_catalog

CONNECTORS = {
    "amazon", "app_store", "arxiv", "ashby", "bluesky", "clinicaltrials",
    "crates_io", "crossref", "datacite", "devto", "digg", "docker_hub", "doaj",
    "github", "gitlab", "greenhouse", "hacker_news", "hugging_face",
    "instagram", "internet_archive", "itmedia", "lemmy", "lever", "linkedin",
    "makuake", "maven_central", "meta_ad_library", "note", "nuget",
    "open_library", "openalex", "package_registries", "patents", "pinterest",
    "polymarket", "pypi", "pubmed", "qiita", "reddit", "rubygems", "sec_edgar",
    "semantic_scholar", "sspai", "steam", "stocktwits", "techmeme",
    "telegram", "threads", "tiktok", "trustpilot", "truthsocial", "world_bank",
    "product_hunt", "stack_overflow", "x", "xiaohongshu", "youtube", "zenodo",
    "zenn",
}


def build_report() -> dict:
    snapshot = {}
    from .resources import data_path

    snapshot_path = data_path("docs", "source-live-status.json")
    try:
        snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        snapshot = {}
    sources = []
    for entry in default_sources():
        name = entry["name"]
        required = [str(key) for key in entry.get("credentials", [])]
        missing = [key for key in required if not credentials.has(key)]
        tools = [str(item) for item in entry.get("tools", [])]
        missing_tools = [item for item in tools if not shutil.which(item)]
        if not entry.get("enabled"):
            state = "DISABLED"
        elif name not in CONNECTORS:
            state = "HOST_REQUIRED"
        elif missing:
            state = "MISSING_CREDENTIALS"
        elif missing_tools:
            state = "MISSING_TOOL"
        else:
            state = "READY_UNVERIFIED"
        sources.append({
            "source": name, "state": state,
            "connector_implemented": name in CONNECTORS,
            "missing_credentials": missing,
            "credential_sources": {
                key: credentials.presence(key)["source"] for key in required
                if credentials.has(key)
            },
            "local_tools": tools,
            "missing_tools": missing_tools,
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
                detail = ", ".join(item["missing_tools"])
            print(f"{item['source']}: {item['state']}" + (f" ({detail})" if detail else ""))
        print(report["note"])
    return 0
