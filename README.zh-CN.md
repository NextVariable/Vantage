# Vantage

**按需情报与机会发现 Skill（On-Demand Intelligence & Opportunity Discovery Skill）**

[English](README.md) · [真实样例](docs/source-expansion-1.1.md#two-real-vantage-reports) · [文档导航](docs/README.md)

Vantage 面向创业者、产品经理、商业化负责人、咨询顾问和研究人员。你主动提出研究问题，它在可用平台上查找近期的行业变化、用户需求和竞争信号。默认研究最近 30 天，时间窗口可调整。

Skill 会先拆出子问题，检索并检查保留的证据。重要缺口或线索值得核实时，最多追加两轮。最终交付带日期和原始链接的报告，以及可重复使用的证据文件。机会假设和产品或 GTM 建议只在明确请求时输出。

## 版本

- **已发布：Vantage 1.0 Beta 1**，版本 `1.0.0b1`。下方安装命令固定使用已发布标签。 [GitHub 预发布说明](https://github.com/NextVariable/Vantage/releases/tag/v1.0.0b1)
- **开发中：Vantage 1.1 Global Source Expansion**，本分支 `dev/vantage-1.1-global-sources` 的包版本为 `1.1.0.dev1`。已有公开来源扩展和阶段性验证记录，尚未发布 1.1。 [1.1 验收记录](docs/source-expansion-1.1.md#phase-3-codex-host-acceptance-2026-11-24)

## 可以研究什么

| 用途 | 示例问题 |
| --- | --- |
| 产品需求与反馈 | AI 会议助手的用户最近在夸什么、抱怨什么？有哪些反复出现的需求？ |
| 市场与竞品研究 | 最近日本 AI 会议助手市场有哪些竞品和变化？日本用户在讨论什么？ |
| 行业动态 | 最近 AI 视频领域出现了哪些新工具、技术进展和实际玩法？ |
| 机会发现 | 哪些未满足的需求值得提出机会假设？怎么验证或推翻？ |

安装后，直接告诉智能体：

> 用 Vantage 研究最近30天 AI 视频领域的新工具和用户反馈，保留日期、原始链接和反例。

## 安装 1.0 Beta 1

需要 Python 3.10+，以及支持网页搜索、推理和交互式终端的智能体。以 Codex 为例，在尚未占用的技能目录中安装：

```sh
git clone --branch v1.0.0b1 --depth 1 \
  https://github.com/NextVariable/Vantage.git ~/.codex/skills/vantage
cd ~/.codex/skills/vantage
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -c "import sourceglint; print(sourceglint.__version__)"
.venv/bin/vantage doctor
```

版本应输出 `1.0.0b1`。检查通过后，让智能体使用 Vantage。请保留完整仓库，单独复制 `SKILL.md` 无法运行。Windows 请使用 `.venv\Scripts\python.exe`。检查命令确认本地配置是否就绪，来源当下是否可访问则以实际研究为准。

### 安装 1.1 开发版

用于开发和验证时，把上面的 `--branch v1.0.0b1` 换成
`--branch dev/vantage-1.1-global-sources`，目标目录换成
`~/.codex/skills/vantage-dev`，之后在该目录安装。版本检查应输出
`1.1.0.dev1`。同一 Codex 环境只启用一份名为 `vantage` 的 Skill。

直接使用 `vantage` 时默认启用自适应研究，最多运行三轮。命令行仍需宿主
提供结构化模型，例如通过 `--model sourceglint.host_stdio:build_model` 交互。
用 `--window DAYS` 或 `--start-date` 和 `--end-date` 设置时间窗，后者包含首尾 UTC 日期。
原 `sourceglint` 命令和 Python 导入路径继续可用。
[四种使用示例与真实宿主记录](docs/examples/vantage-1.0.md)列出了完整提示词和输出边界。

## 输出与覆盖范围

你会得到带来源的报告，以及保存链接、日期和原文节选的证据文件。报告区分厂商陈述、用户体验与推断，保留反例，并说明未访问到的来源或材料不足的地方。

1.0 Beta 在 GitHub、Reddit、Hacker News、YouTube、Qiita 和智能体网页搜索之间选择相关路径。1.1 可按研究意图使用 Hybrid 或 Expanded，并在可用时补充讨论、评论或字幕。每次检索的来源随问题和可访问性变化。Skill 默认使用公开来源。直接调用 CLI 时可另行配置需凭据的来源，智能体自身的使用额度仍适用。

检索是有限采样，覆盖受访问权限、限流、语言和主题影响。报告生成成功不代表信息已全部覆盖，也不能直接证明市场需求。目前不支持历史窗口增长比较、实时监控、新闻聚合或定时推送。直接调用旧 CLI 或 Python API 默认维持单轮，可分别用 `--adaptive` 或 `adaptive=True` 启用自适应模式。

### 状态与可信度

- `status`：`SUCCESS` 表示必要执行阶段已完成且有可用简报；`PARTIAL` 表示有可用输出但有阶段降级；`NO_EVIDENCE` 表示没有可用证据；`FAILED` 表示执行失败。`SUCCESS` 不等于覆盖完整或质量合格。
- `delivery_level`：`full_brief`、`evidence_backed_brief`、`evidence_only_report` 或 `no_evidence`，表示交付层级，不替代 `status`。
- `research_quality`：独立的覆盖规则结论（`ADEQUATE`、`LIMITED` 或 `NOT_ASSESSED`），不能由简报成功反推。
- JSON 同时提供 `execution_status` 和兼容字段 `status`。每条事实性发现附带证据支持状态：`supported`（引文可在所引来源中逐字定位）、`verified`（另经宿主语义支持校验）、`partial`（只能支持部分陈述）、`vendor_only`（仅有厂商材料支持）或 `unverified`（无法确认）。合法但无关的引用、拼接引文和厂商自称的“独立测试”都会被拒绝，不会被标为已验证事实。
- 行业、需求与竞争研究是基础能力；机会发现和产品建议只在明确请求时生成。

### 1.1 来源验证

截至 2026-11-24，1.1 的最近结构化联网记录有 **35 个免费直连平台**，另有
**1 个 CLI 平台**（YouTube 公开视频元数据）。Host 网页探针取得 **24 个
带日期和原文的来源样本**，其中 PR TIMES 和 G2 已进入真实 Vantage 报告。
合并并去重后，最新联网口径为 **38 个平台**。授权 API、独立 MCP、
当前被限流的 arXiv 和未取到评论的 Steam 单列。查看来源访问指南可区分
目录登记、运行时槽位、冻结回放与真实联网结果。 [来源访问](docs/source-access-matrix.md) · [统计快照](docs/source-live-status.json)

## 真实研究与文档

- [1.1 最新真实研究](docs/source-expansion-1.1.md#two-real-vantage-reports)，日本会议纪要产品发布与 Otter 用户反馈。两例的研究质量均为 `LIMITED`。
- [1.0 Beta 四类真实研究](docs/examples/beta-final-2026-11-24/README.md)，包括竞争情报、需求、行业与机会发现。
- [文档导航](docs/README.md) · [授权指南](docs/source-authorization.md) · [变更日志](CHANGELOG.md) · [参与开发](CONTRIBUTING.md)

采用 [MIT 许可](LICENSE)。
