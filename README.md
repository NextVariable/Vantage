# Vantage

**On-Demand Intelligence & Opportunity Discovery Skill**

[简体中文](README.zh-CN.md) · [Examples](docs/source-expansion-1.1.md#two-real-vantage-reports) · [Documentation](docs/README.md)

Vantage helps founders, product managers, commercialization teams, consultants and researchers investigate industry changes, user needs and competitive signals across available platforms. Start by asking a research question. The default window is 30 days and can be adjusted.

The Skill plans subquestions before searching, checks retained evidence against them, and can run up to two targeted rounds for material gaps or corroboration. It deduplicates dated evidence and delivers a cited brief and reusable evidence file. Opportunity hypotheses and product or GTM recommendations are opt-in.

## Versions

- **Published: Vantage 1.0 Beta 1** (`1.0.0b1`). The installation below pins the published tag. [GitHub pre-release](https://github.com/NextVariable/Vantage/releases/tag/v1.0.0b1)
- **In development: Vantage 1.1 Global Source Expansion**. This branch, `dev/vantage-1.1-global-sources`, installs package version `1.1.0.dev2`. It has dated source validation and remains an unreleased development build. [1.1 acceptance record](docs/source-expansion-1.1.md#phase-3-codex-host-acceptance-2026-11-24)

## What you can research

| Purpose | Example question |
| --- | --- |
| Product discovery | What are users praising or complaining about in AI meeting assistants? Which needs recur? |
| Market research | What changed in Japan's AI meeting assistant market, and what are Japanese users discussing? |
| Industry changes | Which AI video tools, technical developments and practical workflows appeared recently? |
| Opportunity discovery | Which unmet needs suggest a testable opportunity, and what would disconfirm it? |

After installation, ask your agent:

> Use Vantage to research AI video tools and user feedback from the last 30 days. Keep dates, original links and counterexamples.

## Install 1.0 Beta 1

Requires Python 3.10+ and an agent with web search, reasoning and an interactive terminal. For Codex, use an unused Skill directory:

```sh
git clone --branch v1.0.0b1 --depth 1 \
  https://github.com/NextVariable/Vantage.git ~/.codex/skills/vantage
cd ~/.codex/skills/vantage
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -c "import sourceglint; print(sourceglint.__version__)"
.venv/bin/vantage doctor
```

Confirm the version prints `1.0.0b1`. Then ask your agent to use Vantage. Keep the complete repository; `SKILL.md` alone is insufficient. On Windows, use `.venv\Scripts\python.exe`. The doctor command checks local readiness; actual research determines source availability.

### Install the 1.1 development build

For development or validation, replace `--branch v1.0.0b1` with
`--branch dev/vantage-1.1-global-sources` and use
`~/.codex/skills/vantage-dev` as the target and working directory. The version
check should print `1.1.0.dev2`. Enable one copy of the `vantage` Skill in a
Codex environment at a time.

For direct use, `vantage` defaults to adaptive research with a three-round
cap. The CLI requires a structured host model, for example
`--model sourceglint.host_stdio:build_model` with a host answering its JSON
requests. Use `--window DAYS` or inclusive UTC `--start-date` and `--end-date`.
The legacy `sourceglint` executable and Python import remain available.
See [four worked prompts and a recorded run](docs/examples/vantage-1.0.md).

### One-command setup

```sh
vantage setup            # inspect, choose, store, optionally probe
vantage setup --skip     # print what already works; change nothing
vantage setup --free-only --json
vantage setup --probe    # bounded live check, no paid calls
```

The wizard detects the OS, Python, existing keys (names only), local CLIs
(`yt-dlp`, `gh`, `digg-pp-cli`, `trustpilot-pp-cli`, `brightdata`), an
authorized local Xiaohongshu MCP service and a GitHub CLI login. It lists the
free sources, recommends the smallest account set, lets you skip everything,
and stores a pasted key in the macOS Keychain (falling back to a 0600 file).
Environment variables still win. It never registers an account, buys a plan,
tops up a balance, enables auto-renewal, reads browser cookies or widens an
existing account's scopes. See the [setup guide](docs/setup-guide.md).

## Results and coverage

You receive a cited report and an evidence file containing links, dates and source excerpts. Reports distinguish maker claims, user experiences and interpretations, retain counterexamples, and disclose missing sources or thin evidence. Cross-platform synthesis is the main body; a supplementary `Platform Observations` section appears only when at least two original platforms contributed cited evidence, and citations keep the original platform next to the retrieval route (`Reddit via host_web_search`). Use `--platform`/`--exclude-platform` (or "only Reddit and GitHub" / "排除 X") to scope a run, and `--exclude-official` to drop owner-published material.

The Beta Skill selects relevant routes from a hybrid profile with GitHub, Reddit, Hacker News, YouTube, Qiita and agent web search. The 1.1 Skill can choose Hybrid or Expanded by research intent. A run need not query every route. Discussion, comment and caption enrichment is attempted where available. The Skill uses public sources by default. Credentialed routes can be configured for direct CLI use. Host usage limits still apply.

Research is bounded sampling. Coverage depends on access, rate limits, language and topic. A completed report does not establish complete platform coverage or prove market demand. Historical-window growth comparison, continuous monitoring, news aggregation and scheduled delivery are outside this workflow. Raw CLI/API calls keep single-pass retrieval unless invoked with `--adaptive` or `adaptive=True`.

### Status and trust

- `status`: `SUCCESS` means the required execution stages completed and a usable brief was produced; `PARTIAL` means usable output with a degraded stage; `NO_EVIDENCE` means no usable evidence; `FAILED` means the run did not complete. `SUCCESS` never implies full coverage or research quality.
- `delivery_level`: `full_brief`, `evidence_backed_brief`, `evidence_only_report` or `no_evidence`. It describes the deliverable, not the status.
- `research_quality`: a separate coverage verdict (`ADEQUATE`, `LIMITED` or `NOT_ASSESSED`). A brief cannot upgrade it.
- The JSON makes `execution_status` explicit while preserving the legacy `status`. Each factual finding carries an evidence support state: `supported` (the quote occurs verbatim in the cited item), `verified` (additionally passed the separate semantic check), `partial` (only part of the statement is quoted), `vendor_only` (only vendor material supports it) or `unverified` (support could not be established). A valid but unrelated evidence id, a stitched quotation, or a vendor claim of independent testing is rejected — never promoted to a verified fact.
- Industry, demand and competitive research are the core. Opportunity hypotheses and product recommendations are generated only when explicitly requested.

### 1.1 source verification

As of 2026-11-25, every deduplicated upstream last30days platform has a Vantage
connector (24/24). Seven have a direct live round-trip (YouTube, Hacker News,
GitHub, arXiv, DEV, Techmeme, USPTO patents) and one more was verified from a
frozen original page (Trustpilot), for 8/24. A bounded probe also re-confirmed
Hacker News, GitHub, arXiv, DEV and Techmeme, and opened an anonymous USPTO
search session that returned dated patent evidence.

One `SCRAPECREATORS_API_KEY` can enrich nine platforms (TikTok, Instagram,
Threads, Pinterest, LinkedIn, Reddit, YouTube, Telegram and Meta Ad Library),
subject to that provider's plan. Without it the free routes still run:
`yt-dlp` for YouTube and explicit public TikTok/Instagram links, public Reddit
RSS/archive, Digg and Trustpilot CLIs when installed, and the keyless USPTO
session. Each platform tries its free route first and records the route it
actually used. Paid fallback is capped
(`VANTAGE_PAID_FALLBACK_CALLS`, default 10) and can be disabled entirely with
`VANTAGE_DISABLE_PAID_FALLBACK=1`. No credential means no paid call.

The 2026-11-24 snapshot's 35 key-free direct platforms remain valid. Authorized
APIs, CLI tools that are not installed here (Digg, Trustpilot, Bright Data) and
currently unreachable endpoints (Reddit public RSS 404, Polymarket 413) are
tracked separately. [Source access](docs/source-access-matrix.md) · [Verification snapshot](docs/source-live-status.json)

## Research examples and docs

- [Latest 1.1 research runs](docs/source-expansion-1.1.md#two-real-vantage-reports) cover Japanese meeting-note product launches and Otter feedback. Both reported `LIMITED` research quality.
- [Four published Beta examples](docs/examples/beta-final-2026-11-24/README.md) cover industry, demand, competition and opportunity discovery.
- [Documentation index](docs/README.md) · [Authorization guide](docs/source-authorization.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

Licensed under [MIT](LICENSE).
