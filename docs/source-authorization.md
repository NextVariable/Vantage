# Source authorization guide (Vantage 1.1)

This guide records credential, ownership, and approval requirements for
implemented connectors and potential platform routes.

## Rules the runtime follows

- Credentials are resolved in this order: process environment → private
  `~/.config/vantage/credentials.env` (0600) → macOS Keychain
  (`vantage-<NAME>`). Values are never written to logs, reports, evidence, or
  test output.
- `vantage setup` is the supported way to store a key. It prints names and
  sources only, and its `--probe` step never makes a paid call.
- Vantage never creates accounts, buys plans, tops up balances, enables
  auto-renewal, imports browser cookies, or widens an existing account's
  scopes. A missing credential is reported, not worked around.
- When a credential is absent the source is marked `credential_required` /
  `approval_required`. A declared public-web fallback is usable only when the
  original item can be verified.
- Do not paste a key into a prompt, issue, commit, or config file. Set it in the
  environment or enter it through the wizard’s hidden prompt to save it in the private local file. Existing Keychain entries can still be read.
- Reddit, X, Bluesky and similar platforms forbid cookie scraping and
  logged-in automation. Only the documented OAuth/API path is implemented.

## Checking your setup

```bash
vantage setup                 # inspect, optionally store keys, optionally probe
vantage setup --skip --json   # nothing is changed; machine-readable inventory
vantage setup --free-only     # hide paid suggestions
sourceglint doctor            # human-readable states
sourceglint doctor --json     # machine-readable, names only
```

States you may see:

| State | Meaning |
| --- | --- |
| `DISABLED` | Connector exists but the registry entry is off and no auto-enable condition is met. |
| `MISSING_CREDENTIALS` | Enabled route whose credential variables are unset. |
| `MISSING_TOOL` | A declared local binary (`yt-dlp`, `digg-pp-cli`, `trustpilot-pp-cli`, `brightdata`) is absent. |
| `READY_UNVERIFIED` | Offline checks passed; upstream access is not certified. |
| `HOST_REQUIRED` | Needs a host search/fetch capability or an official-fetch connector. |

A disabled entry is enabled for the current process only when **every** declared
credential is present (or, for a tool-only entry, the binary is on `PATH`).
`VANTAGE_AUTO_ENABLE_KEYED=0` turns that behaviour off and restores a strictly
static registry.

`doctor` is offline. It never makes a network request and never certifies that
an upstream API currently works.

## Credential-gated sources

