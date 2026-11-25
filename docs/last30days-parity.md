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
  `implemented_unverified`, `host_only`, `unavailable`, `non_platform`.
- Counting rule: a lane is never counted twice, and configuration alone never
  counts as coverage. `host_only` means the platform is reachable only through
  a host web search, and nothing has been proven in this build environment.

Machine-readable matrix: [last30days-parity.csv](last30days-parity.csv)
(31 lanes).

## Result

| Measure | Value |
| --- | --- |
| Upstream lanes audited | 31 |
| Deduplicated upstream platforms | 24 |
| Aligned with a Vantage connector (free, gated or unverified) | 10 / 24 (42%) |
| Verified by a real round-trip (direct or frozen Host page) | 7 / 24 (29%) |
| Upstream platforms still host-only without verification | 12 |
| Upstream platforms unreachable from this network | 1 (Polymarket) |
| Vantage verified direct platforms not present upstream | 32 |
| Deduplicated platforms with a direct or live-web route | 39 |
| Deduplicated platforms including named Host replays | 59 |

Aligned and verified upstream platforms: YouTube, Hacker News, GitHub, arXiv,
DEV, Techmeme (direct) and Trustpilot (frozen original page through Host
search). Aligned but credential-gated or unverified: X, Reddit, Bluesky,
TikTok. The three ATS boards (Lever, Greenhouse, Ashby) implement the upstream
`jobs` lane as three independent platforms and are separately live-verified.

Still host-only or blocked: Instagram, Threads, Pinterest, LinkedIn,
Xiaohongshu, Truth Social, Telegram, Digg, Amazon, Meta Ad Library, StockTwits,
Patents. Reasons are in the CSV and in the authorization guide.

## What changed in this round

- **Techmeme** — public `techmeme.com/feed.xml` parsed through the shared feed
  adapter. Real items with links and `pubDate` were returned on 2026-11-25.
  Only the current feed window is searchable; it is not an archive search.
- **TikTok** — ScrapeCreators keyword adapter implemented behind
  `SCRAPECREATORS_API_KEY` (paid, small free credit allowance). No key means it
  is reported as `MISSING_CREDENTIALS`, never as verified. Offline contract test
  uses the upstream field shape; no live claim is made.
- **Platform attribution** — citations now print the original platform and the
  retrieval route when they differ (`Reddit via host_web_search`). All citations
  for mapped domains use the platform label.
- **Platform observations** — the brief gains a supplementary section grouped by
  original platform, only when at least two platforms contributed cited
  evidence. It never pads empty platforms.
- **Platform routing** — explicit "only Reddit and GitHub" / "exclude X" and
  `--platform` / `--exclude-platform` produce a hard source scope; ordinary
  mentions ("focus on X, Reddit and GitHub") stay soft planner preferences.
- **Official-evidence exclusion** — "排除官方宣传 / exclude official" drops
  `official_web` and host pages flagged official before normalization and
  records `official_evidence_excluded=N`.
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
