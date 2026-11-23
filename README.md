# Vantage

**On-Demand Intelligence & Opportunity Discovery Skill**

[简体中文](README.zh-CN.md) · [Examples](docs/examples/2026-10-04/README.md) · [Documentation](docs/README.md)

Vantage helps founders, product managers, commercialization teams, consultants and researchers investigate industry changes, user needs and competitive signals across available platforms. Start by asking a research question. The default window is 30 days and can be adjusted.

The Skill plans subquestions before searching, checks retained evidence against them, and can run up to two targeted rounds for material gaps or corroboration. It deduplicates dated evidence and delivers a cited brief and reusable evidence file. Opportunity hypotheses and product or GTM recommendations are opt-in.

## What you can research

| Purpose | Example question |
| --- | --- |
| Product discovery | What are users praising or complaining about in AI meeting assistants? Which needs recur? |
| Market research | What changed in Japan's AI meeting assistant market, and what are Japanese users discussing? |
| Industry changes | Which AI video tools, technical developments and practical workflows appeared recently? |
| Opportunity discovery | Which unmet needs suggest a testable opportunity, and what would disconfirm it? |

After installation, ask your agent:

> Use Vantage to research AI video tools and user feedback from the last 30 days. Keep dates, original links and counterexamples.

## Install

Requires Python 3.10+ and an agent with web search, reasoning and an interactive terminal. For Codex, use an unused Skill directory:

```sh
git clone --branch release/vantage-1.0-beta --depth 1 \
  https://github.com/NextVariable/Vantage.git ~/.codex/skills/vantage
cd ~/.codex/skills/vantage
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -c "import sourceglint; print(sourceglint.__version__)"
.venv/bin/vantage doctor
```

The version must print `1.0.0b1`; if it prints another version you are on a
different branch or an older install. Then ask your agent to use Vantage. Keep the complete repository; `SKILL.md` alone is insufficient. On Windows, use `.venv\Scripts\python.exe`. The doctor command checks local readiness; actual research determines source availability.

For direct use, `vantage` defaults to adaptive research with a three-round
cap. The CLI requires a structured host model, for example
`--model sourceglint.host_stdio:build_model` with a host answering its JSON
requests. Use `--window DAYS` or inclusive UTC `--start-date` and `--end-date`.
The legacy `sourceglint` executable and Python import remain available.
See [four worked prompts and a recorded run](docs/examples/vantage-1.0.md).

## Results and coverage

You receive a cited report and an evidence file containing links, dates and source excerpts. Reports distinguish maker claims, user experiences and interpretations, retain counterexamples, and disclose missing sources or thin evidence.

The default Skill selects relevant routes from a hybrid profile with GitHub, Reddit, Hacker News, YouTube, Qiita and agent web search. A run need not query every route. Discussion, comment and caption enrichment is attempted where available. The Skill uses public sources by default. Credentialed routes can be configured for direct CLI use. Host usage limits still apply.

Research is bounded sampling. Coverage depends on access, rate limits, language and topic. A completed report does not establish complete platform coverage or prove market demand. Historical-window growth comparison, continuous monitoring, news aggregation and scheduled delivery are outside this workflow. Raw CLI/API calls keep single-pass retrieval unless invoked with `--adaptive` or `adaptive=True`.

### Status and trust

- `status`: `SUCCESS` means the core research and brief completed; `PARTIAL` means usable output with a degraded stage; `NO_EVIDENCE` means no usable evidence; `FAILED` means the run did not complete. `SUCCESS` never implies full coverage or research quality.
- `delivery_level`: `full_brief`, `evidence_backed_brief`, `evidence_only_report` or `no_evidence`. It describes the deliverable, not the status.
- `research_quality`: a separate coverage verdict (`ADEQUATE`, `LIMITED` or `NOT_ASSESSED`). A brief cannot upgrade it.
- Every FACT carries an evidence support state: `supported` (the quote occurs verbatim in the cited item), `verified` (additionally passed the separate semantic check), `partial` (only part of the statement is quoted), `vendor_only` (only vendor material supports it) or `unverified` (support could not be established). A valid but unrelated evidence id, a stitched quotation, or a vendor claim of independent testing is rejected — never promoted to a verified fact.
- Industry, demand and competitive research are the core. Opportunity hypotheses and product recommendations are generated only when explicitly requested.

## More

- [Recorded research examples](docs/examples/2026-10-04/README.md)
- [Source access](docs/source-access-matrix.md) and [fallbacks](docs/source-fallback-playbook.md)
- [Agent integration and evidence exports](references/host-protocol.md)
- [1.0 release readiness and live benchmark](docs/rc-release-readiness.md)
- [1.0 development audit](docs/vantage-1.0.md)
- [Adaptive research baseline and replay](docs/adaptive-research.md)
- [Validation records](docs/validation.md)
- [Repository guide](docs/repository-guide.md) and [contributing](CONTRIBUTING.md)

Licensed under [MIT](LICENSE).
