"""Layer 1+ : code symbol graph (Python AST + JS/TS regex fallback).

Adds code-level reverse dependency to the document graph. Treats imports,
class/function definitions, and module references as typed edges so a
function rename can surface "files calling this symbol" the same way an
Overview.md edit surfaces derivative PRDs.

Design choices:
  - Python: stdlib ast (zero deps, robust)
  - JS/TS: regex (good enough for import/from/require + named exports)
  - Symbol nodes prefixed `symbol:<module>::<name>` to avoid collision
    with file paths in the unified graph
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple


# Edge types specific to code graph (kept disjoint from doc edges)
CODE_EDGE_TYPES = ("imports", "defines", "references")

# JS/TS import patterns. Three forms covered:
#   import X from 'mod'
#   import { X } from 'mod'
#   const X = require('mod')
_JS_IMPORT_FROM = re.compile(
    r"""(?:^|;)\s*import\s+(?:[^'"]+from\s+)?["']([^"']+)["']""",
    re.MULTILINE,
)
_JS_REQUIRE = re.compile(
    r"""require\s*\(\s*["']([^"']+)["']\s*\)""",
)
_JS_EXPORT_NAMED = re.compile(
    r"""(?:^|\n)\s*export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)""",
)
_JS_EXPORT_DEFAULT_FN = re.compile(
    r"""(?:^|\n)\s*export\s+default\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)""",
)


def _module_id(rel_path: str) -> str:
    """Convert 'src/foo/bar.py' -> 'src.foo.bar' (stable Python-style id)."""
    no_ext = re.sub(r"\.(py|pyi|js|jsx|ts|tsx|mjs|cjs)$", "", rel_path)
    return no_ext.replace("/", ".").replace("\\", ".")


def _symbol_node(module: str, name: str) -> str:
    return f"symbol:{module}::{name}"


def parse_python(rel_path: str, text: str) -> List[Tuple[str, str, str]]:
    """Extract (source, edge_type, target) edges from a Python source file.

    Edges produced:
      - file -> imports -> imported_module
      - file -> defines -> symbol:<self_module>::<name>
      - file -> references -> symbol:<imported_module>::<name>  (when import-from)
    """
    edges: List[Tuple[str, str, str]] = []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return edges

    self_module = _module_id(rel_path)

    # walk only direct children of the module (not class/function bodies),
    # so that methods inside classes do NOT appear as top-level defines.
    for node in tree.body:
        # import X / import X as Y / import X.Y.Z
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append((rel_path, "imports", alias.name))
        # from X import Y, Z
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # relative imports (level > 0) are noisy without resolution; record
            # the literal module name when present
            if mod:
                edges.append((rel_path, "imports", mod))
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    edges.append(
                        (rel_path, "references", _symbol_node(mod, alias.name))
                    )
        # def foo(...) / async def foo(...) / class Foo
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            edges.append((rel_path, "defines", _symbol_node(self_module, node.name)))

    return edges


def parse_js_ts(rel_path: str, text: str) -> List[Tuple[str, str, str]]:
    """Extract import + export edges from a JS/TS source file.

    Regex-based (zero deps). Sufficient for top-level import/require/export
    patterns. Inner imports inside conditionals are intentionally skipped.
    """
    edges: List[Tuple[str, str, str]] = []
    self_module = _module_id(rel_path)

    seen_imports: Set[str] = set()
    for pattern in (_JS_IMPORT_FROM, _JS_REQUIRE):
        for match in pattern.finditer(text):
            mod = match.group(1).strip()
            if not mod or mod in seen_imports:
                continue
            seen_imports.add(mod)
            edges.append((rel_path, "imports", mod))

    seen_exports: Set[str] = set()
    for pattern in (_JS_EXPORT_NAMED, _JS_EXPORT_DEFAULT_FN):
        for match in pattern.finditer(text):
            name = match.group(1)
            if not name or name in seen_exports:
                continue
            seen_exports.add(name)
            edges.append((rel_path, "defines", _symbol_node(self_module, name)))

    return edges


# Map extension -> parser. Drives auto-detection in build_code_graph.
PARSERS = {
    ".py": parse_python,
    ".js": parse_js_ts,
    ".jsx": parse_js_ts,
    ".ts": parse_js_ts,
    ".tsx": parse_js_ts,
    ".mjs": parse_js_ts,
    ".cjs": parse_js_ts,
}


def extract_code_edges(file_path: Path, root: Path) -> List[Tuple[str, str, str]]:
    """Detect language by extension and dispatch to the right parser."""
    parser = PARSERS.get(file_path.suffix.lower())
    if parser is None:
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = str(file_path.relative_to(root)).replace("\\", "/")
    return parser(rel, text)


# Default code corpus directories. Conservative — favors common src layouts
# without crawling vendor/build outputs.
DEFAULT_CODE_DIRS = (
    "src",
    "lib",
    "app",
    "tools",
    "scripts",
    ".claude/hooks",
    ".claude/skills",
    "plugins",
)

DEFAULT_CODE_EXTS = tuple(PARSERS.keys())

EXCLUDE_PATTERNS = (
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".next",
    "_generated",
    "_archived",
)


def _excluded(path: Path) -> bool:
    parts = set(path.parts)
    return any(p in parts for p in EXCLUDE_PATTERNS)


def iter_code_files(
    root: Path,
    extensions: Optional[Iterable[str]] = None,
    extra_dirs: Optional[Iterable[str]] = None,
) -> Iterable[Path]:
    """Walk the configured code corpora. Mirrors graph_builder._iter_files."""
    exts = tuple(extensions) if extensions else DEFAULT_CODE_EXTS
    bases = list(DEFAULT_CODE_DIRS) + list(extra_dirs or [])
    for sub in bases:
        base = root / sub
        if not base.exists() or not base.is_dir():
            continue
        for ext in exts:
            try:
                for path in base.rglob(f"*{ext}"):
                    if path.is_file() and not _excluded(path):
                        yield path
            except (OSError, PermissionError):
                continue
