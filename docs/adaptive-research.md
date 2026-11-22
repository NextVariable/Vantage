# Adaptive research

Baseline at `fd625b9`: 2104 offline tests passed, 14 live tests skipped (12.07 s).
After implementation: 2123 offline tests passed, 14 live tests skipped (14.61 s).
Lint, repository checks and wheel installation from outside the checkout passed.

```text
SKILL.md → CLI → run_sourceglint → request/parser → application/orchestrator
  → research plan → query expansion / source registry → adapters (native or host)
  → normalization → publication-window filter → deduplication → evidence ledger
  → intelligence (clusters, signals, contradictions) → insights (facts, inferences)
  → optional recommendations → brief selection / Markdown → SkillResult
```

The baseline has one retrieval phase with multiple preplanned queries. Cache
keys, route limits and result deduplication already exist. Coverage detects
access failures, thin samples and host-reported unanswered aspects after
retrieval. It does not assess evidence against planned subquestions, replan,
or stop future retrieval on evidence sufficiency. Connector retries and
fallbacks are transport behavior, not research iterations.

The adaptive path extends the existing research plan. The normalized request
owns the market, languages and time window; the host proposes a research goal,
objects and bounded subquestions. Each subquestion specifies evidence types,
preferred registry routes, priority, completion criteria and an initial query.
At most one follow-up round can address material gaps with an eligible new
query or route. Assessment sees only retained, dated evidence with stable IDs.
Both rounds use the same connector, filtering and deduplication pipeline and
share one ledger. The existing synthesis stages run once on the combined evidence.

```text
Parsed request → structured plan → initial retrieval → evaluate dated evidence
  → eligible material gap? → one targeted follow-up → final coverage
                           ↘ no → final coverage
  → one ledger → existing signals / insights / brief → optional hypotheses
```

Legacy callers can keep their existing single-pass behavior. The Skill opts
into adaptive research. Opportunity hypotheses require a separate explicit
opt-in and cite validated insights. Neither mode schedules future work.

## Budget and stop conditions

| Limit | Adaptive Skill behavior |
| --- | --- |
| Initial plan | Up to six subquestions and six adapter requests |
| Follow-up | At most one round and three additional adapter requests |
| Registry | Per-source query caps, market and language eligibility apply across both rounds |
| Host web search | Up to three routed targets per adapter request |
| Planner and evaluator | One plan, at most two coverage calls, up to 40 evidence items per coverage call |
| Opportunity task | At most one call and three hypotheses, only with explicit opt-in and valid insights |

An assessed subquestion needs usable IDs and the required tiers and independent
publishing surfaces. The model judges semantic relevance and the stated
criterion. Engine checks establish that the referenced items exist, are dated,
and satisfy those structural conditions. They cannot independently prove the
semantic judgment or establish market representativeness. The existing domain-based
origin estimator also discounts substantial copied text. Feedback
labels are model judgments about reported experiences.

A fully covered plan, absent/invalid assessment, or no eligible, materially
useful follow-up ends the run after the first round. The second assessment
reports remaining gaps and cannot request further retrieval. Blocked routes
are excluded, and source/language/normalized-query keys prevent repeats within
a run. Evidence deduplication spans both rounds. Connector retries, host tool
internals and downstream synthesis have separate limits. These budgets are
request counts, not a wall-clock or billing guarantee.

The API switches are `adaptive=True` and `opportunities=True`. The legacy
`sourceglint` command accepts the corresponding `--adaptive` and
`--opportunities` flags. The Skill enables adaptive research and uses
opportunity discovery only on explicit request. The opportunity output includes
a hypothesis, a validation test, a disconfirming observation and citations
resolved through the existing insight and evidence IDs.

## Validation

Run `python scripts/evaluate_adaptive.py` from the checkout. This replays the
single-pass and adaptive entry paths against the same synthetic adapter
responses and scripted model for four cases in [adaptive-research.json](../evals/adaptive-research.json).
Relevant evidence and claim support are measured against the fixed answer key.
An unproductive call returns no relevant fixture evidence.

| Offline replay, four cases | Single pass | Adaptive |
| --- | ---: | ---: |
| Relevant retained items | 4/12 | 8/11 |
| Supported factual claims | 4/4 | 8/8 |
| Subquestions with evidence | 4/8 | 8/8 |
| Adapter requests | 24 | 11 |
| Unproductive adapter requests | 16 | 3 |
| Model requests | 20 | 40 |
| Model input characters | 27,860 | 63,260 |
| Median local time (one run) | 17.24 ms | 14.83 ms |

One case finished after the initial round and three performed targeted
follow-ups. This is an execution and regression check with scripted judgments.
It cannot establish real retrieval precision, response time, model quality
or billing. The call and character counts are workload proxies. Supporting
evidence for an extra claim is not a change in the fixture support rate.

Separate real endpoint checks passed for Hacker News and anonymous GitHub search
on rerun (2 passed). The first GitHub attempt returned HTTP 403 with a rate-limit
response. The same two connector checks also passed against the baseline checkout.
These tests exercise source connectors only. A paired, live evaluation with independently reviewed
evidence and actual host latency and usage remains open. Use the same cutoffs
and access permissions, record the URLs and review relevance and support
without showing reviewers which path produced the evidence.
