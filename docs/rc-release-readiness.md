# Vantage 1.0 release readiness

**BETA_ONLY** · `1.0.0.dev1` · `dev/vantage-1.0`

The [original 1.0 development audit](vantage-1.0.md) compared the development branch with `main` (`0a93cc1`). This sprint compares the prior development engine (`7e1757e`) with the live benchmark engine (`13a0635`). Per-run metadata records the full commit and whether its checkout was dirty. The historical 20-case live retrieval evaluation used scripted model judgments. The RC benchmark uses a logged-in Codex host for the model exchanges and live public retrieval.

## Run path

```text
Vantage Skill → vantage CLI → request and registry → structured Host plan
  → first retrieval: public adapters and Host web search
  → date and URL normalization → deduplicated evidence ledger
  → assess subquestions and evidence gaps → bounded follow-up requests
  → screened evidence → synthesis and conflicts → brief with citations
  → opportunity hypotheses only by explicit request
```

| Capability | Assessed this sprint |
| --- | --- |
| Scope, plan and execution | Existing planner and the shared engine use the structured plan. The benchmark saves requests and answers for every completed Host exchange. |
| Adaptive search | Existing adapter limits, duplicate control, gap routing and stopping rules are exercised offline and logged live. The sprint adds per-subquestion fallback for unavailable preferred routes. Extra rounds still need independent evidence of useful lift. |
| Evidence and sources | Source replies have an explicit JSON contract, per-query source observations persist, and malformed or credential-bearing citation URLs are discarded before ledger insertion. Qiita is included in the Japanese hybrid profile. |
| Synthesis and opportunity | The existing assessed-evidence view supports attribution, conflicts and explicit gap disclosure. Opportunity generation remains opt-in and can abstain on insufficient evidence. |
| Install and runner | The same wheel supports `vantage` and `sourceglint`. Fresh-install checks now run with a test matrix for Python 3.10 and 3.13 across Linux, macOS and Windows. |

## Reproduce and review

The [catalog](../evals/rc-benchmark.json) has five prompts in each research category and includes English, Chinese, Japanese, and 7-, 30-, 60-, and 90-day windows. Check out the engine commit for the experiment, use a host with existing authenticated Codex access, and keep the engine and logs on the same machine. `--engine-checkout` accepts a detached checkout of the prior commit, with `--baseline-compat` for the prior credential-isolation path.

```sh
python scripts/run_real_benchmark.py --as-of 2026-11-22T04:50:37Z \
  --output runs/rc/reproduction --workers 2 --seconds 270
python scripts/audit_real_benchmark.py runs/rc/reproduction --output runs/rc/review
```

The recorder retains exact questions and cutoffs, plans and replies, each query, source outcomes, raw and retained ledgers, cited briefs, timings and Host usage when reported. Raw records and review packets are ignored by Git. The projected web tool limit is a Host instruction; recorded web events are the observed count. Billed cost requires provider billing data and is unavailable from these traces. Exact-source replication can vary as public pages change or rate limits apply.

The [independent review rubric](../evals/rc-rubric.md) defines semantic scores and denominators. Machine checks match citation IDs, URLs and dates against the run ledger, and check dates against the requested interval. Source verification separately checks the origin page and the proposition it supports.
