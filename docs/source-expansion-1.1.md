# Vantage 1.1 — global source expansion record

Development branch: `dev/vantage-1.1-global-sources`. Baseline release:
`v1.0.0b1` (`d9eba3ce`). This branch does not modify the 1.0 release, tags, or
the Research Harness. Source breadth is added as opt-in routing around the
existing adapter contract, registry, catalog, evidence ledger and FACT checks.

Machine-readable companion: [source-expansion-1.1.csv](source-expansion-1.1.csv)
(one row per research candidate, 149 total) and
[source-expansion-1.1-additions.csv](source-expansion-1.1-additions.csv)
(platforms implemented in phase 2 that were not rows in the original matrix).

This record covers two implementation waves on the same branch. Phase 1
activated and corrected the 1.0 connectors and added ten structured routes.
Phase 2 adds eighteen further key-free routes (research registries, package
registries, an app store, a federated community and Japan/China publisher
platforms) and produces a machine-readable host-search verification pack for
the platforms that cannot be reached without a host retrieval capability.

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
| `youtube` | verified | `yt-dlp` returned a real video with an upload date in the 2026-11-24 live run |
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

Phase 2 appends eighteen more slots, all **disabled** in `config/sources.yaml`
so the default Skill run is unchanged: `pubmed`, `doaj`, `zenodo`, `datacite`,
`open_library`, `internet_archive`, `clinicaltrials`, `maven_central`, `nuget`,
`rubygems`, `docker_hub`, `app_store`, `lemmy`, `zenn`, `note`, `itmedia`,
`sspai`, `makuake`.

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

## Phase 2: key-free routes added after a real probe

Every row below answered a real request in this environment with an original
URL and a usable date field. Dates that are coarser than a day are labelled
(`date_precision`, `date_semantics`) rather than padded to a fake timestamp.

| Platform | Endpoint | Time anchor | Notes |
| --- | --- | --- | --- |
| PubMed | `eutils.ncbi.nlm.nih.gov/entrez/eutils` | journal `pubdate` | `epubdate` and last edit kept separate |
| DOAJ | `doaj.org/api/search/articles` | journal year/month | index `created_date` kept separate |
| Zenodo | `zenodo.org/api/records` | `publication_date` | record creation is a labelled fallback |
| DataCite | `api.datacite.org/dois` | published / issued / doi_created | fallback order is labelled |
| Open Library | `openlibrary.org/search.json` | `first_publish_year` | year precision, explicitly labelled |
| Internet Archive | `archive.org/advancedsearch.php` | item `date` | archive field, not first publication |
| ClinicalTrials.gov | `clinicaltrials.gov/api/v2/studies` | first posted | last-update-posted kept separate |
| Maven Central | `search.maven.org/solrsearch/select` | latest version `timestamp` (ms) | version count is not engagement |
| NuGet | `azuresearch-usnc.nuget.org` + registration | version `published` | search payload has no date |
| RubyGems | `rubygems.org/api/v1/search.json` + gem doc | `version_created_at` | search payload has no date |
| Docker Hub | `hub.docker.com/v2/search` + repository detail | `date_registered` | `last_updated` kept separate |
| App Store | `itunes.apple.com/search` | `releaseDate` | current-version date separate; reviews need an app id |
| Lemmy | `lemmy.world/api/v3/search` | `post.published` | federated `ap_id` is the permalink |
| Zenn | `zenn.dev/api/search` | `article.published_at` | RSS feed documented as fallback |
| note | `note.com/api/v3/searches` | `publish_at` | canonical `/{user}/n/{key}` URL |
| ITmedia | `rss.itmedia.co.jp/rss/2.0/news_bursts.xml` | feed `pubDate` | local topic filter |
| SSPAI | `sspai.com/feed` | feed `pubDate` | local topic filter |
| Makuake | `makuake.com/rss` | feed date | local topic filter |

Cache, per-source budget, retry policy and error classification are unchanged:
the new adapters use the same HTTP client, timeout handling and bounded
enrichment (at most three detail lookups per query for NuGet/RubyGems/Docker
Hub) as the phase-1 connectors.

## Host-search verification pack

This build environment has no Host Web Search capability, so platforms with no
public structured endpoint cannot be honestly marked as covered here. Instead,
`docs/host-web-verification-tasks.json` contains one machine-readable task per
catalog row that only has a host-web route (65 tasks): platform, domains, query
template, markets, languages, modes, evidence roles, expected fields and
`status: pending_host`. A capable host or Codex run fills `final_url`,
`published_at` and a snippet, then flips the status. Nothing in that file is
counted as verified coverage.

