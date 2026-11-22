# Vantage 1.0 release readiness

**BETA_ONLY** · `1.0.0b1` · `release/vantage-1.0-beta`

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

## Engineering verification

| Check | Observed status |
| --- | --- |
| Offline baseline `7e1757e` | 2,140 passed, 14 live tests skipped. |
| Final local regression | 2,150 passed, 14 live tests skipped. The final scope includes the Reddit archive and opportunity status regressions. |
| Local macOS, Python 3.13 | Wheel build, isolated install, `pip check`, both entry points and installed runtime smoke passed. Editable installation and `vantage doctor` also passed. |
| Codex Skill entry | A separate Codex process explicitly discovered `$vantage`, loaded `SKILL.md` and ran the installed `vantage doctor` with exit zero. This checks local discovery and startup. Full research is verified separately through the Host/CLI benchmark. |
| First cross-platform CI | Four macOS/Linux jobs passed. Windows surfaced a path-dependent default skip and a hard-coded path separator assertion. |
| Windows fixes `d3ea40c` | All six CI jobs passed, including offline tests and isolated wheel installation, on Windows, macOS and Ubuntu with Python 3.10 and 3.13. [GitHub Actions matrix](https://github.com/NextVariable/Vantage/actions/runs/44988447227) |
| Data and credential checks | Repository scanner, tracked history check and ignored raw evidence verified. The benchmark used public lanes with no paid adapter credentials. Direct CLI users can opt into other configured routes. |

Full run reports, ledgers, evidence snippets and tool event logs may contain user research and upstream data. Keep `runs/`, caches and local configuration out of source control. Review source permissions separately from installation readiness. See [source access](source-access-matrix.md) and [fallbacks](source-fallback-playbook.md).

## Beta blocker closure

The independent audit (`e59f4f1`) left three release blockers. All are closed on
`release/vantage-1.0-beta`.

| Blocker | Fix | Regression evidence |
| --- | --- | --- |
| STDIO timeout starvation | Requests carry `protocol: sourceglint-host/v2` and a deterministic `request_id`; replies echo it. A timed-out id is abandoned, its late reply is skipped by id, and later requests continue. Legacy streams that never echo an id are closed after a timeout (fail closed). One stream reader queues lines, so an abandoned read cannot consume the next reply. | `tests/unit/test_host_recovery.py` uses real `os.pipe` pairs and controllable delays: contradiction timeout, late-reply isolation, FACT dispatch under its own id, a coalesced late/FACT burst, legacy fail-closed, duplicate/cross-request rejection. |
| FACT support not established | Each FACT carries atomic claims with a verbatim excerpt from the cited item. The engine rejects unrelated ids, paraphrased or stitched quotes, vendor material presented as independent testing, and same-origin reposts counted as corroboration. `supported` is the best deterministic outcome; only the separate semantic stage can return `verified`, and an unavailable model leaves facts unverified. | `tests/unit/insights/test_evidence_support_contract.py` and `scripts/replay_frozen_quality.py`. |
| Unassessed relevance scored as zero | `compute_score` excludes unassessed factors and renormalises the remaining weights. Diagnostics expose `score_completeness`, `score_coverage`, `unassessed_factors` and per-factor `missing_reasons`; weak-signal nomination ignores an unassessed relevance. | `tests/unit/intelligence/test_missing_factors.py`, including input-order swaps and the weak-signal boundary. |

`scripts/stdio_recovery_acceptance.py` repeats the timeout scenario against the
real installed Codex host over pipes, and `scripts/run_real_benchmark.py` now
writes `provenance.json` with commit SHA, working-tree state, budgets, evidence
hash, call accounting and the token split. A dirty checkout is stored with
`release_evidence: false`. On 2026-11-23 the real host answered `clustering`
(request `clustering-0001`) and returned a late `contradiction` reply 18.2 s
after its 0.05 s deadline; the engine skipped that frame, dispatched
`fact_synthesis` as `fact_synthesis-0003`, and matched its payload. All seven
checks passed with no cross-framing.

## Real benchmark results

[Per-case machine results](../evals/rc-results.json) · [Independent source spot checks and quality comparison](rc-quality-review.md) · [Four example reports](examples/rc/README.md)

The full `13a0635` run produced 20 records with briefs and ledgers where evidence survived. All 20 recorded Host plans, but 12 cases missed a timely reply and one engine was terminated after its partial payload had been saved. The recorded CLI totals were 13 `PARTIAL`, six `NO_EVIDENCE` and one `SUCCESS`. The `SUCCESS` case had an unavailable opportunity assessment despite the successful core brief, so it did not qualify as a complete opportunity report. That status composition was repaired after this matrix and regression-tested. The result file preserves the original status.

The engine retained 42 dated records inside their recorded windows. All 32 displayed evidence IDs had matching URL/date pairs in the ledger. This is a traceability check. Independent spot checks found correctly attributed claims and original URLs that could not be reopened. There is no representative independent score for citation accuracy, key claim support or coverage. The engine itself marked zero of its 51 planned subquestions fully covered, although brief sections did provide partial answers and disclose gaps.

Initial and follow-up routes made 75 adapter requests. Forty-five returned no rows and five failed. Nine of 24 follow-up rounds produced new retained candidates. The useful incremental findings in those rounds have not been independently established. The median time was 241.99 seconds and 72 Host web events were visible. Model usage was available for 18 cases, including input/cache breakdown. Actual charges were unavailable.

## Release gates and next iteration

| Gate | Judgment |
| --- | --- |
| Key claim support ≥95% and core questions answered or explicitly disclosed ≥80% | Unverified across the matrix. Selected origin checks alone cannot establish either rate. |
| No undisclosed material factual errors | Unverified; material provenance and original-page gaps were observed. |
| Falsifiable opportunities without unsupported demand claims | Both negative controls yielded no evidence. The fictional opportunity prompt abstained. One documentation study design was explicitly tentative, with an origin the reviewer could not reopen. |
| Repeatable hosted research | Repeatable runner, pinned versions and 20 actual records. Too many late exchanges and unavailable sources for the RC quality gate. |
| Improvement over the previous engine | Five paired prompts retained more records and failed fewer adapter routes, with a substantial latency and Host interaction penalty. Semantic improvement remains unproven. |
| Clean install, command paths and platform support | Verified locally for macOS and in the six-job Windows/macOS/Ubuntu matrix at `d3ea40c`. |

The beta candidate closes the three release blockers and is published from
`release/vantage-1.0-beta`. Remaining improvements are post-beta backlog, not
release blockers: reserve more synthesis time and stop low-yield lanes earlier,
resolve publisher provenance separately from route identity, and compare
sources and question coverage through a blinded rerun.
