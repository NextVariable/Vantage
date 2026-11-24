"""Live-test boundary harness (Phase 4 §21, §29).

Tests in this directory are skipped by default. They run only when
`RUN_LIVE_TESTS=1` is set and the required credentials are available.

The live tests verify that the production mapping — the SAME code
that's exercised by the offline tests — still produces correct output
against the real upstream. They are NOT a substitute for offline
fixture tests; they're a check that fixture parity didn't drift.

Run only what you mean to:

  RUN_LIVE_TESTS=1 \
    pytest tests/live -q -k hacker_news

  RUN_LIVE_TESTS=1 GITHUB_TOKEN=ghp_*** \
    pytest tests/live -q -k github

  RUN_LIVE_TESTS=1 REDDIT_CLIENT_ID=*** REDDIT_CLIENT_SECRET=*** \
    pytest tests/live -q -k reddit
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


LIVE_FLAG = "RUN_LIVE_TESTS"
LIVE_DIR = Path(__file__).resolve().parent

# Maps each live test file to the env-var dependencies that the host
# integration must supply for the corresponding live run. Tests consult
# this map to SKIP rather than FAIL when credentials are missing.
LIVE_DEPS = {
    "test_live_hacker_news": set(),
    "test_live_bluesky": {"BSKY_HANDLE", "BSKY_APP_PASSWORD"},
    "test_live_youtube": set(),
    "test_live_github": set(),
    "test_live_reddit": set(),
    "test_live_open_sources": set(),
    "test_live_expansion": set(),
    "test_live_semantic_scholar": {"SEMANTIC_SCHOLAR_API_KEY"},
    "test_live_x": {"X_BEARER_TOKEN"},
    "test_live_product_hunt": {"PRODUCT_HUNT_TOKEN"},
}


def pytest_collection_modifyitems(config, items):
    """Three-state skip rule for the live directory:

      * RUN_LIVE_TESTS unset / != "1"        → SKIP (offline by default)
      * RUN_LIVE_TESTS=1 + creds available   → RUN
      * RUN_LIVE_TESTS=1 + creds missing     → SKIP (does NOT FAIL)
    """
    flag = os.environ.get(LIVE_FLAG)
    for item in items:
        if not item.path.is_relative_to(LIVE_DIR):
            continue
        if flag != "1":
            item.add_marker(pytest.mark.skip(
                reason=f"live test — set {LIVE_FLAG}=1 to enable"
            ))
            continue
        missing = sorted(name for name in LIVE_DEPS.get(item.path.stem, ()) if not os.environ.get(name))
        if missing:
            item.add_marker(pytest.mark.skip(
                reason=f"missing live creds: {','.join(missing)}"
            ))
