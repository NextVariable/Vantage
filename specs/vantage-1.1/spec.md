# Vantage 1.1 — Global Source Expansion · Implementation Spec

Baseline: `v1.0.0b1` = `d9eba3ce670daaa89d161e8e19b76c4562b8f8ce`
Working branch: `dev/vantage-1.1-global-sources` (already created from `main`, clean tree)

Scope: expand **real** structured direct access and verified Host-Web coverage without rewriting
the 1.0 Research Harness, Registry, Evidence Ledger, FACT verification or Host v2 protocol.
Research inputs are already read from the local `Vantage-1.1-Global-Sources/`
workspace (kept outside this repository): 149 candidates = 136 independent
platforms + 13 aggregators/sub-routes.

---

## 1. Non-negotiable constraints

1. Do not modify `runs/rc/**` historical artifacts, releases or tags; do not merge `main`;
   do not publish a 1.1 release.
2. Keep `SourceAdapter.retrieve(plan, request) -> list[RawSourceResult]`; no new harness,
   ledger, FACT verifier, Host protocol or browser runner.
3. Default research cost must not grow: the first commit keeps `config/sources-hybrid.yaml`
   at its 6 slots and `config/sources.yaml` default-enabled set unchanged. New sources are
   enabled only in a new opt-in profile.
4. Never read/log user secrets. Credential-gated routes fail closed with
   `AdapterAuthMissing` / catalog `credential_required` / `approval_required`.
5. Every claimed-usable source needs: live probe evidence, original URL, explainable date
   field, non-empty relevant item, standard field mapping, attribution, fallback, offline test.
6. One platform = one independent source entry, regardless of adapter/API/CLI/fallback count.
7. Do not fabricate engagement, comments, captions or dates. Missing fields stay empty or are
   recorded as unknown.

## 2. Current code facts that drive the design

- Connectors: `src/sourceglint/connectors/` (`open_sources.py`, `reddit.py`, `youtube.py`,
  `github.py`, `hacker_news.py`, `bluesky.py`, `authorized_sources.py`, `host_search.py`,
  `official_web.py`, `_http.py`, `_recency.py`, `_query.py`, `_deep.py`, `_captions.py`).
- Factory: `src/sourceglint/application/runtime.py::default_adapter_factory`.
- Registry loader: `src/sourceglint/pipeline/source_registry.py`; planning:
  `pipeline/retrieval_plan.py` (enabled + market + language filter, per-source
  `max_queries_per_run`); execution in `pipeline/orchestrator.py::_retrieve_batch`
  (partial-success preservation, per-query deadlines, cache).
- Default Skill: `SKILL.md` runs `--public-sources-only --registry config/sources-hybrid.yaml`;
  `cli.py` filters `cost == free and not auth_required`, so adding free sources to that file
  WOULD raise default calls. Therefore new sources go to an opt-in profile.
- Catalog: `config/source_catalog.yaml` + `schemas/source_catalog.schema.json` (enums for
  family, routes, availability, modes, evidence_roles; unique names). Catalog ≠ connector.
- `src/sourceglint/health.py::CONNECTORS` must list every implemented connector.
- Tests: `tests/unit/connectors/`, `tests/live/` (opt-in `RUN_LIVE_TESTS=1`),
  `tests/contracts/` (registry/catalog schema), `tests/unit/test_repository_privacy.py`.

## 3. Batch 1 — activate the five existing connectors correctly

All edits in `src/sourceglint/connectors/open_sources.py` (+ tests).

| Adapter | Change |
| --- | --- |
| `HuggingFaceAdapter` | `published_at` ← `createdAt` only. Record `lastModified` as `raw_metadata["last_modified"]`, `date_semantics="model_created"`. If `createdAt` is absent, skip the row (never substitute the update time). `text` = model id + pipeline tag; do not invent a description. `raw_metadata` keeps `downloads`, `likes`, `tags`, `pipeline_tag`. |
| `PackageRegistriesAdapter` (npm) | Search `package.date` is the registry index date → store as `raw_metadata["search_index_date"]`; it is NOT `published_at`. Resolve exact publish from the package document `time[version]` (`GET https://registry.npmjs.org/{name}`), bounded to `min(limit, 5)` lookups and skipped when the child deadline is nearly exhausted. If unresolved: `published_at=""`, `raw_metadata["publish_time"]="unresolved"`. |
| `ArxivAdapter` | Parse `updated` into `raw_metadata["updated_at"]` separately from `published_at`; dedupe by base id before the version suffix (`2609.12345v2` → `2609.12345`), keep the newest `published`; record `version`. |
| `StackOverflowAdapter` | Keep `creation_date` as `published_at`; add `last_edit_date` / `last_activity_date` to `raw_metadata` as update fields. |
| `DevToAdapter` | Keep `published_timestamp`; add `edited_at` / `readable_publish_date` to `raw_metadata`. |

Acceptance: two live queries per adapter, non-empty results, valid canonical URL, correct date
semantics; offline fixtures cover the wrong-date traps (HF update-only row, npm search-date-only,
arXiv v1/v2 duplicate).

