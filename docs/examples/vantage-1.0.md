# Vantage 1.0 research examples

Install the complete Skill, then give your host one natural-language request.
The Skill uses the `vantage` CLI and the host's search and reasoning. The
examples below describe the requested deliverable. They do not promise that
the sources will contain enough evidence to complete it.

## Industry intelligence

> 用 Vantage 研究 2026-10-01 至 2026-10-31 期间海外 AI 视频工具有哪些
> 值得注意的公开发布和能力变化。区分厂商公告和实际运行验证，指出哪些结论
> 没有足够独立来源。只做研究。

A dated timeline can support the recent-developments section. Where only the
maker reports a feature, the brief attributes the claim and leaves independent
performance unverified. It updates the research plan without enabling business
opportunities.

## Demand discovery

> Use Vantage to look at the last 45 days of feedback about AI meeting
> transcription tools. Find concrete accounts about speaker labeling and export.
> Include positive counterexamples and call out gaps in firsthand evidence.

The brief separates firsthand descriptions, vendor assertions and contrasts.
It can report a repeated issue in the retained sample where support exists.
A weak sample should leave prevalence unresolved.

## Competitive intelligence

> Vantage で直近60日の VS Code 向けコーディング支援ツールを調べてください。
> GitHub Copilot と代替製品について、公表済みの機能と独立した利用体験を
> 分けて、比較できない点を明記してください。

The plan targets comparison evidence and names the decision criteria.
The competitive section cites dates and sources alongside the eligible
observations. Gaps about relative performance stay visible if the retrieved tests
use different conditions.

## Opportunity discovery

> 用 Vantage 研究最近 90 天海外的离线会议转录工具。哪些用户场景和未满足
> 的需求值得提出创业机会假设？只给有证据支持的少量假设，写清目前替代方案、
> 关键假设和风险，以及怎样验证和推翻。

The Skill activates explicit opportunity discovery. A supported result includes
a target user, problem, alternatives, potential gap, assumptions, risks, a test
and a disconfirming observation. If the available corpus consists of vendor
launches and no verified findings about user friction, the brief may abstain.

## Recorded host run

A separate real research-only run used a 90-day window ending 2026-11-22 UTC to
find offline meeting transcription alternatives and practical limitations. The
host answered the structured planning, coverage and synthesis requests using
the retrieved sources. The first round surfaced maker claims for
[Trace](https://news.ycombinator.com/item?id=49432395) and
[Scrieb](https://news.ycombinator.com/item?id=49906805). The accuracy follow-up
did not establish independent user limitations. DEV returned a rate limit on an exploratory pass and was available on rerun.
The final report kept the two questions separate, identified unavailable evidence,
and did not generate opportunities. See the
[release-readiness notes](../vantage-1.0.md) for the scope of this validation.
