# Vantage 1.1 — global source expansion record

Development branch: `dev/vantage-1.1-global-sources`. Baseline release:
`v1.0.0b1` (`d9eba3ce`). This branch does not modify the 1.0 release, tags, or
the Research Harness. Source breadth is added as opt-in routing around the
existing adapter contract, registry, catalog, evidence ledger and FACT checks.

Machine-readable companion: [source-expansion-1.1.csv](source-expansion-1.1.csv)
(one row per research candidate, 149 total).

## What was read for this round

- `global-source-matrix.csv` — 149 candidates = 136 independent platforms + 13
  aggregators/sub-routes.
- `runtime-16.csv`, `runtime-live-summary.txt` — the 1.0 runtime slots and their
  dated live states.
- `last30days-code-audit.md` — reuse/licence audit of the reference engine.
- `TRAE-implementation.md`, `public-api-probes.json`, `README.md` — probe results
  and implementation constraints.

No broad re-research was performed. Each tabular status below comes from a live
probe or an offline test executed in this round.

## Runtime slots: 1.0 → 1.1

`config/sources.yaml` keeps its original 16 slots unchanged in meaning. Twelve
new slots are appended **disabled**, so a default Skill run is unchanged.

| 1.0 slot | 1.1 state | Notes |
| --- | --- | --- |
| `host_web_search` | unchanged | Host capability |
| `official_web` | unchanged | Official-fetch host capability |
| `reddit` | degraded | Keyless RSS returned 404; bounded archive fallback preserved |
| `hacker_news` | unchanged | Direct connector |
| `github` | unchanged | Direct connector |
| `bluesky` | unchanged | Credential-gated |
| `youtube` | failed route | `yt-dlp` exit 1 in the probe; host-page fallback |
| `stack_overflow` | activated | Publish/update fields separated and live-verified |
| `devto` | activated | Publish/update fields separated and live-verified |
| `hugging_face` | activated | `createdAt` is creation; `lastModified` kept separate |
| `package_registries` (npm) | activated | Per-version registry time is the publish anchor |
| `arxiv` | activated | First submission is the publish anchor; versions deduped |
| `semantic_scholar` | unchanged | Credential-gated; arXiv/OpenAlex/Crossref cover the gap |
| `qiita` | unchanged | Direct connector |
| `x` | unchanged | Credential-gated |
| `product_hunt` | unchanged | Credential-gated |

Twelve appended slots: `crossref`, `openalex`, `pypi`, `crates_io`, `gitlab`,
`lever`, `greenhouse`, `ashby`, `steam`, `world_bank`, `sec_edgar`,
`polymarket`. Eleven are implemented; `polymarket` is registered but exposes no
connector because its public endpoint was unreachable.

`config/sources-expanded.yaml` is the opt-in profile. It enables the verified
free routes with `max_queries_per_run: 1` each, so breadth is available on
demand without multiplying the default research cost.

## Live-verified direct connectors

| Platform | Endpoint | Observed in this round | Time anchor |
| --- | --- | --- | --- |
| Crossref | `api.crossref.org/works` | DOI items with full issued dates | `issued` |
| OpenAlex | `api.openalex.org/works` | Works with publication dates and rebuilt abstracts | `publication_date` |
| PyPI | `pypi.org/pypi/{name}/json` | `requests@2.34.2` | earliest `upload_time` |
| Crates.io | `crates.io/api/v1/crates` | `serde@1.0.229` and topic matches | version `created_at` |
| GitLab | `gitlab.com/api/v4/projects` | Public projects plus bounded releases | `created_at` / release date |
| Lever | `api.lever.co/v0/postings/{board}` | `leverdemo` postings | `createdAt` (ms → ISO) |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{board}/jobs` | `stripe` jobs | `first_published` |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{board}` | `linear` postings; `openai` refused at the 2 MB cap | `publishedAt` |
| World Bank | `api.worldbank.org/v2/.../indicator/...` | CN GDP series | observation year (not a publish date) |
| SEC EDGAR | `efts.sec.gov/LATEST/search-index` | 8-K filing metadata | `file_date` |

The five connectors activated from 1.0 (Stack Overflow, DEV, Hugging Face, npm,
arXiv) also passed live checks with corrected date semantics.

## Honest totals

Derived from the 149-row disposition:

