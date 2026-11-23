# Beta acceptance — 2026-11-23

This record shows what the candidate actually produced on real runs, including
the failures. It is not a marketing card and it does not quote earlier
benchmark scores as this version's results.

## What was attempted

Four real, networked runs on clean commits, one per core scenario, using the
already-authorized Codex host and the engine's native source connectors:

| Scenario | Case | Commit | Status | delivery_level | research_quality | evidence kept | FACTs | Brief |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Industry | `industry-agents` | `8c1b012` | NO_EVIDENCE | `no_evidence` | LIMITED | 65 | 0 | 2,550 chars |
| Demand | `demand-cursor` | `8c1b012` | NO_EVIDENCE | `no_evidence` | LIMITED | 9 | 0 | 4,221 chars |
| Competitive | `competition-linear` | `8c1b012` | PARTIAL | `evidence_backed_brief` | LIMITED | 32 | 0 | 10,475 chars |
| Opportunity | `opportunity-offline` | `8c1b012` | NO_EVIDENCE | `no_evidence` | LIMITED | 0 | 0 | — |

Retained evidence came from GitHub, Hacker News and YouTube. Reddit was
unavailable (RSS invalid response, archive timeouts) and is reported as a gap,
not hidden. The competitive run kept 31 GitHub items and one YouTube item, and
the brief is an evidence-backed report without FACT synthesis.

## Defect found and fixed

The industry and demand runs kept 65 and 9 items but reported `NO_EVIDENCE`:
the adaptive coverage screening returned an empty selection and the
orchestrator then analysed nothing. This discarded completed retrieval. Fixed
in `29853a8`: an empty screening selection now falls back to the full retained
corpus, records `screening_fallback`, and adds an explicit gap. Regression:
`tests/integration/test_vantage_10.py::test_empty_screening_falls_back_to_the_retained_corpus`.

## Why the four scenarios were not re-validated

After the first batch the Codex host began timing out before planning
completed. The retry on `29853a8` recorded one dispatched call, zero successes,
one timeout and an engine `FAILED` with `delivery_level: no_evidence`
(`runs/rc/beta-evidence-29853a8/industry-agents/provenance.json`). No success
status was manufactured. The host limits are external, not a property of this
candidate, but they mean the Beta acceptance bar was not reached in this
environment.

## FACT support on frozen evidence

`scripts/replay_frozen_quality.py` replays the support contract over the frozen
ledger of the competitive run. This is engineering regression, not a new
research result:

| Probe | Previous gate | New contract |
| --- | --- | --- |
| Verbatim excerpt under its own id | accepted | `supported` |
| Valid id, excerpt belongs to another item | accepted | rejected (`unverified`) |

The previous engine accepted both because it only checked that the cited id
existed. Unit regressions additionally cover unrelated ids, overstated scope,
stitched quotes, vendor announcements presented as independent testing,
same-origin reposts, and the semantic-only path to `verified`
(`tests/unit/insights/test_evidence_support_contract.py`).

## Reproduce

```sh
SOURCEGLINT_HOST_OUTPUT=json_envelope \
SOURCEGLINT_HOST_CMD="python3 $PWD/runs/rc/codex_host_bridge.py" \
python3 scripts/run_real_benchmark.py --as-of 2026-11-22T00:00:00Z \
  --output runs/rc/<name> --only competition-linear --native-sources \
  --host-adapter sourceglint.host_command:build_model --budget-mode observe \
  --budget-usd 0.1 --run-budget-usd 0.05 --max-call-usd 0.02 \
  --seconds 300 --workers 1 --skip-preflight
python3 scripts/replay_frozen_quality.py --run runs/rc/<name>/competition-linear
```

Each run writes `provenance.json` with commit SHA, dirty state, budgets, evidence
hash, call accounting and token counts. USD cost is unknown on a subscription
host and is never estimated.
