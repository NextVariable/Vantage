# Source authorization guide (Vantage 1.1)

This guide lists every source that needs a credential, an owner role, or an
explicit approval before a direct connector can return data. It exists so a
user can enable those routes deliberately.

## Rules the runtime follows

- Credentials are read **by environment-variable name** inside the adapter
  factory. Values are never written to logs, reports, evidence, or test output.
- Vantage never creates accounts, buys plans, tops up balances, or enables a
  paid API automatically. A missing credential is reported, not worked around.
- When a credential is absent the source is marked `credential_required` /
  `approval_required` and the public-web route stays available.
- Do not paste a key into a prompt, issue, commit, or config file. Set it in the
  environment of the process that runs Vantage.
- Reddit, X, Bluesky and similar platforms forbid cookie scraping and
  logged-in automation. Only the documented OAuth/API path is implemented.

## Checking your setup

```bash
sourceglint doctor            # human-readable states
sourceglint doctor --json     # machine-readable, names only
```

States you may see:

| State | Meaning |
| --- | --- |
| `DISABLED` | Connector exists but the registry entry is off (the 1.1 default). |
| `MISSING_CREDENTIALS` | Enabled route whose credential variables are unset. |
| `MISSING_TOOL` | A local binary (currently `yt-dlp`) is not installed. |
| `READY_UNVERIFIED` | Offline checks passed; upstream access is not certified. |
| `HOST_REQUIRED` | Needs a host search/fetch capability or an official-fetch connector. |

`doctor` is offline. It never makes a network request and never certifies that
an upstream API currently works.

## Credential-gated sources

| Source | Variable(s) | Access notes | Fallback when absent |
| --- | --- | --- | --- |
| X | `X_BEARER_TOKEN` | X API v2 app-only bearer token; paid tiers apply. | Public pages via host search. |
| Bluesky | `BSKY_HANDLE`, `BSKY_APP_PASSWORD` | App password created in the account settings. | Public bsky.app pages. |
| Product Hunt | `PRODUCT_HUNT_TOKEN` | GraphQL API token; commercial use needs Product Hunt approval. | producthunt.com pages. |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` | Anonymous access is heavily rate-limited. | arXiv / OpenAlex / Crossref. |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Optional. Without it the keyless RSS route is used with bounded degradation. | Public archive and post pages. |
| Discord | `DISCORD_BOT_TOKEN` | Bot must be invited; message content is a privileged intent. | None (no public server search). |
| Telegram | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Public channels or user-authorized chats only. | t.me previews. |
| Meta Ad Library | `META_ACCESS_TOKEN` | Coverage varies by ad type and region. | Public ad-library pages. |
| Similarweb | `SIMILARWEB_API_KEY` | Commercial plan. | Public traffic pages. |
| SEMrush | `SEMRUSH_API_KEY` | Commercial plan. | Public pages. |
| Ahrefs | `AHREFS_API_KEY` | Commercial plan. | Public pages. |
| Rakuten | `RAKUTEN_APPLICATION_ID` | Free developer app registration. | rakuten.co.jp pages. |
| App Store Connect | `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID` | Owner-only review API. | Public apps.apple.com pages. |
| Google Play | `GOOGLE_APPLICATION_CREDENTIALS` | Owner-authorized publisher API. | Public play.google.com pages. |
| USPTO | `USPTO_API_KEY` | Open Data Portal key. | patents.google.com / uspto.gov pages. |
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
| Reddit | <https://www.reddit.com/prefs/apps> (script app) | OAuth client id/secret | Free. Keyless RSS often 404s; OAuth is the durable route. |
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
| Product Hunt | <https://www.producthunt.com/v2/oauth/applications> | App review before a token is issued | GraphQL posts, votes, comments |
| LinkedIn | <https://developer.linkedin.com/product-catalog> | Partner/approval; no public search API | Member/profile data only within approved scopes; no feed scraping |
| G2 | <https://www.g2.com/products/g2-review-api> | Commercial review-API agreement | Review text and ratings |
| Capterra | Gartner Digital Markets partner data | Vendor/partner agreement; no public API | Review text and ratings |
| Trustpilot | <https://developers.trustpilot.com/> | Business-unit authorization for review API | Your own business unit; others via public pages |
| Google Play | <https://developers.google.com/android-publisher> | Owner service account | Your own app's reviews/statistics; competitor data stays public-web |
| App Store Connect | <https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews> | Owner key (issuer id + key id) | Your own app's reviews; competitor reviews need a public app id |
| Amazon Product Advertising API | <https://webservices.amazon.com/paapi5/documentation/> | Affiliate approval + qualifying sales | Product metadata/pricing, not full review text |
| Meta Ad Library | <https://www.facebook.com/ads/library/api/> | Identity/verification | Ads by page, region-dependent |
| TikTok Research API | <https://developers.tiktok.com/products/research-api/> | Research approval | Public video metadata within approved scope |
| X | <https://developer.x.com/en/portal/dashboard> | Paid API tier | Recent search; full archive by plan |

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
