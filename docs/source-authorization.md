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
