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

## Phase 3: Codex Host acceptance, 2026-11-24

The earlier sections are the Phase 1–2 snapshots. Current web results replace
the pending status, and the totals below use platform deduplication.

[Task results and original samples](host-web-verification-tasks.json) ·
[Search/body/comments/engagement matrix](source-host-capabilities.csv) ·
[Machine-readable totals](source-live-status.json) ·
[Authorization checklist](source-authorization.md#phase-3-authorization-checklist).

### Live retrieval and counting

| Measure | Observed |
| --- | ---: |
| Original tasks attempted | 65 of 65 |
| Original tasks with a relevant, attributable and visibly dated original item | 23 |
| Original tasks with partial access, failure, or discovery-only results | 17 partial / 21 failed / 4 discovery-only |
| Supplemental public-web checks | 13 attempted; 1 verified / 8 partial / 4 failed |
| Verified original web samples passing frozen STDIO → ledger → evidence-only report | 24 |
| Of those, eligible for an automatic recommendation in a supported context at the ten-target cap | 7 |
| Latest key-free structured connector passes, excluding CLI | 35 |
| Latest working public CLI platforms | 1 (YouTube via yt-dlp metadata) |
| Verified standalone MCP platforms / new authenticated round trips | 0 / 0 |
| **Deduplicated latest live floor** (35 structured + 1 CLI + 2 live web platforms) | **38** |
| Deduplicated when also including automatic routing + frozen report | 42 |
| Deduplicated when also including a named Host route + frozen report | 59 |

The structured and CLI counts use the preceding Phase 2 live test on
2026-11-24. Phase 3 conducted separate Host probes. arXiv's Oct 4 pass remains
historical beside the latest HTTP 429. Steam's bounded-redirection test
does not demonstrate access to a review. App Store's iTunes search and public
reviews are two capabilities of one platform; YouTube metadata uses one CLI
route. Google Search, Google News, Techmeme, Google Patents, generic job-board
aggregation and newsletter discovery do not add independent evidence-source
platforms. Google Patents is useful as a mirror of a patent office document.
The result for general Host discovery does not prove which vendor ran the index.

The 149 original inventory rows give 136 independent candidate platforms after
13 aggregate/sub-route entries. Its five matrix-external direct additions are
PubMed, DOAJ, ClinicalTrials.gov, Open Library and Internet Archive. These are
inventory rows, not a total to add to the shipped catalog. The 137 catalog
entries include 135 Host-web route declarations. Under this audit's counting
rules, six discovery/aggregator entries are excluded and three host sub-routes
merge into their platforms: Apple App Store public reviews, TikTok Creative
Center and Meta Ad Library. That leaves 128 catalog platform candidates, with
58 Host-declared lanes outside the individual Phase 3 web sample. Those 58
lanes were inspected as configuration entries and have no new individual
public-web acceptance result from this round. Jike received a supplemental
probe outside the catalog and had no complete item date.

A passing web probe can demonstrate access to one public item. Some examples
have historical dates and would need a matching user-requested research
window. Visible review ratings, comment counts, and available comment text
are marked separately. A caption can support only what that caption says.
Licensing, breadth and future accessibility are outside an individual probe.

### Automatic recommendations and named routes

Before changing configuration, some eligible source types were consistently
displaced by priority and the existing family/target cap. G2, for example, was
never automatically recommended in the enumerated contexts despite being web
readable. Its priority is now 97. A frozen test confirms G2 is recommended for
global English voice-of-customer and PR TIMES for Japanese launch research at
the actual three-target benchmark budget. Higher budgets are not required for
these two cases. Across all inspected profile-supported contexts, 15 of the
65 original tasks are automatically recommendable at ten targets; only
seven dated-sample sources across both batches are in that set of recommended
routes. The limit, family diversification and market/language filters still
apply. The enumerated best context is stored per profile in the task record.

For an explicitly requested platform or original domain already in the
catalog and compatible with task scope, the Skill instructs the Host to
substitute that target within its current budget and report the catalog ID
only after trying it. This uses the existing Host request rather than a new
engine route. The replay sends the frozen observations via the real
StdioHostSource adapter, production normalization, Evidence Ledger and
existing evidence fallback renderer. Offline replay uses an unavailable
synthesis model by design, so a citation in a frozen evidence-only report does
not certify successful model synthesis. A regular run with no explicit source
can still omit lower-priority targets.

Codex also performed one read-only natural-language profile dry run using the
updated Skill. It chose Expanded for technical package/paper research, Hybrid
for Otter feedback, Expanded for Japan launch research, and Expanded for
competitive strategy using a named Ashby board and SEC filings. This tests
selection by intent only. The actual research runs below use their scoped
registry explicitly and provide the independent live path check.

### Two real Vantage reports

Both used clean start SHA `ed9a920a9ff3aa625764b855249e2a9becc229a9`, public
source mode, the existing Codex STDIO Host and `gpt-6.1-sol`. Cutoff was
2026-11-24 11:30 UTC. Each had one research round, up to five Host web operations
and a 215-second engine-runner budget. The original request/reply traces, full
reports, ledger and timing remain in ignored `runs/phase3-host/`.

| Case | Selection and retained evidence | Status |
| --- | --- | --- |
| Japanese meeting-notes launch research, Expanded, 60 days | `pr_times` appeared in the three suggestions and was the searched Host source. Three original dated issuer publications entered the ledger and appeared as citations; the report preserves vendor attribution and lack of independent testing. | `PARTIAL / evidence_backed_brief / LIMITED`; 215.84 s including runner overhead. [AI Minutes](https://prtimes.jp/main/html/rd/p/000000075.000087427.html) · [ibisScribe](https://prtimes.jp/main/html/rd/p/000000093.000015594.html) · [YOMEL](https://prtimes.jp/main/html/rd/p/000000045.000066814.html) |
| Otter feedback, Hybrid, 180 days | At baseline, G2 and App Store were named by the question, outside the automatic suggestions. Host searched them explicitly. Three G2 review cards were returned with one retained canonical URL in the final report. Apple cards with complete dates were outside this case's window; recent cards without a year were excluded. The surviving G2 item is an uncorroborated weak signal. | `SUCCESS / full_brief / LIMITED`; 168.91 s. [G2 original reviews](https://www.g2.com/products/otter-ai/reviews) · [App Store original reviews](https://apps.apple.com/us/app/otter-transcribe-voice-notes/id1276437113?see-all=reviews) |

Engineering checks: 25 Phase 3 contract/replay checks passed. The full offline
suite reported 2,475 passed and 45 live-by-default skips. Ruff and the
repository and history scan passed.

### Smallest remaining set

1. Verify more named public Host routes in bounded end-to-end runs, starting
   with Capterra/Trustpilot and Korean, Chinese and Brazil-local sources. To
   widen automatic routes, measure real three-target behavior and adjust small
   groups of priorities without starving first-party or local sources.
2. Continue public-original checks where the first result was a shell, missing
   a date or blocked (including X, Bilibili, Xiaohongshu, Weibo, WeChat,
   LinkedIn and ad surfaces). Accept a date and body only when they can be
   bound to the same item. Keep qualification, paid service and account access
   as user actions. A provider restriction remains a missing route.
3. Count any additional connector or MCP only after an authorized, dated
   original item survives the shipped path. The present evidence does not
   reach the 100-platform target.
