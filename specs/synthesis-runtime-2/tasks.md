# Synthesis Runtime 2.0 — Tasks

Each task is implementable and verifiable on its own. All edits stay on
`dev/trae-research-quality`; no main merge, no release.

## [x] T1 — Budget core

Files: `src/sourceglint/synthesis_budget.py` (new)

- `STAGE_ORDER`, `STAGE_PRIORITY`, `TASK_TO_STAGE`.
- `StageState` (status, seconds, calls, reasons) and `SynthesisBudget`
  (`from_remaining`, `remaining`, `stage_deadline`, `allow`, `mark_stage`,
  `record_refusal`, `to_dict`).
- Gate table from spec §2.1; injectable `clock`.
- `MeteredModel` delegating `model_id` / `complete_structured`, recording
  calls, elapsed, payload chars, approx tokens, and host usage when available.
- Refusal response: `ModelResponse(UNAVAILABLE, error="synthesis budget: <stage> ...")`.

Verify: unit tests T7.1–T7.3.

## [x] T2 — Intelligence pipeline wiring

Files: `src/sourceglint/intelligence/pipeline.py`, `intelligence/factors.py`

- Add `budget` keyword to `run_intelligence_pipeline`.
- Wrap clustering / contradiction in `deadline_scope(budget.stage_deadline(...))`.
- Semantic loop: check `budget.allow("semantic_factors")`; on refusal call
  `derive_factors(..., semantic_reason="semantic factors skipped: budget")`.
- `derive_factors(..., semantic_reason: str = "")` skips the model and uses the reason.
- `mark_stage` statuses: `ok`, `degraded`, `skipped`, `failed`.

Verify: T7.2, T7.3.

## [x] T3 — Insight pipeline wiring

Files: `src/sourceglint/insights/pipeline.py`, `insights/facts.py`,
`insights/inferences.py`, `insights/gtm_implications.py`

- Add `budget` keyword; wrap fact/inference/GTM model calls in stage deadlines.
- Facts always run first; inference and GTM are skipped when the gate refuses and
  record a degradation reason.
- Keep `prepare_signals` safety rule unchanged.

Verify: T7.4.

## [x] T4 — Orchestrator and progressive delivery

Files: `src/sourceglint/application/orchestrator.py`, `brief/dtos.py`,
`brief/sections.py`

- Create the budget from `remaining_time()` before Phase 5; wrap `ctx.model` in
  `MeteredModel`; pass `budget` into both pipelines.
- `ApplicationResult.delivery_level` and `ApplicationResult.synthesis`.
- Compute level from fact count + inference/GTM status + core stage statuses.
- `BriefContext.delivery_level`; one deterministic line in `research_context` for
  `evidence_backed_brief` / `evidence_only_report`; `full_brief` unchanged.
- Every early return path sets the level (`no_evidence`, `evidence_only_report`).

Verify: T7.5, T7.6.

## [x] T5 — Dynamic reserve and packaging

Files: `src/sourceglint/application/api.py`, `interface/result.py`

- Replace `_synthesis_reserve` with the formula in spec §2.5 (subquestions included).
- Record subquestions / expected calls / decision-support in the reserve basis.
- `diagnostics["delivery_level"]`, `diagnostics["synthesis"] = budget.to_dict()`.
- `SkillResult.delivery_level` (default `""`), included in `to_dict()` when non-empty.

Verify: T7.7.

## [x] T6 — Absence scope and pagination

Files: `src/sourceglint/connectors/_github_release.py`,
`src/sourceglint/pipeline/absence.py`

- `Link` header parsing, up to 3 pages, stop on first in-window release.
- `pagination_incomplete` status; `only_outside_window` only when complete.
- `AbsenceContext.coverage_incomplete`, `verified_scopes`, `present_scopes`.
- Scope match by repo full name or short name; unscoped claims are not verified.
- Whole-sentence qualifiers only.

Verify: T7.8–T7.10.

## [x] T7 — Deterministic regressions

File: `tests/unit/test_synthesis_runtime.py` (new) and targeted additions to
`tests/unit/test_research_quality_repairs.py`.

1. Gate: semantic refused when only fact reserve remains; fact call still allowed.
2. Slow contradiction with fake clock: semantic skipped, fact synthesis called.
3. Metered calls/char counts and refusal reasons are recorded.
4. Facts without inference → `evidence_backed_brief`; no facts → `evidence_only_report`.
5. Full success → `full_brief`; no-evidence → `no_evidence`.
6. Reserve grows with subquestions and respects the 45 % cap.
7. `model_payloads(content_budget=...)` bounds content without dropping IDs.
8. Pagination: page 2 in-window release is found; incomplete pagination is not
   `only_outside_window`.
9. Absence: verified repo A does not verify a sentence about repo B / no repo.
10. Baseline timing simulation (49.6 / 15 / 11.7) → fact synthesis attempted.

## [x] T8 — Offline verification

```
PYTHONPATH="$PWD/src" python -m pytest tests -q -m "not live"
ruff check src scripts
python scripts/check_repository.py
```

Fix all regressions before T9.

## [x] T9 — Real A/B benchmark (conditional on authorized Codex Host)

- Command identical to the baseline, `--seconds 355`, `--only industry-agents`,
  same model `gpt-6.1-sol`, same window and sources.
- Output: `runs/rc/synthesis-runtime-2026-11-23/industry-agents/`.
- Record: answer rate, fact-synthesis completion, citation support, elapsed, calls,
  input/cached tokens, degradation reasons, delivery level, status.
- If the host is unavailable or credits are insufficient, report that explicitly and
  do not claim a real improvement. No self-funded purchase.

## [x] T10 — Commit, push, CI, report

- Commit + push `dev/trae-research-quality`.
- Verify GitHub CI.
- Final report: SHA, modules, structural fixes, A/B results, fact completion,
  citation check, performance, new/residual risks, Codex-audit recommendation.

## Acceptance criteria

- Fact synthesis is never refused because semantic factors or GTM consumed the budget.
- Low-priority stages degrade with a recorded reason instead of silently failing.
- `delivery_level` is present and never upgrades a PARTIAL run to SUCCESS.
- Full evidence ledger is preserved; no unverified claim becomes definite.
- Offline suite, ruff and repository check pass.
- No historical run artifact is modified.
