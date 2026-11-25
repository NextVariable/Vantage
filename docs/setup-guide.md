# Vantage setup guide (1.1)

`vantage setup` is the single configuration entry point. It is deliberately
small: detect what already works, recommend the smallest account set, store an
optional key safely, and optionally run a bounded live check. It never registers
an account, buys a plan, recharges a balance, enables auto-renewal, reads browser
cookies, or widens an existing account's permissions.

## Modes

```bash
vantage setup                  # interactive: detect, recommend, optionally store keys
vantage setup --skip           # print the inventory and change nothing
vantage setup --free-only      # hide paid suggestions
vantage setup --json           # machine-readable; names only, never values
vantage setup --probe          # bounded live check (no paid calls)
vantage setup --no-keychain    # store in a 0600 file instead of the Keychain
```

Interactive mode is used only when stdin and stdout are terminals. Use
`--json` or `--non-interactive` in automation.

## What it detects

| Area | Details |
| --- | --- |
| Environment | OS, Python, package version, config directory and whether it is writable, Keychain availability |
| Credentials | Every supported name, whether it is present, and whether it came from the environment, the private file or the Keychain. Values are never printed. |
| Local CLIs | `yt-dlp`, `gh`, `digg-pp-cli`, `trustpilot-pp-cli`, `brightdata`, plus `node`/`npx` for the npm tools |
| Authorized services | A GitHub CLI login (reused read-only) and a local Xiaohongshu MCP login endpoint |
| Free sources | Enabled entries that declare no credential and cost nothing |
| Recommendation | Tier 0 (do nothing), tier 1 (one ScrapeCreators key), tier 2 (free tools/tokens), tier 3 (approval or paid) |

## Where a key is stored

Resolution order, first hit wins:

1. process environment variable (unchanged, cross-platform, backwards compatible);
2. `~/.config/vantage/credentials.env` (or `$VANTAGE_CONFIG_DIR`, `%APPDATA%` on
   Windows), written with mode 0600;
3. macOS Keychain item `vantage-<NAME>`.

`vantage setup` prefers the Keychain on macOS and falls back to the private file.
It never prints the value, and the doctor only reports the credential **name**
and its source.

## Recommended minimum

| Tier | Action | Unlocks | Cost |
| --- | --- | --- | --- |
| 0 | Nothing | YouTube (`yt-dlp`), Reddit public/archive, GitHub, Hacker News, arXiv, DEV, Techmeme, USPTO patents, plus Digg/Trustpilot CLIs when installed | free |
| 1 | One `SCRAPECREATORS_API_KEY` | TikTok, Instagram, Threads, Pinterest, LinkedIn, Reddit, YouTube, Telegram, Meta Ad Library | paid service, small allowance, plan-dependent |
| 2 | Free tools and tokens | Bluesky app password, Truth Social token, Reddit OAuth app, GitHub CLI reuse | free |
| 3 | Approvals or paid datasets | Meta Ad Library, LinkedIn partner, Trustpilot business unit, Amazon/Bright Data | approval or paid |

One key does not guarantee every endpoint: the provider's plan must cover the
route. Vantage does not promise the same allowance as any other project.

## Route behaviour

Each platform may expose several legal routes. The order is always free first:

- Reddit: public RSS/archive → authorized provider;
- YouTube: `yt-dlp` → authorized provider;
- TikTok and Instagram: explicit public post links through `yt-dlp` → authorized
  provider for keyword discovery;
- Meta Ad Library: official Graph API → authorized provider;
- X: bearer token; public pages remain a host-search fallback;
- Telegram: authorized provider plus a channel list; no user-session access.

A failed route keeps the evidence already collected, never retries in a loop,
and records the route that actually returned items in coverage. The same
platform-native item reached through two routes is counted once.

## Probe meaning

`--probe` performs one request per free endpoint (or one `yt-dlp` search), with a
short timeout and no pagination. It also opens an anonymous USPTO session and
checks CLI presence. Credential-only routes are reported as
`not_probed — credential configured; not spent by the wizard`.

A probe result is a point-in-time observation. `available` does not certify
future availability, and `unavailable` records the exact HTTP status or timeout.

## Troubleshooting

| Message | Meaning | Action |
| --- | --- | --- |
| `MISSING_TOOL` | A declared binary is not on `PATH` | Install it (`pipx install yt-dlp`, `npm i -g digg-pp-cli`, …) or use the host web fallback |
| `MISSING_CREDENTIALS` | An enabled route needs a key | Run `vantage setup`, or set the named environment variable |
| `unavailable — HTTP 404/413` | The endpoint answered but refused this request | Leave it recorded; the report will state the limitation |
| `config dir not writable` | The sandbox or filesystem denies writes | Set `VANTAGE_CONFIG_DIR` to a writable path, or use environment variables |
| `not_probed` | A metered route was detected but not spent | Run one small research query after authorizing it |

## Security boundaries

- No account registration, purchase, recharge or auto-renewal.
- No browser cookie import and no logged-in browser automation.
- No reuse of another project's OAuth client, partnership discount or private
  authorization flow.
- No secret in a report, ledger, log line, test fixture or commit.