## 4. Batch 2 — six new structured connectors

New modules, all inside the existing adapter contract, sharing `_http.py`, `_recency.py`,
`_query.py`. Common rules: `limit` ≤ 20; `search_bounds(plan, request)` for windows; only full
dates accepted; update/deposit dates recorded separately; `AdapterRateLimited` on 429,
`AdapterTimeout`, `AdapterUnavailable`, `AdapterInvalidResponse` on bad shapes; no retries beyond
the existing bounded HTTP policy; `retrieved_at` not invented.

| Module | Class | Endpoint / inputs | Mapping & dates |
| --- | --- | --- | --- |
| `scholarly.py` | `CrossrefAdapter` | `api.crossref.org/works?query.bibliographic=&filter=from-pub-date:,until-pub-date:&rows=` | DOI, title, JATS-stripped abstract (only when present), authors, `issued` full date → `published_at`; `deposited`/`indexed` separate; URL `https://doi.org/{doi}`; skip partial dates. |
| `scholarly.py` | `OpenAlexAdapter` | `api.openalex.org/works?search=&filter=from_publication_date:,to_publication_date:` | `id`, `doi`, `title`, `publication_date` (full date only), OA URL; reconstruct abstract from `abstract_inverted_index` word order only when present; `updated_date` separate; optional cursor only when `OPENALEX_API_KEY` is present, otherwise first page. |
| `packages.py` | `PyPIAdapter` | named package `GET pypi.org/pypi/{name}/json`; no global search | canonical package + version, `info.project_url`/`package_url`, summary/description excerpt; `upload_time_iso_8601` (earliest file for multi-file releases); yanked flag; 404 → empty with limitation. |
| `packages.py` | `CratesIoAdapter` | `crates.io/api/v1/crates?q=&per_page=` then one `/api/v1/crates/{id}` for the newest version | crate@version, description, version `created_at`, downloads; crate-level `created_at` separate; search `updated_at` only for discovery; UA identifies Vantage. |
| `devplatforms.py` | `GitLabAdapter` | `gitlab.com/api/v4/projects?search=&order_by=last_activity_at`, then releases for at most 2 verified projects | project id, `web_url`, name/description, `created_at`; releases as `source_type="release"` with tag + `released_at`; anonymous public scope only; `next` link not followed unless budget allows. |
| `ats.py` | `LeverAdapter` | `api.lever.co/v0/postings/{board}?mode=json`; board from `request["boards"]` or `plan["boards"]` | board+id, `hostedUrl`, `text`, `descriptionPlain`, `categories`; no public publish date → `source_type="page"`, `published_at=""`, snapshot semantics. |

Each adapter gets: fixture-based unit tests (success, empty, wrong shape, 429, timeout, literal
`published_at` semantics), one opt-in live test, and a registry entry.

## 5. Batch 3 — repair or bounded-degrade failing routes

| Route | Action |
| --- | --- |
| Reddit RSS | Keep the existing keyless adapter. Add explicit limitation reporting and a fixture for HTTP 404 so the source reports `unavailable`/`partial` without discarding other sources' evidence. No cookies, no retries; public post URL remains the Host fallback. |
| YouTube yt-dlp | Keep the no-cookie/no-download adapter. Classify exit 1 / timeout / empty transcripts as distinct limitations; never claim subtitles from a failed call. Live status stays "search fallback" unless a real probe passes. |
| Greenhouse | New `GreenhouseAdapter` (`boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`) requiring a verified public board; `updated_at` is update-only, `datePosted`/`first_published` authoritative; 404 → limitation, not a global claim. |
| Ashby | New `AshbyAdapter` (`api.ashbyhq.com/posting-api/job-board/{board}`) with a hard response-size cap (`max_bytes`, default 2 MB) and `publishedAt`/`isListed`; oversize → `AdapterInvalidResponse` with limitation. |
| Steam | New `SteamAdapter` (`store.steampowered.com/appreviews/{appid}?json=1&language=&cursor=&purchase_type=`) requiring a verified appid; `recommendationid`, original review URL, `review`, `timestamp_created`, `votes_helpful`; `timestamp_updated` separate; 200-but-unparseable → `AdapterInvalidResponse`. |

Acceptance: one real probe per repaired route; on failure the source is recorded as
`unavailable`/`partial` with a limitation and no fabricated samples. Other evidence is preserved
by the existing per-source loop (already implemented).

## 6. Batch 4 — traverse the 149-row matrix

Disposition is tracked in `docs/source-expansion-1.1.md` (new, public, sanitized):

- **Implemented native connectors (new)**: Crossref, OpenAlex, PyPI, Crates.io, GitLab, Lever,
  Greenhouse, Ashby, Steam, World Bank, SEC EDGAR, Polymarket. Reuse one module per family.
- **Existing native**: Stack Overflow, DEV, Hugging Face, npm, arXiv, Qiita, HN, GitHub, Reddit
  (keyless), YouTube (CLI), Bluesky/X/Product Hunt/Semantic Scholar (credential-gated).
