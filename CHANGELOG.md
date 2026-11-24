# Changelog

Python 3.10 compatibility is exercised by the public CI matrix; recommendation ID construction avoids syntax that requires Python 3.12.

## Unreleased — 1.1 global source expansion

Development branch only; no 1.1 release or tag.

- Add credential-free direct connectors for Crossref, OpenAlex, PyPI,
  Crates.io, GitLab, Lever, Greenhouse, Ashby, World Bank and SEC EDGAR,
  behind new registry slots that are disabled by default.
- Add `config/sources-expanded.yaml`: an opt-in profile that enables the free
  routes at one query per source so default research cost is unchanged.
- Correct publish semantics: Stack Overflow and DEV keep edit/activity fields
  separate; Hugging Face uses `createdAt` rather than `lastModified`; npm reads
  the registry per-version time instead of the search index date; arXiv uses the
  first submission and de-duplicates versions.
- Classify Reddit RSS 404 as bounded unavailability and keep the archive lane;
  separate YouTube metadata, transcript-request and transcript-status fields;
  add a Steam review adapter that refuses HTML redirect gates.
- Bound Ashby boards at 2 MB and map Greenhouse `first_published` separately
  from `updated_at`.
- Record 149 research candidates in `docs/source-expansion-1.1.csv` with honest
  states; register 134 distinct platforms while counting only verified routes as
  coverage.
- Add `docs/source-authorization.md`, `docs/source-expansion-1.1.md` and
  profile-schema tests. No secret value is read, logged, or committed.
- Add eighteen further key-free connectors after a live round-trip: PubMed,
  DOAJ, Zenodo, DataCite, Open Library, Internet Archive, ClinicalTrials.gov,
  Maven Central, NuGet, RubyGems, Docker Hub, App Store (iTunes Search), Lemmy,
  Zenn, note, ITmedia, SSPAI and Makuake. Each returns an original URL, a
  labelled publication anchor and a source-native id; no archive feed is
  counted as live coverage.
- Add shared RSS/Atom parsing and a bounded local topic filter for publisher
  feeds that expose no query parameter; add Zenn and note public search
  endpoints with RSS documented as fallback.
- Add coarse-date and fallback labelling (`date_precision`, `date_semantics`)
  for registries that only publish a year or a version time; cap detail
  lookups at three per query for NuGet, RubyGems and Docker Hub.
- Add `docs/host-web-verification-tasks.json`: 65 machine-readable host-search
  tasks (`status: pending_host`) covering catalog rows with no structured
  endpoint. None is counted as verified coverage.
- Extend `docs/source-authorization.md` with credential-free routes, free
  registration entries, approval/owner requirements and paid services, with
  application links and expected data depth.

## 1.0.0b1 — beta

- Add request/response correlation to the default STDIO host. Timed-out replies
  are skipped by `request_id`, later analysis continues on the same stream, and
  legacy hosts that cannot echo an id fail closed instead of reusing the stream.
- Verify every FACT against a verbatim excerpt from its cited evidence. Reject
  unrelated ids, paraphrased or stitched quotes, and vendor material presented
  as independent testing; only the separate semantic stage may mark a fact
  `verified`.
- Exclude unassessed semantic factors from the score and renormalise the
  remaining weights, so a skipped relevance check is not scored as zero. Report
  score completeness, coverage and missing reasons. Compare mixed signals on
  the same assessed factor set while retaining per-signal relevance for weak-signal decisions.
- Record commit SHA, working-tree state, budgets, host type, evidence hash, call
  accounting and token split per real run; mark dirty checkouts as diagnostics.
- Replay frozen evidence ledgers side by side with the previous citation-id-only
  gate. Frozen replay is regression evidence, not a new research result.

## 1.0.0.dev1 — development

- Define and validate the Host source reply contract and record search outcomes per query.
- Keep citation URLs free of embedded credentials and allow per-question source fallback.
- Add public-source-only execution, a Japanese hybrid route, a real Host benchmark and a cross-platform wheel install check.
- Reject unrelated Reddit archive communities inferred from migration queries.
- Report a partial result when explicitly requested opportunity analysis is unavailable.

- Add the `vantage` CLI and inclusive UTC date ranges. Keep `sourceglint`
  imports and the legacy command.
- Extend research plans with multiple focus areas, hypotheses, open conditions,
  budgets and stop rules. Allow a third round only after assessed progress.
- Apply cooperative deadlines to the built-in HTTP, subprocess and host
  transport. Keep usable earlier evidence when a later assessment fails.
- Separate vendor claims, user reports and contrary observations in briefs.
  Restrict synthesis to assessed evidence and retain the full retrieval ledger.
- Expand explicit opportunity hypotheses with alternatives, assumptions, risks
  and disconfirming tests. Extend live evaluation to 20 paired research cases.

## 0.2.2.dev5 — unreleased

- Read relative time windows written next to more Chinese or Japanese text
  (过去3个月的变化, 直近14日の動向); they previously fell back to 30 days.
- Compare the real host of a URL, not the text before `@`, when deciding whether
  it is an official domain.
- Report a skipped Reddit archive search when a non-Latin query yields no
  community name, instead of returning with no explanation.
