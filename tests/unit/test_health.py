from sourceglint.health import build_report


def test_keyless_reddit_does_not_require_oauth(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    report = build_report()
    reddit = next(row for row in report["sources"] if row["source"] == "reddit")
    assert reddit["state"] == "READY_UNVERIFIED"
    assert reddit["missing_credentials"] == []
    assert report["network_probed"] is False


def test_new_free_connectors_are_reported_as_implemented_but_disabled():
    report = build_report()
    rows = {row["source"]: row for row in report["sources"]}
    for name in (
        "crossref", "openalex", "pypi", "crates_io", "gitlab",
        "lever", "greenhouse", "ashby", "steam", "world_bank", "sec_edgar",
    ):
        assert name in rows, f"{name} must be registered"
        assert rows[name]["connector_implemented"] is True
        assert rows[name]["state"] == "DISABLED"
        assert rows[name]["missing_credentials"] == []


def test_phase2_sources_are_implemented_and_opt_in():
    report = build_report()
    rows = {row["source"]: row for row in report["sources"]}
    for name in (
        "pubmed", "doaj", "zenodo", "datacite", "open_library",
        "internet_archive", "clinicaltrials", "maven_central", "nuget",
        "rubygems", "docker_hub", "app_store", "lemmy", "zenn", "note",
        "itmedia", "sspai", "makuake",
    ):
        assert name in rows, f"{name} must be registered"
        assert rows[name]["connector_implemented"] is True
        assert rows[name]["state"] == "DISABLED"
        assert rows[name]["missing_credentials"] == []


def test_phase2_expanded_profile_enables_each_new_source_once():
    import yaml

    from sourceglint.resources import data_path

    expanded = yaml.safe_load(data_path("config", "sources-expanded.yaml").read_text())
    by_name = {entry["name"]: entry for entry in expanded}
    for name in ("pubmed", "app_store", "zenn", "makuake", "docker_hub"):
        assert name in by_name, f"{name} must be callable from the opt-in profile"
        assert by_name[name]["enabled"] is True
        assert by_name[name]["max_queries_per_run"] == 1


def test_optional_openalex_key_is_not_a_blocking_credential(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    report = build_report()
    openalex = next(row for row in report["sources"] if row["source"] == "openalex")
    assert openalex["missing_credentials"] == []
    assert openalex["state"] == "DISABLED"


def test_credential_required_catalog_entries_name_their_variables():
    from sourceglint.source_catalog import load_source_catalog

    for target in load_source_catalog():
        if target.availability in {"credential_required", "owner_only"}:
            assert target.credentials, f"{target.name} must name its required credential"
            for key in target.credentials:
                assert key.isupper(), f"{target.name} credential must be a NAME, not a value"


def test_health_does_not_expose_a_secret_or_certify_live_access(monkeypatch):
    secret = "private-test-secret-value"
    monkeypatch.setenv("X_BEARER_TOKEN", secret)
    report = build_report()
    assert secret not in str(report)
    x = next(row for row in report["sources"] if row["source"] == "x")
    assert x["state"] == "READY_UNVERIFIED"
