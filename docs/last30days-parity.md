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
| Aligned with a Vantage connector (free, gated or unverified) | 20 / 24 (83%) |
| Verified by a real round-trip (direct or frozen Host page) | 7 / 24 (29%) |
| — verified direct live | 6 (YouTube, Hacker News, GitHub, arXiv, DEV, Techmeme) |
| — verified from a frozen original page | 1 (Trustpilot) |
| Aligned but credential- or authorization-gated | 10 |
| Aligned but unverified without credentials (keyless/CLI) | 4 |
| Upstream platforms still host-only | 4 (Trustpilot, Amazon, Telegram, Patents) |
| Vantage verified direct platforms not present upstream | 32 |
| Deduplicated platforms with a direct or live-web route | 39 |
| Deduplicated platforms including named Host replays | 59 |

Aligned and verified upstream platforms: YouTube, Hacker News, GitHub, arXiv,
DEV, Techmeme (direct live) and Trustpilot (frozen original page through Host
search). The three ATS boards (Lever, Greenhouse, Ashby) implement the upstream
`jobs` lane as three independent platforms, are separately live-verified, and
are not counted in the 24-platform figure because `jobs` is a cross-platform
lane.

Credential- or authorization-gated connectors implemented this round:
Instagram, Threads, Pinterest, LinkedIn (ScrapeCreators key), Truth Social
(account token), Meta Ad Library (approved token) and Xiaohongshu
(user-authorized local MCP service). Keyless connectors implemented but not
verified from this network: StockTwits (403), Polymarket (timeout) and Digg
(CLI absent). Reddit stays connector-implemented and unverified.

Still host-only: Trustpilot (frozen page replay only), Amazon (no free
product/review API), Telegram (needs a paid key and channel scope) and Patents
(legacy PatentsView retired; USPTO ODP requires a key). Reasons are in the CSV
and in the authorization guide.

## Status breakdown

| Bucket | Count | Platforms |
| --- | --- | --- |
| Real live round-trip (direct) | 6 | YouTube, Hacker News, GitHub, arXiv, DEV, Techmeme |
| Frozen replay (original page) | 1 | Trustpilot |
| Implemented, needs credentials | 10 | X, TikTok, Bluesky, Instagram, Threads, Pinterest, LinkedIn, Truth Social, Meta Ad Library, Xiaohongshu |
| Implemented, unverified without credentials | 4 | Reddit, StockTwits, Polymarket, Digg |
| Not implemented, host-only | 3 | Amazon, Telegram, Patents |

## What changed in this round

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

[platform-aware-real-run.md](examples/platform-aware-real-run.md) is one real
multi-platform run: a DeepSeek reasoning model injected through the host-neutral
interface, live retrieval from GitHub, Hacker News, DEV, arXiv, Techmeme and
YouTube, and cited evidence from three platforms. It is model research, not the
scripted rendering sample. The older
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
