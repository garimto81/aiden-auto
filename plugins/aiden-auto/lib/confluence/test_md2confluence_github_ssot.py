#!/usr/bin/env python3
"""Tests for rule 22 — GitHub SSOT document cross-links in md2confluence.

Run: python -m pytest lib/confluence/test_md2confluence_github_ssot.py -v
"""
import os
import tempfile
from pathlib import Path

import md2confluence as md


# ── _github_slug ───────────────────────────────────────────────────────────
def test_github_slug_https():
    assert md._github_slug("https://github.com/garimto81/claude.git") == "garimto81/claude"


def test_github_slug_https_no_dotgit():
    assert md._github_slug("https://github.com/owner/repo") == "owner/repo"


def test_github_slug_ssh():
    assert md._github_slug("git@github.com:owner/repo.git") == "owner/repo"


def test_github_slug_non_github():
    assert md._github_slug("https://gitlab.com/owner/repo.git") == ""
    assert md._github_slug("") == ""


# ── github_url_for ───────────────────────────────────────────────────────────
def _seed(repo_root, base):
    md._GITHUB_BASE_CACHE[str(repo_root)] = base


def test_github_url_for_builds_blob_main():
    root = "/tmp/fakerepo"
    _seed(root, "https://github.com/garimto81/claude/blob/main")
    assert md.github_url_for(root, "docs/00-prd/x.md") == \
        "https://github.com/garimto81/claude/blob/main/docs/00-prd/x.md"


def test_github_url_for_encodes_spaces():
    root = "/tmp/fakerepo2"
    _seed(root, "https://github.com/o/r/blob/main")
    url = md.github_url_for(root, "2. Development/Command Center/Overview.md")
    assert url == "https://github.com/o/r/blob/main/2.%20Development/Command%20Center/Overview.md"
    assert " " not in url  # no raw spaces


def test_github_url_for_empty_when_no_remote():
    root = "/tmp/fakerepo3"
    _seed(root, "")
    assert md.github_url_for(root, "docs/x.md") == ""


def test_github_ssot_disabled_env(monkeypatch=None):
    os.environ["GITHUB_SSOT"] = "0"
    try:
        md._GITHUB_BASE_CACHE.clear()
        assert md.derive_github_base("/tmp/whatever") == ""
    finally:
        del os.environ["GITHUB_SSOT"]
        md._GITHUB_BASE_CACHE.clear()


# ── _linkify_path GitHub-first ───────────────────────────────────────────────
def _make_repo():
    tmp = tempfile.mkdtemp(prefix="ghssot_")
    root = Path(tmp)
    docs = root / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A", encoding="utf-8")
    (docs / "b.md").write_text("# B", encoding="utf-8")
    return root, docs


def test_linkify_path_prefers_github():
    root, docs = _make_repo()
    _seed(root, "https://github.com/o/r/blob/main")
    out = md._linkify_path("b.md", {}, docs, root)
    assert out == '<a href="https://github.com/o/r/blob/main/docs/b.md">b.md</a>'


def test_linkify_path_falls_back_to_code_when_target_missing():
    root, docs = _make_repo()
    _seed(root, "https://github.com/o/r/blob/main")
    # nonexistent target → no GitHub link, no confluence entry → <code>
    out = md._linkify_path("ghost.md", {}, docs, root)
    assert out == "<code>ghost.md</code>"


def test_linkify_path_confluence_fallback_when_no_remote():
    root, docs = _make_repo()
    _seed(root, "")  # no GitHub remote
    repo_map = {"docs/b.md": ("123", "b", "https://wiki/pages/123")}
    out = md._linkify_path("b.md", repo_map, docs, root)
    assert out == '<a href="https://wiki/pages/123">b.md</a>'


# ── transform_cross_links GitHub-first ───────────────────────────────────────
def test_transform_cross_links_to_github():
    root, docs = _make_repo()
    _seed(root, "https://github.com/o/r/blob/main")
    html = '<p>see <a href="b.md">B doc</a></p>'
    out = md.transform_cross_links(html, {}, docs, root)
    assert '<a href="https://github.com/o/r/blob/main/docs/b.md">B doc</a>' in out


def test_transform_cross_links_confluence_fallback():
    root, docs = _make_repo()
    _seed(root, "")
    repo_map = {"docs/b.md": ("123", "b", "https://wiki/pages/123")}
    html = '<p>see <a href="b.md">B doc</a></p>'
    out = md.transform_cross_links(html, repo_map, docs, root)
    assert '<a href="https://wiki/pages/123">B doc</a>' in out


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
