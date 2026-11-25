from __future__ import annotations

import json

from sourceglint import setup_wizard


def test_zero_config_sources_are_enabled_free_connectors():
    names = setup_wizard.zero_config_sources()
    assert "github" in names
    assert "hacker_news" in names
    assert "youtube" in names
    # Patents is keyless through the public USPTO search session.
    assert "patents" in names


def test_free_only_recommendations_never_offer_a_paid_key():
    recs = setup_wizard.recommendations(free_only=True)
    assert all("SCRAPECREATORS" not in rec["action"] for rec in recs)
    assert recs[0]["tier"] == 0


def test_setup_json_never_prints_a_secret(monkeypatch, capsys):
    secret = "sc-live-should-never-print"
    monkeypatch.setenv("SCRAPECREATORS_API_KEY", secret)
    monkeypatch.setattr(setup_wizard, "detect_local_services", lambda: [])
    assert setup_wizard.run_setup(["--json", "--skip"]) == 0
    output = capsys.readouterr().out
    assert secret not in output
    payload = json.loads(output)
    row = next(item for item in payload["credentials"] if item["name"] == "SCRAPECREATORS_API_KEY")
    assert row["present"] is True
    assert row["source"] == "environment"
    assert payload["skipped_all"] is True


def test_setup_free_only_plan_skips_paid_suggestions(monkeypatch, capsys):
    monkeypatch.setattr(setup_wizard, "detect_local_services", lambda: [])
    assert setup_wizard.run_setup(["--json", "--skip", "--free-only"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert all("SCRAPECREATORS" not in rec["action"] for rec in payload["recommendations"])
