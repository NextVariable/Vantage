# last30days source parity (Vantage 1.1, 2026-11-25)

This record compares every research lane implemented by the upstream
`mvanhorn/last30days-skill` project with Vantage's actual routes. It is a
code-level audit, not a README comparison.

## Pinned upstream

| Item | Value |
| --- | --- |
| Repository | <https://github.com/mvanhorn/last30days-skill> |
| Latest release | `v4.6.0`, published 2026-11-22 |
| Release tag object | `a351acba9f99065201b88004321feda120322977` |
| Release commit | `64b1f006f800640022ce07f51de5ce56aad34b76` |
| Audited `main` | `7c2e1c2b099b13abd4397910168c4f53e638bb21` |
| Package version | `4.6.0` (`pyproject.toml`) |

Both the release commit and current main were read. The lane inventory below
comes from `skills/last30days/scripts/lib/*.py` and the dispatch table in
`lib/pipeline.py`; a lane is listed only if code exists for it.

## How to read the matrix

- **lane** — one implemented code path. Several lanes can belong to one
  platform (`x_api`, `bird_x`, `xurl_x`, `xai_x`, `grok_x`, `xquik` are all X).
- **platform** — a deduplicated publishing surface. Search engines, paid answer
  engines, local libraries and cross-platform ATS lanes are not platforms.
- **status** — `verified_direct`, `implemented_credential_required`,
  `implemented_user_authorized`, `implemented_unverified`, `host_only`,
  `unavailable`, `non_platform`.
- Counting rule: a lane is never counted twice, and configuration alone never
  counts as coverage. `host_only` means the platform is reachable only through
  a host web search, and nothing has been proven in this build environment.
  `implemented_*` means adapter code and an offline contract test exist; it is
  not a live-availability claim.

Machine-readable matrix: [last30days-parity.csv](last30days-parity.csv)
(31 lanes).

## Result

| Measure | Value |
| --- | --- |
| Upstream lanes audited | 31 |
| Deduplicated upstream platforms | 24 |
| Aligned with a Vantage connector (free, gated or unverified) | 24 / 24 (100%) |
| Verified by a real round-trip (direct or frozen Host page) | 8 / 24 (33%) |
| — verified direct live | 7 (YouTube, Hacker News, GitHub, arXiv, DEV, Techmeme, USPTO Patents) |
| — verified from a frozen original page | 1 (Trustpilot) |
| Aligned but credential- or authorization-gated | 12 |
| Aligned but unverified without credentials (keyless/CLI) | 4 |
| Upstream platforms still host-only | 0 |
| Vantage verified direct platforms not present upstream | 32 |
| Deduplicated platforms with a direct or live-web route | 39 |
| Deduplicated platforms including named Host replays | 59 |

Aligned and verified upstream platforms: YouTube, Hacker News, GitHub, arXiv,
DEV, Techmeme and USPTO Patents (direct live) plus Trustpilot (frozen original
page through Host search). The three ATS boards (Lever, Greenhouse, Ashby)
implement the upstream `jobs` lane as three independent platforms, are
separately live-verified, and are not counted in the 24-platform figure because
`jobs` is a cross-platform lane.

Credential- or authorization-gated connectors: X (bearer token), TikTok,
Instagram, Threads, Pinterest, LinkedIn, Reddit and YouTube (the
ScrapeCreators key is an optional enrichment; their free routes still run),
Bluesky (app password), Truth Social (account token), Meta Ad Library (approved
token or the provider route), Xiaohongshu (user-authorized local MCP service),
Telegram (provider key plus a channel list) and Amazon (Bright Data CLI plus
key). Keyless connectors implemented but not verified from this network:
Reddit (public RSS 404), StockTwits (403), Polymarket (413) and Digg (CLI
absent). Trustpilot's adapter is implemented, but the local CLI is absent here;
its frozen Host replay is the only verification on record.

Still host-only: none. Every upstream platform now has a code path; an
unreachable endpoint is reported as unavailable rather than silently replaced.

## Status breakdown

| Bucket | Count | Platforms |
| --- | --- | --- |
| Real live round-trip (direct) | 7 | YouTube, Hacker News, GitHub, arXiv, DEV, Techmeme, USPTO Patents |
| Frozen replay (original page) | 1 | Trustpilot |
| Implemented, needs credentials or approval | 12 | X, TikTok, Bluesky, Instagram, Threads, Pinterest, LinkedIn, Truth Social, Meta Ad Library, Xiaohongshu, Telegram, Amazon |
| Implemented, unverified without credentials | 4 | Reddit, StockTwits, Polymarket, Digg |
| Not implemented, host-only | 0 | — |

