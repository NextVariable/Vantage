# 2026-11-26 渠道联网实测

[24 平台、31 条 lane 和逐条引用记录](source-live-2026-11-26.json)覆盖 last30days
v4.6.0（`64b1f006f800640022ce07f51de5ce56aad34b76`）。本轮实测
**15/24 个上游平台、28 个去重来源**。其中 9 个上游平台通过公开原生或 CLI
路径，6 个通过 Host 的公开原文路径。去重总数另含 13 个上游名单之外的来源。
免费结构化档案与目录中的历史通过仍可参考，本轮未重跑或没有合格引用的历史记录
未计入。按 2026-11-26（Asia/Shanghai）记账，机器记录保留 UTC 时间。

每个通过项都有当轮真实请求、非空原始内容、可追溯 URL、平台日期、证据 ID
和 Vantage 报告引用。Host 验收先搜索并打开原始页面，再经生产 STDIO
协议传送当轮实见片段。报告以 `evidence_only_report` 交付，未执行模型综合。
原生验收使用按来源隔离的验收配置。Host 样本使用 150 天窗口，原生样本使用
365 天窗口。证据年龄和日期含义见原始记录。本轮测到了具体路径，默认路由命中率、
所有主题与时窗覆盖率需要各自验收。

| 状态 | 上游平台 | 实测范围或待补条件 |
| --- | --- | --- |
| LIVE_VERIFIED | GitHub、Reddit、YouTube、Hacker News | GitHub 公开 issue 与评论，Reddit 帖子和评论，YouTube 字幕及互动元数据，HN 帖子、评论及反馈计数 |
| LIVE_VERIFIED | DEV、arXiv、Techmeme、Polymarket、USPTO | 文章摘要、论文摘要、聚合片段、有日期的市场描述与成交量、专利申请及 PDF。Polymarket 用市场开始日期作为锚点 |
| LIVE_VERIFIED | Bluesky、Telegram、Stocktwits | 公开原帖经 Host 入账。Stocktwits 原始讨论有可见回复，原生接口返回 403。Bluesky 匿名搜索返回 403，Telegram 商业结构化路线没有调用 |
| LIVE_VERIFIED | Trustpilot、Digg、Amazon | Trustpilot 单条评价正文，Digg 公告正文，Amazon 商品详情及发行日期。商品评分可见，未确认买家评论详情。Digg 结构化搜索请求遭遇 403 验证挑战 |
| USER_ACTION_REQUIRED | TikTok、Instagram、Threads、Pinterest、LinkedIn、Meta Ad Library | 需要配置 ScrapeCreators 的免费额度授权。LinkedIn 公开正文可读但无法核实发布时间，Meta 列表可见但逐条广告永久链接还不能核验同一原文 |
| USER_ACTION_REQUIRED | 小红书 | 未取得可核对发布时间的公开笔记。需要平台允许的只读访问和已明确配置的本地服务 |
| PAYMENT_DECISION_REQUIRED | X | 公开网页探针没有返回合格原始帖。若决定使用 X API，需授权已有开发者项目的计量额度 |
| EXTERNAL_BLOCKED | Truth Social | 公开入口可达，但没有取得合格原始帖子或可合法调用的搜索凭据 |

Lever、Greenhouse、Ashby 三个 ATS 均提交了有日期的公开职位描述及引用。
Yahoo Finance 的公开日期页可发现，Vantage 的行情、新闻富化路线未通过入账
验收。Perplexity 和 Dripstack 属于付费聚合能力，本轮无调用。Host grounding、
本地语料和本地简报库分别是发现、用户证据输入和历史产物复用能力。三者
均不加进独立来源数。聚合连接器本轮只有 npm 的该批结果计为独立 npm 来源。

### 免费工具安装与验证

复用了现有的 `yt-dlp` 2026.03.17 和 GitHub CLI 2.93.0 登录。另从上游 GitHub
发布下载并核对了 `digg-pp-cli` 2026.11.2、`trustpilot-pp-cli` 2026.9.1 和
小红书 MCP v2.7.6 的 macOS arm64 发布包 SHA-256，安装在隔离目录。
Digg 结构化检索真实返回 HTTP 403 challenge。Trustpilot CLI 通过版本检查，
缺少已授权的适用会话。小红书 MCP 通过帮助命令检查，未启动服务或登录。
单次公开点击、工具安装和版本检查均不计入渠道通过数。

### 免费额度授权

1. 打开 [ScrapeCreators 控制台](https://app.scrapecreators.com/)，登录自己的
   账号或自行注册。核对仍有免费积分，未绑定付款方式。供应商公开页面列出
   100 个免费积分，实际余额以账户为准。[套餐与额度](https://scrapecreators.com/)
2. 在本机 Vantage 工作目录运行 `.venv/bin/vantage setup`。在
   `SCRAPECREATORS_API_KEY` 的隐藏提示中输入 Key，其余条目可按 Enter 跳过。
   向导将新凭据写入私有本机配置文件。Key 无需通过聊天、命令参数或 Git 传递。
3. 确认允许仅使用免费积分复测。逐一发起 TikTok、Instagram、Threads、Pinterest、
   LinkedIn、Reddit、YouTube、Telegram、Meta Ad Library 请求，Telegram 只查
   预先指定的公开频道。九条接口均在供应商的
   [OpenAPI](https://docs.scrapecreators.com/openapi.json)中核对过路径、参数和
   示例。实际访问权限、账户扣点及响应内容仍待逐条确认。

本轮商业 API 调用数为零。默认 per-run 允许次数为零。明确授权的运行
可以设定共享次数上限，失败与重试也消耗一次。这个上限衡量请求次数，
供应商积分和费用仍取决于实际端点及账户。暂时停用无法可靠按请求计量的
Bright Data 子进程路线。
