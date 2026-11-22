"""Rendering-quality regressions from the real industry-agents brief.

Baseline defects: 34 redundant backslashes (``code\\.``, ``\\(s\\)``),
undecoded ``&amp;``, and a truncated gap glued to a deterministic sentence
("awaits its first No evidence ...").
"""
from __future__ import annotations

from sourceglint.brief import sections
from sourceglint.brief.dtos import BriefContext, SelectedBrief
from sourceglint.pipeline.adaptive import _join_gap


def test_no_redundant_backslashes_before_punctuation():
    out = sections._untrusted_inline("code. direct observation(s); vendor_claim_verified T2_community")
    assert "code\\." not in out
    assert "\\(s\\)" not in out
    assert "observation(s)" in out


def test_html_entities_are_decoded():
    assert "&amp;" not in sections._untrusted_inline("Official Build &amp; Verified Release")
    assert sections._untrusted_inline("Official Build &amp; Verified") == "Official Build & Verified"


def test_raw_ampersand_is_not_entity_encoded():
    assert sections._untrusted_inline("Ship & iterate") == "Ship & iterate"


def test_injection_still_inert():
    out = sections._untrusted_inline("<script>alert(1)</script> [x](y)")
    assert "&lt;script&gt;" in out
    assert "<script>" not in out
    assert "\\[x\\]" in out


def test_markdown_structure_characters_remain_escaped():
    out = sections._untrusted_inline("a *b* _c_ `d` #e [f]")
    for token in ("\\*", "\\_", "\\`", "\\#", "\\["):
        assert token in out


def test_research_question_renders_absence_status():
    brief = SelectedBrief(
        context=BriefContext(query="q"),
        research_assessments=(
            {
                "question": "Which agents released a version?",
                "status": "partial",
                "gap": "no coding-agent candidate has a dated release artifact",
                "focus": "industry",
                "absence_checks": [{"object": "release", "status": "not_retrieved"}],
            },
        ),
    )
    md = sections.research_questions(brief, {})
    assert "absence: release → not_retrieved" in md
    assert "code\\." not in md


def test_truncated_gap_is_separated_from_addendum():
    truncated = "Page dates do not establish releases; gitoodo explicitly awaits its first"
    joined = _join_gap(truncated, "No evidence of the required kind: release.")
    assert "first No evidence" not in joined
    assert "first … No evidence" in joined or "first. No evidence" in joined


def test_gap_without_terminal_gets_period():
    assert _join_gap("gap text", "addendum") == "gap text. addendum"


def test_gap_with_terminal_is_not_doubled():
    assert _join_gap("Gap text.", "addendum") == "Gap text. addendum"
