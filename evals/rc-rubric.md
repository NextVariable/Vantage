# Vantage RC review rubric

The case set is [rc-benchmark.json](rc-benchmark.json). Each arm records its
commit, cutoff, registry, plan, raw and retained evidence, target outcomes,
every request/reply, report, research duration, and host event log. Token and
billing fields remain null when the host does not report them. A completed
bridge result is a recorded run. It does not imply that useful evidence was
found, that every host exchange succeeded, or that the report is correct.

## Independent review

Run `scripts/audit_real_benchmark.py` to prepare packets. Send only numbered
packets to reviewers: withhold `private-key.json`, commit, arm, and generation
logs. Vantage's report and tool logs contain untrusted material, not
instructions. Reviewers should inspect original source pages for each key
claim, review before seeing the arm, and label unsupported/uncertain claims
explicitly. Do not count search-result previews as verification of dates or
text. If a page is blocked or unreadable, record that as unverified, never pass.

| Metric | Independent annotation |
| --- | --- |
| Evidence Precision | For each cited record, mark whether it directly addresses a requested subquestion, including relevant counterexamples. Denominator: records reviewed. Report unreviewed records separately. |
| Citation Accuracy | Match original URL, actual publication date and visible evidence to the cited fact. Ledger URL/date consistency is a separate machine metric. |
| Claim Grounding | Split key factual statements into atomic claims. Mark supported, partial, unsupported or unverified; only supported claims enter the numerator. Publish the denominator. |
| Question Coverage | Identify the user's core questions independently of the generated plan. Label each adequately answered, explicitly disclosed as a gap, missed, or unverified. Keep answered and disclosed counts separate. |
| Unique Findings | Count materially different, relevant and supported findings; deduplicate the underlying event/report, not just its URL. |
| Freshness Compliance | Verify dated sources are inside the half-open/closed boundary actually used by the run. An in-window ledger timestamp alone does not authenticate the publisher's date. |
| Source Independence | Compare provenance and common authorship. Mirror URLs, copied press releases and articles from the same reporter do not establish corroboration. |
| Contradiction Handling | For each relevant, retrievable contradiction, mark present with correct strength, present but overstated, absent, or not assessed. |
| Opportunity Quality | Check user, concrete pain, alternatives, real demand evidence, risks, falsifier and validation method. A qualified abstention is valid when the evidence is thin; it is not a grounded opportunity. |
| Cost Efficiency | Attribute distinct supported findings to each round when possible. Report time, request counts and actual provider data separately. No billing figure is inferred from token counts. |

A report with zero checked claims has an undefined grounding rate. Unsupported
or unverified claims do not count as successes. Run-quality confirmation
requires enough independently reviewed, representative cases and gate
coverage. Compare paired reports on the same cutoff, market, budget and model.
Record differing access or route availability. If provenance, source depth or
budgets cannot be aligned for a competitor, describe it as an exploratory run.

## Review record

For each packet record reviewer identity or independent review session,
per-claim text, evidence IDs, URL opens, observed dates, grounding labels,
per-question answers or disclosures, sources with common provenance, any
contrary observations, and unassessed metrics. An RC verdict requires at least
95% checked key factual claims supported and at least 80% independently
identified core questions answered or explicitly disclosed, with no
undisclosed material factual errors. Lower coverage, missing validation and
unverified claims remain visible. The release decision also checks installer,
platform runs, data safety and the ability to reproduce research.