| Measure | Count |
| --- | --- |
| Candidate rows reviewed | 149 |
| Independent platform candidates | 136 |
| Aggregators / same-platform sub-routes | 13 |
| Direct structured access verified | 18 |
| Web-search coverage verified this round | 1 |
| Implemented but not verified this round | 1 (Reddit) |
| Registered only (catalog route, no round-trip) | 85 |
| Credential required | 21 |
| Approval / paid licence required | 8 |
| Access failed in this environment | 3 (YouTube, Steam, Polymarket) |
| Not applicable / aggregator | 12 |

Catalog and routing totals:

- `config/source_catalog.yaml`: 125 entries, 123 with a domain-scoped host-web
  route, 24 with a direct-connector route.
- Distinct registered platforms after de-duplicating the App Store public/owner
  split and the `jobs_pages` / `rss_newsletters` aggregators: **122**.
- Free direct structured platforms: **18**.
- Verified web coverage: **1**. A catalog row is not counted as verified web
  coverage until a host search returns a relevant original page with a real date.

## Dispositions of note

- **Steam** — the `appreviews` endpoint answered the probe network with a 302 to
  the store home page. The adapter classifies this as bounded unavailability
  instead of parsing HTML or inventing reviews. Public store pages remain the
  fallback.
- **Polymarket** — `gamma-api.polymarket.com` was unreachable (connection
  failure, not an HTTP error). No connector is exposed; the catalog entry is
  marked `unavailable`.
- **Ashby** — the `openai` board is 14.48 MB and is rejected by the 2 MB cap;
  `linear` (419 KB) passes. This is a deliberate bound, not a parser bug.
- **Reddit** — RSS 404 is now reported as a bounded limitation and the archive
  lane still runs, so other sources' evidence is never discarded.
- **YouTube** — exit 1, timeout and empty transcripts are distinct statuses;
  metadata-only routing is separated from transcript depth.
- **SEC EDGAR** — filing metadata only. The body is not fetched, so
  `content_kind` stays `filing_metadata` rather than claiming full text.

## Comparison with the reference engine (last30days)

| Capability | last30days (audit) | Vantage 1.1 |
| --- | --- | --- |
| Reddit | Public JSON/HTML scraping with retry | Official OAuth when configured; keyless RSS + bounded archive; no scraping |
| X / Bluesky | ScrapeCreators / authenticated | Native credentialed connectors; no scraping |
| YouTube | `yt-dlp` metadata and captions | Same bounded tool, no cookies, classified failures |
| Scholarly | Not a first-class lane | arXiv + Crossref + OpenAlex with date semantics |
| Package ecosystems | npm only | npm + PyPI + Crates.io |
| Code forges | GitHub | GitHub + GitLab |
| Hiring signals | Not covered | Lever + Greenhouse + Ashby (named boards) |
| Economic / regulatory | Not covered | World Bank + SEC EDGAR |
| Source accounting | Informal | 149-row disposition with nine explicit states |

Vantage does not import the reference engine. Only patterns confirmed by the
licence audit were reused: bounded fallbacks, per-source budgets, and explicit
limitation reporting.

## Research coverage delta

- +10 new verified structured platforms (Crossref, OpenAlex, PyPI, Crates.io,
  GitLab, Lever, Greenhouse, Ashby, World Bank, SEC EDGAR).
- +5 activated and corrected 1.0 connectors (Stack Overflow, DEV, Hugging Face,
  npm, arXiv).
- +1 verified web route (vendor changelogs).
- 0 changes to the default Skill source mix or the 1.0 research contract.

## Verification performed

- Offline unit + contract + integration suite: see the delivery report for the
  final count.
- `RUN_LIVE_TESTS=1 pytest tests/live/test_live_expansion.py` — 13 checks passed
  against public endpoints.
- Representative live end-to-end runs wrote real items into the evidence
  ledger:
  - Crossref: 13 items with DOI URLs and full dates.
  - OpenAlex: 20 items with DOI URLs and full dates.
  - Both runs reported `failed_sources: []`.

## Limits that remain

- Host web search could not be exercised in the build environment; 85 catalog
  rows stay `registered_only` rather than being counted as coverage.
- Named-parameter sources (Lever, Greenhouse, Ashby, Steam, World Bank, SEC)
  need the host to pass a board, appid, country/indicator pair, or form filter.
  Without it they record a limitation instead of guessing.
- Steam and YouTube direct routes are blocked from this network; Polymarket has
  no reachable public endpoint. These are recorded, not retried indefinitely.