## What changed in the unified-activation round (2026-11-25)

- **Setup wizard** — `vantage setup` detects environment, keys (names only),
  CLIs and an authorized local MCP service; lists free sources; recommends the
  smallest account set; supports skip-all and free-only; stores a key in the
  Keychain or a 0600 file; and runs an opt-in bounded probe.
- **ScrapeCreators expansion** — one key now reaches Reddit, YouTube, Telegram
  and Meta Ad Library in addition to TikTok, Instagram, Threads, Pinterest and
  LinkedIn (nine platforms). Each endpoint has an offline contract test.
- **New connectors** — Telegram channel posts, Trustpilot local CLI, Amazon
  through the Bright Data CLI, and US patents through the anonymous USPTO
  Public Search session. The patent route returned a dated application inside
  a real research pipe, so it counts as verified direct.
- **Bounded fallback** — free route first; paid route only with a configured
  key, an explicit call budget and no infinite retry; evidence is kept when a
  later route fails; one platform-native id yields one evidence item; the
  actual route is recorded per item and summarised in coverage.
- **Latent source-type fix** — `video`, `pin`, `ad`, `market` and `story` were
  invalid evidence types and would have been dropped by the normaliser. They
  now map to `post`/`page`, so those adapters can contribute evidence.
- **Truthful live status** — Reddit public RSS 404, Polymarket 413 and the
  absent Digg/Trustpilot/Bright Data binaries are recorded as such. No
  simulated data is counted as a live result.

### Earlier parity-closure work

- **Ten parity adapters** — Instagram, Threads, Pinterest, LinkedIn (one
  shared ScrapeCreators adapter with per-platform mapping), Truth Social,
  Meta Ad Library, StockTwits, Polymarket, Digg and Xiaohongshu. Each has an
  offline contract test; none is counted as live without a real round-trip.
- **Hard platform scope in two layers** — the registry/plan layer selects
  only the requested sources (or adds `host_web_search` with a domain
  allowlist for host-only platforms), and the pipeline drops any host row that
  belongs to an excluded platform. `platform_scope_dropped=N` records the
  count.
- **Unknown domains are not platforms** — unmapped hosts render as
  `Web page (host)` and never group into a platform observation.
- **Official exclusion** — "排除官方宣传 / exclude official" now also drops
  `*_official` sources and rows flagged `vendor`, `press_release` or
  `self_published`, not only `official_web`.
- **Only/exclude parsing** — the nearest cue within 30 characters decides the
  direction, so "排除官方宣传，只分析 X" no longer over-restricts the
  exclusion set.
- **Syndication disclosure** — identical title + opening text on two platforms
  is reported as a syndicated copy and is not treated as independent
  corroboration.

## Reuse and licence notes

- No upstream code was copied. The adapters are new implementations of the same
  public endpoints; the ScrapeCreators field names were read from the upstream
  parser to keep the contract compatible.
- Vantage keeps its existing licence headers and does not vendor upstream files
  or fixtures.
- Paid or approval-only routes are code-gated by environment-variable name and
  are never activated by default.

## Acceptance run

[platform-aware-real-run.md](examples/platform-aware-real-run.md) is a real
multi-platform run from the parity round: a DeepSeek reasoning model injected
through the host-neutral interface, live retrieval from GitHub, Hacker News,
DEV, arXiv, Techmeme and YouTube, and cited evidence from three platforms.

[source-activation-run-1.1.md](examples/source-activation-run-1.1.md) is the
2026-11-25 activation run with the same contract plus USPTO patents. It retained
17 items across DEV, GitHub, USPTO and YouTube, rendered platform observations
that quote retrieved text, and recorded arXiv as rate-limited instead of
substituting another route. A second patents-only run retrieved a dated
application through the anonymous USPTO session. Both are model research, not
the scripted rendering sample. The older
[platform-aware-sample.md](examples/platform-aware-sample.md) stays as a
rendering regression only.

## Reproduce

```bash
# Offline contract checks for the new routes
.venv/bin/python -m pytest -q tests/unit/interface/test_platforms.py \
  tests/unit/connectors/test_authorized_sources.py \
  tests/unit/brief/test_platform_observations.py

# Real feed probe (Techmeme)
RUN_LIVE_TESTS=1 .venv/bin/python -m pytest -q -k techmeme tests/live

# TikTok remains skipped without a key; this is intentional
.venv/bin/sourceglint doctor --json | grep -A3 tiktok
```
