from __future__ import annotations

import os

import pytest

from sourceglint import credentials


@pytest.fixture(autouse=True)
def _no_keychain(monkeypatch):
    monkeypatch.setattr(credentials, "_keychain_get", lambda name: "")
    monkeypatch.setattr(credentials, "_keychain_set", lambda name, value: False)


def test_store_and_resolve_from_private_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    layer = credentials.store("X_BEARER_TOKEN", "secret-value", prefer_keychain=False)
    assert layer == "config-file"
    assert credentials.resolve("X_BEARER_TOKEN") == "secret-value"
    assert credentials.presence("X_BEARER_TOKEN") == {
        "name": "X_BEARER_TOKEN", "present": True, "source": "config-file",
    }
    mode = os.stat(credentials.credentials_file()).st_mode & 0o777
    if os.name == "posix":
        assert mode == 0o600


def test_environment_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    credentials.store("X_BEARER_TOKEN", "file-value", prefer_keychain=False)
    monkeypatch.setenv("X_BEARER_TOKEN", "env-value")
    assert credentials.resolve("X_BEARER_TOKEN") == "env-value"
    assert credentials.presence("X_BEARER_TOKEN")["source"] == "environment"


def test_unknown_credential_name_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    assert credentials.resolve("RANDOM_UNLISTED_NAME") == ""
    with pytest.raises(ValueError):
        credentials.store("RANDOM_UNLISTED_NAME", "value", prefer_keychain=False)


def test_delete_removes_file_value(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    credentials.store("BSKY_HANDLE", "someone.bsky.social", prefer_keychain=False)
    removed = credentials.delete("BSKY_HANDLE")
    assert "config-file" in removed
    assert credentials.resolve("BSKY_HANDLE") == ""


def test_keychain_store_removes_a_shadowing_file_value(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    credentials.store("BSKY_HANDLE", "old-file-value", prefer_keychain=False)
    store: dict[str, str] = {}
    monkeypatch.setattr(credentials, "_keychain_set", lambda name, value: store.setdefault(name, value) is not None)
    monkeypatch.setattr(credentials, "_keychain_get", lambda name: store.get(name, ""))
    layer = credentials.store("BSKY_HANDLE", "new-keychain-value", prefer_keychain=True)
    assert layer == "keychain"
    assert credentials.resolve("BSKY_HANDLE") == "new-keychain-value"
    assert "BSKY_HANDLE" not in credentials.credentials_file().read_text()


def test_export_environment_never_overrides_process_values(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTAGE_CONFIG_DIR", str(tmp_path))
    credentials.store("BSKY_HANDLE", "stored.example", prefer_keychain=False)
    env = credentials.export_environment({"BSKY_HANDLE": "process.example"})
    assert env["BSKY_HANDLE"] == "process.example"
