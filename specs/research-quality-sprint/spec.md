# Spec — Research Quality Sprint（首次真实研究缺陷修复）

- 仓库：NextVariable/Vantage（本地 `sourceglint`）
- 分支：`dev/trae-research-quality`
- 基线：`66e4251901563ec2ac62344a10dd616bce50d4bf`
- 真实基线产物（只读，不得修改）：`runs/rc/beta-real-codex-2026-11-22/case6/industry-agents/`
- 范围：P0 证据目标检索、P0 否定性结论验证、P1 渲染质量、P1 调用效率、离线与真实验收
- 非范围：SaaS/Dashboard/监控；账本与 Host 架构重构；历史运行结果改写

## 0. 已确认的根因（来自基线产物与代码）

1. `connectors/github.py::GitHubAdapter.retrieve` 只调用 `/search/repositories`，每条记录 `source_type="page"`，`published_at=repo.created_at`。
   - 仓库"存在"被当成"发布物不存在"的证据。
   - 未调用 `/repos/{owner}/{repo}/releases`，因此 `Azx8788/opencode-plus` 的 v0.3.25（2026-11-17）、v0.3.26/v0.3.27（2026-11-21）全部漏检。
2. 仓库搜索窗口用 `created:` 限定，语义上是"仓库创建时间"，不是"发布/活跃时间"；release 意图的问题会被错误收窄。
3. `pipeline/adaptive.py` 把模型 `gap` 与确定性补充句用 `" ".join(...)` 拼接；模型 gap 被 Host 在 240 字符处按词截断且无终止标点，产生
   `... awaits its first No evidence of the required kind ...` 粘连。
4. `brief/sections.py::_untrusted_inline` 先 `html.escape` 再用 `([\\`*_{}\[\]()#+.!|])` 全量转义：
   - `code\.`、`\(s\)`、`vendor\_claim\_verified` 等多余反斜杠；
   - 源文本中的 `&` 被转成 `&amp;`（HTML 实体未解码）；
   - 仍未处理"截断句 + 确定性句子"的边界。
5. 模型生成的否定性结论（如 "no coding-agent candidate has a dated release artifact"）没有任何缺失状态模型，直接进入 `research_questions` 的 gap 与最终 brief，无法区分"已核查不存在 / 未检索到 / 数据源不可用 / 窗口内未发现 / 未核实"。
6. 调用审计：11 次 = planning 1 + coverage 1 + clustering 1 + contradiction 3 + semantic_factors 3 + fact_synthesis 1 + inference_synthesis 1。`contradiction` 对单成员 cluster 也发起模型调用，属于可确定性跳过；其余语义调用暂无安全删减依据。

## 1. P0 — 面向证据目标的 GitHub 检索

### 1.1 新模块 `src/sourceglint/connectors/_github_release.py`

```python
@dataclass(frozen=True)
class ReleaseOutcome:
    results: list[RawSourceResult]
    observations: list[dict]     # 缺失/失败事实，非证据
    limitations: list[str]

def release_intent(plan, request) -> bool
def fetch_releases(http_client, repos, *, headers, per_repo, max_repos,
                   window, checked_at) -> ReleaseOutcome
def fetch_tags(http_client, repo, *, headers, max_tags) -> dict | None
```

- `release_intent`：扫描 `request["query"]`、`request.get("evidence_goals")`、`plan` 的 `topic` / `subquestions[].question`，命中 release/released/version/changelog/tag/artifact/publish/发布/版本/发行/更新日志 等词即 True。
- `fetch_releases`：
  - 仅对本次搜索已返回的候选仓库调用，最多 `max_repos=5`，每仓 `per_repo=10`；不新增无关数据源。
  - URL：`https://api.github.com/repos/{full_name}/releases?per_page={per_repo}`。
  - 每条 release 生成 `RawSourceResult`：
    - `source_type="release"`
    - `source_native_id=f"release:{full_name}:{release_id or tag_name}"`
    - `title=f"{full_name} {tag_name}"`；`text=body or name or tag_name`
    - `published_at = release.published_at or release.created_at`（发布优先；缺失则跳过该条并记 limitation，不用仓库创建时间顶替）
    - `raw_metadata`：`github_full_name`、`github_kind="release"`、`github_release_id`、`github_tag_name`、`github_release_published_at`、`github_release_created_at`、`github_repo_created_at`、`github_prerelease`、`github_draft`、`version_source="release_published_at"`
  - 每条 observation：
    - 有窗口内 release → `status="present"`
    - 有 release 但全部在窗口外 → `status="only_outside_window"`
    - API 返回空列表 → `status="verified_absent"`（限定该仓库、该端点）
    - 404 → `not_found`；401 → `auth_missing`；403/429 → `rate_limited`；超时 → `timeout`；其他 → `unavailable`；JSON/结构异常 → `invalid_response`
    - 统一字段：`kind="releases"`、`repository`、`count`、`checked_at`、`detail`
  - releases 为空且 `release_intent` 时，对最多 3 个仓库调用 `/tags`，只返回 observation（`kind="tags"`、`status="present"|"verified_absent"`），不伪造 tag 日期，不生成证据。
