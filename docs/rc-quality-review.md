# Vantage 1.0 real research quality review

The review below was conducted after report generation in a separate research session. It checks selected material claims against origin pages. The selection was purposive and the reviewer knew the arm. These spot checks are auditable examples, not a blinded representative estimate of the 95% grounding or 80% question coverage gates.

| Case and claim unit | Independent finding |
| --- | --- |
| `industry-agents` · Goose 1.56.0 partly worked in a small hands-on edit test | Supported. The test page shows a failed edit and one successful edit on October 25. The test did not exercise the new subagent capability. [Original test](https://theagenticweekly.com/tests/goose) |
| `industry-agents` · Goose 1.56.0 announcement added subagent resume | Feature verified on the project release; the report’s cited secondary page was inaccessible. The project UI gives day and month, and the test report verifies that the version existed in the window. [Project release](https://github.com/aaif-goose/goose/releases/tag/v1.56.0) |
| `industry-agents` · DeepSeek released Super-Agent under MIT | The run’s secondary link was inaccessible. The ordinary agent found a public research prototype and its license. Do not restate a dated formal product release from the supplied citation. [Original repository](https://github.com/deepseek-ai/dsh-superagent-prototype) |
| `industry-inference-jp` · Trans-N announced Swama 2.5.1 and compared local and cloud workloads | Supported as vendor-reported. The original date, version and internal measurement conditions agree. Outside those conditions, performance is unverified. [Original announcement](https://prtimes.jp/main/html/rd/p/000000018.000146925.html) |
| `demand-meeting-jp` · A Notta user reported transcription review friction and found the paid allowance adequate | Supported as one reported experience. The examples used a short recording. No prevalence inference. [Original user account](https://note.com/lush_liger4304/n/nef2c5dba6925) |
| `demand-meeting-jp` · A separate two-speaker example correctly separated speakers but retained errors | Supported with scope. The original source describes a fictional meeting and 26 turns. Counterevidence cannot generalize to production meetings. [Original experiment](https://note.com/msman_ai/n/n957c0e502996) |
| `demand-cursor` · Specific billing, model-selection and contrary experiences | The reviewer could not reopen three selected Reddit/HN links. Keep these as unverified user reports; the ledger match does not authenticate them. [Billing post](https://www.reddit.com/r/cursor/comments/1wqpxkx/bugbot_subscription) · [Model selection comment](https://www.reddit.com/r/CursorAI/comments/1x5iav8/great_time_for_competitors_to_step_in/pgx35w2) · [Contrary account](https://news.ycombinator.com/item?id=49913644) |
| `competition-linear` · Linear announced BYOK for its cloud agent | Supported as a vendor release on November 12. The generic web route’s Tier 4 classification triggered a false official-source gap. [Original changelog](https://linear.app/changelog/2026-11-12-bring-your-own-key) |
| `competition-linear` · Setup takes more admin time than Linear | Unverified. The run’s excerpt omits the product being compared and the review could not open the linked editorial. The report disclosed missing migration evidence. [Editorial cited by run](https://velotouch.com/linear-alternatives) |
| `opportunity-offline` · Overlap can remove the local speaker’s words, with headphones as a workaround | The author’s release notes support the statement. It is a known product limitation without independent demand evidence. The other maker announcement was inaccessible to the reviewer. [Diarist project release](https://github.com/ebt55/diarist/releases/tag/v0.1.0-beta.6) · [Scrieb maker post cited by the run](https://news.ycombinator.com/item?id=49906805) |

## Exploratory competitor comparison

One question, `industry-agents`, was run across the updated Vantage engine, ordinary Codex web research and last30days v3.23.0. Ordinary Codex used the same model, exact cutoff and a six-call stated web limit. It found four direct GitHub releases omitted by Vantage. The original release pages opened and confirmed the version and displayed month/day. A comparison of broad market coverage and independent hands-on validation still requires additional checked cases and provenance. [OpenCode](https://github.com/anomalyco/opencode/releases/tag/v2.3.0) · [goose](https://github.com/aaif-goose/goose/releases/tag/v1.59.0) · [Pi](https://github.com/earendil-works/pi/releases/tag/v1.5.0) · [Codex CLI](https://github.com/openai/codex/releases/tag/rust-v0.170.0)

last30days ran its headless public-only path with isolated config, no browser cookies, keyless web and a six-fetch option. It reported six native GitHub candidates in its terminal summary in 6.7 seconds and zero final serialized report results; web grounding returned zero. That invocation used its deterministic fallback plan and a day-level cutoff. The CLI supports a Host-provided plan, explicit days, source selection, and fetch caps. Its access and planning differed here, so this is one exploratory observation. A 5–10 case matched three-way comparison remains pending.

## Root causes and corrections

- The live pilot found a usable candidate in Host search, but the bridge lost it because the reply nested records in a model-style payload. The engine now sends the exact source reply schema, including the top-level result array, required native ID and original publication timestamp. The real matrix exercises this contract. Regression tests retain compatibility with older replies, reject malformed citation destinations and keep each query’s observed source limitations.
- In `competition-linear`, the follow-up `switched from Linear to experience` sent Reddit archive discovery to verb-derived community names. A later live adapter probe repeated that exact query and scope on both versions. The previous route attempted 17 requests, including unrelated `SwitchedAtBirth`, in 24.32 s. The scoped route performed one `Linear` discovery request in 2.38 s and skipped listings when community descriptions did not establish the issue-tracker context. Both arms returned zero evidence. The measured gain is removal of irrelevant calls in this one probe. A regression also proves that a contextually verified `LinearApp` community can remain eligible while `LinearAlgebra` is rejected.
- The first-party role inferred for the Linear changelog disagrees with the default generic web tier. A future fix needs trusted publisher provenance or an explicitly verified owner domain before tier promotion. Vendor status alone must not make a claim authoritative. The sprint preserves the observed classification issue instead of claiming it is fixed.
- The `opportunity-docs` case produced a single explicitly tentative study design for documentation confusion. It identified developer users and candidate substitutes, described risks and a falsifier, and disclosed that no buyer, recurrence, or willingness to pay had been established. Its sole cited origin was inaccessible during independent review. The hypothesis remains unverified. [Source cited by the run](https://artechio.com/blog/outdated-documentation-ai-coding)

## Five matched prompts · prior engine versus updated engine

The engines used the same prompt IDs, cutoff, public-only access, model, profile, and case ceilings. Public feeds and Host search rankings were live and can vary. `7e1757e` used two concurrent cases and `13a0635` used four; wall-clock comparisons include that contention. The connector-level lane probe above is a separate single-query experiment.

| Observed metric | `7e1757e` | `13a0635` |
| --- | ---: | ---: |
| Prompts yielding retained evidence | 2/5 | 5/5 |
| Dated retained records | 2 | 24 |
| Displayed evidence IDs with ledger URL/date match | 2/2 | 15/15 |
| Adapter requests / empty / failed | 16 / 9 / 5 | 21 / 11 / 1 |
| Follow-up rounds / with new retained candidates | 5 / 0 | 8 / 4 |
| Recorded web events / forwarded bridge exchanges | 10 / 17 | 20 / 29 |
| Cases missing a timely Host reply | 1/5 | 5/5 |
| Median wall time per case | 198.13 s | 283.86 s |
| Core questions marked fully covered by the engine | 0/12 | 0/13 |

The updated engine’s median was 85.73 s higher, about 43%. Extra evidence includes relevant dated items from original sources and weak or unverifiable items. A claim-grounding uplift, live unit cost, and incremental useful findings per round cannot be quantified from the available judgments. The [per-case results](../evals/rc-results.json) preserve counts and reported model usage. Four of the updated runs recorded token usage, so aggregate input counts should not be compared as if coverage were identical.

The core report for `opportunity-support-cn` was labeled `SUCCESS` even though its separately requested opportunity assessment was unavailable. The delivery fixes this by retaining the brief and returning `PARTIAL` when opportunity analysis was explicitly requested and its model step failed. Evidence-based abstention retains its existing contract. The full matrix above was captured before the status fix and before the standalone Reddit lane correction.
