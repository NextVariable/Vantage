# Vantage 1.0 development and acceptance

For the later authenticated Host benchmark and current release decision, see [RC release readiness](rc-release-readiness.md).

Baseline: `0a93cc1` on `main`, 2,123 offline tests passed and 14 online tests
skipped. Development takes place on `dev/vantage-1.0`.

| Capability | Baseline code audit |
| --- | --- |
| Intent and scope | Rule parser emits one routing mode, market, languages and relative window. The adaptive planner adds subquestions and evidence criteria. Opportunity discovery is an explicit switch. |
| Plan and source routing | Existing schema is executable through registry adapters; no separate hypothesis, assumption or run-budget fields on the plan. |
| Research loop | One optional follow-up; coverage checks dated IDs, tiers and independent origins. Unchanged result sets stop the prior flow only after its last round. |
| Evidence and synthesis | Adapter normalization, publication filtering, ledger, URL/native-ID dedup and substantive copied-text suppression for origin counts, clusters, contradiction and fact/inference validation. Publication dates and links remain traceable. |
| Opportunities | Opt-in, evidence-linked, falsifiable but limited to a short hypothesis, test and disconfirming result. |
| Brief | Fixed section order with empty sections omitted; subquestion outcomes are visible but grouped together. |
| Validation | Offline fixture comparison and limited endpoint checks; no balanced, 20-case live quality baseline. |

```text
Skill / vantage CLI / legacy sourceglint → normalized request and scope
  → structured intent and research plan → enabled source registry
  → retrieve → normalize / time-filter / deduplicate → assess the evidence
  → bounded refinement while there is a material eligible gap
  → one evidence ledger → clusters / contradictions → validated insights
  → brief organized by research focus → optional opportunity hypotheses
```

The upgrade extends the existing plan and assessment contracts and keeps a single
retrieval implementation and one final evidence ledger. Existing hosts can keep
their previous entry point and round limit. The new CLI and Skill use the richer
research path. Purely descriptive requests retain research-only output.

## Runtime contract

`vantage` starts with a three-round cap, a total budget of twelve adapter
requests and a registry-enforced per-source cap of at most three. The default
hybrid profile caps each route at two. Up to six initial requests are planned
and each follow-up can use up to three. The discovery deadline is 90 seconds
by default, followed by a 45-second allowance for synthesis. The built-in
transport caps each request by the remaining time and suppresses retries when
their backoff would exceed it. The host bridge rejects late frames after a
timeout. These are cooperative deadlines: arbitrary injected adapter/model
calls, OS DNS resolution, and third-party provider internals cannot be
forcibly interrupted by this contract.

The initial plan carries the request's geography, language and date scope.
Its hypotheses are questions to test. They are not evidence. Later rounds
require a new eligible route and a material gap or a high-value grounded
verification lead. Round three requires a coverage improvement or new distinct
assessed evidence. Identical copied text, irrelevant new results and repeated
queries cannot by themselves extend the run. Source failures stop that route;
accepted material from other routes stays available.

The full ledger retains dated deduplicated candidates for audit. A read-only
view of that same ledger excludes unassessed candidates from clustering,
insights and the displayed excerpts. A valid evidence ID only establishes
traceability. The host still judges relevance and whether the evidence
supports the actual claim. Vendor self-reports and user accounts are labeled
in the brief, including vendor claims posted on community platforms.
Opportunity analysis adds no hypotheses on research-only requests.

The pipeline currently plans one market per run and does not compute growth
relative to a prior period. Evidence class labels and coverage are sample-bound
and host-judged. The CLI's automatic opportunity detection is conservative;
explicit `--opportunities` and `--no-opportunities` are available.

## Validation and quality

The offline suite passed **2,140 tests**, compared with **2,123** on the
baseline, with 14 live tests skipped in each offline run. Lint and repository
checks passed. The wheel installed into a fresh Python 3.13 environment
outside the checkout. Both launchers worked, installed-resource checks passed,
and `pip check` found no unsatisfied dependency. No new package dependency,
account, paid connector or scheduler was introduced.

The [20-case matrix](../evals/vantage-1.0-live.json) covers four research areas,
English, Chinese and Japanese, and 7–90 day windows. The controlled paired
experiment used real HN, DEV and Qiita calls, the same UTC cutoff
(2026-11-22 04:00), and the real baseline checkout. Model answers were scripted
to isolate retrieval and evaluation behavior. The two arms ran sequentially,
so public source availability and rankings differed. The detailed
[per-case results](../evals/vantage-1.0-results.json) retain those differences.

| Controlled live retrieval metric | Baseline | Revised source filtering |
| --- | ---: | ---: |
| Relevant in single-reviewer, shuffled spot check | 6/19 | 8/16 |
| Dated retained records | 165 | 89 |
| Literal screening matches (not judged findings) | 66 | 72 |
| Cases meeting the scripted coverage rule | 2/20 | 4/20 |
| Unique displayed IDs with ledger URL and date present | 165/165 | 89/89 |
| Adapter requests / none matching literal screen | 40 / 22 | 41 / 21 |
| Median elapsed per case | 3.39 s | 4.39 s |
| Structured model requests (scripted) | 201 | 202 |
| Scripted model input characters | 733,411 | 701,895 |
| Reported source failures / observed failures | 0 / 0 | 6 / 6 |

The spot check used one candidate per non-empty case, shuffled across arms.
It measured direct topical usefulness from the available excerpt, including
counterexamples and attributed announcements where appropriate. It excluded
empty cases and is not an independently replicated quality estimate. A literal
match is not evidence precision. The scripted coverage threshold and citation
consistency check do not score insight grounding or hallucination rates.
Unique relevant findings, comprehensive question answering, adaptive utility,
inference grounding, actual hosted cost and hallucination rates remain
unverified across the matrix. Third-round behavior was exercised in one live
case and the controlled regressions; the live run does not establish that the
third round improves useful findings generally.

That experiment exposed incidental matches and source-rate-limit sensitivity.
Vantage now uses a topic check on DEV and Qiita candidates and keeps
non-assessed items out of the brief and synthesis. The latter filter was
validated independently through focused regressions and a real host run,
rather than attributed to the table above. Two maker reports passed the
coverage screen out of eleven retained candidates in the research-only run.
The request focused on offline meeting transcription. The engine used two
rounds, marked independent limitations unanswered, and stopped when the
follow-up added no evidence. A second live run through the wheel installed in
a fresh environment explicitly asked for opportunities and returned
`insufficient_evidence` with no hypotheses. It reused reviewed host responses;
internal artifacts include the actual retrieved records and exchange JSON.

## Release decision

**Development preview only.** The code is suitable for review on
`dev/vantage-1.0`. A formal 1.0 release needs full hosted runs with independent
judgments of question coverage, insight grounding and false claims. The
observed improvement in a small spot check, reduced noise, and verified
abstention do not establish a reliable improvement across the four research
areas. The current priority is to improve Chinese and Japanese retrieval with
suitable local sources, recheck unavailable routes with matched permissions,
and repeat the matrix with full host reasoning before adjusting the round
budget. No merge or release tag is part of this development delivery.

[Usage and recorded examples](examples/vantage-1.0.md) ·
[Offline baseline design](adaptive-research.md)
