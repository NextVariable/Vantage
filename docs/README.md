# Vantage 文档 · Documentation

## 使用与安装 · Getting started

- [中文使用说明](../README.zh-CN.md) · [English guide](../README.md)
- [Beta 1 预发布与固定标签安装 · Published Beta](https://github.com/NextVariable/Vantage/releases/tag/v1.0.0b1)
- [宿主 Skill 入口 · Skill entry](../SKILL.md) · [交互协议与证据导出 · Host protocol](../references/host-protocol.md)

## 数据源与授权 · Sources and access

- [来源访问与统计口径 · Source coverage and counting rules](source-access-matrix.md)
- [账号、凭据与授权步骤 · Authorization](source-authorization.md) · [失败降级 · Fallbacks](source-fallback-playbook.md)
- [验收快照 · Dated verification snapshot](source-live-status.json) · [平台探针和原始样本 · Host probe records](host-web-verification-tasks.json)

## 当前架构与维护 · Current architecture and maintenance

- [运行架构 · Architecture](architecture.md) · [自适应研究、预算和停止条件 · Adaptive research](adaptive-research.md)
- [测试、安装检查与真实研究验收方式 · Validation](validation.md) · [仓库、分支与许可 · Repository guide](repository-guide.md)
- [1.1 实施规格 · Expansion specification](../specs/vantage-1.1/spec.md) · [实施记录 · Task record](../specs/vantage-1.1/tasks.md) · [第二阶段计划 · Phase 2 plan](../specs/vantage-1.1-phase2/plan.md)

## 真实研究 · Recorded research

- [1.1 最新真实案例 · Latest 1.1 runs](source-expansion-1.1.md#two-real-vantage-reports)，日本会议纪要产品发布、Otter 用户反馈。Read the reported status, quality and coverage limitations with each result.
- [1.0 Beta 四类真实研究 · Four published-Beta cases](examples/beta-final-2026-11-24/README.md)
- [1.0 使用示例与运行方式 · Worked prompts and invocation](examples/vantage-1.0.md)

## 当前发布与验收 · Release and acceptance

- [变更日志 · Changelog](../CHANGELOG.md)
- [1.1 Phase 3 实测验收 · Development acceptance](source-expansion-1.1.md#phase-3-codex-host-acceptance-2026-11-24)
- [1.0 Beta 最终验收及历史复验 · Published Beta closure](beta-final-closure.md)

## 历史档案 · Historical record

保留原路径，供复现及引用。各文档的版本、状态和结论以当时的记录为准。 Files stay at their original paths so references and reproducibility checks keep working.

| 记录 · Record | 原始入口 · Original records |
| --- | --- |
| 早期发布与真实样例 · Earlier release and runs | [v0.2.1](releases/v0.2.1.md) · [2026-10-04 样例](examples/2026-10-04/README.md) · [较早的 Beta 样例索引](examples/beta-2026-11-23/README.md) |
| 1.0 开发与研究质量 · Development and quality review | [1.0 审计](vantage-1.0.md) · [RC 审阅](rc-release-readiness.md) · [质量评估与失败分析](rc-quality-review.md) · [探索性案例](examples/rc/README.md) |
| Beta 与 Synthesis Runtime · Audits and interim acceptance | [阶段性 Beta 验收](beta-acceptance.md) · [Synthesis Runtime 2 审计](synthesis-runtime-2-audit.md) · [最终验收中的复验记录](beta-final-closure.md) |
| 设计与开发决策 · Design and implementation history | [ADR 索引](adr/README.md) · [研究质量规格](../specs/research-quality-sprint/spec.md) · [研究质量任务](../specs/research-quality-sprint/tasks.md) · [Synthesis Runtime 规格](../specs/synthesis-runtime-2/spec.md) · [Synthesis Runtime 任务](../specs/synthesis-runtime-2/tasks.md) |
| 评测题、评分和结果 · Evaluation inputs and outputs | [Beta 四题](../evals/beta-acceptance.json) · [RC 题库](../evals/rc-benchmark.json) · [评分标准](../evals/rc-rubric.md) · [RC 结果](../evals/rc-results.json) · [1.0 实测题库](../evals/vantage-1.0-live.json) · [1.0 结果](../evals/vantage-1.0-results.json) · [自适应回放题](../evals/adaptive-research.json) · [检索矩阵](../evals/retrieval-matrix.json) |

本地原始研究输出放在 Git 忽略的 `runs/`。Keep private or unreviewed run data in ignored `runs/`.