- 错误分类复用现有 adapter 异常；403 视为 `rate_limited`（与 `github.py` 现行策略一致）。

### 1.2 修改 `src/sourceglint/connectors/github.py`

- 新增 dataclass 字段（保持既有构造调用兼容）：
  - `max_release_repos: int = 5`
  - `release_per_repo: int = 10`
  - `absence_observations: list[dict] = field(default_factory=list, compare=False)`
- `retrieve()` 开头 `self.absence_observations.clear()`。
- 计算 `intent = release_intent(plan, request)`；当 `intent` 且 `_recency.search_bounds` 有界时，搜索限定词由 `created:` 改为 `pushed:`（活动时间），避免把"窗口内发布但仓库更早创建"排除。
- 仓库结果补充 `raw_metadata`：`github_license_spdx`、`github_license_name`、`github_created_at`、`github_kind="repository"`。
  - `license is null` → observation `kind="license", status="verified_absent"`；有 license → `status="present"`。
- 候选排序：`pushed_at` 降序，其次 `stargazers_count` 降序；取前 `max_release_repos` 调 `fetch_releases`。
- 将 release results 追加到返回值，observations/limitations 合并到实例列表。

### 1.3 修改 `src/sourceglint/pipeline/orchestrator.py`

- `_retrieve_batch` 在每次 `adapter.retrieve` 后读取 `getattr(adapter, "absence_observations", ())`，累计到 run 级列表。
- `run()` 调用 `build_coverage_report(..., absence_observations=...)`。
- 将 absence observations 传入自适应评估（`AdaptiveResearch.assess(..., absence_observations=...)`），供否定性结论分类。

### 1.4 修改 `src/sourceglint/pipeline/coverage.py`

- `CoverageReport` 新增 `absence_observations: tuple[Mapping[str, object], ...] = ()`，`to_dict()` 输出 `absence_checks`。
- `gaps` 只对确定性事实生成文字：
  - `GitHub Releases: {repo} — API returned zero releases (verified absent)`
  - `GitHub Releases: {repo} — releases exist only outside the research window`
  - `GitHub Releases: {repo} — {status}`（rate_limited/auth_missing/timeout/unavailable/not_found）
- 不把 `not_retrieved` / `unverified` 写成"不存在"。

## 2. P0 — Negative Claim Verification

### 2.1 新模块 `src/sourceglint/pipeline/absence.py`

状态常量：

```python
VERIFIED_ABSENT   = "verified_absent"      # 已核查且证实不存在（限定范围）
NOT_RETRIEVED     = "not_retrieved"        # 未检索到
SOURCE_UNAVAILABLE= "source_unavailable"   # 数据源不可用
OUT_OF_WINDOW     = "out_of_window"        # 研究窗口内未发现
UNVERIFIED        = "unverified"           # 尚未核实
```

API：

```python
def detect_absence_claims(text: str) -> tuple[AbsenceClaim, ...]
def classify_absence(obj: str, *, verified_absent: bool, source_unavailable: bool,
                     window_checked: bool, searched: bool) -> str
def qualify_text(text: str, *, context: AbsenceContext) -> tuple[str, tuple[dict, ...]]
```

- 识别对象：release/releases/artifact/tag/version/changelog/license/feedback/competitor/发布/版本/许可证/反馈/竞品。
- 否定模式：`no|none|never|zero|without|there is no|there are no|没有|无|尚未` + 对象名词。
- 反例排除：`no longer`、`no doubt`、`no fewer than`、`not only`、`no less than` 不视为缺失断言。
- `qualify_text` 对每个句子：
  - `verified_absent` → 原样保留，附 basis。
  - `OUT_OF_WINDOW` → 前缀 `Within the research window: `。
  - `SOURCE_UNAVAILABLE` → 前缀 `Absence not verified (source unavailable): `。
  - `NOT_RETRIEVED` / `UNVERIFIED` → 前缀 `Unverified absence: `，句末追加 ` (absence not established; scoped to retrieved evidence)`。
  - 改写只动前缀/后缀，不改写原句事实内容；返回 machine-readable `checks`。

### 2.2 传播点

- Planner prompt（`pipeline/` 中 planner prompt 模板）：新增规则"Do not state that an object does not exist unless a deterministic check verified absence; describe what would verify it."
- Assessment（`pipeline/adaptive.py`）：gap 先 `qualify_text`，再写入 row；row 增加 `absence_checks`。
- Fact / Inference 合成（`insights/facts.py`、`insights/inferences.py`）：解析出的 `draft.statement` 过 `qualify_text`（无确定性核验上下文 → UNVERIFIED 前缀）。
- Brief（`brief/sections.py`）：`research_questions` 渲染 `absence_checks`，格式 `  - absence: <object> → <status>`；不得输出无状态的确定性缺失。

### 2.3 测试

- `tests/unit/pipeline/test_absence.py`：5 种状态分类；`no longer` 等反例；真实 gap 文案
  `no coding-agent candidate has a dated release artifact` 必须变成非确定性表述。
