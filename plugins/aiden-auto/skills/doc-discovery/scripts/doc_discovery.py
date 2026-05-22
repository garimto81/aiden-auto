#!/usr/bin/env python3
"""doc-discovery CLI — Layer 1+ reverse-dependency impact analysis.

Layer 1   frontmatter graph (Week 1 MVP)
Layer 1+  + code graph (Python ast / JS / TS) + PageRank + mtime cache  (Week 2-3)

Usage:
    python scripts/doc_discovery.py --impact-of <file> [options]
    python scripts/doc_discovery.py --rank [--top N]
    python scripts/doc_discovery.py --cache-info | --cache-clear

Exit codes:
    0  no impact (safe to change)
    1  impact found (caller must act)
    2  input error
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# allow running directly without installing as a package
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.cache import EdgeCache, default_cache_path  # noqa: E402
from lib.graph_builder import (  # noqa: E402
    impact_analysis,
    to_json,
    to_text,
)
from lib.pagerank import pagerank, rank_files  # noqa: E402
from lib.unified_graph import ALL_EDGE_TYPES, build_unified_graph  # noqa: E402

# Layer 2 (lazy-imported below to keep --impact-of fast in the common path)
from lib.fts5_index import FTS5Index  # noqa: E402
from lib.embedder import Embedder  # noqa: E402
from lib.hybrid_search import (  # noqa: E402
    default_index_path,
    hybrid_search,
    should_fallback,
)


def _parse_edge_types(raw: str):
    if not raw:
        return None
    requested = [s.strip() for s in raw.split(",") if s.strip()]
    invalid = [e for e in requested if e not in ALL_EDGE_TYPES]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown edge types: {invalid}. valid: {ALL_EDGE_TYPES}"
        )
    return requested


def _normalize_target(target: str, root: Path) -> str:
    candidate = Path(target)
    if candidate.is_absolute():
        try:
            return str(candidate.resolve().relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(candidate).replace("\\", "/")
    repo_rel = (root / candidate).resolve()
    if repo_rel.exists():
        try:
            return str(repo_rel.relative_to(root)).replace("\\", "/")
        except ValueError:
            pass
    return str(candidate).replace("\\", "/")


def _flatten_forward(graph) -> dict:
    """Convert DocGraph.forward (nested by edge type) into a flat node->set."""
    flat = {}
    for src, edge_map in graph.forward.items():
        targets = set()
        for _edge_type, target_set in edge_map.items():
            targets.update(target_set)
        flat[src] = targets
    return flat


def _print_rank(graph, top: int) -> int:
    forward = _flatten_forward(graph)
    rank_table = pagerank(forward, graph.nodes)
    sorted_files = sorted(rank_table.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    print(f"PageRank — top {len(sorted_files)} of {len(graph.nodes)} nodes")
    for path, score in sorted_files:
        print(f"  {score:.6f}  {path}")
    return 0


def _print_cache_info(cache_path: Path) -> int:
    cache = EdgeCache(cache_path)
    try:
        stats = cache.stats()
    finally:
        cache.close()
    print(f"Cache  {stats['db_path']}")
    print(f"  entries: {stats['entries']}")
    return 0


def _clear_cache(cache_path: Path) -> int:
    cache = EdgeCache(cache_path)
    try:
        cache.clear()
        print(f"OK  cache cleared: {cache_path}")
    finally:
        cache.close()
    return 0


def _resolve_fts_path(args) -> Path:
    return Path(args.fts_path) if args.fts_path else default_index_path()


def _fts_build(args) -> int:
    """Build/refresh the Layer 2 FTS5 index. Returns exit code."""
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR  --root not found: {root}", file=sys.stderr)
        return 2
    fts_path = _resolve_fts_path(args)
    started = time.perf_counter()
    with FTS5Index(fts_path) as fts:
        result = fts.build(root)
        stats = fts.stats()
    elapsed = time.perf_counter() - started
    print(f"OK  FTS5 index built at {fts_path}")
    print(f"    indexed={result['indexed']} skipped={result['skipped']} "
          f"removed={result['removed']} elapsed={elapsed*1000:.0f}ms")
    print(f"    docs={stats['docs']} chunks={stats['chunks']}")
    return 0


def _print_search_report(report) -> None:
    band_marker = {"high": "✓", "medium": "~", "low": "?"}
    marker = band_marker.get(report.confidence_band, "?")
    print(f"{marker} Layer 2 — {len(report.hits)} hit(s) "
          f"[{report.backend}] confidence={report.confidence:.2f} "
          f"({report.confidence_band})")
    for note in report.notes:
        print(f"  note: {note}")
    if not report.hits:
        print("  (no results — try a broader query)")
        return
    for h in report.hits:
        sources = "+".join(h.sources)
        print(f"  {h.score:.4f} [{sources}] {h.path}#chunk{h.chunk_id}")
        snippet = h.snippet.replace("\n", " ")[:140]
        print(f"      {snippet}")


def _semantic_search(args) -> int:
    """Layer 2 — natural language search."""
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR  --root not found: {root}", file=sys.stderr)
        return 2
    fts_path = _resolve_fts_path(args)
    if not fts_path.exists():
        print(f"ERROR  FTS5 index not built. Run: --fts-build", file=sys.stderr)
        return 2
    embedder = None if args.no_embed else Embedder()
    with FTS5Index(fts_path) as fts:
        report = hybrid_search(args.semantic_of, fts=fts, embedder=embedder, top_k=args.top)
    if args.format == "json":
        import json as _json
        payload = {
            "query": report.query,
            "confidence": report.confidence,
            "confidence_band": report.confidence_band,
            "backend": report.backend,
            "hits": [
                {
                    "path": h.path, "chunk_id": h.chunk_id, "score": h.score,
                    "sources": h.sources, "snippet": h.snippet,
                }
                for h in report.hits
            ],
            "notes": report.notes,
        }
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_search_report(report)
    return 0 if report.hits else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="doc_discovery.py",
        description="Reverse-dependency impact analysis (docs + code, with cache + PageRank)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--impact-of", metavar="FILE", help="path to the file being changed")
    mode.add_argument("--rank", action="store_true", help="print PageRank top-N nodes")
    mode.add_argument("--cache-info", action="store_true", help="print cache stats")
    mode.add_argument("--cache-clear", action="store_true", help="evict all cache entries")
    mode.add_argument(
        "--semantic-of", metavar="QUERY",
        help="Layer 2 — natural-language search (FTS5 + optional embedding)",
    )
    mode.add_argument(
        "--fts-build", action="store_true",
        help="(re)build the FTS5 index for Layer 2 semantic search",
    )

    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="output format"
    )
    parser.add_argument("--no-transitive", action="store_true", help="direct dependents only")
    parser.add_argument(
        "--edge-types", default="", type=_parse_edge_types,
        help=f"comma-separated edge types (default: all of {ALL_EDGE_TYPES})",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="bypass mtime cache (Week 2 cache layer)"
    )
    parser.add_argument(
        "--cache-path", default=None, help="override cache db location"
    )
    parser.add_argument("--no-code", action="store_true", help="skip code corpora (docs only)")
    parser.add_argument("--no-doc", action="store_true", help="skip doc corpora (code only)")
    parser.add_argument("--top", type=int, default=20, help="--rank top-N (default: 20)")
    parser.add_argument(
        "--with-rank", action="store_true",
        help="annotate --impact-of report with PageRank scores",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="print build stats (cache hit rate, elapsed time)",
    )
    parser.add_argument(
        "--auto-fallback", action="store_true",
        help="(--impact-of) when Layer 1 returns 0 hits, auto-run Layer 2 semantic search "
             "using the file name + first 200 chars as the query",
    )
    parser.add_argument(
        "--fts-path", default=None,
        help="override Layer 2 FTS5 index location",
    )
    parser.add_argument(
        "--no-embed", action="store_true",
        help="(--semantic-of) skip embedding even if a backend is installed",
    )

    args = parser.parse_args(argv)

    cache_path = Path(args.cache_path) if args.cache_path else default_cache_path()

    if args.cache_info:
        return _print_cache_info(cache_path)
    if args.cache_clear:
        return _clear_cache(cache_path)

    if args.fts_build:
        return _fts_build(args)
    if args.semantic_of:
        return _semantic_search(args)

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR  --root not found: {root}", file=sys.stderr)
        return 2

    cache = None if args.no_cache else EdgeCache(cache_path)
    started = time.perf_counter()
    try:
        graph = build_unified_graph(
            root,
            cache=cache,
            include_doc=not args.no_doc,
            include_code=not args.no_code,
        )
    finally:
        if cache is not None:
            cache_stats = cache.stats()
            cache.close()
        else:
            cache_stats = None
    elapsed = time.perf_counter() - started

    if args.stats:
        print(
            f"STATS  nodes={len(graph.nodes)} elapsed={elapsed*1000:.1f}ms "
            f"cache={'on' if cache_stats else 'off'}",
            file=sys.stderr,
        )
        if cache_stats:
            print(
                f"       cache.hits={cache_stats['hits']} misses={cache_stats['misses']} "
                f"hit_rate={cache_stats['hit_rate']:.1%} entries={cache_stats['entries']}",
                file=sys.stderr,
            )

    if args.rank:
        return _print_rank(graph, args.top)

    target = _normalize_target(args.impact_of, root)
    report = impact_analysis(
        graph,
        target=target,
        transitive=not args.no_transitive,
        edge_types=args.edge_types,
    )

    if args.with_rank and report["total_affected"] > 0:
        forward = _flatten_forward(graph)
        rank_table = pagerank(forward, graph.nodes)
        ranked_direct = rank_files(report["direct"], rank_table)
        report["direct"] = [path for path, _ in ranked_direct]
        report["pagerank"] = {path: score for path, score in ranked_direct}

    if args.format == "json":
        print(to_json(report))
    else:
        print(to_text(report))

    # Layer 1 → Layer 2 auto-fallback (CRAG-style safety net)
    if args.auto_fallback and should_fallback(report["total_affected"]):
        fts_path = _resolve_fts_path(args)
        if fts_path.exists():
            file_path = root / target
            query = Path(target).stem
            try:
                preview = file_path.read_text(encoding="utf-8", errors="replace")[:200]
                query = f"{query} {preview}"
            except OSError:
                pass
            print()
            print(f"[Layer 1 returned 0 hits — auto-falling back to Layer 2 semantic search]")
            embedder = None if args.no_embed else Embedder()
            with FTS5Index(fts_path) as fts:
                report2 = hybrid_search(query, fts=fts, embedder=embedder, top_k=args.top)
            _print_search_report(report2)
            return 1 if report2.hits else 0
        else:
            print(f"[skip Layer 2 fallback — FTS5 index not built at {fts_path}]",
                  file=sys.stderr)

    return 1 if report["total_affected"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
