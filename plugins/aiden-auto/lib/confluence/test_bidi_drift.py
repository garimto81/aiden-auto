#!/usr/bin/env python3
"""Tests for confluence_bidi_sync.py — drift classification + planning + manifest."""

import confluence_bidi_sync as bs


# --- frontmatter handling ---------------------------------------------------

def test_split_body_with_frontmatter():
    md = "---\ntitle: X\nconfluence-page-id: 1\n---\nreal body here\n"
    assert bs.split_body(md) == "real body here\n"


def test_split_body_without_frontmatter():
    md = "no frontmatter body\n"
    assert bs.split_body(md) == md


def test_merge_frontmatter_keeps_local_fm():
    local = "---\ntitle: Local\n---\nold body\n"
    merged = bs.merge_frontmatter(local, "new body\n")
    assert merged.startswith("---\ntitle: Local\n---\n")
    assert "new body" in merged
    assert "old body" not in merged


# --- drift 4-case -----------------------------------------------------------

def test_drift_neither():
    assert bs.classify_drift("body", "body", "body", 5, 5) == bs.NEITHER


def test_drift_only_local():
    assert bs.classify_drift("LOCAL", "body", "body", 5, 5) == bs.ONLY_LOCAL


def test_drift_only_remote():
    assert bs.classify_drift("body", "body", "REMOTE", 6, 5) == bs.ONLY_REMOTE


def test_drift_both():
    assert bs.classify_drift("LOCAL", "body", "REMOTE", 6, 5) == bs.BOTH


def test_drift_cosmetic_version_bump_ignored():
    """Version bumped but normalized content identical → NOT remote-changed.

    Cosmetic = trailing whitespace + collapsible blank-line runs (Confluence
    re-format noise). Real paragraph-structure changes are NOT masked.
    """
    base = "line one\n\nline two"
    theirs = "line one\n\n\n\nline two   \n"   # extra blanks + trailing ws only
    assert bs.classify_drift(base, base, theirs, 7, 5) == bs.NEITHER


def test_drift_remote_version_same_no_change():
    assert bs.classify_drift("body", "body", "REMOTE-but-version-same", 5, 5) == bs.NEITHER


# --- plan_document ----------------------------------------------------------

def test_plan_bootstrap_when_no_base():
    plan = bs.plan_document("---\nt: 1\n---\nbody\n", None, "body", 5, None, {"dropped": []})
    assert plan["action"] == bs.BOOTSTRAP
    assert plan["merged_body"] == "body\n"


def test_plan_only_local_push():
    local = "---\nt: 1\n---\nLOCAL edit\n"
    plan = bs.plan_document(local, "orig\n", "orig\n", 5, 5, {"dropped": []})
    assert plan["action"] == bs.ONLY_LOCAL
    assert plan["status"] == "push"


def test_plan_only_remote_pull():
    local = "---\nt: 1\n---\norig\n"
    plan = bs.plan_document(local, "orig\n", "REMOTE\n", 6, 5, {"dropped": []})
    assert plan["action"] == bs.ONLY_REMOTE
    assert plan["merged_body"] == "REMOTE\n"


def test_plan_both_automerge_clean():
    base = "alpha\nbeta\ngamma\ndelta\n"
    local = "---\nt:1\n---\nALPHA\nbeta\ngamma\ndelta\n"
    theirs = "alpha\nbeta\ngamma\nDELTA\n"
    plan = bs.plan_document(local, base, theirs, 6, 5, {"dropped": []})
    assert plan["action"] == bs.BOTH
    assert plan["status"] == "merged"
    assert plan["conflict"] is False
    assert "ALPHA" in plan["merged_body"] and "DELTA" in plan["merged_body"]


def test_plan_both_conflict():
    base = "title\nshared\nfoot\n"
    local = "---\nt:1\n---\ntitle\nLOCAL\nfoot\n"
    theirs = "title\nREMOTE\nfoot\n"
    plan = bs.plan_document(local, base, theirs, 6, 5, {"dropped": []})
    assert plan["action"] == bs.BOTH
    assert plan["status"] == "conflict"
    assert plan["conflict"] is True


def test_plan_warns_on_dropped_macros():
    plan = bs.plan_document("body", "body", "body", 5, 5, {"dropped": ["mystery"]})
    assert any("mystery" in w for w in plan["warnings"])


# --- manifest I/O -----------------------------------------------------------

def test_manifest_roundtrip(tmp_path):
    data = {"schema": 1, "entries": {"docs/A.md": {"page_id": "123", "confluence_version": 4}}}
    bs.save_manifest(tmp_path, data)
    loaded = bs.load_manifest(tmp_path)
    assert loaded["entries"]["docs/A.md"]["page_id"] == "123"
    assert loaded["entries"]["docs/A.md"]["confluence_version"] == 4


def test_manifest_default_when_missing(tmp_path):
    loaded = bs.load_manifest(tmp_path)
    assert loaded == {"schema": 1, "entries": {}}


def test_base_snapshot_roundtrip(tmp_path):
    bs.write_base(tmp_path, "999", "base body content\n")
    assert bs.read_base(tmp_path, "999") == "base body content\n"
    assert bs.read_base(tmp_path, "000") is None


def test_build_link_resolver_inverts():
    repo_map = {
        "docs/Foundation.md": ("123", "Foundation", "http://x/pages/123"),
        "Foundation.md": ("123", "Foundation", "http://x/pages/123"),  # basename dup
    }
    resolver = bs.build_link_resolver(repo_map)
    assert resolver["Foundation"] == "docs/Foundation.md"
