# Source failure and fallback playbook

When a platform route fails, do not immediately remove the source and do not
pretend that a web-search snippet is equivalent to direct coverage. Classify
the failure first, then inspect maintained open-source implementations and the
platform's current documentation before choosing one bounded alternate route.

## Decision order

1. Prefer an official API or documented public endpoint.
2. If the API is unavailable but a maintained local tool can read public data,
   use it without importing browser cookies or downloading unrelated content.
3. Use a user-authorized browser, MCP connector, bot, or export only for data
   the user is entitled to access.
4. Treat third-party aggregation APIs as explicit opt-in integrations. Record
   credentials, pricing, data-processing and terms constraints; never silently
   send a query to them.
5. Fall back to domain-restricted public web search. Label the result partial
   because indexing, dates, comments and engagement may be missing.

For a new workaround, confirm that the upstream repository is active, inspect
its source rather than copying README claims, check recent issues for breakage,
and add an offline adapter test plus an opt-in live check. A route becomes
"working" only after a live check succeeds in the current environment.

## Source-specific routes

Use [the access matrix](source-access-matrix.md) for maintained capabilities and
[the source guides](sources/host-web-search.md) for host integration. Route failures
must preserve already retrieved evidence and disclose the missing depth.

Bluesky requires an authorized app-password session and an authenticated AppView.
YouTube uses local `yt-dlp` for public metadata and attempts public captions.
Reddit can use RSS and public archive enrichment, with OAuth as an optional route.
GitHub and Hacker News retrieve bounded discussions and dated comments.
A successful parent search does not establish complete comment coverage.

X, TikTok, Instagram and LinkedIn access depends on the configured route and its
authorization. Catalog entries are not proof of implemented or working access.
Paid providers and browser-cookie access require explicit authorization.

Check the platform's current documentation when diagnosing transport failures.
Use only one bounded alternate route and record the actual source status;
a local readiness check alone cannot establish live availability.

## 1.1 route outcomes

| Route | Failure seen | Bounded behaviour |
| --- | --- | --- |
| Reddit keyless RSS | HTTP 404 | Classified as unavailable; the archive lane still runs and appends a limitation, so other evidence survives. |
| YouTube `yt-dlp` | Exit 1 | Classified separately from timeout and empty transcript; public pages remain the fallback. |
| Steam reviews | 302 to the store home page | Classified as a regional/anti-bot gate; the adapter refuses HTML instead of fabricating reviews. |
| Ashby board | Response above 2 MB | Refused with a size bound; smaller boards are parsed normally. |
| Polymarket | Connection failure | No connector; catalog marked `unavailable`. |
| Named-board / named-series sources | No board, appid, country/indicator, or form filter | `AdapterInvalidResponse` with a precise instruction; nothing is guessed. |
| Publisher RSS without a query parameter | The feed returns its whole channel | Topic terms are filtered locally; items without a title, link or date are skipped. |
| Zenn / note RSS | Feed content did not match the topic | Public site JSON search is used; RSS stays documented as the fallback. |
| Google News RSS | Redirects to a publisher page and cannot supply the original article URL | Not implemented as a structured connector; host search must cite the original page. |
| PR Times `/feed/` | HTTP 404 | Public pages through host search; no connector is claimed. |

A blocked route is recorded once and not retried indefinitely. Credential-gated
sources never fall back to cookies or logged-in scraping; see
[the authorization guide](source-authorization.md).
