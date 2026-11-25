"""Credential resolution without ever printing a secret.

Resolution order (first hit wins):

1. process environment  — unchanged, backward compatible;
2. a private local file  — ``$VANTAGE_CONFIG_DIR/credentials.env`` or the
   platform default (0600 on POSIX);
3. macOS Keychain        — service ``vantage-<NAME>``, read through
   ``security(1)``.

Only an allowlist of names is accepted, so a typo cannot read an unrelated
Keychain item. Public helpers return booleans or names, never values.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from .connectors._command import run_command


# Credentials Vantage may read or store. Keep this list explicit: it is the
# contract between the setup wizard, the doctor and the adapters.
CREDENTIAL_NAMES: frozenset[str] = frozenset({
    # Aggregated social search
    "SCRAPECREATORS_API_KEY",
    # Independent tokens
    "X_BEARER_TOKEN",
    "BSKY_HANDLE",
    "BSKY_APP_PASSWORD",
    "TRUTHSOCIAL_TOKEN",
    "META_ACCESS_TOKEN",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "GITHUB_TOKEN",
    "PRODUCT_HUNT_TOKEN",
    "SEMANTIC_SCHOLAR_API_KEY",
    "OPENALEX_API_KEY",
    "USPTO_API_KEY",
    # Local services / tools
    "XHS_MCP_URL",
    "TELEGRAM_SOURCES",
    "BRIGHTDATA_API_KEY",
    # Optional interface addresses
    "VANTAGE_CONFIG_DIR",
})

# The aggregated ScrapeCreators key is the only key that unlocks several
# platforms at once. Named here so the setup output can explain the trade-off.
SCRAPECREATORS_PLATFORMS = (
    "tiktok", "instagram", "threads", "pinterest", "linkedin",
    "reddit", "youtube", "telegram", "meta_ad_library",
)


def config_dir() -> Path:
    override = os.environ.get("VANTAGE_CONFIG_DIR") or os.environ.get("SOURCEGLINT_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "vantage"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "vantage"


def credentials_file() -> Path:
    return config_dir() / "credentials.env"


def _valid_name(name: str) -> bool:
    return name in CREDENTIAL_NAMES


def _read_file(path: Path | None = None) -> dict[str, str]:
    target = path or credentials_file()
    try:
        if not target.exists():
            return {}
    except OSError:
        return {}
    values: dict[str, str] = {}
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            if _valid_name(key) and value.strip():
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def _keychain_service(name: str) -> str:
    return f"vantage-{name}"


def _keychain_get(name: str) -> str:
    if sys.platform != "darwin" or not shutil.which("security"):
        return ""
    try:
        result = run_command(
            ["security", "find-generic-password", "-s", _keychain_service(name), "-w"],
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _keychain_set(name: str, value: str) -> bool:
    if sys.platform != "darwin" or not shutil.which("security"):
        return False
    account = os.environ.get("USER") or os.environ.get("USERNAME") or "vantage"
    try:
        result = run_command(
            [
                "security", "add-generic-password", "-a", account,
                "-s", _keychain_service(name), "-w", value, "-U",
            ],
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def resolve(name: str) -> str:
    """Return the credential value, or an empty string. Never logs."""
    if not _valid_name(name):
        return ""
    env_value = os.environ.get(name, "")
    if env_value:
        return env_value
    file_value = _read_file().get(name, "")
    if file_value:
        return file_value
    return _keychain_get(name)


def has(name: str) -> bool:
    return bool(resolve(name))


def presence(name: str) -> dict[str, object]:
    """Report *whether* and *where* a credential is configured (no value)."""
    if not _valid_name(name):
        return {"name": name, "present": False, "source": "unknown-name"}
    if os.environ.get(name):
        return {"name": name, "present": True, "source": "environment"}
    if _read_file().get(name):
        return {"name": name, "present": True, "source": "config-file"}
    if _keychain_get(name):
        return {"name": name, "present": True, "source": "keychain"}
    return {"name": name, "present": False, "source": ""}


def store(name: str, value: str, *, prefer_keychain: bool = True) -> str:
    """Persist a credential. Returns the layer used: keychain | config-file.

    Raises ``ValueError`` for an unknown name or an empty value.
    """
    if not _valid_name(name):
        raise ValueError(f"unsupported credential name: {name}")
    value = value.strip()
    if not value:
        raise ValueError("empty credential value")
    if prefer_keychain and _keychain_set(name, value):
        # A stale file value would shadow the new Keychain item, so remove it.
        existing = _read_file()
        if name in existing:
            existing.pop(name, None)
            _write_file(existing)
        return "keychain"
    existing = _read_file()
    existing[name] = value
    _write_file(existing)
    return "config-file"


def _write_file(values: dict[str, str]) -> None:
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Vantage credentials (private, 0600). Values are never printed.",
        "# Environment variables take precedence over this file.",
    ]
    for key in sorted(values):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def delete(name: str) -> list[str]:
    """Remove a stored credential from the local file and macOS Keychain."""
    if not _valid_name(name):
        raise ValueError(f"unsupported credential name: {name}")
    removed: list[str] = []
    path = credentials_file()
    existing = _read_file(path)
    if name in existing:
        existing.pop(name, None)
        if existing:
            lines = [f"{key}={existing[key]}" for key in sorted(existing)]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            try:
                path.unlink()
            except OSError:
                pass
        removed.append("config-file")
    if sys.platform == "darwin" and shutil.which("security"):
        try:
            result = run_command(
                ["security", "delete-generic-password", "-s", _keychain_service(name)],
                timeout=5,
            )
            if result.returncode == 0:
                removed.append("keychain")
        except (OSError, subprocess.TimeoutExpired):
            pass
    return removed


def export_environment(target: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return ``target`` plus every stored credential not already set.

    Used only by the setup wizard's probe step. Values are copied into the
    child/process environment for the probe and never printed.
    """
    env = dict(target if target is not None else os.environ)
    for name in sorted(CREDENTIAL_NAMES):
        if env.get(name):
            continue
        value = resolve(name)
        if value:
            env[name] = value
    return env


__all__ = [
    "CREDENTIAL_NAMES",
    "SCRAPECREATORS_PLATFORMS",
    "config_dir",
    "credentials_file",
    "delete",
    "export_environment",
    "has",
    "presence",
    "resolve",
    "store",
]
