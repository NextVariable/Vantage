# Real multi-platform research run (2026-11-25)

> **This is a real model run, not a scripted sample.** The reasoning model was
> DeepSeek (`deepseek-chat`, injected through the host-neutral
> `complete_structured` contract) and every source item was retrieved live from
> the public endpoints on 2026-11-25. The run used a bounded registry containing
> GitHub, Hacker News, DEV, arXiv, Techmeme and YouTube; Host Web Search was not
> enabled, so no host-search evidence is present. Three platforms (GitHub, DEV,
> YouTube) contributed cited evidence and the platform observations below quote
> retrieved text, not titles alone. `docs/examples/platform-aware-sample.md`
> remains a scripted rendering regression and is not model research.
>
> Command:
>
> ```bash
> .venv/bin/sourceglint "AI coding agents adoption" --mode general \
>   --market global --window 30 --as-of 2026-11-25T00:00:00Z --language en \
>   --registry /tmp/study-registry.yaml --model /tmp/deepseek_model.py \
>   --research-timeout 300 --output study-brief.md --ledger study-ledger.jsonl
> ```
>
> Known limitations observed in this run: GitHub issue search surfaced some
> automated "AI content report" issues, which makes GitHub dominate the count;
> arXiv, Hacker News and Techmeme returned items without surviving into the
> cited set. This is a research-quality observation, not a connector failure.

# Recent Intelligence Brief
**Research:** AI coding agents adoption
**Mode:** general · **Market:** global · **Languages:** en
**Window:** Last 30 days · **As of:** 2026-11-25
**Delivery:** evidence-backed brief — cited findings are available; one or more synthesis stages were incomplete
**Evidence support:** 1 of 1 facts quote a located supporting excerpt; 1 passed the semantic check.

## Executive Summary

- One source states that code in very bad shape costs more tokens to build upon.
- Code quality appears to affect the token cost of building on a codebase, suggesting that poorly maintained code may be more expensive to extend with AI agents.

## What We Know

