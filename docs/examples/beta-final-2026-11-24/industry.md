# 行业研究｜AI Coding Agent 的新发布

2026-11-24 08:15 UTC 截止，全球英文，30 天。以下是 Vantage 在干净提交 `6da52f7` 上的真实输出摘要，另附独立来源复核。运行返回 `PARTIAL / evidence_backed_brief / LIMITED`。

- GitHub 公布 Copilot Fusion 正式可用，用于在 Copilot 内选择并编排模型。这是具体产品变化，证据来自 GitHub 自己的更新日志。 [GitHub Copilot Fusion](https://github.blog/changelog/2026-10-28-route-and-orchestrate-models-with-github-copilot-fusion/)
- Replit 宣布 Missions，并把代理协作、任务预算和边界控制写入产品说明。该信息适合用来追踪产品方向，性能和稳定性仍缺独立测试。 [Replit Missions](https://replit.com/blog/introducing-replit-missions)
- 报告还收录了 llama.cpp 的 Hy4 Flash 集成提案。它属于技术线索，需要另核合并状态和发行版本。

独立复核确认 GitHub 原文支持发布状态，Replit 页面可打开并确认为厂商说明。纳入的资料足以说明部分具体更新，无法估计采用率或证明实测改善。GitHub Releases 和部分评论访问受限。原始记录保留在本地 `runs/rc/beta-final-live/industry-coding-releases/`。

## 最终代码复验

`b59a5e9` 在同一截止时刻另跑一条面向开发团队的 30 天题。返回 `PARTIAL / evidence_backed_brief / LIMITED`，账本 4 条，报告产生 4 条事实性发现，其中 2 条经过 Host 的语义支持判断。

独立复核确认 GitHub 的三项说明：JetBrains 的 Copilot cloud sandbox 在 GitHub 托管隔离环境执行并分批推出；Copilot app 从 1.2.0 起兼容已正式推出的 GHES 支持；更新后的云端公告说沙箱自 11 月 23 日计入适用的 Actions 用量额度。厂商文档可用于判断功能范围、部署和用量变化，实测稳定性与使用成效仍待验证。报告把通用网页路由上的这些一手公告标为 T4，故其“缺少 T1”属于分级限制。 [JetBrains 更新](https://github.blog/changelog/2026-11-17-github-copilot-in-jetbrains-ignite-releases/) · [Copilot app 更新](https://github.blog/changelog/2026-11-17-github-copilot-app-microsoft-ignite-releases/) · [云端用量公告](https://github.blog/changelog/2026-10-28-work-from-anywhere-with-a-new-connected-copilot-cloud-experience/)
