"""Shared fixtures for the doc-discovery test suite.

`root` and `script_path` are referenced by the Week 1 test_graph_builder.py
suite — without these, pytest reports `fixture 'root' not found`. The
fixtures here mirror the in-process `_run_all()` runner inside
test_graph_builder.py so both pytest and direct execution succeed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Materialize the Week 1 fixture project in a fresh tmp dir."""
    from tests.test_graph_builder import make_fixture  # local import

    make_fixture(tmp_path)
    return tmp_path


@pytest.fixture
def script_path() -> Path:
    """Absolute path to the CLI entrypoint."""
    return HERE.parent / "scripts" / "doc_discovery.py"
