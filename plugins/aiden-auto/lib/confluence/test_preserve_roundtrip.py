#!/usr/bin/env python3
"""Round-trip tests: confluence-storage fence survives pull -> push verbatim."""

import shutil
from pathlib import Path

import pytest

import md2confluence as m2c
import confluence2md as c2m

HAS_PANDOC = shutil.which("pandoc") is not None
pandoc_only = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc not installed")

TOC = '<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">3</ac:parameter></ac:structured-macro>'


def test_extract_restore_roundtrip():
    md = f"# Title\n\n```confluence-storage name=toc\n{TOC}\n```\n\nbody\n"
    stripped, preserved = m2c._extract_preserved_storage(md)
    assert preserved == [TOC]
    assert "ac:name=\"toc\"" not in stripped     # pulled out before pandoc
    assert "CONFLUENCESTORAGEINJECT0X" in stripped
    # simulate pandoc wrapping the token in a paragraph
    html = stripped.replace("CONFLUENCESTORAGEINJECT0X", "<p>CONFLUENCESTORAGEINJECT0X</p>")
    restored = m2c._restore_preserved_storage(html, preserved)
    assert TOC in restored
    assert "CONFLUENCESTORAGEINJECT" not in restored


def test_restore_noop_when_empty():
    assert m2c._restore_preserved_storage("<p>x</p>", []) == "<p>x</p>"


def test_extract_noop_when_no_fence():
    md = "# Plain\n\njust text\n"
    stripped, preserved = m2c._extract_preserved_storage(md)
    assert preserved == []
    assert stripped == md


@pandoc_only
def test_full_push_reinjects_toc(tmp_path):
    md = f"# Heading\n\n```confluence-storage name=toc\n{TOC}\n```\n\nSome body.\n"
    f = tmp_path / "doc.md"
    f.write_text(md, encoding="utf-8")
    result = m2c.convert(str(f), "0", dry_run=True)
    html = Path(result["preview"]).read_text(encoding="utf-8")
    assert 'ac:name="toc"' in html
    assert 'ac:name="maxLevel"' in html
    assert "CONFLUENCESTORAGEINJECT" not in html


@pandoc_only
def test_pull_then_push_preserves_toc(tmp_path):
    """Full bidirectional: storage -> confluence2md -> md -> md2confluence -> storage."""
    storage = f"<h1>T</h1><p>intro</p>{TOC}<p>end</p>"
    md, ledger = c2m.confluence_to_md(storage, run_pandoc=True)
    assert ledger["dropped"] == []
    f = tmp_path / "doc.md"
    f.write_text(md, encoding="utf-8")
    result = m2c.convert(str(f), "0", dry_run=True)
    out = Path(result["preview"]).read_text(encoding="utf-8")
    assert 'ac:name="toc"' in out
    assert 'ac:name="maxLevel"' in out
