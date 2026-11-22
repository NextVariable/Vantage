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
objects and bounded subquestions. Each subquestion specifies the evidence
*kind* a conclusion needs (`evidence_requirements.roles_any_of`), how many
direct observations and independent origins are sufficient, and which tiers
are merely preferred. Explicit planner `required_evidence` still blocks a
covered verdict; tiers derived from the focus are recorded as preferred, so a
broad question is not made unreachable just because one source class is absent.
At most one follow-up round can address material gaps with an eligible new
query or route. Assessment sees only retained, dated evidence with stable IDs.
Both rounds use the same connector, filtering and deduplication pipeline and
share one ledger. The existing synthesis stages run once on the combined
evidence.

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

Wall-clock budget is separate from request counts. Research stops at
`research_deadline`; a synthesis reserve is held back so a slow final round
cannot starve the brief. The reserve is `min(130s, 45% of the run)` capped by a
complexity target, so it never exceeds the share cap even for very short
budgets; research receives exactly the remainder and the window is never
negative. A remainder below 30 seconds sets `short_budget` so the run is
reported as research-starved instead of silently degraded. The chosen reserve
and its basis are recorded in
`diagnostics.performance`, together with per-phase `planning`, `retrieval`,
`assessment` and `synthesis` seconds. Rejected routes are counted by reason
(`duplicate_query`, `source_query_limit`, `route_budget`,
`language_not_requested`, `source_language_unsupported`) instead of being
silently dropped.

An assessed subquestion needs usable IDs, the evidence kinds named in
`roles_any_of`, its independent publishing surfaces and, where the focus
requires it, at least one direct observation (verified announcement, firsthand
report or independent test). Preferred tiers are reported but never block
coverage. Each subquestion reports one of four answer states:
`fully_answered`, `partially_answered`, `explicitly_disclosed` (a named gap
such as missing required evidence, too few direct observations or blocked
sources) or `unanswered`. Disclosed gaps are not counted as answers, and
`research_quality: ADEQUATE` requires every subquestion to be fully answered.
The report exposes `answer_rates.answered` and `answer_rates.disclosed_gap`
separately; they are never combined into one success rate.

Evidence identity is never inferred from a username. An item is a verified
vendor claim only through registry/official designation; a community post is
third-party commentary unless the assessment cites it as feedback, and a
first-party announcement ("our team shipped ...") is reclassified as an
unverified vendor claim from its text. The model judges semantic relevance and
the stated criterion. Engine checks establish that the referenced items exist,
are dated, and satisfy the structural conditions above. They cannot
independently prove the semantic judgment or establish market
representativeness.

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

## Host runtime

The engine keeps one model contract (`complete_structured`) and two transports:

* `sourceglint.host_stdio:build_model` — the Codex-compatible JSONL host. It is
  unchanged and remains the default for interactive Skill runs.
* `sourceglint.host_command:build_model` — a provider-neutral bridge to any
  locally installed command-line runner. Configuration is environment-only:
  `SOURCEGLINT_HOST_CMD` (argv), `SOURCEGLINT_HOST_OUTPUT` (`text` or
  `json_envelope`), `SOURCEGLINT_HOST_PROMPT` (`stdin` or `argv`),
  `SOURCEGLINT_HOST_TIMEOUT`, and `SOURCEGLINT_HOST_USAGE` for a JSONL record of
  latency, status, token usage and billed cost. No endpoint, model name or
  credential is stored in the package.

```text
SOURCEGLINT_HOST_CMD='my-runner --print' \
SOURCEGLINT_HOST_OUTPUT=json_envelope \
SOURCEGLINT_HOST_PROMPT=argv \
SOURCEGLINT_HOST_USAGE=runs/host.usage.jsonl \
python scripts/run_real_benchmark.py --native-sources \
  --host-adapter sourceglint.host_command:build_model --seconds 150 \
  --as-of <ISO> --output runs/<id>
```

Timeouts, non-zero exits, oversized replies, non-JSON output and schema
failures map to `TIMEOUT`, `UNAVAILABLE` or `INVALID_OUTPUT`; a late reply never
leaves the runner waiting for a frame it already abandoned. Model text and
usage are recorded separately.

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

## Real-host status (2026-11-22)

The command bridge completed one real structured planning call against a locally
installed runner (`ModelStatus.SUCCESS`, 19,371 input / 2,606 output tokens,
$0.162 billed), which verifies the adapter end to end. The same account then
returned HTTP 402 (insufficient balance) on the next call, so the 20-case
Benchmark could not be completed. A single `industry-agents` probe did run the
full engine against native GitHub/Reddit connectors; it returned `NO_EVIDENCE`
in 66.4 s because planning fell back to query expansion and the retrieval window
was exhausted. Those artifacts are in `runs/rc/beta-native-probe/industry-agents`
and are not a quality result. No synthetic or fake host output is used to fill
the gap, and no Beta/RC claim is made from these numbers.

