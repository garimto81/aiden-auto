"""Unified doc + code reverse-dependency graph.

Combines:
  - DocGraph (frontmatter `derivative-of` / `references` / `supersedes` + md links)
  - Code graph (Python ast + JS/TS regex: `imports` / `defines` / `references`)

Adds bridge edges when code comments mention .md targets (`# see docs/X.md`),
turning the union into a single navigable graph.

Optional mtime cache (lib.cache.EdgeCache) speeds up repeated builds:
unchanged files reuse cached edges, only modified files are re-parsed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .cache import EdgeCache
from .code_graph import (
    CODE_EDGE_TYPES,
    DEFAULT_CODE_EXTS,
    extract_code_edges,
    iter_code_files,
)
from .graph_builder import (
    DEFAULT_CORPUS_DIRS,
    DocGraph,
    EDGE_TYPES,
    _extract_edges as extract_doc_edges,
    _iter_files as iter_doc_files,
)


# Bridge: comments / docstrings referencing markdown paths (`docs/X.md`,
# `# see docs/foo/bar.md`, `// related: docs/...`).
_COMMENT_MD_REF = re.compile(
    r"""(?:#|//|\*|\"\"\"|''')\s*[^\n]*?([\w./\-]+\.md)""",
)


ALL_EDGE_TYPES = EDGE_TYPES + CODE_EDGE_TYPES


def _extract_bridge_edges(file_path: Path, root: Path) -> List[Tuple[str, str, str]]:
    """Find code comments that reference .md files. Adds (code -> references -> doc)."""
    if file_path.suffix.lower() not in DEFAULT_CODE_EXTS:
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    src = str(file_path.relative_to(root)).replace("\\", "/")
    edges: List[Tuple[str, str, str]] = []
    seen: set = set()
    for match in _COMMENT_MD_REF.finditer(text):
        target = match.group(1).strip()
        if not target or target in seen:
            continue
        seen.add(target)
        # only add if the doc-side path exists in root or nearby
        candidate = (root / target).resolve()
        if candidate.exists():
            try:
                normalized = str(candidate.relative_to(root)).replace("\\", "/")
            except ValueError:
                normalized = target
        else:
            normalized = target
        edges.append((src, "references", normalized))
    return edges


def _file_meta(path: Path) -> Tuple[float, int]:
    stat = path.stat()
    return stat.st_mtime, stat.st_size


def build_unified_graph(
    root: Path,
    cache: Optional[EdgeCache] = None,
    include_doc: bool = True,
    include_code: bool = True,
    extra_dirs: Optional[Iterable[str]] = None,
) -> DocGraph:
    """Build a single graph spanning docs and code.

    Args:
        root: project root
        cache: optional EdgeCache. None disables cache.
        include_doc: walk DEFAULT_CORPUS_DIRS for .md
        include_code: walk DEFAULT_CODE_DIRS for Python/JS/TS
        extra_dirs: extra code corpora (passed to code_graph.iter_code_files)
    """
    graph = DocGraph(root=root)

    def _process(path: Path, extractor) -> None:
        rel_path = str(path.relative_to(root)).replace("\\", "/")
        edges: Optional[List[Tuple[str, str, str]]] = None

        if cache is not None:
            try:
                mtime, size = _file_meta(path)
                edges = cache.get(path, mtime, size)
            except OSError:
                pass

        if edges is None:
            edges = extractor(path, root)
            if cache is not None:
                try:
                    mtime, size = _file_meta(path)
                    cache.put(path, mtime, size, edges)
                except OSError:
                    pass

        for src, edge_type, target in edges:
            graph.add_edge(src, edge_type, target)
        graph.nodes.add(rel_path)

    if include_doc:
        for path in iter_doc_files(root, (".md",)):
            _process(path, extract_doc_edges)

    if include_code:
        for path in iter_code_files(root, extensions=DEFAULT_CODE_EXTS, extra_dirs=extra_dirs):
            # combine code edges + bridge edges into a single cached payload
            def _combined(p: Path, r: Path) -> List[Tuple[str, str, str]]:
                return extract_code_edges(p, r) + _extract_bridge_edges(p, r)
            _process(path, _combined)

    return graph