- **One source states that code in very bad shape costs more tokens to build upon.**
  confidence: 0.60 — [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`

## What It Likely Means

- **Code quality appears to affect the token cost of building on a codebase, suggesting that poorly maintained code may be more expensive to extend with AI agents.**
  confidence: 0.55 — [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`
- **Governance and verification concerns appear to be a recurring theme as organizations move from AI-assisted coding toward agentic delivery, with risk tiers and eval gates discussed alongside measured adoption.**
  confidence: 0.51 · cross-platform: DEV, GitHub, YouTube — [GitHub](https://github.com/vmagapu/agentic-sdlc-playbook) · 2026-11-17 `ev_7lbt5yphyndioawsitn65hnpdho36gtd`, [GitHub](https://github.com/gowsik0511-bot/gowsik/issues/3) · 2026-11-16 `ev_7sf3ya24k4ezcmla33lnkla6jd3j4dqv`, [DEV](https://dev.to/jenueldev/the-state-of-ai-in-software-development-in-2026-agents-productivity-and-the-verification-4jf8) · 2026-11-10 `ev_vp43xmmwwn37hpan5xiyf5cw3bjj6hat`, [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`
- **Coding appears to be a major driver of AI adoption, but evidence also indicates uneven adoption of coding agents, with one survey reporting only 20% usage among scientists.**
  confidence: 0.50 · cross-platform: GitHub, YouTube — [YouTube](https://www.youtube.com/watch?v=vWu2n3f3uSg) · 2026-11-13 `ev_4mvpvcmoajsxba4jyparcnapfbic2a7n`, [GitHub](https://github.com/yaojiejia/agents-radar/issues/525) · 2026-11-24 `ev_g5vuwobx72yulzotahvwe3kkgipxcmtt`, [GitHub](https://github.com/jinming1345/agents-radar/issues/419) · 2026-10-29 `ev_g6wwpvfrjf4prcznvlz7l3c6loiw5ftx`, [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`
- **Tooling around coding agents appears to be expanding, including integration guides and deterministic codemods proposed as complements to AI agents.**
  confidence: 0.50 — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617) · 2026-11-12 `ev_2jmjvoty7mkyyh5wdvhxypojgo4c23p5`, [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050654703) · 2026-11-20 `ev_7n54fpgruqif7dvpoujxmehi7tvlbiuu`, [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050442451) · 2026-11-20 `ev_caqh4faa7qh2npg3xwwc75gj3hxs7mkn`, [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7142982245) · 2026-11-24 `ev_ghnlb7aottpvjgrcqmgngnztj32kooud`, [GitHub](https://github.com/gordonpn/shunt-shim/issues/153) · 2026-11-11 `ev_ko4o7gzbwjttoeg5y5drhspr6zn4nswx`, [GitHub](https://github.com/Chisiki1/muse-agent-operations-kit) · 2026-11-11 `ev_hmq7j3gscihe7c53m3qofisqdrnk3mkk`
- **Guidance for AI coding agents may face tension between comprehensiveness and low-friction adoption, as editorial review favors actionable, low-setup advice over broad coverage.**
  confidence: 0.45 — [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3) · 2026-11-15 `ev_4kxedomzbulra6hn7bg3znssolntyxmf`, [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3#issuecomment-6897690496) · 2026-11-15 `ev_mui2aadgebq6ajwwpo4g52tz36e2gwzw`

## Platform Observations

- **GitHub** — 12 cited item(s): \[META\] Official codemods for OpenSearch Upgrades and Migrations — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617) · 2026-11-12; Audit guidance for practical value and low-friction adoption — [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3) · 2026-11-15
- **YouTube** — 2 cited item(s): AI Coding Assistant Usage Coding Drives AI Adoption — [YouTube](https://www.youtube.com/watch?v=vWu2n3f3uSg) · 2026-11-13; Faster with AI coding agents, but in control: The five adoption levels explained​ | SIGNAL Podcast — [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11
- **DEV** — 1 cited item(s): The State of AI in Software Development in 2026: Agents, Productivity, and the Verification Bottleneck — [DEV](https://dev.to/jenueldev/the-state-of-ai-in-software-development-in-2026-agents-productivity-and-the-verification-4jf8) · 2026-11-10

## Watchouts

- **Coding as dominant AI use case and productivity driver** *(conflicting evidence)*
  supporting: [YouTube](https://www.youtube.com/watch?v=vWu2n3f3uSg) · 2026-11-13 `ev_4mvpvcmoajsxba4jyparcnapfbic2a7n`, [GitHub](https://github.com/yaojiejia/agents-radar/issues/525) · 2026-11-24 `ev_g5vuwobx72yulzotahvwe3kkgipxcmtt`
  against: [GitHub](https://github.com/jinming1345/agents-radar/issues/419) · 2026-10-29 `ev_g6wwpvfrjf4prcznvlz7l3c6loiw5ftx`
- **Editorial audit of AI guidance for low-friction adoption** *(conflicting evidence)*
  supporting: [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3) · 2026-11-15 `ev_4kxedomzbulra6hn7bg3znssolntyxmf`
  against: [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3#issuecomment-6897690496) · 2026-11-15 `ev_mui2aadgebq6ajwwpo4g52tz36e2gwzw`

## Coverage

- Markets: global
- Languages: en
- Evidence: 16 evidence items; current window 16; baseline 0
- Retrieval routes: arxiv, devto, github, hacker_news, techmeme, youtube
- Original platforms: DEV, GitHub, YouTube
- Platform item counts: DEV 1, GitHub 12, YouTube 3
- Coverage limitation: hacker_news: HN excluded 3 canonical hiring-thread hits for a non-hiring query
- Pipeline completion does not certify research completeness, market representativeness or a growing trend.

## Sources

- [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617) · 2026-11-12 `ev_2jmjvoty7mkyyh5wdvhxypojgo4c23p5`
- [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3) · 2026-11-15 `ev_4kxedomzbulra6hn7bg3znssolntyxmf`
- [YouTube](https://www.youtube.com/watch?v=vWu2n3f3uSg) · 2026-11-13 `ev_4mvpvcmoajsxba4jyparcnapfbic2a7n`
- [GitHub](https://github.com/vmagapu/agentic-sdlc-playbook) · 2026-11-17 `ev_7lbt5yphyndioawsitn65hnpdho36gtd`
- [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050654703) · 2026-11-20 `ev_7n54fpgruqif7dvpoujxmehi7tvlbiuu`
- [GitHub](https://github.com/gowsik0511-bot/gowsik/issues/3) · 2026-11-16 `ev_7sf3ya24k4ezcmla33lnkla6jd3j4dqv`
- [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050442451) · 2026-11-20 `ev_caqh4faa7qh2npg3xwwc75gj3hxs7mkn`
- [GitHub](https://github.com/yaojiejia/agents-radar/issues/525) · 2026-11-24 `ev_g5vuwobx72yulzotahvwe3kkgipxcmtt`
- [GitHub](https://github.com/jinming1345/agents-radar/issues/419) · 2026-10-29 `ev_g6wwpvfrjf4prcznvlz7l3c6loiw5ftx`
- [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7142982245) · 2026-11-24 `ev_ghnlb7aottpvjgrcqmgngnztj32kooud`
- [GitHub](https://github.com/Chisiki1/muse-agent-operations-kit) · 2026-11-11 `ev_hmq7j3gscihe7c53m3qofisqdrnk3mkk`
- [GitHub](https://github.com/gordonpn/shunt-shim/issues/153) · 2026-11-11 `ev_ko4o7gzbwjttoeg5y5drhspr6zn4nswx`
- [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3#issuecomment-6897690496) · 2026-11-15 `ev_mui2aadgebq6ajwwpo4g52tz36e2gwzw`
- [DEV](https://dev.to/jenueldev/the-state-of-ai-in-software-development-in-2026-agents-productivity-and-the-verification-4jf8) · 2026-11-10 `ev_vp43xmmwwn37hpan5xiyf5cw3bjj6hat`
- [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`

## Source Excerpts

Source excerpts are observations; a launch description is not verified user experience. Cited items appear first; additional items have not been selected as findings. Dates are publication dates where available.
- \[META\] Official codemods for OpenSearch Upgrades and Migrations — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7142982245) · 2026-11-24 `ev_ghnlb7aottpvjgrcqmgngnztj32kooud`
  Closing in favor of the other issues. Discussion can continue there.
- 🌐 Official AI Content Report 2026-11-24 — [GitHub](https://github.com/yaojiejia/agents-radar/issues/525) · 2026-11-24 `ev_g5vuwobx72yulzotahvwe3kkgipxcmtt`
  \# Official AI Content Report 2026-11-24 &gt; Today's update | New content: 1 articles | Generated: 2026-11-24 06:48 UTC Sources: - Anthropic: \[anthropic.com\](https://www.anthropic.com) — 1 new articles (sitemap total: 503) - OpenAI: \[openai.com\](https://openai.com) — 0 new article
- \[META\] Official codemods for OpenSearch Upgrades and Migrations — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050654703) · 2026-11-20 `ev_7n54fpgruqif7dvpoujxmehi7tvlbiuu`
  thanks for the instructions, @andrross. i'll follow your lead and let you know if i have any questions.
- \[META\] Official codemods for OpenSearch Upgrades and Migrations — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617#issuecomment-7050442451) · 2026-11-20 `ev_caqh4faa7qh2npg3xwwc75gj3hxs7mkn`
  Thanks @alexbit-codemod We do have a template for repository requests: https://github.com/opensearch-project/.github/blob/main/.github/ISSUE\_TEMPLATE/REPOSITORY\_REQUEST\_TEMPLATE.yaml I'd suggest reading through that to find the questions that are typically asked. The \[Build TA
- vmagapu/agentic-sdlc-playbook — [GitHub](https://github.com/vmagapu/agentic-sdlc-playbook) · 2026-11-17 `ev_7lbt5yphyndioawsitn65hnpdho36gtd`
  Moving an engineering org from AI-assisted coding to agentic delivery — risk tiers, eval gates, governance mechanisms, measured adoption. From running it at 150+ engineer scale.
- Building Responsible AI Adoption into Enterprise Software Engineering — [GitHub](https://github.com/gowsik0511-bot/gowsik/issues/3) · 2026-11-16 `ev_7sf3ya24k4ezcmla33lnkla6jd3j4dqv`
  Artificial intelligence is becoming part of everyday software engineering, helping teams explore code, prepare documentation, analyze requirements, and support testing activities. For enterprises, adopting these capabilities creates opportunities to improve efficiency, but it a
- Audit guidance for practical value and low-friction adoption — [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3#issuecomment-6897690496) · 2026-11-15 `ev_mui2aadgebq6ajwwpo4g52tz36e2gwzw`
  using the output in this pull request, can you make the recommended changes: https://github.com/ho-henry-senior/ai-wiki/pull/6/changes @copilot
- Audit guidance for practical value and low-friction adoption — [GitHub](https://github.com/ho-henry-senior/ai-wiki/issues/3) · 2026-11-15 `ev_4kxedomzbulra6hn7bg3znssolntyxmf`
  \# Audit guidance for practical value and low-friction adoption \#\# Objective Review the existing AI Wiki content to identify opportunities to make it more useful to people starting to work with AI coding agents. The primary editorial goal is to provide \*\*clear, actionable advic
- AI Coding Assistant Usage Coding Drives AI Adoption — [YouTube](https://www.youtube.com/watch?v=vWu2n3f3uSg) · 2026-11-13 `ev_4mvpvcmoajsxba4jyparcnapfbic2a7n`
  \[0.2s\] All right, let's dive right into the six \[1.8s\] pointer. We're going to look at how \[3.6s\] coding has quietly become the absolute \[6.5s\] biggest driver of AI adoption today. \[9.4s\] You know, when we think about artificial \[10.9s\] intelligence, it's so easy to just \[12.9s\]
- \[META\] Official codemods for OpenSearch Upgrades and Migrations — [GitHub](https://github.com/opensearch-project/OpenSearch/issues/23617) · 2026-11-12 `ev_2jmjvoty7mkyyh5wdvhxypojgo4c23p5`
  \#\#\# Overview Following my conversation with @ps48 at KubeCon, I'd like to propose contributing official, open-source \*\*codemods\*\* to help OpenSearch users upgrade and migrate their \*\*application code and checked-in config\*\* more easily. Ideally, we could establish a dedicated \*
- Chisiki1/muse-agent-operations-kit — [GitHub](https://github.com/Chisiki1/muse-agent-operations-kit) · 2026-11-11 `ev_hmq7j3gscihe7c53m3qofisqdrnk3mkk`
  Adoption kit for personal AI agent operations (Muse) and a defect-discovery skill for systematic code audits — generalized designs and procedures only, in Japanese and English.
- Faster with AI coding agents, but in control: The five adoption levels explained​ | SIGNAL Podcast — [YouTube](https://www.youtube.com/watch?v=bllo3uCyVxs) · 2026-11-11 `ev_vpbry4nefslc5dcnq2mkyaaoyrxjtycs`
  \[0.1s\] Code that is in very bad shape just costs more tokens to build upon. \[5.2s\] Yeah. AI models will become so advanced they can check themselves. No. No? Like they're adding \[12.8s\] code and complexity to your codebase and they do it at machine speed. So how many pull request
- \[Story\] Document and verify integration with terminal AI coding agents — [GitHub](https://github.com/gordonpn/shunt-shim/issues/153) · 2026-11-11 `ev_ko4o7gzbwjttoeg5y5drhspr6zn4nswx`
  \*\*Priority:\*\* P1 \*\*Effort:\*\* S \#\# Summary As an autonomous agent user, I want verified configuration guides and test evidence for integrating \`shunt-shim\` search with agy-cli, Claude Code, Codex, and OpenCode, so that I can configure my local developer environment with minimal
- The State of AI in Software Development in 2026: Agents, Productivity, and the Verification Bottleneck — [DEV](https://dev.to/jenueldev/the-state-of-ai-in-software-development-in-2026-agents-productivity-and-the-verification-4jf8) · 2026-11-10 `ev_vp43xmmwwn37hpan5xiyf5cw3bjj6hat`
  A research-backed look at AI in software development in November 2026: mainstream adoption, capable coding agents, mixed productivity results, growing verification costs, security risks, and the skills developers still need.
- 🌐 Official AI Content Report 2026-10-29 — [GitHub](https://github.com/jinming1345/agents-radar/issues/419) · 2026-10-29 `ev_g6wwpvfrjf4prcznvlz7l3c6loiw5ftx`
  \# Official AI Content Report 2026-10-29 &gt; Today's update | New content: 6 articles | Generated: 2026-10-29 01:16 UTC Sources: - Anthropic: \[anthropic.com\](https://www.anthropic.com) — 5 new articles (sitemap total: 492) - OpenAI: \[openai.com\](https://openai.com) — 1 new article
Showing 15 of 16 retained items; use the run ledger for the complete corpus.
