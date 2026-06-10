#!/usr/bin/env python3
"""Tests for threeway.py — 3-way merge helper."""

import threeway as tw


def test_no_change_returns_base():
    status, merged = tw.merge_texts("same\nbody\n", "same\nbody\n", "same\nbody\n")
    assert status == tw.CLEAN
    assert "same" in merged and "body" in merged


def test_only_ours_changed():
    base = "line1\nline2\nline3\n"
    ours = "line1\nLOCAL-EDIT\nline3\n"
    theirs = base
    status, merged = tw.merge_texts(ours, base, theirs)
    assert status == tw.CLEAN
    assert "LOCAL-EDIT" in merged


def test_only_theirs_changed():
    base = "line1\nline2\nline3\n"
    ours = base
    theirs = "line1\nREMOTE-EDIT\nline3\n"
    status, merged = tw.merge_texts(ours, base, theirs)
    assert status == tw.CLEAN
    assert "REMOTE-EDIT" in merged


def test_both_changed_different_lines_automerges():
    base = "alpha\nbeta\ngamma\ndelta\n"
    ours = "ALPHA-LOCAL\nbeta\ngamma\ndelta\n"      # changed line 1
    theirs = "alpha\nbeta\ngamma\nDELTA-REMOTE\n"    # changed line 4
    status, merged = tw.merge_texts(ours, base, theirs)
    assert status == tw.CLEAN
    assert "ALPHA-LOCAL" in merged
    assert "DELTA-REMOTE" in merged


def test_both_changed_same_line_conflicts():
    base = "title\nshared line\nfooter\n"
    ours = "title\nLOCAL version\nfooter\n"
    theirs = "title\nREMOTE version\nfooter\n"
    status, merged = tw.merge_texts(ours, base, theirs)
    assert status == tw.CONFLICT
    assert tw.has_conflict_markers(merged)
    assert "LOCAL version" in merged and "REMOTE version" in merged


def test_sha256_stable_and_differs():
    a = tw.sha256_text("hello")
    b = tw.sha256_text("hello")
    c = tw.sha256_text("world")
    assert a == b
    assert a != c
    assert a.startswith("sha256:")


def test_normalize_ignores_cosmetic_whitespace():
    a = "# Title\n\n\n\npara   \n"
    b = "# Title\n\npara\n"
    assert tw.normalize_for_compare(a) == tw.normalize_for_compare(b)


def test_normalize_strips_html_comments():
    a = "body\n<!-- confluence-macro: toc -->\nmore"
    b = "body\n\nmore"
    assert tw.normalize_for_compare(a) == tw.normalize_for_compare(b)


def test_normalize_keeps_real_difference():
    a = tw.normalize_for_compare("real content one")
    b = tw.normalize_for_compare("real content two")
    assert a != b


def test_has_conflict_markers_false_on_clean():
    assert not tw.has_conflict_markers("just\nnormal\ntext\n")
