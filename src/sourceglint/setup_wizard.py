"""``vantage setup`` — one bounded configuration pass, no surprises.

The wizard is deliberately small and offline-first:

* it inspects the environment, configured credentials (names only), local
  CLIs and an optional local MCP service;
* it prints what already works with zero configuration;
* it recommends the smallest set of accounts that unlocks the most platforms;
* it lets the user skip everything, or choose free-only;
* it stores any pasted secret in the macOS Keychain (falling back to a 0600
  file) and never echoes it;
* the live probe is opt-in and bounded; its verdict is what it observed, not
  a promise about future availability.

It never registers an account, buys a plan, tops up a balance, reads browser
cookies, or widens the scopes of an existing account.
"""
from __future__ import annotations

import getpass
import json
import platform
import shutil
import sys
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import credentials
from .connectors._http import (
    HttpPermanentError,
    HttpTimeoutError,
    HttpTransientError,
    StdlibHttpClient,
)

# Connectors that need no credential of their own.
ZERO_CONFIG_CONNECTORS = frozenset({
    "arxiv", "ashby", "clinicaltrials", "crates_io", "crossref", "datacite",
    "devto", "digg", "docker_hub", "doaj", "github", "gitlab", "greenhouse",
    "hacker_news", "hugging_face", "internet_archive", "itmedia", "lemmy",
    "lever", "makuake", "maven_central", "note", "nuget", "open_library",
    "openalex", "package_registries", "patents", "pypi", "pubmed", "qiita",
    "reddit", "rubygems", "sec_edgar", "semantic_scholar", "sspai",
    "stack_overflow", "techmeme", "trustpilot", "world_bank", "youtube",
    "zenodo", "zenn",
})

OPTIONAL_KEYS = (
    # (name, prompt, note)
    ("SCRAPECREATORS_API_KEY", "ScrapeCreators API key",
     "Unlocks TikTok, Instagram, Threads, Pinterest, LinkedIn and richer Reddit/YouTube/Telegram search. Paid service with a free allowance."),
    ("X_BEARER_TOKEN", "X API bearer token",
     "Official X API; metered credits belong to your X developer project."),
    ("BSKY_HANDLE", "Bluesky handle", "Used with an app password."),
    ("BSKY_APP_PASSWORD", "Bluesky app password", "Create one in Bluesky settings."),
    ("TRUTHSOCIAL_TOKEN", "Truth Social access token", "From your own Truth Social session."),
    ("REDDIT_CLIENT_ID", "Reddit OAuth client id", "Optional: the keyless public route works without it."),
    ("REDDIT_CLIENT_SECRET", "Reddit OAuth client secret", "Optional: the keyless public route works without it."),
    ("META_ACCESS_TOKEN", "Meta Ad Library access token", "Requires identity verification on Meta's side."),
    ("TELEGRAM_SOURCES", "Telegram channel list", "Comma-separated public channel handles for the ScrapeCreators route."),
    ("BRIGHTDATA_API_KEY", "Bright Data API key", "Legacy Amazon route; disabled until requests can be safely metered."),
)

LOCAL_CLIS = (
    # (binary, purpose, install hint)
    ("yt-dlp", "YouTube metadata and captions (free)", "pipx install yt-dlp"),
    ("gh", "GitHub CLI; its existing login is reused as a token", "brew install gh"),
    ("digg-pp-cli", "Digg stories (free)", "See the upstream Printing Press library catalog"),
    ("trustpilot-pp-cli", "Trustpilot cached company records (free)", "See the upstream Printing Press library catalog"),
    ("brightdata", "Amazon product/review datasets (paid)", "npm i -g @brightdata/cli"),
    ("node", "Required by the npm-based CLIs", "brew install node"),
    ("npx", "Alternative runner for those CLIs", "comes with Node.js"),
)

