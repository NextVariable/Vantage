# Vantage 1.1 Phase 2 — execution plan

Baseline: `dev/vantage-1.1-global-sources` at `21be222` (5 commits, push blocked
by network). No harness, FACT, ledger or host-protocol changes.

## Reality check

- Free structured direct: 18 → target 30–40.
- CLI/MCP/authorized: count only what actually runs; no padding.
- Verified web coverage: needs a real Host Search. This TRAE environment has
  none, so produce a machine-readable verification task list for a host/Codex
  run and keep catalog rows `registered_only` until evidence exists.
- Do not count configuration, offline stubs or duplicate routes.

## Wave A — credential-free endpoints to probe then implement

Research/registry: PubMed E-utilities, Europe PMC, DOAJ, Zenodo, DataCite,
Open Library, Internet Archive advancedsearch, ClinicalTrials.gov v2, Wikidata.
News/community: GDELT DOC 2.0, Google News RSS, Bluesky public AppView,
Lobsters, Lemmy, Codeberg, Hashnode.
Developer packages: Maven Central, NuGet, RubyGems, Packagist, Docker Hub,
WordPress plugin API.
App store: iTunes Search API + customer-reviews RSS.
Japan feeds: Zenn RSS, PR Times RSS, ITmedia RSS, note RSS.

Rule: probe first with a raw HTTP request; implement only if it returns real
items with an original URL and a usable date field. Otherwise record the exact
failure (status, redirect, auth, ToS) and move on.

## Wave B — reusable adapters, not per-site crawlers

- `feeds.py`: one RSS/Atom adapter driven by per-feed config; each feed is a
  distinct platform entry.
- `packages.py`: extend the existing package-registry style for Maven, NuGet,
  RubyGems, Packagist, Docker Hub.
- `community.py` (or extend devplatforms): Lobsters, Lemmy, Codeberg, Hashnode.
- Keep every adapter behind `SourceAdapter.retrieve`; no new framework.

## Wave C — authorized/paid guide

Extend `docs/source-authorization.md` with application URL, scopes, cost,
config steps and expected depth for X, Reddit, Product Hunt, LinkedIn, G2,
Capterra, Trustpilot, Google Play, Amazon, Meta Ad Library, TikTok, Steam,
Discord/Telegram, and paid aggregators. Never register or purchase.

## Wave D — host-web verification pack

Generate `docs/host-web-verification-tasks.json` from the catalog:
platform, domains, query template, market/language, expected evidence fields.
Status starts `pending_host`; a host run fills verified URL/date/snippet.
Batch-probe cheaply (one query per platform), not full research runs.

## Acceptance

- Each new connector: offline unit test + live probe evidence + registry entry
  (disabled by default) + expanded-profile entry.
- Default 6-slot Skill unchanged.
- Full pytest, ruff on changed files, repository check, install smoke.
- Update 149-row CSV, expansion doc, counts and CHANGELOG.
- Commit locally; push if GitHub becomes reachable.
