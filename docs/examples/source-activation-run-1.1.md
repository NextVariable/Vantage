# Real multi-platform run after unified source activation (2026-11-25)

> **Real model run, not a scripted sample.** The reasoning model was DeepSeek
> (`deepseek-chat`, injected through the host-neutral `complete_structured`
> contract). Sources were retrieved live on 2026-11-25; no host web search was
> used. The platform observations quote retrieved text, not titles alone.
> `docs/examples/platform-aware-sample.md` remains a scripted rendering
> regression and is not model research.

Command:

```bash
.venv/bin/sourceglint "AI coding agents adoption" --mode general \
  --market global --window 30 --as-of 2026-11-25T00:00:00Z --language en \
  --registry /tmp/study-registry-2.yaml --model /tmp/deepseek_model.py \
  --research-timeout 300 --output study-brief-2.md
```

The bounded registry contained GitHub, Hacker News, DEV, arXiv, Techmeme,
YouTube and the new USPTO patents route.

## Result

- 17 retained evidence items, all inside the 30-day window.
- Original platforms: DEV (1), GitHub (12), USPTO (1), YouTube (3).
- Retrieval routes attempted: devto, github, hacker_news, patents, techmeme,
  youtube; arXiv was rate-limited upstream and reported as unavailable.
- The synthesis stage produced a partial brief: 5 of 12 facts passed the
  semantic check and 7 remain unverified, so they are not presented as
  established findings.
- `Platform Observations` was rendered because at least two original platforms
  contributed cited evidence. The USPTO line proves the patent route is
  attributed to its original platform, not folded into a generic web source.

## Excerpt: Platform Observations

- **GitHub** — 7 cited item(s): \[META\] Official codemods for OpenSearch
  Upgrades and Migrations — 2026-11-12; Audit guidance for practical value and
  low-friction adoption — 2026-11-15
- **YouTube** — 2 cited item(s): AI Coding Assistant Usage Coding Drives AI
  Adoption — 2026-11-13; Faster with AI coding agents, but in control: The five
  adoption levels explained — 2026-11-11
- **DEV** — 1 cited item(s): The State of AI in Software Development in 2026:
  Agents, Productivity, and the Verification Bottleneck — 2026-11-10
- **USPTO** — 1 cited item(s): SYSTEM AND METHOD OF MAINTAINING CONTEXTUAL
  RELATIONSHIPS AND OPERATIONAL COMPATIBILITY IN CODEBASE FUNCTIONALITY — 2026-11-12

## Excerpt: Coverage

```
- Evidence: 17 evidence items; current window 17; baseline 0
- Retrieval routes: devto, github, hacker_news, patents, techmeme, youtube
- Original platforms: DEV, GitHub, USPTO, YouTube
- Platform item counts: DEV 1, GitHub 12, USPTO 1, YouTube 3
- Coverage limitation: arxiv: rate_limited: upstream rate limit
- Coverage limitation: hacker_news: HN excluded 1 canonical hiring-thread hits for a non-hiring query
- Sources unavailable: arxiv
```

## Second real run: patents-only

A shorter run used the patents route alone to confirm the anonymous USPTO
session end-to-end:

```bash
.venv/bin/sourceglint "meeting assistant" --platform patents --window 90 \
  --model /tmp/deepseek_model.py --max-rounds 1 --research-timeout 60
```

It retrieved one dated application (`2026-10-01`) and the brief labelled it
`[USPTO]` with the original PDF URL. No credential, cookie or paid service was
involved.

## Limitations observed

- arXiv was rate-limited during the run; it is recorded as unavailable instead
  of being replaced silently.
- GitHub dominated the item count because its issue search returns many
  automated reports. This is a sampling observation, not a connector failure.
- The synthesis stage is deliberately strict; an evidence-backed brief with
  unverified facts is a correct outcome, not a success upgrade.