# Probes are intentionally tiny: one request (or one yt-dlp search), short
# timeout, no pagination, and no paid call.
_PROBES: dict[str, tuple[str, str]] = {
    "hacker_news": ("https://hn.algolia.com/api/v1/search?query=ai&tags=story&hitsPerPage=1", "HN Algolia"),
    "github": ("https://api.github.com/rate_limit", "GitHub REST"),
    "reddit": ("https://www.reddit.com/search.rss?q=ai&limit=1", "Reddit public RSS"),
    "arxiv": ("https://export.arxiv.org/api/query?search_query=all:ai&max_results=1", "arXiv Atom"),
    "devto": ("https://dev.to/api/articles?per_page=1", "DEV public API"),
    "techmeme": ("https://www.techmeme.com/feed.xml", "Techmeme feed"),
    "polymarket": ("https://gamma-api.polymarket.com/public-search?q=ai&limit=1", "Polymarket Gamma"),
}


@dataclass
class ProbeResult:
    source: str
    state: str  # available | unavailable | not_configured | not_probed | missing_tool
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"source": self.source, "state": self.state, "detail": self.detail}


@dataclass
class SetupReport:
    environment: dict[str, object] = field(default_factory=dict)
    credentials: list[dict[str, object]] = field(default_factory=list)
    zero_config: list[str] = field(default_factory=list)
    tools: list[dict[str, object]] = field(default_factory=list)
    local_services: list[dict[str, object]] = field(default_factory=list)
    recommendations: list[dict[str, object]] = field(default_factory=list)
    probes: list[ProbeResult] = field(default_factory=list)
    wrote: list[str] = field(default_factory=list)
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "environment": self.environment,
            "credentials": self.credentials,
            "zero_config": self.zero_config,
            "tools": self.tools,
            "local_services": self.local_services,
            "recommendations": self.recommendations,
            "probes": [p.as_dict() for p in self.probes],
            "wrote_layers": self.wrote,
            "skipped_all": self.skipped,
            "notes": self.notes,
        }


def detect_environment() -> dict[str, object]:
    version = ""
    try:
        from importlib.metadata import version as package_version

        version = package_version("sourceglint")
    except Exception:  # pragma: no cover - metadata absent in some checkouts
        version = ""
    target = credentials.config_dir()
    writable = False
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    return {
        "os": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "package_version": version,
        "config_dir": str(target),
        "config_dir_writable": writable,
        "config_file": str(credentials.credentials_file()),
        "keychain_available": platform.system() == "Darwin" and bool(shutil.which("security")),
        "interactive_tty": bool(sys.stdin.isatty() and sys.stdout.isatty()),
        "environment_variables_win": True,
    }


def detect_credentials() -> list[dict[str, object]]:
    rows = []
    for name in sorted(credentials.CREDENTIAL_NAMES):
        rows.append(credentials.presence(name))
    return rows


def zero_config_sources() -> list[str]:
    from .application.runtime import default_sources

    names = []
    for entry in default_sources():
        name = str(entry.get("name") or "")
        if not name or not entry.get("enabled"):
            continue
        if entry.get("credentials"):
            continue
        if str(entry.get("cost") or "") != "free":
            continue
        if name in ZERO_CONFIG_CONNECTORS:
            names.append(name)
    return sorted(names)


def detect_tools() -> list[dict[str, object]]:
    return [
        {
            "binary": binary,
            "purpose": purpose,
            "install_hint": hint,
            "present": shutil.which(binary) is not None,
        }
        for binary, purpose, hint in LOCAL_CLIS
    ]


