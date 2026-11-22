# Vantage

**按需情报发现 Skill（On-Demand Intelligence Discovery Skill）**

[English](README.md) · [真实样例](docs/examples/2026-10-04/README.md) · [文档导航](docs/README.md)

Vantage 面向创业者、产品经理、商业化负责人、咨询顾问和研究人员。你主动提出研究问题，它在可用平台上查找近期的行业变化、用户需求和竞争信号。默认研究最近 30 天，时间窗口可调整。

Skill 会先拆出子问题，检索并检查保留的证据。重要缺口有明确补搜价值时，最多追加一轮。最终交付带日期和原始链接的报告，以及可重复使用的证据文件。机会假设和产品或 GTM 建议只在明确请求时输出。

## 可以研究什么

| 用途 | 示例问题 |
| --- | --- |
| 产品需求与反馈 | AI 会议助手的用户最近在夸什么、抱怨什么？有哪些反复出现的需求？ |
| 市场与竞品研究 | 最近日本 AI 会议助手市场有哪些竞品和变化？日本用户在讨论什么？ |
| 行业动态 | 最近 AI 视频领域出现了哪些新工具、技术进展和实际玩法？ |
| 机会发现 | 哪些未满足的需求值得提出机会假设？怎么验证或推翻？ |

安装后，直接告诉智能体：

> 用 Vantage 研究最近30天 AI 视频领域的新工具和用户反馈，保留日期、原始链接和反例。

## 安装

需要 Python 3.10+，以及支持网页搜索、推理和交互式终端的智能体。以 Codex 为例，在尚未占用的技能目录中安装：

```sh
git clone https://github.com/NextVariable/Vantage.git ~/.codex/skills/vantage
cd ~/.codex/skills/vantage
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m sourceglint doctor
```

然后让智能体使用 Vantage。请保留完整仓库，单独复制 `SKILL.md` 无法运行。Windows 请使用 `.venv\Scripts\python.exe`。检查命令确认本地配置是否就绪，来源当下是否可访问则以实际研究为准。

## 输出与覆盖范围

你会得到带来源的报告，以及保存链接、日期和原文节选的证据文件。报告区分厂商陈述、用户体验与推断，保留反例，并说明未访问到的来源或材料不足的地方。

默认从 GitHub、Reddit、Hacker News、YouTube 和智能体网页搜索中选择相关路径，并在可用时补充讨论、评论或字幕。每次检索的来源随问题和可访问性变化。无需先配齐各平台密钥，智能体自身的工具费用和额度由使用者承担。

检索是有限采样，覆盖受访问权限、限流、语言和主题影响。报告生成成功不代表信息已全部覆盖，也不能直接证明市场需求。目前不支持历史窗口增长比较、实时监控、新闻聚合或定时推送。直接调用旧 CLI 或 Python API 默认维持单轮，可分别用 `--adaptive` 或 `adaptive=True` 启用自适应模式。

## 进一步了解

- [真实研究样例](docs/examples/2026-10-04/README.md)
- [来源访问](docs/source-access-matrix.md)与[降级方式](docs/source-fallback-playbook.md)
- [智能体集成与证据导出](references/host-protocol.md)
- [自适应研究设计与回放](docs/adaptive-research.md)
- [验证记录](docs/validation.md)
- [仓库目录说明](docs/repository-guide.md)与[参与开发](CONTRIBUTING.md)

采用 [MIT 许可](LICENSE)。