- **Credential/approval only**: X, Bluesky, Product Hunt, Semantic Scholar, Threads,
  Meta Ad Library, FRED, Discord, Telegram, Crunchbase, IT桔子, Similarweb, Semrush, Ahrefs,
  Rakuten, USPTO/EPO/The Lens, Companies House/EDINET, app-store owner APIs.
- **Host-Web catalog targets**: the remaining public-indexable F-class platforms, each with
  explicit domains/languages/markets/evidence roles.
- **No compliant route / unavailable**: the 2 G-class candidates and endpoints documented as
  404/403 in the research probes (e.g. Europe PMC probe, GitHub Releases 403, initial
  Greenhouse 404) remain unverified; no invented API.

World Bank / SEC / Polymarket are implemented only if their public endpoints pass a live probe
during this round; otherwise they stay catalog-only and are reported as unverified.

## 7. Batch 5 — maximize Host-Web coverage honestly

- Extend `config/source_catalog.yaml` with explicit targets: more CN/JP/KR/IN/BR sources,
  review/commerce, crowdfunding, ads/channel, hiring/financial/regulatory, patents, app stores,
  community/forum, newsletters/podcasts.
- Each target defines `family`, `routes: [host_web_search]`, `availability`, `modes`, `markets`,
  `languages`, `domains`, `evidence_roles`, `priority`, `notes`.
- Catalog entries do not count as verified until a real Host search returns an original page,
  real date and supporting excerpt. Targets that cannot be live-verified in this environment
  are labeled `search_fallback`/`tools_unverified`, never `ready` by wishful thinking.
- Do not change `select_host_search_targets` semantics or the target budget (10).

## 8. Batch 6 — credential-gated sources

- Keep existing X / Bluesky / Product Hunt / Semantic Scholar adapters.
- Add a shared credential check that raises `AdapterAuthMissing` with the **name** of the missing
  variable only; no value reads in logs/tests.
- `doctor` (health) reports `MISSING_CREDENTIALS` with names + setup URLs.
- Document scopes and setup in `docs/source-authorization.md`; all four remain
  `credential_required` in the catalog with public-web fallback. Never auto-create accounts,
  purchase credits or bypass platform limits.

## 9. Config & wiring changes

- `config/sources.yaml`: append new entries with `enabled: false` (documented opt-in) so the
  1.0 default run is unchanged. Credential entries keep `credentials: [NAME]`.
- `config/sources-expanded.yaml` (new): opt-in profile with the new free connectors enabled,
  `max_queries_per_run: 1` for each new source, priorities chosen so no single source dominates;
  this is the profile used for representative end-to-end studies.
- `config/sources-hybrid.yaml` / `config/sources-native.yaml`: comments only (no slot change),
  pointing to the expanded profile.
- `src/sourceglint/application/runtime.py`: map new names to adapters; keep
  `allow_credentials` behavior; no credentials for free sources.
- `src/sourceglint/health.py`: extend `CONNECTORS`.

## 10. Tests & verification

- New unit files: `tests/unit/connectors/test_scholarly.py`, `test_packages.py`,
  `test_devplatforms.py`, `test_ats.py`, `test_open_data.py` (if implemented), plus updates to
  `test_open_sources.py` for date semantics.
- Contract tests: registry schema for `sources.yaml` + new profile; catalog uniqueness/schema.
- Live (opt-in) tests: `tests/live/test_live_open_sources.py` extended; new
  `tests/live/test_live_new_sources.py`.
- Regression: full offline suite, `ruff check`, install check (`pip install -e .`),
  `python scripts/check_repository.py` (if present), privacy test.
- Representative end-to-end: run `config/sources-expanded.yaml` on a small query with a frozen
  host/model stub (no Codex cost), assert new-source evidence ids reach the ledger, FACT support
  contract unchanged, deadline/partial behavior unchanged.
- Record live probe results in `docs/source-expansion-1.1.md` with date, URL, field observed.

## 11. Docs

Update: `README.md`, `README.zh-CN.md`, `SKILL.md` (minimal usage note + opt-in profile),
`CHANGELOG.md`, `docs/source-access-matrix.md`, `docs/source-fallback-playbook.md`.
Add: `docs/source-authorization.md`, `docs/source-expansion-1.1.md`.
Remove local absolute paths, secrets and identity data; keep only public URLs and observed fields.

## 12. Git delivery

Logical commits on `dev/vantage-1.1-global-sources`:
1. Batch 1 date semantics + tests.
2. Batch 2 connectors + wiring + tests.
3. Batch 3 repairs + tests.
4. Expanded registry/catalog + Batch 4/5 coverage docs.
5. Batch 6 credential docs/tests.
6. Docs, changelog, final verification.

Push only this branch (no `main`, no tags). If GitHub connectivity fails, report the exact error
and the local SHA.

## 13. Final acceptance report (single delivery)

Latest SHA; old 16 slots vs new; newly usable platforms; free-direct platforms; verified web
coverage; credential-required; failing/unavailable; 149-row disposition; last30days comparison;
coverage delta; 1.0 regression results; tests/CI/security; `SOURCE_EXPANSION_READY` verdict
(only if the claimed counts are real and reproducible).
