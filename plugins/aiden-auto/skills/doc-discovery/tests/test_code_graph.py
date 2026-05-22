"""Self-verification suite for Layer 1+ code graph (Week 2)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.code_graph import (  # noqa: E402
    extract_code_edges,
    iter_code_files,
    parse_js_ts,
    parse_python,
)


def test_python_imports_and_defs():
    text = """
import os
from collections import defaultdict
from .utils import helper

def foo(): pass
async def bar(): pass

class Baz:
    def method(self): pass
"""
    edges = parse_python("src/mod.py", text)
    edge_set = {(s, t, x) for s, t, x in edges}

    assert ("src/mod.py", "imports", "os") in edge_set
    assert ("src/mod.py", "imports", "collections") in edge_set
    assert ("src/mod.py", "references", "symbol:collections::defaultdict") in edge_set
    assert ("src/mod.py", "defines", "symbol:src.mod::foo") in edge_set
    assert ("src/mod.py", "defines", "symbol:src.mod::bar") in edge_set
    assert ("src/mod.py", "defines", "symbol:src.mod::Baz") in edge_set
    # method should NOT be a top-level define (only Baz is)
    assert ("src/mod.py", "defines", "symbol:src.mod::method") not in edge_set


def test_python_handles_syntax_error_gracefully():
    edges = parse_python("broken.py", "def foo( oops")
    assert edges == []


def test_python_star_import_skipped():
    edges = parse_python("x.py", "from foo import *")
    edge_set = {(s, t, x) for s, t, x in edges}
    # 'foo' as imports yes; '*' as references no
    assert ("x.py", "imports", "foo") in edge_set
    assert all("*" not in target for _, _, target in edges)


def test_js_imports_and_exports():
    text = """
import React from 'react';
import { useState, useEffect } from 'react';
const lodash = require('lodash');

export function Foo() {}
export const Bar = () => {};
export default function Baz() {}
"""
    edges = parse_js_ts("src/Foo.tsx", text)
    edge_set = {(s, t, x) for s, t, x in edges}

    assert ("src/Foo.tsx", "imports", "react") in edge_set
    assert ("src/Foo.tsx", "imports", "lodash") in edge_set
    assert ("src/Foo.tsx", "defines", "symbol:src.Foo::Foo") in edge_set
    assert ("src/Foo.tsx", "defines", "symbol:src.Foo::Bar") in edge_set
    assert ("src/Foo.tsx", "defines", "symbol:src.Foo::Baz") in edge_set


def test_js_dedup_imports():
    text = "import a from 'lib';\nimport b from 'lib';"
    edges = parse_js_ts("x.js", text)
    imports = [e for e in edges if e[1] == "imports"]
    assert len(imports) == 1


def test_extract_code_edges_unknown_extension_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        unknown = root / "data.csv"
        unknown.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        assert extract_code_edges(unknown, root) == []


def test_iter_code_files_respects_exclude():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        keep = root / "lib" / "real.py"
        keep.parent.mkdir(parents=True)
        keep.write_text("x = 1", encoding="utf-8")

        skip = root / "lib" / "node_modules" / "junk.js"
        skip.parent.mkdir(parents=True)
        skip.write_text("var x;", encoding="utf-8")

        files = list(iter_code_files(root))
        rel_files = [str(f.relative_to(root)).replace("\\", "/") for f in files]

        assert "lib/real.py" in rel_files
        assert all("node_modules" not in p for p in rel_files)


# ─────────────────── runner ────────────────────

def _run_all() -> int:
    failures = []
    tests = [
        test_python_imports_and_defs,
        test_python_handles_syntax_error_gracefully,
        test_python_star_import_skipped,
        test_js_imports_and_exports,
        test_js_dedup_imports,
        test_extract_code_edges_unknown_extension_returns_empty,
        test_iter_code_files_respects_exclude,
    ]
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, f"{type(e).__name__}: {e}"))
            print(f"ERROR {fn.__name__}: {e}")
    print("─" * 60)
    if failures:
        print(f"FAILED  {len(failures)}/{len(tests)} test(s)")
        return 1
    print(f"OK  all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
