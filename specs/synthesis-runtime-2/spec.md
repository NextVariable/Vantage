# Synthesis Runtime 2.0 — Spec

Status: proposed (awaiting approval)
Branch: `dev/trae-research-quality`
Baseline HEAD: `4769cfa296fc1b5ac9bd21655d6883ff5b982021`
Scope: scheduling, budgeting, progressive delivery, evidence/token efficiency, absence scope.
Non-goals: new sources, new UI, main merge, 1.0 release, extending the total timeout.

## 1. Problem statement

The real `industry-agents` run (345.01 s) reached PARTIAL because synthesis had no
stage budget:

| stage | time | calls |
|---|---|---|
| clustering | 49.6 s | 1 |
| contradiction | 15.0 s | per multi-member cluster |
| semantic_factors | 11.7 s | per cluster |
| fact_synthesis | refused at deadline | 1 |
| inference / GTM | refused | 1 each |

The existing reserve in `application/api.py` is `45 + 9 * complexity` (min 60, max
130, capped at 45 % of the run). It ignores subquestions, cluster count, selected
evidence and observed host latency, and every synthesis stage shares one deadline.
A low-priority per-cluster stage can therefore consume the whole reserve.

## 2. Design

### 2.1 New module `src/sourceglint/synthesis_budget.py`

Execution order is unchanged: clustering → contradiction → semantic factors →
facts → inference → GTM → brief. Priority order is different from execution order:

1. `clustering` (required)
2. `contradiction` (required for a signal to be fact-eligible)
3. `fact_synthesis` (core deliverable)
4. `brief` (deterministic, floor 1.5 s)
5. `inference_synthesis`
6. `semantic_factors` (ranking enrichment only)
7. `gtm_implications`
8. `recommendations`

`SynthesisBudget` holds: overall monotonic deadline, fact reserve, inference
reserve, brief floor, semantic call cap, per-task calls/seconds/input chars,
per-stage status and degradation reasons.

Reserve split at synthesis start (`R = remaining_time()`):

- `brief_floor = 1.5` s
- `fact_reserve = min(max(0.35 * R, 15), 60)` s, capped at `R - 15` s
- `inference_reserve = min(max(0.12 * R, 0), 20)` s
- `semantic_call_cap`: number of semantic calls that fit before
  `deadline - fact_reserve - inference_reserve - brief_floor`, using the observed
  per-call latency (median of completed calls, default 10 s); `0` when it does not fit.

Gate rules (checked before every model call):

| task | allowed while |
|---|---|
| clustering | `remaining > brief_floor` |
| contradiction | `remaining > fact_reserve + brief_floor` |
| semantic_factors | `remaining > fact_reserve + inference_reserve + brief_floor` and `calls < cap` |
| fact_synthesis | `remaining > brief_floor` |
| inference_synthesis | `remaining > brief_floor + 1` |
| gtm_implications | `remaining > 8` |
| recommendations | `remaining > 8` |

A refused call returns `ModelResponse(status=UNAVAILABLE, error="synthesis budget: ...")`.
Existing degradation paths already handle non-ok responses; no stage raises because of
budget except the required clustering, which degrades the run to an evidence-only report.

`MeteredModel` wraps the host model transparently (`model_id` delegated) and records per
task: calls, refusal reason, elapsed seconds, payload characters, approx input tokens
(`chars / 4`). When the inner model exposes `usage_summary()`, host-reported tokens and
cost are copied into diagnostics. Cache hits bypass the model and are therefore not
counted as calls.

### 2.2 Intelligence pipeline (`intelligence/pipeline.py`)

- New optional keyword-only `budget: SynthesisBudget | None = None`.
- clustering is wrapped in `deadline_scope(budget.stage_deadline("clustering"))`.
- contradiction is wrapped in `deadline_scope(budget.stage_deadline("contradiction"))`.
- semantic factors: before each cluster, if `budget.allow("semantic_factors")` is false,
  skip the call and build the factor set via `derive_factors(..., semantic_reason=...)`
  with `decision_relevance=0`, `model_status="unavailable"`, `degraded=True`.
  The reason is recorded once per stage (`semantic factors skipped: budget`).
- `IntelligencePipelineResult.model_status` keeps the existing vocabulary.
- Baseline-only clusters are still excluded before any model call (already true).

`intelligence/factors.py` gains `semantic_reason: str = ""` on `derive_factors`; when set,
the semantic call is skipped and the reason is used instead of the generic "no model".

### 2.3 Insight pipeline (`insights/pipeline.py`, `facts.py`, `inferences.py`, `gtm_implications.py`)

- New optional `budget` parameter.
- fact synthesis is wrapped in `deadline_scope(budget.stage_deadline("fact_synthesis"))`;
  it always runs before inference and GTM.
- inference and GTM are skipped when their gate refuses; the fact layer is returned.
- `fact_synthesis` failure still yields `evidence_only_report` (never fabricated facts).
- `insights/preparation.py`: the existing safety rule stays (an unassessed contradiction
  cannot feed facts). The scheduling fix guarantees contradiction runs before the fact
  reserve is touched; if it still fails, the run degrades honestly.

