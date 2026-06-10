#!/usr/bin/env python3
"""Tests for confluence2md.py — reverse converter + lossless macro preservation."""

import shutil

import pytest

import confluence2md as c2m

HAS_PANDOC = shutil.which("pandoc") is not None
pandoc_only = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc not installed")


# --- Lossless preservation (the core guarantee) ----------------------------

def test_toc_macro_preserved_verbatim():
    """The Confluence Table of Contents macro has no MD equivalent — it MUST be
    preserved verbatim, never dropped (the user's explicit requirement)."""
    toc = '<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">3</ac:parameter></ac:structured-macro>'
    storage = f"<p>intro</p>{toc}<p>outro</p>"
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "toc" in ledger["preserved"]
    assert ledger["dropped"] == []
    assert f"```{c2m.PRESERVE_FENCE} name=toc" in md
    assert 'ac:name="toc"' in md           # original macro xml embedded
    assert 'ac:name="maxLevel"' in md      # params survive too


def test_self_closing_macro_preserved():
    storage = '<ac:structured-macro ac:name="status" ac:schema-version="1"/>'
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "status" in ledger["preserved"]
    assert 'ac:name="status"' in md


def test_unknown_macro_preserved_not_dropped():
    storage = '<ac:structured-macro ac:name="some-future-macro"><ac:parameter ac:name="x">1</ac:parameter></ac:structured-macro>'
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "some-future-macro" in ledger["preserved"]
    assert ledger["dropped"] == []
    assert "some-future-macro" in md


def test_children_macro_preserved():
    storage = '<ac:structured-macro ac:name="children"/>'
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "children" in ledger["preserved"]


# --- Convertible macros -----------------------------------------------------

def test_code_macro_converts():
    storage = (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">python</ac:parameter>'
        '<ac:plain-text-body><![CDATA[print("hi")]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "code" in ledger["converted"]
    assert "code" not in ledger["preserved"]
    assert 'class="python"' in md
    assert 'print(&quot;hi&quot;)' in md or 'print("hi")' in md


def test_code_cdata_escape_reversed():
    # Decode the split-CDATA escape directly (HTML stage will entity-escape '>',
    # which pandoc later restores — so test the decoder, not the escaped HTML).
    macro = (
        '<ac:structured-macro ac:name="code">'
        '<ac:plain-text-body><![CDATA[a]]]]><![CDATA[>b]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    assert c2m._plain_body(macro) == "a]]>b"


def test_info_panel_to_blockquote():
    storage = '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>heads up</p></ac:rich-text-body></ac:structured-macro>'
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "info" in ledger["converted"]
    assert "<blockquote>" in md
    assert "heads up" in md


def test_causality_panel_dropped():
    """Auto-generated causality panel must NOT round-trip into the body."""
    storage = (
        '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
        '<p><strong>ℹ️ 문서 인과관계</strong></p><ul><li>x</li></ul>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "문서 인과관계" not in md
    assert "info" in ledger["converted"]  # handled, not preserved


def test_expand_to_details():
    storage = (
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">More</ac:parameter>'
        '<ac:rich-text-body><p>hidden</p></ac:rich-text-body>'
        '</ac:structured-macro>'
    )
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "expand" in ledger["converted"]
    assert "<details><summary>More</summary>" in md
    assert "hidden" in md


def test_nested_preserve_inside_expand():
    """A preserved macro nested in a convertible wrapper still survives."""
    storage = (
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="toc"/>'
        '</ac:rich-text-body>'
        '</ac:structured-macro>'
    )
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "expand" in ledger["converted"]
    assert "toc" in ledger["preserved"]
    assert 'ac:name="toc"' in md


# --- Images / links / layout ------------------------------------------------

def test_image_attachment_collected():
    storage = '<ac:image ac:alt="d"><ri:attachment ri:filename="diagram.png" /></ac:image>'
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "diagram.png" in ledger["attachments"]
    assert 'src="diagram.png"' in md


def test_link_reverse_resolves():
    storage = (
        '<ac:link><ri:page ri:content-title="Foundation"/>'
        '<ac:plain-text-link-body><![CDATA[see foundation]]></ac:plain-text-link-body></ac:link>'
    )
    md, _ = c2m.confluence_to_md(
        storage, link_resolver={"Foundation": "docs/Foundation.md"}, run_pandoc=False,
    )
    assert 'href="docs/Foundation.md"' in md


def test_link_unresolved_degrades_to_text():
    storage = (
        '<ac:link><ri:page ri:content-title="Ghost"/>'
        '<ac:plain-text-link-body><![CDATA[ghost link]]></ac:plain-text-link-body></ac:link>'
    )
    md, _ = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "ghost link" in md
    assert "href" not in md


def test_layout_unwrapped():
    storage = '<ac:layout><ac:layout-section ac:type="two_equal"><ac:layout-cell><p>L</p></ac:layout-cell><ac:layout-cell><p>R</p></ac:layout-cell></ac:layout-section></ac:layout>'
    md, _ = c2m.confluence_to_md(storage, run_pandoc=False)
    assert "ac:layout" not in md
    assert "L" in md and "R" in md


# --- Silent-loss guard ------------------------------------------------------

def test_dropped_always_empty():
    storage = (
        '<p>text</p>'
        '<ac:structured-macro ac:name="toc"/>'
        '<ac:structured-macro ac:name="weird-macro"/>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[x]]></ac:plain-text-body></ac:structured-macro>'
    )
    _, ledger = c2m.confluence_to_md(storage, run_pandoc=False)
    assert ledger["dropped"] == []


# --- Full pandoc path -------------------------------------------------------

@pandoc_only
def test_full_pipeline_toc_survives_with_pandoc():
    toc = '<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">2</ac:parameter></ac:structured-macro>'
    storage = f"<h1>Title</h1><p>body text</p>{toc}"
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=True)
    assert "Title" in md
    assert f"```{c2m.PRESERVE_FENCE} name=toc" in md
    assert 'ac:name="toc"' in md
    assert ledger["dropped"] == []


@pandoc_only
def test_full_pipeline_code_block():
    storage = (
        '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">js</ac:parameter>'
        '<ac:plain-text-body><![CDATA[const x = 1;]]></ac:plain-text-body></ac:structured-macro>'
    )
    md, _ = c2m.confluence_to_md(storage, run_pandoc=True)
    assert "const x = 1;" in md
    assert "```" in md