- Load `--model path/to/file.py`; the file form raised `UnboundLocalError`.
- Accept a brief input with no context, and give the YouTube adapter an explicit
  `bounds` default.

## 0.2.2.dev4 — 2026-10-05

- Validate cited publication dates as dates without treating their digits as supported percentages.


- Send Reddit application authentication as an actual form-encoded POST;
  keep concurrent HTTP timeouts local to each request.
- Remove unreachable retry handling, duplicate registry work and stale imports;
  repair runtime type annotations without moving public entry points.
- Add source/script lint and Skill metadata, documentation-link and repository
  hygiene checks to both supported Python CI jobs.
- Add a reusable twelve-topic public comparison matrix with source fingerprints,
  language hints, isolated credentials and explicit comparison boundaries.
- Reorganize both READMEs around first use; retain dated evaluations behind a
  validation index and document ambiguous-product query handling.

## 0.2.2.dev3 — 2026-10-05

- Retain correctly scoped GitHub issues for resolved repository aliases and
  carry repository context into independently dated child comments.
- Balance bounded HN story/comment searches, retain original research intent
  during selection, exclude canonical hiring threads unless hiring is requested,
  and disclose failed lanes without dropping the surviving lane.
- Accumulate limits across query variants and expose native-source warnings in
  final coverage; disclose cached retrieval and avoid caching incomplete or host
  results without their coverage diagnostics.
- Correct hybrid evaluation routing.

- Check the complete Reddit topic with Latin word boundaries, CJK matching,
  hyphen/plural handling and local co-occurrence; retain semantic intent review.
- Preserve two-character topic terms in verbatim excerpts, including Chinese,
  Japanese and AI, and retain original Unicode topic spelling for matching;
  iterate only the bounded candidate match count.

- Keep failed contradiction assessments explicitly unassessed; exclude those
  signals from fact generation and preserve empty support partitions.
- Enrich duplicate evidence with compatible source bodies while preserving
  identity, publication dates, quotes and retrieval provenance; register aliases.
- Apply copied-text origin suppression consistently to signal and insight support.
- Select bounded verbatim head/topic/tail excerpts with Unicode-safe offsets;
  fingerprint model inputs so body enrichment invalidates cached analyses.
- Try alternative public caption tracks within a four-attempt budget, retaining
  failure diagnostics and avoiding malformed tracks.

## 0.2.2.dev2 — 2026-10-05

- Use relevance-ranked Reddit RSS discovery, resolve public community names,
  prioritize exact observed communities, reject unrelated prefix collisions
  using public descriptions and deduplicate names without case sensitivity.
- Retrieve Reddit archive candidates in four time strata and retain available
  strata and distinct publication days during selection; report missing coverage
  instead of implying a full month.
- Fall back from archive HTTP 422 keyword-search failures to bounded community
  samples, preserve incomplete-source warnings and bound enrichment retries.
- Check visible HN subject text with limited overfetch; preserve actual story
  text when the provider supplies it, alongside comment evidence.
- Add selectable topics/routes and parent-date metrics to the live comparison runner.

## Unreleased — 2026-10-04

- Pass the original research topic into semantic analysis in general mode;
  bound batch body inputs and mark omitted passages explicitly.
- Read bounded source bodies in semantic analysis rather than only the first
  280 characters; preserve the short quote contract and unabridged raw export.
- Add GitHub issues/PRs, independently dated comments and recent replies in
  older threads; preserve comment anchors and classify community claims as T2.
- Add public Reddit archive discovery and dated comment evidence, with explicit
  archive provenance and filtering of unrelated feed entries and moderator bots.
- Read recent YouTube timed captions without downloading media or cookies.
- Make the maintained Skill workflow use bounded native retrieval plus host
  supplements instead of leaving deep connectors outside the first-run path.

- Clarify the research-first installation and workflow; add host metadata and
  move protocol details into progressively loaded references.
- Archive historical designs and obsolete manual review gates without deleting
  their content; document current runtime ownership.
- Add installed `sourceglint doctor`, separating offline readiness and dated
  live checks, and eliminate the duplicate diagnostics implementation.
- Query recent HN stories and comments with upstream date bounds, preserve
  original comment URLs and raw markup, and render readable text.
- Date-bound GitHub repository searches; classify them as pages and retain
  forks as provider metadata instead of falsely reporting comments.
- Prioritize the literal topic before broad query expansions.
- Persist normalized evidence and a separate unvalidated raw-source archive
  with `--ledger`, reject reused nonempty run files, and show
  cited excerpts before unselected observations.

## 0.2.1 — 2026-10-04

- Retain direct-source public-search fallbacks in the host-only first-run path;
  a catalog entry marked ready no longer means it was queried in this run.
- Report original platforms, publication dates, actual host searches, missing
  aspects and small-sample limitations separately from pipeline completion.
- Preserve verbatim source excerpts in discovery reports, including observations
  that were not selected as headline facts.
- Include runtime configuration, schemas and model prompts in wheel/sdist
  distributions and resolve them from the installed package.
- Add MIT licensing, contribution guidance, installed-package checks and CI.

This is an early research Skill. Source breadth is partial, report completeness
is not certified automatically, and prior-window trend retrieval is unavailable.