## Honest totals

Derived from the 149-row disposition:

| Measure | Count |
| --- | --- |
| Candidate rows reviewed | 149 |
| Independent platform candidates | 136 |
| Aggregators / same-platform sub-routes | 13 |
| Direct structured access verified (in the 149 rows) | 32 |
| Direct structured access verified (phase-2 additions not in the matrix) | +5 |
| **Total verified free structured platforms** | **37** |
| Web-search coverage verified this round | 1 |
| Implemented but not verified this round | 1 (Reddit) |
| Registered only (catalog route, no round-trip) | 73 |
| Credential required | 20 |
| Approval / paid licence required | 8 |
| Access failed in this environment | 2 (Steam, Polymarket) |
| Not applicable / aggregator | 12 |

Catalog and routing totals:

- `config/source_catalog.yaml`: 137 entries, 135 with a domain-scoped host-web
  route, 43 with a direct-connector route (36 passed the 2026-11-24 live run;
  arXiv returned a transient 429 that run and passed the 2026-10-04 snapshot),
  65 host-only entries waiting in the verification pack.
- Distinct registered platforms after de-duplicating the App Store public/owner
  split and the `jobs_pages` / `rss_newsletters` aggregators: **134**.
- Free direct structured platforms with a live pass on record: **37** = 43
  connector implementations minus 4 credential-gated (X, Bluesky, Product Hunt,
  Semantic Scholar) minus 2 that did not answer (Steam, Reddit's keyless lane).
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
- **YouTube** — the 2026-11-24 live run returned a real video with an upload
  date through local `yt-dlp`. Exit 1, timeout and empty transcripts remain
  distinct statuses; metadata-only routing stays separate from transcript depth.
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

- +10 new verified structured platforms in phase 1 (Crossref, OpenAlex, PyPI,
  Crates.io, GitLab, Lever, Greenhouse, Ashby, World Bank, SEC EDGAR).
- +18 new verified structured platforms in phase 2 (PubMed, DOAJ, Zenodo,
  DataCite, Open Library, Internet Archive, ClinicalTrials.gov, Maven Central,
  NuGet, RubyGems, Docker Hub, App Store, Lemmy, Zenn, note, ITmedia, SSPAI,
  Makuake).
- +5 activated and corrected 1.0 connectors (Stack Overflow, DEV, Hugging Face,
  npm, arXiv); YouTube's local metadata route passed the 2026-11-24 live run.
- +1 verified web route (vendor changelogs).
- 0 changes to the default Skill source mix or the 1.0 research contract.

## Verification performed

- Offline suite (2026-11-24): `2450 passed, 45 skipped` with
  `.venv/bin/python -m pytest -q`; live tests are skipped by default.
- `scripts/check_repository.py`: `PASS`, 474 files, 173 local links, no errors.
- Live suite (`RUN_LIVE_TESTS=1 pytest tests/live -q -rA`): 39 passed, 2 failed,
  4 skipped. The 36 source-level passes returned real dated items. The two
  failures are bounded and classified: arXiv returned a transient 429 (it passed
  on 2026-10-04) and Reddit's keyless RSS returned 404. The four skips are the
  credential-gated X, Bluesky, Product Hunt and Semantic Scholar checks.
- Phase-2 live checks (`tests/live/test_live_phase2_sources.py`): 18 checks
  passed across research registries, package registries, the App Store, Lemmy
  and the Japanese/Chinese publisher feeds.
- Representative live end-to-end runs wrote real items into the evidence
  ledger:
  - Crossref: 13 items with DOI URLs and full dates.
  - OpenAlex: 20 items with DOI URLs and full dates.
  - Both runs reported `failed_sources: []`.

## Limits that remain

- Host web search could not be exercised in the build environment; 73 catalog
  rows stay `registered_only` rather than being counted as coverage. The 65
  host-only rows are listed as machine-readable tasks in
  [the verification pack](host-web-verification-tasks.json).
- Named-parameter sources (Lever, Greenhouse, Ashby, Steam, World Bank, SEC)
  need the host to pass a board, appid, country/indicator pair, or form filter.
  Without it they record a limitation instead of guessing.
- Steam's review endpoint is blocked from this network; Polymarket has no
  reachable public endpoint. Both are recorded, not retried indefinitely.
- X, Reddit, LinkedIn, G2, Capterra, Trustpilot, Product Hunt, the app-store
  owner APIs and the ad libraries need credentials or approval. This round
  prepared the application paths but did not register, buy or scrape anything.
