#!/usr/bin/env python3
"""Tests for md2confluence table column auto-width fitting.

Covers _display_width (CJK-aware glyph width) and _fit_table_columns
(per-column px injection into pandoc data tables). Run individually:

    pytest lib/confluence/test_md2confluence_table.py -v
"""

import importlib.util
import re
from pathlib import Path

import pytest

# Load md2confluence.py by path so the test is independent of sys.path / cwd.
_MOD_PATH = Path(__file__).with_name("md2confluence.py")
_spec = importlib.util.spec_from_file_location("md2confluence", _MOD_PATH)
md2c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(md2c)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_widths(html):
    """Extract integer px widths from a <colgroup> in the given html."""
    return [int(w) for w in re.findall(r'<col style="width:\s*(\d+)px"\s*/>', html)]


def _table(*header_then_rows):
    """Build a bare pandoc-style data <table> from (cells_per_row...) tuples.

    First tuple = header cells, the rest = body rows. Each arg is a tuple of
    plain-text cell contents.
    """
    header, *body = header_then_rows
    th = "".join(f"<th>{c}</th>" for c in header)
    out = [f"<table><thead><tr>{th}</tr></thead><tbody>"]
    for row in body:
        td = "".join(f"<td>{c}</td>" for c in row)
        out.append(f"<tr>{td}</tr>")
    out.append("</tbody></table>")
    return "".join(out)


# ---------------------------------------------------------------------------
# _display_width
# ---------------------------------------------------------------------------

class TestDisplayWidth:
    def test_ascii_is_one_unit_each(self):
        assert md2c._display_width("abc") == 3

    def test_hangul_is_two_units_each(self):
        assert md2c._display_width("한글") == 4

    def test_mixed_ascii_and_cjk(self):
        # 1 ASCII (1) + 1 Hangul (2) = 3
        assert md2c._display_width("a한") == 3

    def test_empty_string_is_zero(self):
        assert md2c._display_width("") == 0

    def test_cjk_ideograph_is_two_units(self):
        assert md2c._display_width("漢字") == 4


# ---------------------------------------------------------------------------
# _fit_table_columns — structure
# ---------------------------------------------------------------------------

class TestFitTableStructure:
    def test_injects_colgroup_with_one_col_per_column(self):
        html = _table(("A", "Name"), ("1", "Bob"))
        out = md2c._fit_table_columns(html)
        assert out.count("<colgroup>") == 1
        assert out.count("<col ") == 2  # two columns

    def test_sets_data_layout_default(self):
        html = _table(("A", "B"), ("1", "2"))
        out = md2c._fit_table_columns(html)
        assert '<table data-layout="default">' in out

    def test_widths_are_integers_in_px(self):
        html = _table(("Col1", "Col2"), ("x", "y"))
        widths = _col_widths(md2c._fit_table_columns(html))
        assert len(widths) == 2
        assert all(isinstance(w, int) and w > 0 for w in widths)


# ---------------------------------------------------------------------------
# _fit_table_columns — sizing behavior (the actual feature)
# ---------------------------------------------------------------------------

class TestFitTableSizing:
    def test_short_cells_hit_min_col_floor(self):
        # "A" = 1 unit -> 1*7 + 24 = 31 -> clamped up to _TBL_MIN_COL (70)
        html = _table(("A", "B"), ("1", "2"))
        widths = _col_widths(md2c._fit_table_columns(html))
        assert widths == [md2c._TBL_MIN_COL, md2c._TBL_MIN_COL]

    def test_columns_are_not_distributed_evenly(self):
        # Different content lengths must yield different widths
        # (the core fix: short cells should NOT become as wide as long ones).
        html = _table(
            ("ID", "Description"),
            ("1", "A fairly long description spanning many many words here"),
        )
        widths = _col_widths(md2c._fit_table_columns(html))
        assert widths[0] < widths[1]

    def test_long_column_capped_at_max_col(self):
        long_text = "word " * 200  # far exceeds _TBL_MAX_COL when *7
        html = _table(("Only",), (long_text,))
        widths = _col_widths(md2c._fit_table_columns(html))
        # single column, total < max_total so no scale-down -> exact cap
        assert widths == [md2c._TBL_MAX_COL]

    def test_total_width_scaled_down_when_over_budget(self):
        # 5 long columns would blow past _TBL_MAX_TOTAL (760) -> scaled down
        long = "x" * 100
        html = _table(tuple(f"H{i}" for i in range(5)), tuple(long for _ in range(5)))
        widths = _col_widths(md2c._fit_table_columns(html))
        # rounding can add at most <1px per column above the budget
        assert sum(widths) <= md2c._TBL_MAX_TOTAL + len(widths)
        # and scaling actually happened (each below the per-column cap)
        assert all(w < md2c._TBL_MAX_COL for w in widths)

    def test_hangul_column_wider_than_ascii_for_same_char_count(self):
        ascii_html = _table(("Head",), ("abcd",))   # 4 ASCII units
        hangul_html = _table(("머리",), ("한글유저",))  # 4 CJK -> 8 units
        ascii_w = _col_widths(md2c._fit_table_columns(ascii_html))[0]
        hangul_w = _col_widths(md2c._fit_table_columns(hangul_html))[0]
        assert hangul_w > ascii_w


# ---------------------------------------------------------------------------
# _fit_table_columns — must NOT touch layout blocks
# ---------------------------------------------------------------------------

class TestFitTableLayoutBlocksUntouched:
    def test_presentation_table_is_left_unchanged(self):
        layout = (
            '<table role="presentation"><tbody><tr>'
            "<td>left</td><td>right</td></tr></tbody></table>"
        )
        out = md2c._fit_table_columns(layout)
        assert out == layout
        assert "<colgroup>" not in out

    def test_data_table_processed_while_layout_table_preserved(self):
        layout = '<table role="presentation"><tbody><tr><td>x</td></tr></tbody></table>'
        data = _table(("A", "B"), ("1", "2"))
        out = md2c._fit_table_columns(layout + data)
        assert 'role="presentation"' in out          # layout intact
        assert out.count("<colgroup>") == 1            # only the data table got one