- `tests/unit/insights/test_negative_claims.py`：fact/inference 中的缺失断言被限定。
- `tests/unit/brief/test_renderer.py` 增加：brief 不出现未限定的 "no ... release"。

## 3. P1 — 报告输出质量

修改 `src/sourceglint/brief/sections.py`：

1. `_untrusted_inline`：
   ```python
   text = html.unescape(_inline(text))
   text = text.replace("&", "&")  # 不解码/不再实体化普通 &
   text = text.replace("<", "&lt;").replace(">", "&gt;")
   text = re.sub(r"([\\`*_\[\]#])", r"\\\1", text)
   ```
   - 不再转义 `.` `(` `)` `!` `+` `|` `{` `}`。
   - 保留 `<`/`>` 实体化与 `[`/`]`/`` ` ``/`*`/`_`/`#`/`\` 转义，防止 Markdown/HTML 注入。
   - `html.unescape` 在转义前执行，保证 `&amp;` 显示为 `&`。
2. `pipeline/adaptive.py::_join_gap(gap, addition)`：
   - 若 gap 不以 `.!?;:。！？；：` 结尾，补 `.`；
   - 若 gap 长度 >= 238 且无终止标点，末尾补 ` …`（显式截断）；
   - 再与确定性补充句以空格连接。
3. 引用一致性：`_ref` 保持 `[source] (url) · date \`ev_id\``；`sources` 注册表统一为 `` `ev_id` — [source] (url) · date ``，确保正文 ID 可在 Sources 中一一对应（按现有测试格式微调，不破坏排序/去重断言）。
4. 新增 `tests/unit/brief/test_rendering_quality.py`：
   - 传入含 `code.`、`direct observation(s)`、`Official Build & Verified`、`&amp;` 的 gap/statement，断言无 `\.`、`\(`、`&amp;`；
   - 断言 `<script>` 仍被实体化、`[x] (y)` 仍被转义；
   - 断言截断 gap + 补充句之间不粘连（出现 `. ` 或 ` … `）。

## 4. P1 — 模型执行效率

- `intelligence/contradiction.py`：`len(member_ids) < 2` 时确定性返回
  `ContradictionAssessment(cluster_id, supporting=members, counter=(), kind="none", confidence=0.0, rationale="single-member cluster; contradiction not assessable", degraded=False)`，不调用模型。
- 保持 clustering / semantic_factors / fact_synthesis / inference_synthesis 的调用数不变（必要核验，不删减）。
- 记录并输出：调用次数、有效输入 tokens、cached tokens、E2E 秒数（沿用 `host.usage.jsonl` 与 `status.json`）。
- 新增 `tests/unit/intelligence/test_contradiction_skip.py`：单成员 cluster 不触发 `complete_structured`。

## 5. 验收

### 5.1 离线确定性回归（必须）

- 用真实漏检案例构造 fixture：`Azx8788/opencode-plus` Releases 返回 v0.3.25/v0.3.26/v0.3.27；另外两个候选返回 `[]`。
- 断言：
  1. 产生 3 条 `source_type="release"` 证据，`published_at` 分别为 2026-11-17 / 2026-11-21，URL 指向 release 页面，metadata 含 repo、tag、release_published_at、repo_created_at；
  2. 零 release 仓库产生 `verified_absent` observation，且不产生"全局无 release"结论；
  3. 404/403/429/超时分别映射为 `not_found`/`rate_limited`/`rate_limited`/`timeout`；
  4. 真实 gap 文案被限定，brief 不再出现确定性否定；
  5. 渲染无多余反斜杠、无未解码实体、无截断粘连。
- 运行：`PYTHONPATH="$PWD/src" python -m pytest tests -q -m "not live"`、`ruff check src scripts`、`python scripts/check_repository.py`。

### 5.2 真实端到端（条件性）

- 仅当已授权 Codex Host 可用、预算允许时，用 `runs/rc/codex_host_bridge.py` + `--budget-mode observe` 重跑一次 `industry-agents`。
- 必须证明：窗口内 Release 被发现；无错误否定性结论；引用可追踪原始 URL；两个核心子问题质量不下降；渲染改善；调用与成本有真实记录。
- 若不可用，明确说明阻塞原因；不得用模拟结果宣称真实质量提升。

### 5.3 交付

- 提交并推送 `dev/trae-research-quality`；不合并 `main`，不发布正式 Release。
- 报告：Commit SHA、根因与关键文件、离线/真实结果、基线与新版对照、正确性改进、性能与调用变化、剩余缺陷、是否建议 Codex 独立审核。

## 6. 风险与边界

- 不修改 `runs/rc/beta-real-codex-2026-11-22/` 下任何历史文件。
- 不自动充值、不绕过供应商权限。
- Release 检索只限本次搜索命中的仓库，最多 5 个；tags 仅作零 release 时的范围核验，最多 3 个。
- 缺失状态改写不删除原句，只加限定前缀/后缀，避免误删真实信息。
