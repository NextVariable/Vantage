# Vantage Synthesis Runtime 2.0 独立终审

**RC HOLD · Beta**。新版在一次历史运行中完成了 FACT 层，保住了带引文的简报。默认 Codex Skill 的 STDIO 恢复、正向事实的证据支持，以及可绑定到提交的研究质量复验仍是发布门槛。

审查对象为 GitHub `dev/trae-research-quality` 的 `3576cc83f5eba92d7a6ae08c081b18a2eae955d7`，基线为 `4769cfa296fc1b5ac9bd21655d6883ff5b982021`。远端送审分支、main 和起始工作区均已核对。修复位于独立分支 `audit/synthesis-runtime-2`。

## P0 · 状态和正确性

| 缺陷与位置 | 根因、复现和影响 | 处理与回归 |
| --- | --- | --- |
| 执行降级返回成功 · [application/orchestrator.py](../src/sourceglint/application/orchestrator.py#L47)、[interface/result.py](../src/sourceglint/interface/result.py#L22)、[brief/dtos.py](../src/sourceglint/brief/dtos.py#L34)、[brief/sections.py](../src/sourceglint/brief/sections.py#L113) | 两个最终分支依据失败来源决定 `SUCCESS`。让推论或已请求的建议超时，仍有 FACT 时可看到成功。研究 deadline、规划回退和部分 FACT 损失也会漏传。简报标题还把有限交付写成“事实和引文完整”。外部软件据此可能把降级结果当作完整结果。 | **已修复。** 按实际阶段汇总执行状态，交付层与覆盖质量各自保留。公开 API 回归检查推论超时、建议失败以及 FACT 留存；用原有用例验证机会失败、空证据和正常路径。 |
| STDIO 前置超时导致 FACT 无法派发 · [host_stdio.py](../src/sourceglint/host_stdio.py#L26)、[intelligence/pipeline.py](../src/sourceglint/intelligence/pipeline.py#L79)、[synthesis_budget.py](../src/sourceglint/synthesis_budget.py#L156) | 旧桥接靠顺序匹配，不带请求 ID。一次读取超时会把流放入 `_expired_streams`，以避免迟到应答串帧。离线先让 contradiction 超时，再给 FACT 10 秒，得到两次 TIMEOUT、仅一条外发帧。即使数值上保留了 FACT 时间也无法使用。历史 A/B 走 `host-command:v1`，无法验证默认 Skill 入口的这一行为。 | **待 TRAE。** 为可恢复 Host 增加可协商的请求关联或可隔离的 transport，继续保留旧顺序协议。用真实管道注入迟到及同任务重复回复，验证只接收匹配帧，FACT 在剩余预算内正常完成。现有审计修复维持旧协议的防串帧保护。 |
| 局部预算和计数边界失真 · [synthesis_budget.py](../src/sourceglint/synthesis_budget.py#L156)、[application/api.py](../src/sourceglint/application/api.py#L312)、[intelligence/pipeline.py](../src/sourceglint/intelligence/pipeline.py#L163) | 父级截止本来会被上下文取最早值，但已耗尽的预算曾绕过合成封装。短窗口可没有 FACT 预留。四个建议任务的实际名称未映射，可能吃掉渲染时段。抛异常未计入尝试，阶段拒绝没进入 refusals，独立机会调用未单列。 | **已修复。** 有限预算在零秒仍启用；短预算保留一部分 FACT 时间；建议/GTM 保留简报余量；异常调用计一次，拒绝不计入派发；机会调用单列。测试覆盖过期父截止、短预算、建议抛超时、计数与 FACT 留存。预算约束依然需要 Host 配合。 |
| 分页及出处错误产生假阴性 · [connectors/_github_release.py](../src/sourceglint/connectors/_github_release.py#L270)、[connectors/github.py](../src/sourceglint/connectors/github.py#L270) | 三页均为空但仍有 next，会先落入 `verified_absent`。坏日期可能被误判为窗口外；创建时间不是发布时间。Tags 非数组曾被当成空列表，搜索元数据的 NOASSERTION 曾充当“无许可”。Link 也缺乏同仓库校验。 | **已修复。** 只对走完且记录有效的 endpoint 标记 verified_absent，并记录端点、仓库、页数、窗口和完成状态。next 限于 GitHub 同仓库端点，允许同仓库数值 ID 路径。首个命中提前结束仍可记为 present，并保留扫描未完状态。测试覆盖翻页命中、翻页封顶、外部 Link、坏时间与空页面。 |
| 自由文本继承无关的缺失证明 · [pipeline/absence.py](../src/sourceglint/pipeline/absence.py#L104)、[pipeline/adaptive.py](../src/sourceglint/pipeline/adaptive.py#L677)、[insights/facts.py](../src/sourceglint/insights/facts.py#L109) | 原逻辑将两个仓库的观测汇成跨对象的短名匹配，甚至可把窗口外记录变成错误的确定限定。分句会拆开版本和链接。未核验否定被贴上前缀后仍可进 FACT。复现用 `a/b has no releases`、别仓库观察及含版本和换行的句子。 | **已修复。** 结构化核验结果仅留在端点观测中。自由文本保留句子及边界并标记未证实；检测到的未核验否定进入拒绝诊断，覆盖缺口中的否定句继续附带范围限定。测试覆盖同名/异仓库、版本、URL、换行和 FACT 拒绝。检测是词法规则，语义广覆盖仍须证据验收。 |
| 合法证据 ID 可以挂在不受支持的正向事实后 · [insights/facts.py](../src/sourceglint/insights/facts.py#L109)、[insights/preparation.py](../src/sourceglint/insights/preparation.py#L86)、[brief/sections.py](../src/sourceglint/brief/sections.py#L144) | 现有规则验证 ID、归属、部分数字和措辞。离线把“The app runs fully offline in production”引用到仅描述网页工具栏换色的条目，`validate_fact` 返回空违规。事实模型的 excerpt 与 ID 也没有逐条配对。历史三条 FACT 有来源标注，厂商能力独立验证仍缺证据。 | **部分修复，仍阻断 RC。** 加入非空引文约束并取消“完整”承诺。待 TRAE 建立逐主张、逐 ID、可定位原文的支持契约，明确厂商自述及独立实测。回归需要合法但无关 ID、跨摘录拼接、伪造独立测试、同一厂商多条公告，以及有效引用正例。 |

### 对外语义

- `execution_status` / 旧 `status`：可用简报且必要阶段完成才是 `SUCCESS`；带可用输出的运行降级是 `PARTIAL`；无可用证据沿用 `NO_EVIDENCE`，执行失败沿用 `FAILED`。
- `delivery_level` 描述交付层级，带 FACT 的降级简报仍是 `evidence_backed_brief`。机会分析在简报完成之后运行，机会阶段失败可以使执行状态降级，已有简报层级仍可保留。
- `research_quality` 是覆盖规则结果，不能用简报或运行状态反推。旧 JSON `status`、`SkillResult.ok`、CLI 退出码和 STDIO 帧保持兼容。带有效降级简报仍走原 CLI 成功退出路径，自动化读取 JSON 可区分 `PARTIAL`。

## P1 · 排序与 A/B 可复核性

| 缺陷与位置 | 根因、复现和影响 | 处理与回归 |
| --- | --- | --- |
| 未评估相关性被当作低相关性 · [intelligence/factors.py](../src/sourceglint/intelligence/factors.py#L280)、[intelligence/signals.py](../src/sourceglint/intelligence/signals.py#L114)、[scoring.py](../src/sourceglint/scoring.py#L30) | semantic 跳过后相关性用 0.0 表示，但打分仍赋予它 35% 的权重。其余因子为 0.6 时，0.0 与 0.5 得分分别为 0.2514、0.5629。混合完成时，遗漏可压过真实排序差异，也影响弱信号判断。 | **待 TRAE。** 建立同一运行内一致的缺失因子策略，记录不可比较状态。回归应各放一个跳过和已评估但真实低相关的聚类，交换输入顺序并验证排名及弱信号。 |
| A/B 无法绑定提交，样本与口径变化 · [run_real_benchmark.py](../scripts/run_real_benchmark.py#L149)、[specs/synthesis-runtime-2/tasks.md](../specs/synthesis-runtime-2/tasks.md#L112) | 两份都是 dirty checkout，HEAD 分别记为 `66e4251` 和 `4769cfa`。问题、时间、模型标签、配置文本、总预算相同，但实际内部研究预算 282→250 秒，证据量与分析内容不同。用任一回执里的一次运行无法推出可重复质量提升。 | **待 TRAE。** 先用同一冻结 ledger 和相同 Host 信息作双臂离线重放，再根据授权在干净 SHA 上跑一项有限真实复测。回归验收应拒绝 dirty 运行作为提交级发布凭证，同时公布 phases、scope 和 stdout 运行器类型。 |
| 阶段预算主要是协作式而非硬保证 · [deadline.py](../src/sourceglint/deadline.py#L9)、[insights/pipeline.py](../src/sourceglint/insights/pipeline.py#L101) | 子 deadline 会取父级最早值，clustering/contradiction 可消耗全部非保留窗口。推论 `inference_reserve_seconds` 是调度留量而非调用上限，历史推论调用约 24.75 秒即可复现这种差别。渲染与不读取 deadline 的宿主无法被强制中断。 | **保留协作式约束。** 待 TRAE 明确支持的 Host 契约及提前拒绝策略。测试应复现协作/不协作 Host、阶段总预算、Fact 有效派发、以及超时后 FACT 留存。 |

### 原始 A/B 复查

本地记录分别为 `runs/rc/rq-sprint-2026-11-22-r2/industry-agents` 与 `runs/rc/synthesis-runtime-2026-11-23/industry-agents`。检查了 run、status、result、brief、ledger 及 `host.usage.jsonl`。两边都是 `gpt-6.1-sol` 标签、2026-11-22 00:00 UTC 截止、30 天、相同题目与 registry 内容。两个 `host.events.jsonl` 均为空，使用量明细来自命令式 Host。

| 指标 | 旧记录 | 新记录 |
| --- | ---: | ---: |
| 引擎用时 / harness 用时 | 345.01 / 345.16 s | 343.51 / 343.73 s |
| `host.usage.jsonl` 记录数 | 10 | 7 |
| 有正耗时的记录 / 成功回复 | 6 / 5 | 7 / 5 |
| FACT / 推论 | 0 / 0 | 3 / 0 |
| 引擎自判研究子问题 | 3 partial | 2 partial、1 unanswered |
| `research_quality` | LIMITED | LIMITED |

旧记录的 10 次包含 4 次 0ms 截止超时。新版取消了五条 semantic 记录，并增加第二次 coverage 尝试和一次推论尝试。记录数下降，成功回复数持平，不能据此断言实际付费调用减少。新版的三条 FACT 分别是 OpenCode Plus 项目方发布材料、gitoodo 项目的一手自述、AgentMCTS 第三方视频描述。现存简报做了来源归因，实测性能和独立使用结果仍待补证。复核时三个选定原页均无法重新打开，未把本地 ledger 匹配算作原页验证。

## P2 · 诊断口径

- [synthesis_budget.py](../src/sourceglint/synthesis_budget.py#L241) 的字符估算不是计费 token，尤其不能把中、日、英混合文本按统一四字符换算后比较成本。`model_io` 是合成期派发尝试，而 `host_usage` 是底层 Host 截至该阶段的累计快照。复现可对比历史新版的 synthesis 4 条与 Host 累计 7 条。已单列机会尝试。待 TRAE 给每种指标标注范围和来源，回归应覆盖缓存命中、早拒绝、上游阻断、异常和未知账单。
- [brief/dtos.py](../src/sourceglint/brief/dtos.py#L34) 是渲染输入，继续承载交付层级。它无需推断执行结果。保持公开 JSON 三个字段各自有测试，避免 CLI 成功退出隐式代表质量达标。

## 验证与最小剩余工作

送审 HEAD 的本地基线为 2,338 项通过、14 项联网用例跳过。[送审 GitHub Actions](https://github.com/NextVariable/Vantage/actions/runs/45048277539) 已成功。审计修复本地 2,347 项通过、14 项跳过，另运行 lint 和仓库检查。本轮未消耗模型额度重跑真实研究。

1. 修默认 STDIO 超时恢复或提供兼容的可隔离 Host，证明超时后 FACT 状态和派发一致。
2. 增加逐主张的支持验证和独立使用证据约束，拿合法但无关的引用做负例。
3. 用冻结证据作对照，先验证缺失相关性的排序规则，再在干净 SHA 上用受控流程复验，并独立评分。真实复测以用户授权为前提。
