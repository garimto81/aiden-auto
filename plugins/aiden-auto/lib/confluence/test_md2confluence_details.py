#!/usr/bin/env python3
"""Tests for md2confluence <details>/<summary> -> Confluence expand macro.

Covers the 0a.5 transform in postprocess_html: a GitHub-native collapsible
block becomes a Confluence `expand` macro so "접기" works on both platforms.
Run individually:

    pytest lib/confluence/test_md2confluence_details.py -v
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

# Load md2confluence.py by path so the test is independent of sys.path / cwd.
_MOD_PATH = Path(__file__).with_name("md2confluence.py")
_spec = importlib.util.spec_from_file_location("md2confluence", _MOD_PATH)
md2c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(md2c)


# ---------------------------------------------------------------------------
# postprocess_html: <details><summary> -> expand macro
# ---------------------------------------------------------------------------

def test_details_to_expand_basic():
    # Simulate pandoc output: details/summary raw + inner pre/code.
    html = (
        "<details>\n<summary>📐 원본 ASCII 다이어그램 보기</summary>\n"
        "<pre><code>+--+\n|AA|\n+--+</code></pre>\n</details>"
    )
    out = md2c.postprocess_html(html)
    assert '<ac:structured-macro ac:name="expand">' in out
    assert '<ac:parameter ac:name="title">📐 원본 ASCII 다이어그램 보기</ac:parameter>' in out
    assert 'ac:name="code"' in out          # inner code macro nested (from step 0a)
    assert "<details" not in out and "<summary" not in out  # raw tags gone


def test_summary_less_details_untouched():
    # No <summary> -> not converted (and raw <details> survives, which is fine
    # because authors never write summary-less <details> in our docs).
    html = "<details><p>no summary</p></details>"
    out = md2c.postprocess_html(html)
    assert 'ac:name="expand"' not in out


def test_no_double_escape_of_ampersand_in_title():
    # pandoc already escaped & -> &amp; ; we must NOT re-escape to &amp;amp;.
    html = (
        "<details>\n<summary>A &amp; B</summary>\n"
        "<pre><code>x</code></pre>\n</details>"
    )
    out = md2c.postprocess_html(html)
    assert '<ac:parameter ac:name="title">A &amp; B</ac:parameter>' in out
    assert "&amp;amp;" not in out


def test_two_sibling_details_blocks():
    html = (
        "<details>\n<summary>One</summary>\n<pre><code>a</code></pre>\n</details>\n"
        "<details>\n<summary>Two</summary>\n<pre><code>b</code></pre>\n</details>"
    )
    out = md2c.postprocess_html(html)
    assert out.count('<ac:structured-macro ac:name="expand">') == 2


# ---------------------------------------------------------------------------
# Integration guard: pandoc nests the fenced code INSIDE <details>.
# This is the load-bearing authoring contract (blank line after </summary>
# and before </details>). If this fails, the .md authoring is wrong, not
# the Python transform.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_pandoc_nests_code_in_details():
    md = "<details>\n<summary>T</summary>\n\n```\nABC\n```\n\n</details>\n"
    raw = md2c.md_to_html(md, ".")
    assert "<pre" in raw and "<code" in raw   # fence became a code block
    assert "<details" in raw                   # wrapper passed through raw
    # Full pipeline then yields an expand macro with a nested code macro.
    out = md2c.postprocess_html(raw)
    assert '<ac:structured-macro ac:name="expand">' in out
    assert 'ac:name="code"' in out
