# Beta acceptance package: real research under a strict budget

Date: 2026-11-22. Branch: `dev/trae-research-quality`. Base: `4e88623`.

## Gate status: not met (external blocker)

The budget-integrity work is complete and verified offline. The real research
package below could not run because the local host rejected its configured
model alias before any request was sent, and the account behind it previously
returned HTTP 402. No case was started, no paid benchmark was run and no
synthetic output is used as a substitute. No main merge and no 1.0 Release were
performed.

## Acceptance task

| Field | Value |
| --- | --- |
| Case | `industry-agents` (catalog `evals/rc-benchmark.json`) |
| Question | Which concrete open coding-agent tools were released recently? Separate announcements from independently observed behavior. |
| Market / language | global / en |
| Window | 30 days |
| Mode | trend |
| Required stages | plan → native retrieval → evidence assessment → intelligence synthesis → brief |
| Required artifacts | `request-*.json`, `evidence.jsonl`, `result.json`, `brief.md`, `status.json`, `host.usage.jsonl`, `cost.ledger.jsonl` |

## Reproducible command

Run from the checkout. `--max-call-usd` is what upgrades the cap from guarded to
strict; `--native-sources` keeps retrieval on the engine's connectors.

```bash
SOURCEGLINT_HOST_CMD='claude -p --output-format json' \
SOURCEGLINT_HOST_OUTPUT=json_envelope \
python scripts/run_real_benchmark.py \
  --native-sources \
  --host-adapter sourceglint.host_command:build_model \
  --only industry-agents --seconds 300 --workers 1 \
  --budget-usd 0.10 --run-budget-usd 0.05 --max-call-usd 0.02 \
  --budget-mode hard \
  --as-of 2026-11-22T00:00:00Z \
  --output runs/rc/<run-id>
```

A different locally installed, authorized runner can replace
`SOURCEGLINT_HOST_CMD`; do not change providers to bypass a balance or alias
problem.

## Preflight result (actual, this round)

Artifact: `runs/rc/beta-budget-acceptance/preflight.json` (ignored run data).

| Field | Value |
| --- | --- |
| Registry | ok (`reddit`, `hacker_news`, `github`, `youtube`, `qiita`) |
| Command found | yes (`claude` 2.1.322) |
| Status / category | `fail` / `model_not_found` |
| Budget enforcement | `strict` (`max_call_usd = 0.02`) |
| Cost state | `unbilled`, charged `0.00`, reported amount `null` |
| Batch committed / in flight | `0.00` / `0` |
| Runner exit | `2`; no case process started |

Ledger evidence (2 rows: one reservation, one no-charge settlement):

```json
{"kind":"reserve","call_id":"...","run_id":"preflight","task":"host_preflight","status":"in_flight","cost_state":"in_flight","reserved_usd":0.02,"cost_usd":null,"cost_known":false}
{"kind":"settle","call_id":"...","run_id":"preflight","task":"host_preflight","status":"model_not_found","cost_state":"unbilled","basis":"no_charge","cost_usd":0.0,"cost_known":true}
```

External blockers:

1. `ANTHROPIC_MODEL=deepseek-flash[1m]` is rejected locally
   (`[claude-code:unrecognized_model]`), so the bridge classifies it as
   `model_not_found`.
2. The account behind that endpoint previously answered HTTP 402
   `Insufficient Balance`. Neither the alias nor the balance is fixed by code.

## Budget integrity evidence

- `CostLedger.reserve` re-reads the shared JSONL, evaluates the batch and run
  caps, and appends an `in_flight` row in one lock (`fcntl` on POSIX,
  `msvcrt.locking` on Windows). The old `check()`-then-`record()` gap is gone
  from the host path.
- Strict mode requires a declared per-call ceiling. With it,
  `settled + in_flight <= cap` at every decision, so actual spend cannot exceed
  the cap. Without a ceiling the report says `guarded` and
  `strict_budget=false`, never "strict".
- Cost states are explicit: `known`, `unknown`, `unbilled`, `in_flight`.
  Unknown is never zero; in strict mode it charges the reserved ceiling and the
  next call is refused with `cost_unknown`.
- A reported bill above the ceiling records `overshoot_usd` and latches
  `budget_overshoot`.
- Timeout, non-zero exit, 401/402/403, rate limit, missing command/model and
  schema failure each have a regression test. Cross-process tests exercise one
  shared ledger; the thread test exercises the Windows lock path on CI.

## Offline verification

| Check | Result |
| --- | --- |
| `pytest tests -q -m "not live"` | 2270 passed, 14 skipped |
| `ruff check src scripts` | pass |
| `scripts/check_repository.py` | pass (recorded in the delivery report) |

## Quality review

Not performed. There was no host output to review, and scripted fixtures are
not used to claim research quality. The acceptance package is therefore a
reproducible run specification plus an auditable failure, not a research result.

## Beta release gate

Not met. The engineering gate (budget invariants, regression coverage, offline
suite) passes; the real-research gate requires one completed `industry-agents`
run with real planning, retrieval, assessment, synthesis, a brief and reviewed
citations. That is blocked only by model access. Once an authorized runner with
usable balance and a valid model alias is configured, rerun the command above;
the preflight must pass and the ledger must show a non-zero reported cost with
`overshoot_usd = 0`.