| Source | Variable(s) | Access notes | Fallback when absent |
| --- | --- | --- | --- |
| X | `X_BEARER_TOKEN` | X API v2 app-only bearer token; current endpoints use metered credits. | Public pages via host search. |
| Bluesky | `BSKY_HANDLE`, `BSKY_APP_PASSWORD` | App password created in the account settings. | Public bsky.app pages. |
| Product Hunt | `PRODUCT_HUNT_TOKEN` | GraphQL API token; commercial use needs Product Hunt approval. | producthunt.com pages. |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` | Anonymous access is heavily rate-limited. | arXiv / OpenAlex / Crossref. |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Optional. Without it the keyless RSS route is used with bounded degradation. | Public archive and post pages. |
| Discord | `DISCORD_BOT_TOKEN` | Bot must be invited; message content is a privileged intent. | None (no public server search). |
| ScrapeCreators | `SCRAPECREATORS_API_KEY` | One key for TikTok, Instagram, Threads, Pinterest, LinkedIn, Reddit, YouTube, Telegram and Meta Ad Library; endpoint availability depends on the plan. | The free routes still run. |
| Telegram | `SCRAPECREATORS_API_KEY`, `TELEGRAM_SOURCES` | Public channel handles only; no user session or chat access. | `t.me` previews via host search. |
| Meta Ad Library | `META_ACCESS_TOKEN` | Coverage varies by ad type and region. | Public ad-library pages. |
| Similarweb | `SIMILARWEB_API_KEY` | Commercial plan. | Public traffic pages. |
| SEMrush | `SEMRUSH_API_KEY` | Commercial plan. | Public pages. |
| Ahrefs | `AHREFS_API_KEY` | Commercial plan. | Public pages. |
| Rakuten | `RAKUTEN_APPLICATION_ID` | Free developer app registration. | rakuten.co.jp pages. |
| App Store Connect | `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID` | Owner-only review API. | Public apps.apple.com pages. |
| Google Play | `GOOGLE_APPLICATION_CREDENTIALS` | Owner-authorized publisher API. | Public play.google.com pages. |
| USPTO patents | none (anonymous public search session) | No key or cookie; one page per database, bounded query set. | `patents.google.com` pages via host search. |
| Amazon | `BRIGHTDATA_API_KEY` + `brightdata` CLI | Paid dataset route; both the binary and an authorization are required. | amazon.com pages via host search. |
| Trustpilot | none; optional `trustpilot-pp-cli` | The adapter only reads a replayable local session and never launches a browser. | Host search of public business pages. |
| EPO OPS | `EPO_OPS_KEY`, `EPO_OPS_SECRET` | Free OPS registration with quota. | epo.org pages. |
| The Lens | `THE_LENS_TOKEN` | Account token. | thelens.org pages. |
| Companies House | `COMPANIES_HOUSE_API_KEY` | Free UK register key. | Public company pages. |
| FRED | `FRED_API_KEY` | Free St. Louis Fed key. | fred.stlouisfed.org pages. |
| Crunchbase | `CRUNCHBASE_API_KEY` | Paid API product. | crunchbase.com pages. |
| IT桔子 | `ITJUZI_API_KEY` | Commercial data service. | itjuzi.com pages. |
| PitchBook | none (enterprise licence) | Requires explicit user approval; no automated access. | Public pages. |
| OpenAlex | `OPENALEX_API_KEY` (optional) | Only unlocks cursor paging / polite pool. Anonymous search works. | Anonymous search. |

## Phase 2: routes that need no credential at all

These were added after a live round-trip and can be used by setting
`GTM_INTELLIGENCE_SOURCES_YAML=config/sources-expanded.yaml` (or by enabling a
single registry entry). No account, key, cookie or paid plan is involved.

| Platform | Route | Published access terms to respect |
| --- | --- | --- |
| PubMed | E-utilities `esearch`/`esummary`, JSON | NCBI asks for ≤3 requests/second without a key and an identifying User-Agent (set: `VantageResearch/1.1`). |
| DOAJ | `doaj.org/api/search/articles` | Public open-access metadata; keep the article link. |
| Zenodo | `zenodo.org/api/records` | Public records; respect the record licence. |
| DataCite | `api.datacite.org/dois` | Public DOI metadata; cite the DOI. |
| Open Library | `openlibrary.org/search.json` | Public bibliographic data; year-only dates are labelled. |
| Internet Archive | `archive.org/advancedsearch.php` | Public item metadata; item dates are archive fields. |
| ClinicalTrials.gov | `api/v2/studies` | Public registry data. |
| Maven Central | `search.maven.org/solrsearch/select` | Public artifact metadata. |
| NuGet | Search + registration endpoints | Public package metadata. |
| RubyGems | `rubygems.org/api/v1` | Public gem metadata. |
| Docker Hub | `hub.docker.com/v2` | Public repository metadata; detail lookups are capped at three per query. |
| App Store | `itunes.apple.com/search` | Public storefront search; reviews only via a public app id. |
| Lemmy | `lemmy.world/api/v3/search` | Public federated posts on that instance. |
| Zenn / note | Site JSON search endpoints | Public article search used by the sites themselves; RSS kept as fallback. |
| ITmedia / SSPAI / Makuake | Official RSS/Atom feeds | Public feeds; topic filtering is local because the feeds expose no query parameter. |

Rate limits are enforced per source by the existing registry (`rate_limit.rpm`)
and `max_queries_per_run`; the default Skill profile still uses six slots.

## Free registration (no payment) — user action required

| Source | Where to apply | What you get | Notes |
| --- | --- | --- | --- |
| Bluesky | <https://bsky.app/settings/app-passwords> | App password | Free. Public AppView search returned 403 from this network. |
| Semantic Scholar | <https://www.semanticscholar.org/product/api#api-key-form> | API key | Free key raises the anonymous rate limit. |
| FRED | <https://fred.stlouisfed.org/docs/api/api_key.html> | API key | Free. |
| USPTO | <https://developer.uspto.gov/api-catalog> | Open Data Portal key | Free. |
| Companies House | <https://developer.company-information.service.gov.uk/> | API key | Free UK register. |
| EPO OPS | <https://developers.epo.org/> | Key + secret | Free tier with quota. |
| Rakuten | <https://webservice.rakuten.co.jp/> | Application id | Free; Japanese marketplace data. |
| Telegram | <https://my.telegram.org> | `api_id` / `api_hash` | Public channels only; no scraping of private chats. |
| Discord | <https://discord.com/developers/applications> | Bot token | Message content is a privileged intent and needs approval. |

## Approval or owner role required

| Source | Application | What is required | Depth if approved |
| --- | --- | --- | --- |
| Product Hunt | <https://www.producthunt.com/v2/oauth/applications> | Access token; permitted uses and commercial approval by case | GraphQL posts and available votes/comments |
| LinkedIn | <https://developer.linkedin.com/product-catalog> | Partner/approval; no public search API | Member/profile data only within approved scopes; no feed scraping |
| G2 | <https://www.g2.com/products/g2-review-api> | Commercial review-API agreement | Review text and ratings |
| Capterra | Gartner Digital Markets partner data | Vendor/partner agreement; no public API | Review text and ratings |
| Trustpilot | <https://developers.trustpilot.com/> | Business-unit authorization for review API | Your own business unit; others via public pages |
| Google Play | <https://developers.google.com/android-publisher> | Owner service account | Your own app's reviews/statistics; competitor data stays public-web |
| App Store Connect | <https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews> | Owner key (issuer id + key id) | Your own app's reviews; competitor reviews need a public app id |
| Amazon Product Advertising API | <https://webservices.amazon.com/paapi5/documentation/> | Affiliate approval + qualifying sales | Product metadata/pricing, not full review text |
| Meta Ad Library | <https://www.facebook.com/ads/library/api/> | Identity/verification | Ads by page, region-dependent |
| TikTok Research API | <https://developers.tiktok.com/products/research-api/> | Research approval | Public video metadata within approved scope |
| X | <https://docs.x.com/x-api/getting-started/pricing> | API access and endpoint-specific credits | Recent search; full archive depends on access |

## Paid data services

| Service | Model | Use |
| --- | --- | --- |
| Similarweb | Subscription | Traffic/audience estimates |
| SEMrush / Ahrefs | Subscription | Search and backlink intelligence |
| Crunchbase | Subscription | Company/funding data |
| PitchBook | Enterprise licence | Private-market data |
| IT桔子 | Commercial API | China startup/funding data |
| The Lens | Institutional/free scholarly tier | Patents and scholarly records |

Prices change frequently and are quoted by the vendor; Vantage does not embed a
price list or start a trial. Confirm the current price and terms on the
provider's page before purchasing.

## Aggregators that cover several platforms at once

One contract can cover many platforms (for example DataForSEO for SERPs, Apify
actors, or social-data vendors such as ScrapeCreators). They are **not**
integrated by default: an aggregator's terms may not permit redistribution of
every platform's content, and several operate by scraping. If you want one,
authorize it explicitly and confirm that the covered platforms allow it. Until
then those platforms stay on the host-web route.

## Configuration steps

1. Obtain access from the provider under its current terms.
2. Export the variable(s) in the process environment, for example
   `export PRODUCT_HUNT_TOKEN=...` in a private shell profile.
3. Re-run `sourceglint doctor` and confirm the state is no longer
   `MISSING_CREDENTIALS`.
4. Enable the registry entry (`enabled: true`) or use
   `config/sources-expanded.yaml`.
5. Run a small live probe. A configured credential is not proof that the
   upstream API still answers with the expected shape.

## What we will not do

- Read browser cookies or local session stores for platform access.
- Bypass rate limits, CAPTCHAs, or regional gates.
- Rotate proxies or retry a blocked route indefinitely.
- Print, log, commit, or transmit a credential value.
- Create accounts, purchase plans, or start paid trials on the user's behalf.

## Phase 3 authorization checklist

Phase 3 only accessed public material, so the confirmed count of authorized
platforms and independent MCP round trips is zero. Available or listed
credentials describe possible routes. This table separates readiness in
Vantage from provider scope; check the current provider terms and prices before
applying. Where account or application details are required, the user obtains
them outside the Skill.

| Platform | Official entry and approval | Payment and resulting depth | Vantage and next check |
| --- | --- | --- | --- |
| X | [Developer Console / pricing](https://docs.x.com/x-api/getting-started/pricing), a project and app-only bearer with access to the relevant search endpoint. | Metered credits with endpoint-specific prices. Recent search and full archive have separate scope. Text and available metrics under the granted window. | Existing connector. Confirm recent, then if permitted full archive with a small one-query sample. |
| Reddit | [Developer platform access](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Developer-Platform-Accessing-Reddit-Data) · [Data API Terms](https://redditinc.com/policies/data-api-terms). Follow the provider approval path for the project and permitted purpose. | Access and commercial use depend on granted terms. A normal account alone cannot certify API access. Approved OAuth access may return dated posts and accessible comments. | Existing conditional OAuth. Test only after approval; compare separately to RSS 404 and partial archive. |
| Bluesky | [App password settings](https://bsky.app/settings/app-passwords) for an account. | Free account and revocable app password; AppView search and public post metadata. | Existing connector. Verify known post and dates; use a small approved query. |
| Semantic Scholar | [API key application](https://www.semanticscholar.org/product/api#api-key-form). | Free key subject to provider acceptance and limits; paper metadata and available abstract/citation fields. | Existing connector. Check one dated query and 429 handling. |
| YouTube | [Data API quota](https://developers.google.com/youtube/data/determine_quota_cost) · [search](https://developers.google.com/youtube/v3/docs/search/list). Cloud project with Data API enabled and an appropriate key. | Quota-limited official search and eligible public comments. Caption access depends on resource and method authorization. | Current CLI is verified for metadata and needs no user action. Official API needs integration and a separate dated search/comment test. |
| Product Hunt | [OAuth applications](https://www.producthunt.com/v2/oauth/applications) · [API terms](https://api.producthunt.com/v2/docs). Request appropriate scope; obtain business-use approval where needed. | Token, platform limits and commercial permission. Launch feed and available vote/comment fields. | Existing GraphQL connector. Probe recent named launch and preserve feed coverage limitation. |
| LinkedIn | [Posts API](https://learn.microsoft.com/linkedin/marketing/community-management/shares/posts-api) · [developer products](https://developer.linkedin.com/product-catalog). Product access and organization roles or approved scope. | Access depends on product and agreement; authorized Posts API covers scoped organization/person data. | Catalog only. After approval, first confirm selected organization and scope, then implement a bounded original-post check. |
| G2 / Capterra | [G2 Review API](https://www.g2.com/products/g2-review-api) · [Gartner Digital Markets](https://www.gartner.com/en/digital-markets). Request a vendor agreement or approved partner access. | Commercial licence/quote; review text and ratings only within the contract. | Both public web samples verified. No dedicated licensed connector. Require a permitted review plus its ID/date before integration. |
| Trustpilot | [Trustpilot developer portal](https://developers.trustpilot.com/), OAuth and applicable business unit/API product. | Scope and cost depend on the API plan. Public sample contains one dated review; account approval does not grant competitor review exports. | Public web verified, API catalog only. Check one approved business unit after confirming the plan. |
| App Store and Google Play | [App Store Connect reviews](https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews) · [Google Play reviews](https://developers.google.com/android-publisher/api-ref/rest/v3/reviews). Appropriate owner or administrator role and application identity. | Owner-scoped review data and separate developer-account requirements. Public sample accessible without granting those permissions. | App Store iTunes Search connector plus public reviews; Play public web verified. No owner-authorized runtime acceptance. Verify only a controlled app. |
| TikTok / Instagram | [TikTok Research API](https://developers.tiktok.com/products/research-api/) · [Instagram API](https://developers.facebook.com/docs/instagram-platform/). TikTok Research is approval/eligibility restricted. Instagram requires app review, account type and scopes for the chosen surface. | Accounts alone do not unlock general search; data depth depends on approved purpose and endpoint. | No verified dedicated connector. Confirm eligible use and one dated accessible item before work. |
| Google Trends / Ads / Meta / TikTok ads | [Trends Alpha](https://developers.google.com/search/apis/trends) · [Google Ads Transparency](https://support.google.com/adspolicy/answer/13733850) · [Meta Ad Library API](https://www.facebook.com/ads/library/api/) · [TikTok Creative Center](https://ads.tiktok.com/business/creativecenter/). Terms and regions differ. | Public UIs and approval-scoped data products; pricing and eligibility depend on access route. Date range, advertiser and visible metrics must be independently captured. | Catalog only. The public probes did not verify a dated series or individual ad. |
| 小红书、知乎、哔哩哔哩、微博、微信公众号、即刻 | Use public original pages or a platform-approved business/developer interface whose scope actually includes the requested objects. | A normal account does not establish research/API rights. No paid or login route was verified. | No authorized connector. Attempt a public original permalink with full date and text, or document the blocked route. |

After obtaining user-approved access, configure the secret in the runtime
environment, enable only the relevant registry entry, and run a single
nonempty query or named-object probe. Record scope, date bounds, canonical URL,
which fields were observed, and whether a matching public observation reached
the ledger and report. If the provider denies access or requires new payment,
leave the route unverified. The Skill does not ask for cookies or credential
values in chat.

## last30days parity channels (added 2026-11-25)

These are the remaining upstream routes that are not yet verified in Vantage.
Each entry states the exact gate to clear before a connector can be claimed.

| Channel | Application / entry | Gate | What Vantage can return after approval | Current state |
| --- | --- | --- | --- | --- |
| TikTok (ScrapeCreators) | <https://scrapecreators.com/> → sign up → API key | Paid plan; a small free credit allowance is normally offered | Keyword search, video description, author, publish time, views/likes/comments/shares; optional transcript costs extra credits | Adapter implemented; `SCRAPECREATORS_API_KEY` unset, so `MISSING_CREDENTIALS` |
| Instagram | Meta app review + Instagram Graph API, or the same ScrapeCreators key for reels search | App review, professional account, scoped permissions; ScrapeCreators is paid | Reels/posts metadata and comments within the approved surface | Adapter implemented (`third_party_api`); `SCRAPECREATORS_API_KEY` unset |
| Threads | Meta Threads API, or ScrapeCreators | App review/scopes or paid key | Keyword posts and engagement | Adapter implemented; `SCRAPECREATORS_API_KEY` unset |
| Pinterest | ScrapeCreators (no free public search API) | Paid key | Keyword pins, engagement; undated items are dropped rather than fabricated | Adapter implemented; `SCRAPECREATORS_API_KEY` unset |
| LinkedIn | <https://developer.linkedin.com/product-catalog> or ScrapeCreators | Partner/product approval; no public search API | Organization/member posts within approved scopes | Adapter implemented (`third_party_api`); key unset |
| X | <https://developer.x.com/en/portal/dashboard> | Paid API tier | Recent/full-archive search, engagement | Connector present; `X_BEARER_TOKEN` unset |
| Reddit | <https://www.reddit.com/prefs/apps> (script app) | Free OAuth registration | Dated posts and accessible comments | Connector present; OAuth env vars unset, keyless route failed |
| Bluesky | <https://bsky.app/settings/app-passwords> | Free app password | Search posts and engagement | Connector present; `BSKY_HANDLE`/`BSKY_APP_PASSWORD` unset |
| Truth Social | <https://truthsocial.com> account → developer/API token, or public pages | Account bearer token; Vantage will not import browser sessions | Public statuses and engagement | Adapter implemented; `TRUTHSOCIAL_TOKEN` unset |
| Telegram | ScrapeCreators channel-posts endpoint plus a channel list | `SCRAPECREATORS_API_KEY` and `TELEGRAM_SOURCES` | Dated channel posts, views, forwards | Adapter implemented; both variables unset (paid) |
| Digg | `digg-pp-cli` from the printing-press CLI set | Local binary | Stories and dates | Adapter implemented; binary absent, reported `MISSING_TOOL` |
| StockTwits | <https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json> | None, but a ticker is required; public API returned 403 from this network | Symbol messages and engagement | Adapter implemented; not verified |
| Patents (USPTO) | Public Patent Public Search session | None (anonymous) | Dated applications, title, applicant, PDF | Verified live 2026-11-25 |
| Amazon | Bright Data CLI + dataset | Paid credits and an installed `brightdata` binary | Product metadata; review text depends on the dataset | Adapter implemented; binary and key absent |
| Meta Ad Library | <https://www.facebook.com/ads/library/api/> | Identity verification and access token, or the provider fallback | Ads by page and region | Adapter implemented; `META_ACCESS_TOKEN` unset |
| Yahoo Finance | Public quote/news endpoints | None for public pages; RSS was rate-limited in the probe | Quotes/news as enrichment, not a search platform | Not a source; artifact only |
| Perplexity / Deepline | Provider paid API | Paid key | Answer/enrichment, not independent evidence | Not a platform; excluded from counts |
| Xiaohongshu | A local MCP service plus a user-authorized session, or public pages | Local service and explicit user authorization | Notes, comments, engagement | Adapter implemented (`mcp`); `XHS_MCP_URL` unset, refuses when not logged in |
| Trustpilot | `trustpilot-pp-cli` or <https://developers.trustpilot.com/> | Local CLI session (Vantage never runs the browser login) or business-unit approval | Dated reviews | Adapter implemented (local reads only); binary absent; one frozen page replay on record |

### Minimum authorization list

| Category | Channels | Connector done? | Expected depth | Verification command |
| --- | --- | --- | --- | --- |
| Zero configuration | YouTube (`yt-dlp`), Reddit public/archive, Patents (USPTO), GitHub, Hacker News, arXiv, DEV, Techmeme, Digg CLI when installed, Trustpilot CLI when installed | Yes | Metadata, dates, captions/reviews where available | `vantage setup --probe` |
| One account, free | Bluesky (app password), Truth Social (account token), Reddit OAuth app | Yes | Dated posts, author, some engagement | `vantage setup`, then one small query |
| Free API key | Semantic Scholar; USPTO ODP is no longer required for the anonymous route | Yes | Metadata and dates | `RUN_LIVE_TESTS=1 .venv/bin/python -m pytest -q -k "semantic or patents" tests/live` |
| User-authorized MCP | Xiaohongshu | Yes | Notes and engagement | `XHS_MCP_URL=... vantage setup --probe` |
| Platform approval | Meta Ad Library, LinkedIn partner product, Instagram/Threads Graph API, Trustpilot business unit | Yes | Approved-surface posts/ads/reviews | Approval first; then one named-object probe |
| Paid | ScrapeCreators (9 platforms), X API tier, Amazon via Bright Data | Yes | Keyword search with engagement; Amazon product pages | `vantage setup`, then `vantage setup --probe` (the probe does not spend) |
| Single vendor, many platforms | ScrapeCreators covers TikTok, Instagram, Threads, Pinterest, LinkedIn, Reddit, YouTube, Telegram and Meta Ad Library with one key | Yes, one shared adapter | Same depth per platform, subject to plan quota | Configure one key; verify each platform separately |

The shortest list that only you can perform:

1. Create a ScrapeCreators account and paste its key into `vantage setup` (skip
   this to stay free).
2. If you want X: create/upgrade an X developer project and paste its bearer
   token.
3. If you want Bluesky or Truth Social: create an app password/account token
   and paste it into `vantage setup`.
4. If you want Amazon: install the Bright Data CLI and authorize that account.
5. If you want Meta Ad Library: complete Meta's identity verification.

Everything else either works already, is downloaded by the package manager
(`yt-dlp`), or is a local session you create once with the vendor CLI
(`trustpilot-pp-cli auth login`).

No connector is registered, purchased, recharged, or cookie-imported here.
Everything above is an external authorization decision for the operator.

To enable any implemented gated route:

```bash
vantage setup                                    # prefer this: detects and stores keys
export SCRAPECREATORS_API_KEY=...                # nine platforms, subject to your plan
export TELEGRAM_SOURCES=buildernews,ainews        # required by the Telegram route
export TRUTHSOCIAL_TOKEN=...
export META_ACCESS_TOKEN=...
export BRIGHTDATA_API_KEY=...                    # Amazon; the CLI must also be installed
export XHS_MCP_URL=http://127.0.0.1:...          # Xiaohongshu local service, must be logged in
.venv/bin/sourceglint doctor --json | grep -A2 '"source": "instagram"'
```

Budget and fallback controls:

| Variable | Default | Effect |
| --- | --- | --- |
| `--paid-source-calls N` / API `paid_source_calls=N` | `0` | Shared per-run limit on metered HTTP attempts, including failures and retries. Only opt in after the user authorizes the provider and credit use. |
| `VANTAGE_PAID_FALLBACK_CALLS` | `10` | Additional legacy ceiling per fallback adapter; it does not grant metered access. |
| `VANTAGE_DISABLE_PAID_FALLBACK` | unset | `1`/`true` makes the engine use only free routes even when a key exists. |
| `VANTAGE_AUTO_ENABLE_KEYED` | `1` | `0` stops credentials from activating disabled registry entries. |

A configured key is not a verification. Run one small query and check that
dated items with original URLs reach the ledger before marking the route
verified.

