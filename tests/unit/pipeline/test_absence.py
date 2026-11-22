"""Deterministic absence-state model tests (Research Quality Sprint P0)."""
from __future__ import annotations

import pytest

from sourceglint.pipeline.absence import (
    NOT_RETRIEVED,
    OUT_OF_WINDOW,
    SOURCE_UNAVAILABLE,
    UNVERIFIED,
    VERIFIED_ABSENT,
    AbsenceContext,
    classify_absence,
    detect_absence_claims,
    qualify_text,
)


class TestClassify:
    def test_verified_absence_wins(self):
        assert classify_absence(
            "release",
            verified_absent=True,
            source_unavailable=True,
            window_checked=True,
            searched=False,
        ) == VERIFIED_ABSENT

    def test_unavailable_source(self):
        assert classify_absence(
            "release",
            verified_absent=False,
            source_unavailable=True,
            window_checked=False,
            searched=True,
        ) == SOURCE_UNAVAILABLE

    def test_window_scoped(self):
        assert classify_absence(
            "release",
            verified_absent=False,
            source_unavailable=False,
            window_checked=True,
            searched=True,
        ) == OUT_OF_WINDOW

    def test_searched_but_absent(self):
        assert classify_absence(
            "release",
            verified_absent=False,
            source_unavailable=False,
            window_checked=False,
            searched=True,
        ) == NOT_RETRIEVED

    def test_never_searched(self):
        assert classify_absence(
            "release",
            verified_absent=False,
            source_unavailable=False,
            window_checked=False,
            searched=False,
        ) == UNVERIFIED


class TestDetect:
    def test_real_baseline_claim_is_detected(self):
        claims = detect_absence_claims(
            "no coding-agent candidate has a dated release artifact"
        )
        assert any(c.object == "release" for c in claims)

    def test_no_longer_is_not_an_absence_claim(self):
        assert detect_absence_claims("The project no longer publishes releases.") == ()

    def test_not_only_is_not_an_absence_claim(self):
        assert detect_absence_claims("Not only releases but tags moved.") == ()

    def test_no_fewer_than_is_not_an_absence_claim(self):
        assert detect_absence_claims("No fewer than three releases shipped.") == ()

    def test_chinese_absence_claim(self):
        claims = detect_absence_claims("该仓库在窗口内没有发布版本。")
        assert any(c.object == "release" for c in claims)

    def test_positive_statement_has_no_claim(self):
        assert detect_absence_claims("Three releases shipped in November.") == ()


class TestQualify:
    def test_unverified_claim_is_scoped_not_deleted(self):
        text, checks = qualify_text(
            "no coding-agent candidate has a dated release artifact",
            context=AbsenceContext(searched=True),
        )
        assert text.startswith("Unverified absence:")
        assert "dated release artifact" in text
        assert checks[0]["status"] == NOT_RETRIEVED

    def test_verified_absence_is_preserved(self):
        text, checks = qualify_text(
            "There are no releases for example/repo.",
            context=AbsenceContext(verified_objects=frozenset({"release"})),
        )
        assert "Unverified absence" not in text
        assert checks[0]["status"] == VERIFIED_ABSENT

    def test_unavailable_source_prefix(self):
        text, _ = qualify_text(
            "There are no releases.",
            context=AbsenceContext(source_unavailable=True),
        )
        assert text.startswith("Absence not verified (source unavailable):")

    def test_out_of_window_prefix(self):
        text, _ = qualify_text(
            "There are no releases.",
            context=AbsenceContext(window_checked=True),
        )
        assert text.startswith("Within the research window:")

    def test_non_claim_text_unchanged(self):
        value = "Three releases shipped."
        text, checks = qualify_text(value, context=AbsenceContext())
        assert text == value
        assert checks == ()

    def test_multiple_sentences_keep_boundaries(self):
        text, _ = qualify_text(
            "Releases are documented. No user feedback was found.",
            context=AbsenceContext(searched=True),
        )
        assert "Releases are documented." in text
        assert "Unverified absence:" in text


class TestContextFromObservations:
    def test_zero_release_observations_verify_only_that_object(self):
        ctx = AbsenceContext.from_observations(
            [
                {"kind": "releases", "status": "verified_absent", "repository": "a/b"},
                {"kind": "releases", "status": "verified_absent", "repository": "c/d"},
            ]
        )
        assert ctx.verified_objects == frozenset({"release"})
        text, checks = qualify_text("a/b has no releases.", context=ctx)
        assert checks[0]["status"] == VERIFIED_ABSENT
        assert "Unverified" not in text

    def test_unscoped_claim_is_not_verified_outside_checked_repositories(self):
        ctx = AbsenceContext.from_observations(
            [
                {"kind": "releases", "status": "verified_absent", "repository": "a/b"},
                {"kind": "releases", "status": "verified_absent", "repository": "c/d"},
            ]
        )
        text, checks = qualify_text("No releases found.", context=ctx)
        assert checks[0]["status"] == NOT_RETRIEVED
        assert "Unverified absence" in text

    def test_single_repo_absence_is_not_market_wide(self):
        ctx = AbsenceContext.from_observations(
            [{"kind": "releases", "status": "verified_absent", "repository": "a/b"}]
        )
        assert ctx.verified_objects == frozenset()

    def test_one_present_repo_blocks_verified_absence(self):
        ctx = AbsenceContext.from_observations(
            [
                {"kind": "releases", "status": "verified_absent", "repository": "a/b"},
                {"kind": "releases", "status": "present", "repository": "c/d"},
            ]
        )
        assert "release" not in ctx.verified_objects

    def test_rate_limit_marks_source_unavailable(self):
        ctx = AbsenceContext.from_observations(
            [{"kind": "releases", "status": "rate_limited", "repository": "a/b"}]
        )
        assert ctx.source_unavailable is True
        assert "rate_limited" in " ".join(ctx.basis)