### 2.4 Progressive delivery

`ApplicationResult.delivery_level` and `SkillResult.delivery_level` (backwards
compatible, default `""`):

| level | condition |
|---|---|
| `full_brief` | research OK, ≥1 validated fact, inference completed, no core stage degraded |
| `evidence_backed_brief` | ≥1 validated fact, but inference/GTM/semantic degraded or skipped |
| `evidence_only_report` | no validated fact (model synthesis unavailable), evidence + sources + gaps rendered |
| `no_evidence` | research retrieved nothing usable |

Delivery level never changes `Status`. A PARTIAL run can be `full_brief`; a
`full_brief` label is impossible without validated facts and completed inference.
`BriefContext.delivery_level` adds one deterministic line to the brief for non-full
levels; `full_brief` leaves the brief byte-identical.

### 2.5 Dynamic reserve (`application/api.py`)

Replace `_synthesis_reserve` with:

```
complexity = 1 + min(4, entities) + min(3, languages) + min(6, subquestions)
target = 40 + 11 * complexity + (8 if mode in {competitor, opportunity, market} else 0)
upper = min(140, 0.45 * total)
reserve = clamp(target, min(60, upper), upper)
```

For the real case (1 entity, 1 language, 3 subquestions, mode industry):
`complexity = 6`, `target = 106` s, research window `239` s. The reserve basis
(subquestions, estimated calls, observed latency at synthesis time, cluster count) is
recorded in `diagnostics.performance.synthesis_reserve_basis`.

### 2.6 Evidence and token efficiency

- `intelligence/preparation.model_payloads` gains `content_budget: int = 48000`
  (default unchanged). Contradiction passes `32000`, semantic factors `20000`;
  clustering keeps the default. Only the per-call excerpt budget changes; the ledger
  is never modified.
- `insights/preparation._extract_summary` caps each evidence summary at
  `MAX_FACT_SUMMARY_CHARS = 3000` (was 6000) to bound the fact payload.
- IDs remain the only cross-call reference; every payload keeps `evidence_ids`.
- `synthesis.model_io` in diagnostics records calls, input chars, approx tokens and
  host-reported usage per task.

### 2.7 Absence and pagination

`connectors/_github_release.py`:

- read the `Link` response header; fetch up to 3 pages while a next page exists and
  no in-window release has been seen;
- new observation status `pagination_incomplete` when the page cap is reached with a
  next link still present and zero in-window releases;
- `only_outside_window` is only emitted when pagination is complete.
- observations record `pages_fetched` and `pagination_complete`.

`pipeline/absence.py`:

- `AbsenceContext.coverage_incomplete` (new flag, no new public status) is set for
  `pagination_incomplete`; such claims classify as `not_retrieved`.
- `AbsenceContext.verified_scopes` / `present_scopes` carry the repositories that were
  actually checked. When scopes exist, `verified_absent` only applies to a sentence that
  names a verified repository and no repository with a positive observation.
  Contexts built without scopes keep the current object-level behaviour.
- qualifiers stay whole-sentence prefixes/suffixes; no mid-sentence insertion and no
  duplicated suffix.

## 3. Compatibility

- All new parameters are optional keyword-only with `None` defaults.
- `FakeIntelligenceModel`, fixtures, the Host Adapter protocol, Cost Ledger, CLI and
  legacy entry points are untouched.
- No historical run artifact is modified.
- `Status` semantics are unchanged; no verification step is removed.
- Deterministic-core rule: no `datetime.now` / locale in synthesis code; durations use
  `monotonic`, injected clock in tests.

## 4. Verification

1. `PYTHONPATH="$PWD/src" python -m pytest tests -q -m "not live"` — full offline suite.
2. New deterministic tests (see tasks T7).
3. `ruff check src scripts`.
4. `python scripts/check_repository.py`.
5. Real A/B on `industry-agents` with identical model, window, sources, budget and
   subquestions; output under `runs/rc/synthesis-runtime-2026-11-23/`.
   Report answer rate, fact-synthesis completion, citation support, elapsed, calls,
   input/cached tokens, degradation reasons and delivery level. No simulated claims.

## 5. Risks and rollback

- A larger reserve reduces the research window from ~273 s to ~239 s; round 2 may
  retrieve less. Mitigation: protected fact layer + delivery level; measure evidence
  count in A/B.
- Smaller per-cluster excerpt budgets may reduce contradiction quality. Mitigation:
  contradiction keeps the largest per-cluster budget (32 k chars); facts keep 3 k
  chars per item; all IDs and the full ledger are preserved.
- Scope-aware absence may downgrade some claims from verified to not-retrieved.
  Mitigation: conservative by design; explicit basis strings in the report.
- No parallelism is introduced: host calls mutate shared cost/usage state and the
  cost ledger is file-backed; bounded sequential execution with priority gates keeps
  wall-clock, call-count and cost accounting consistent. Batching contradiction and
  semantic factors into one call is documented as future work, not silently claimed.
