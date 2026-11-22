# Tasks — Research Quality Sprint

执行顺序按依赖排列。每项完成后运行对应测试；最后统一跑全量。

## [x] T1. 新增否定性事实状态模型
- 新建 `src/sourceglint/pipeline/absence.py`
  - 状态常量：`VERIFIED_ABSENT` / `NOT_RETRIEVED` / `SOURCE_UNAVAILABLE` / `OUT_OF_WINDOW` / `UNVERIFIED`
  - `AbsenceClaim`、`AbsenceContext`、`detect_absence_claims`、`classify_absence`、`qualify_text`
  - 反例：`no longer` / `no doubt` / `no fewer than` / `not only`
- 新建 `tests/unit/pipeline/test_absence.py`：
  - 5 状态分类
  - 真实句 `no coding-agent candidate has a dated release artifact`
  - 反例不误判

## [x] T2. 新增 GitHub Releases 证据检索
- 新建 `src/sourceglint/connectors/_github_release.py`
  - `release_intent(plan, request)`
  - `fetch_releases(...)` → `ReleaseOutcome(results, observations, limitations)`
  - `fetch_tags(...)` 仅在 releases 为 0 时返回 observation
  - 时间语义：`release.published_at` → `release.created_at`，绝不用 repo `created_at`
  - 失败分类：404 / 401 / 403 / 429 / timeout / unavailable / invalid_response
- 新建 `tests/unit/connectors/test_github_releases.py`（fixture 复现 opencode-plus 漏检）

## [x] T3. 接线 GitHubAdapter
- 修改 `src/sourceglint/connectors/github.py`
  - 新字段 `max_release_repos`、`release_per_repo`、`absence_observations`
  - release 意图时搜索限定改用 `pushed:`
  - repo metadata 增补 license / created_at / kind
  - 调 `fetch_releases`，合并结果与 observations
- 扩展 `tests/unit/connectors/test_github.py`

## [x] T4. 覆盖率与 orchestrator 传递
- 修改 `src/sourceglint/pipeline/coverage.py`
  - `absence_observations` 字段、`absence_checks` 输出、精确 gap 文案
- 修改 `src/sourceglint/pipeline/orchestrator.py`
  - `_retrieve_batch` 收集 absence observations
  - `run()` 传给 coverage 与 adaptive
- 新建/扩展 `tests/unit/pipeline/test_coverage.py` 断言 absence 文案不夸大

## [x] T5. Assessment 使用否定性状态
- 修改 `src/sourceglint/pipeline/adaptive.py`
  - gap 过 `qualify_text`
  - `absence_checks` 写入 assessment row
- 新建 `tests/integration/test_negative_claim_propagation.py`

## [x] T6. Fact / Inference / Planner 传播
- 修改 `src/sourceglint/insights/facts.py`、`src/sourceglint/insights/inferences.py`
  - 解析后的 `statement` 过 `qualify_text`
- 修改 planner prompt 模板（`src/sourceglint/pipeline/` 内实际 planner 位置）
  - 增加"不得断言不存在，除非确定性核验"规则
- 新建 `tests/unit/insights/test_negative_claims.py`

## [x] T7. 渲染质量修复
- 修改 `src/sourceglint/brief/sections.py`
  - `_untrusted_inline`：先 `html.unescape`，`<`/`>` 实体化，仅转义 Markdown 结构字符
  - `research_questions` 渲染 `absence_checks`
  - Sources 与正文 ID 映射一致
- 修改 `src/sourceglint/pipeline/adaptive.py` 的 gap 拼接（`_join_gap`）
- 新建 `tests/unit/brief/test_rendering_quality.py`

## [x] T8. 调用效率
- 修改 `src/sourceglint/intelligence/contradiction.py`
  - 单成员 cluster 确定性返回，不调模型
- 新建 `tests/unit/intelligence/test_contradiction_skip.py`
- 不删减 clustering / semantic_factors / fact_synthesis / inference_synthesis

## [x] T9. 全量验证
- `PYTHONPATH="$PWD/src" python -m pytest tests -q -m "not live"` → 2322 passed, 14 skipped
- 针对性联网测试（`tests/live/test_live_github.py`）→ 1 passed
- `ruff check src scripts` → All checks passed
- `python scripts/check_repository.py` → PASS (420 files, 111 local links)
- 安全检查：渲染注入用例、无 token 泄漏

## [x] T10. 真实复测（条件性）
- Codex Host 可用（`gpt-6.1-sol`，`--budget-mode observe`，未充值/未改权限）
- 第一次 `--seconds 330`：`NO_EVIDENCE`，coverage 仅剩 25s 而超时；已保留产物
- 第二次 `--seconds 355`（与基线成功案例同参数）：`PARTIAL`，345.01s，10 次 host 记录
- 已发现窗口内 3 个 `Azx8788/opencode-plus` Release（v0.3.25+33/v0.3.26+34/v0.3.27+35）
- 否定性结论被限定为 `Unverified absence` / `absence: release → not_retrieved`
- 已完成调用：planning 43.1s、coverage 34.4s、clustering 49.6s、contradiction 15.0s、semantic_factors 11.7s
- 剩余缺陷：49 条证据进入 synthesis 后，fact_synthesis 在 345s 总时限内被截断（4 次调用在 deadline 后被拒）

## [x] T11. 提交与交付
- 提交并推送 `dev/trae-research-quality`
- 不合并 `main`，不发布 Release
- 输出交付报告（SHA、根因、对照、剩余缺陷、审核建议）