def detect_local_services() -> list[dict[str, object]]:
    """Presence-only probes for user-authorized local services."""
    results: list[dict[str, object]] = []
    github_auth = False
    if shutil.which("gh"):
        try:
            from .connectors._command import run_command

            completed = run_command(["gh", "auth", "status"], timeout=5)
            github_auth = completed.returncode == 0
        except Exception:  # pragma: no cover - defensive
            github_auth = False
    results.append({
        "service": "GitHub CLI login",
        "present": github_auth,
        "note": "Reused as a read-only token; no new account or scope is requested.",
    })
    xhs_url = credentials.resolve("XHS_MCP_URL")
    logged_in = False
    if xhs_url:
        try:
            client = StdlibHttpClient(default_timeout=1.5, max_attempts=1)
            response = client.request(f"{xhs_url.rstrip('/')}/api/v1/login/status", timeout=1.5)
            payload = response.json()
            data = payload.get("data") if isinstance(payload, Mapping) else None
            logged_in = bool(isinstance(data, Mapping) and data.get("is_logged_in"))
        except (HttpPermanentError, HttpTimeoutError, HttpTransientError, OSError, ValueError):
            pass
    results.append({
        "service": "Xiaohongshu local MCP",
        "present": logged_in,
        "note": "Checked the login status of the configured service." if xhs_url else "No authorized service configured.",
    })
    return results


def recommendations(*, free_only: bool) -> list[dict[str, object]]:
    recs: list[dict[str, object]] = [
        {
            "tier": 0,
            "action": "Do nothing",
            "unlocks": [s for s in zero_config_sources()],
            "cost": "free",
            "requires_authorization": False,
        },
    ]
    if not free_only:
        recs.append({
            "tier": 1,
            "action": "Configure one SCRAPECREATORS_API_KEY",
            "unlocks": list(credentials.SCRAPECREATORS_PLATFORMS),
            "cost": "paid service with a small free allowance; per-page metering",
            "requires_authorization": True,
            "limit": "Each platform still needs the provider's plan to cover its endpoint. Vantage does not promise any free quota.",
        })
    recs.append({
        "tier": 2,
        "action": "Reuse free local tools (yt-dlp, gh) and free tokens",
        "unlocks": ["youtube", "github", "bluesky", "reddit_oauth", "truthsocial"],
        "cost": "free",
        "requires_authorization": True,
    })
    recs.append({
        "tier": 3,
        "action": "Platform approvals or paid datasets",
        "unlocks": ["meta_ad_library", "linkedin_partner", "trustpilot_business", "amazon"],
        "cost": "approval or paid",
        "requires_authorization": True,
        "limit": "Not attempted automatically; remains web fallback until you approve.",
    })
    return recs


