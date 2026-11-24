# 竞争情报｜Cursor 与 GitHub Copilot

2026-11-24 08:15 UTC 截止，全球英文，30 天。以下是 Vantage 在干净提交 `6da52f7` 上的真实输出摘要，另附独立来源复核。运行返回 `PARTIAL / evidence_backed_brief / LIMITED`。

GitHub 公布了 11 月 16 日的 Copilot 模型调整。报告保留的一个要点是个人年付订户仍可使用 Claude Opus 4.8。Cursor 与 GitHub 的多个官方更新已保留在检索账本，简报未完成逐产品功能对照或用户反馈比较。 [GitHub 模型更新原文](https://github.blog/changelog/2026-11-16-github-copilot-models-deprecated-on-november-16-2026/)

独立复核确认上面的订阅范围与官方说明相符。它适合做竞品变化的证据线索，作为双边竞争分析仍不够。原始记录保留在本地 `runs/rc/beta-final-live/competition-cursor-copilot/`。

## 最终代码复验

`b59a5e9` 复验返回 `PARTIAL / evidence_only_report / LIMITED`，保留 6 条记录。原文复查确认 Cursor 开放了代理语音交互，GitHub 则公布了面向 Copilot 的 Azure DevOps 预览和模型调整。报告明确标出六个未评估的比较问题，只有检索摘录，没有形成功能、定位和一手反馈对照。一次无关第三方产品的目录 PR 因同时提及两款工具被保留，独立评审将其排除。该案例未通过发布验收。 [Cursor 更新日志](https://cursor.com/changelog) · [Copilot 更新公告](https://github.blog/changelog/2026-11-17-github-copilot-app-microsoft-ignite-releases/)

## 竞争情报发布阻断复验

干净提交 `af11318f1aa460542a686b191cd54b6efc339f11` 使用原题和原 30 天窗口。引擎最终输出 `PARTIAL / evidence_backed_brief / LIMITED`，实际完成一轮，因截止时间停止。简报按双产品和三项维度交付。以下为引擎原始对照，来自该次运行的 `brief.md`。

Dated source excerpts. An uncovered cell makes no claim about product capability.

| Dimension | Cursor AI editor | GitHub Copilot |
| --- | --- | --- |
| Product updates and availability | Publisher excerpt, source-reported: Voice chat works in the Agents Window, the IDE, on web, and in Cursor for iOS. — [cursor.com](https://cursor.com/changelog) · 2026-11-06 `ev_of77mhpe6icvby4eobnbz35ijoxqnhpf` | Publisher excerpt, source-reported: Adaptive is now in public preview. Cross-repository context is now in public preview for public repositories. — [github.blog](https://github.blog/changelog/2026-11-17-copilot-code-review-adaptive-effort-secret-detection-and-more) · 2026-11-17 `ev_watxb4nrig63pytsv5a25hj3l44avxyo`<br>Publisher excerpt, source-reported: Azure DevOps integration is now in public preview. Cloud sessions aren’t available for GHES. Browser use is off by default. — [github.blog](https://github.blog/changelog/2026-11-17-github-copilot-app-microsoft-ignite-releases) · 2026-11-17 `ev_spnct7vwpyjeur5oanfj63l46zql47tp` |
| Positioning and intended workflows | Uncovered in the retained sample | Uncovered in the retained sample |
| Firsthand use and counterexamples | Uncovered in the retained sample | First-person account, source-reported: I use GitHub Copilot at work ($100 plan, payed by employer) and Claude Code personally ($20 plan). Claude Code gives me MUCH more usage and real work done, I also like CC harness more — [reddit](https://www.reddit.com/r/GithubCopilot/comments/1xzhxdj/who_use_github_copilot_your_experience/19su13vtaar5w) · 2026-11-18 `ev_r3s4dgbuxib52mg26pkfk47wdkkt2eby` |

### 独立来源核验

- **Cursor。** 11 月 6 日公告确认代理语音聊天覆盖 Agents Window、IDE、网页与 iOS。报告将该结论表述为 Cursor 的发布说明。 [Cursor 原始更新日志](https://cursor.com/changelog)
- **GitHub Copilot。** 11 月 17 日公告确认 Azure DevOps 集成处于公开预览，浏览器操作默认关闭，GitHub Enterprise Server 的云会话不可用。三句话在公告中分属不同段落。另一条同日公告确认 Adaptive 审查和公开仓库的跨仓上下文均为公开预览。11 月 16 日公告也确认 Claude Opus 5 从模型选择器移除，有权限的运行时回退仍可使用。 [Copilot 应用公告](https://github.blog/changelog/2026-11-17-github-copilot-app-microsoft-ignite-releases/) · [代码审查公告](https://github.blog/changelog/2026-11-17-copilot-code-review-adaptive-effort-secret-detection-and-more/) · [模型更新公告](https://github.blog/changelog/2026-11-16-github-copilot-models-deprecated-on-november-16-2026/)
- **用户反馈与定位。** 在 Reddit 原帖复核了 Copilot 使用者的原话。该用户采用的是工作环境的 Copilot 和个人环境的 Claude Code，这一自述只能作为 Copilot 使用案例。Cursor 缺少合格的一手反馈，双方定位变化均未覆盖。报告没有据此推出产品功能缺失或竞争优劣。 [Reddit 原帖](https://www.reddit.com/r/GithubCopilot/comments/1xzhxdj/who_use_github_copilot_your_experience/)

筛前 31 条记录中有 5 条进入竞争综合。现场报告排除了顺带提及目标的材料，历史目录 PR 由原冻结账本单独验证。独立评审通过功能更新对照，保留一手反馈与定位缺口。运行原始计划、完整机器报告、来源状态与账本存于本地忽略目录 `runs/rc/beta-competition-closure/competition-cursor-copilot/`。
