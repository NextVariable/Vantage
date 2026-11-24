# Vantage 1.1 — Task Plan

Status legend: [ ] pending · [~] in progress · [x] done

## Phase A — Baseline & Batch 1
- [x] A1 Confirm `main`/`v1.0.0b1` = `d9eba3c`, branch `dev/vantage-1.1-global-sources`, clean tree.
- [x] A2 Fix `HuggingFaceAdapter`: `createdAt` → `published_at`; `lastModified` → metadata only; skip update-only rows.
- [x] A3 Fix npm publish semantics: search date → `search_index_date`; exact `time[version]` lookup (≤5, deadline-aware).
- [x] A4 Fix arXiv: `updated` separate, base-id dedupe, version metadata.
- [x] A5 Record update timestamps separately for Stack Overflow and DEV.
- [x] A6 Update `tests/unit/connectors/test_open_sources.py` + add date-trap fixtures.
- [x] A7 Live probe 5 adapters (2 queries each); record results.

## Phase B — Batch 2 connectors
- [x] B1 `connectors/scholarly.py`: `CrossrefAdapter`, `OpenAlexAdapter`.
- [x] B2 `connectors/packages.py`: `PyPIAdapter`, `CratesIoAdapter`.
- [x] B3 `connectors/devplatforms.py`: `GitLabAdapter`.
- [x] B4 `connectors/ats.py`: `LeverAdapter`.
- [x] B5 Unit tests for B1–B4 (success/empty/bad shape/429/timeout/date semantics).
- [x] B6 Wire factory + `health.CONNECTORS`; add disabled registry entries.
- [x] B7 Live probes (one query each, ≤5 items); record URL/date/fields.

## Phase C — Batch 3 repairs
- [x] C1 Reddit RSS: limitation/fixture behavior on 404, no evidence loss.
- [x] C2 YouTube: classify exit 1 / timeout / empty transcripts; no false claims.
- [x] C3 `GreenhouseAdapter` with verified board; `updated_at` ≠ publish.
- [x] C4 `AshbyAdapter` with `max_bytes` cap; oversize → invalid response + limitation.
- [x] C5 `SteamAdapter` with appid/cursor; parse failure explicit.
- [x] C6 Unit tests + one live probe per route; record outcomes.

## Phase D — Batch 4 expansion
- [x] D1 Implement World Bank / SEC EDGAR / Polymarket only if live probes pass.
- [x] D2 Add `config/sources-expanded.yaml` (opt-in, max_queries_per_run=1, no default change).
- [x] D3 Append disabled entries to `config/sources.yaml`.
- [x] D4 Build 149-row disposition table in `docs/source-expansion-1.1.md`; counts by status 1–9.

## Phase E — Batch 5 Host coverage
- [x] E1 Extend `config/source_catalog.yaml` with explicit public-web targets (domains/languages/markets/roles).
- [x] E2 Validate schema + uniqueness; selector tests unchanged.
- [x] E3 Mark verification level honestly (ready only when real retrieval observed).

## Phase F — Batch 6 credentials
- [x] F1 Shared credential-name check + fail-closed messages (X/Bluesky/PH/Semantic Scholar).
- [x] F2 `doctor` credential reporting; tests that no secret value is emitted.
- [x] F3 `docs/source-authorization.md` with scopes/setup/fallback.

## Phase G — Docs & verification
- [x] G1 Update README/README.zh-CN/SKILL/CHANGELOG/access matrix/fallback playbook.
- [x] G2 Remove local absolute paths, secrets, identity data; privacy test passes.
- [x] G3 Full offline pytest; ruff; install check; repository check; security scan. (2419 passed/27 skipped; changed-file ruff clean; repo lint has pre-existing failures outside this diff; install smoke PASS; repository check PASS; pip-audit unavailable offline)
- [x] G4 Representative expanded-profile end-to-end study with frozen model; verify ledger + FACT contract.
- [x] G5 Logical commits + push `dev/vantage-1.1-global-sources` (or report network failure). (4 local commits; push blocked: `Empty reply from server` over HTTPS, retried once with HTTP/1.1)

## Phase H — Final delivery
- [x] H1 16-slot vs new comparison, source counts by status, 149-row disposition.
- [x] H2 last30days comparison, coverage delta, 1.0 regressions, tests/CI/security.
- [x] H3 `SOURCE_EXPANSION_READY` verdict + latest SHA.