def _probe_http(name: str, url: str, label: str) -> ProbeResult:
    client = StdlibHttpClient(default_timeout=6.0, max_attempts=1)
    try:
        headers = {}
        if name == "github":
            token = credentials.resolve("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        response = client.request(url, headers=headers, timeout=6.0, max_bytes=64_000)
    except HttpTimeoutError:
        return ProbeResult(name, "unavailable", f"{label} timed out")
    except HttpTransientError as exc:
        return ProbeResult(name, "unavailable", f"{label} HTTP {exc.status}")
    except HttpPermanentError as exc:
        return ProbeResult(name, "unavailable", f"{label} HTTP {exc.status}")
    except OSError as exc:
        return ProbeResult(name, "unavailable", f"{label} network error: {type(exc).__name__}")
    if response.status >= 400:
        return ProbeResult(name, "unavailable", f"{label} HTTP {response.status}")
    return ProbeResult(name, "available", f"{label} answered")


def _probe_youtube() -> ProbeResult:
    binary = shutil.which("yt-dlp")
    if not binary:
        return ProbeResult("youtube", "missing_tool", "yt-dlp is not installed")
    try:
        from .connectors._command import run_command

        completed = run_command(
            [binary, "--ignore-config", "--no-cookies-from-browser", "ytsearch1:ai",
             "--dump-json", "--no-warnings", "--no-download"],
            timeout=30,
        )
    except Exception as exc:  # pragma: no cover - subprocess boundary
        return ProbeResult("youtube", "unavailable", f"yt-dlp failed: {type(exc).__name__}")
    if completed.returncode != 0 or not completed.stdout.strip():
        return ProbeResult("youtube", "unavailable", f"yt-dlp exited {completed.returncode}")
    return ProbeResult("youtube", "available", "yt-dlp returned one metadata record")


def _probe_cli(name: str, binary: str) -> ProbeResult:
    if not shutil.which(binary):
        return ProbeResult(name, "missing_tool", f"{binary} is not installed")
    return ProbeResult(name, "available", f"{binary} is installed (not run)")


def _probe_patents() -> ProbeResult:
    client = StdlibHttpClient(default_timeout=6.0, max_attempts=1)
    try:
        response = client.request(
            "https://ppubs.uspto.gov/api/users/me/session",
            method="POST",
            json_data=-1,
            headers={
                "User-Agent": "VantageResearch/1.1",
                "Content-Type": "application/json",
                "Referer": "https://ppubs.uspto.gov/pubwebapp/",
                "Origin": "https://ppubs.uspto.gov",
                "X-Access-Token": "null",
            },
            timeout=6.0,
            max_bytes=8_000,
        )
    except HttpTimeoutError:
        return ProbeResult("patents", "unavailable", "USPTO session timed out")
    except HttpTransientError as exc:
        return ProbeResult("patents", "unavailable", f"USPTO session HTTP {exc.status}")
    except HttpPermanentError as exc:
        return ProbeResult("patents", "unavailable", f"USPTO session HTTP {exc.status}")
    except OSError as exc:
        return ProbeResult("patents", "unavailable", f"USPTO network error: {type(exc).__name__}")
    if response.status >= 400:
        return ProbeResult("patents", "unavailable", f"USPTO session HTTP {response.status}")
    return ProbeResult("patents", "available", "anonymous USPTO search session opened")


def run_probes(*, include_cli: bool = True) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    for name, (url, label) in _PROBES.items():
        results.append(_probe_http(name, url, label))
    results.append(_probe_youtube())
    if include_cli:
        results.append(_probe_cli("digg", "digg-pp-cli"))
        results.append(_probe_cli("trustpilot", "trustpilot-pp-cli"))
        results.append(_probe_cli("amazon", "brightdata"))
    results.append(_probe_patents())
    # Credential-only routes are metered; presence is reported, not spent.
    for name, variable in (
        ("tiktok", "SCRAPECREATORS_API_KEY"),
        ("instagram", "SCRAPECREATORS_API_KEY"),
        ("threads", "SCRAPECREATORS_API_KEY"),
        ("pinterest", "SCRAPECREATORS_API_KEY"),
        ("linkedin", "SCRAPECREATORS_API_KEY"),
        ("telegram", "SCRAPECREATORS_API_KEY"),
        ("meta_ad_library", "META_ACCESS_TOKEN"),
        ("x", "X_BEARER_TOKEN"),
        ("stocktwits", ""),
        ("xiaohongshu", "XHS_MCP_URL"),
    ):
        if variable and not credentials.has(variable):
            results.append(ProbeResult(name, "not_configured", f"{variable} is not set"))
        elif variable:
            results.append(ProbeResult(name, "not_probed", "credential configured; not spent by the wizard"))
        else:
            results.append(ProbeResult(name, "not_probed", "public endpoint not probed by the wizard"))
    return results


def _print_report(report: SetupReport) -> None:
    env = report.environment
    print("Vantage setup")
    print(f"  environment : {env.get('os')} {env.get('release')} · Python {env.get('python')}")
    print(f"  config dir  : {env.get('config_dir')} ({'writable' if env.get('config_dir_writable') else 'not writable'})")
    print(f"  keychain    : {'macOS Keychain available' if env.get('keychain_available') else 'not available; a 0600 file is used'}")
    print()
    print(f"Zero-configuration sources ({len(report.zero_config)}):")
    print("  " + ", ".join(report.zero_config))
    print()
    configured = [row for row in report.credentials if row.get("present")]
    print(f"Detected credentials ({len(configured)}), names only:")
    if configured:
        for row in configured:
            print(f"  {row['name']}: configured via {row['source']}")
    else:
        print("  none")
    print()
    print("Local tools:")
    for tool in report.tools:
        state = "present" if tool["present"] else f"missing — {tool['install_hint']}"
        print(f"  {tool['binary']}: {state}")
    print()
    print("Authorized local services:")
    for service in report.local_services:
        print(f"  {service['service']}: {'available' if service['present'] else 'not detected'}")
    print()
    print("Recommended minimum:")
    for rec in report.recommendations:
        print(f"  [{rec['tier']}] {rec['action']}")
        print(f"      unlocks: {', '.join(rec['unlocks'])}")
        print(f"      cost: {rec.get('cost')}")
        if rec.get("limit"):
            print(f"      limit: {rec['limit']}")
    print()
    if report.skipped:
        print("All optional authorization was skipped. Zero-config sources still work.")
    if report.wrote:
        print("Stored credentials: " + ", ".join(report.wrote) + " (values not shown)")
    if report.probes:
        print()
        print("Live probe (bounded):")
        for probe in report.probes:
            print(f"  {probe.source}: {probe.state}" + (f" — {probe.detail}" if probe.detail else ""))
    if report.notes:
        print()
        for note in report.notes:
            print(f"note: {note}")


def _prompt_and_store(report: SetupReport, *, free_only: bool, prefer_keychain: bool) -> None:
    print("\nOptional credentials (press Enter to skip each one; nothing is purchased).")
    for name, label, note in OPTIONAL_KEYS:
        if credentials.presence(name)["present"]:
            continue
        if free_only and name in {"SCRAPECREATORS_API_KEY", "BRIGHTDATA_API_KEY", "META_ACCESS_TOKEN"}:
            continue
        try:
            value = getpass.getpass(f"{label} [{name}] — {note}\n  value (hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\n  skipped remaining prompts")
            return
        if not value.strip():
            continue
        try:
            layer = credentials.store(name, value, prefer_keychain=prefer_keychain)
        except ValueError as exc:
            print(f"  not stored: {exc}")
            continue
        report.wrote.append(f"{name} ({layer})")

    # GitHub: reuse the existing CLI login rather than asking for a token.
    if not credentials.presence("GITHUB_TOKEN")["present"] and shutil.which("gh"):
        try:
            from .connectors._command import run_command

            completed = run_command(["gh", "auth", "status", "--hostname", "github.com"], timeout=5)
            if completed.returncode == 0:
                report.notes.append("GitHub CLI login detected; Vantage can reuse it for read-only requests.")
        except Exception:  # pragma: no cover - defensive
            pass


def _load_or_build() -> SetupReport:
    report = SetupReport()
    report.environment = detect_environment()
    report.credentials = detect_credentials()
    report.zero_config = zero_config_sources()
    report.tools = detect_tools()
    report.local_services = detect_local_services()
    report.recommendations = recommendations(free_only=False)
    return report


def run_setup(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    free_only = "--free-only" in args
    skip = "--skip" in args
    probe = "--probe" in args
    no_keychain = "--no-keychain" in args
    non_interactive = "--non-interactive" in args or as_json

    report = _load_or_build()
    if free_only:
        report.recommendations = recommendations(free_only=True)
    report.notes.append(
        "Vantage never registers accounts, buys plans, recharges, enables auto-renewal, "
        "reads browser cookies, or widens an existing account's permissions."
    )

    interactive = bool(report.environment.get("interactive_tty")) and not non_interactive

    if skip:
        report.skipped = True
        if not probe:
            if as_json:
                print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
            else:
                _print_report(report)
            return 0

    if interactive and not skip:
        if not as_json:
            _print_report(report)
        _prompt_and_store(report, free_only=free_only, prefer_keychain=not no_keychain)
        if not probe and not as_json:
            try:
                answer = input("\nRun the bounded live probe now (about 30s)? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            probe = answer in ("", "y", "yes")

    if probe:
        report.probes = run_probes()

    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - thin alias
    return run_setup(argv)


__all__ = [
    "ProbeResult",
    "SetupReport",
    "detect_credentials",
    "detect_environment",
    "detect_local_services",
    "detect_tools",
    "main",
    "recommendations",
    "run_probes",
    "run_setup",
    "zero_config_sources",
]
