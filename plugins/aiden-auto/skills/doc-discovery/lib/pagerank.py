"""Iterative PageRank for ranking impacted nodes by structural importance.

Used after impact_analysis() to surface the most "central" affected files
first — i.e., files that themselves have many dependents are reported
ahead of leaf-level dependents.

Pure Python. Power iteration with damping=0.85, convergence threshold 1e-6,
max 50 iterations. No numpy/networkx dependency.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple


def pagerank(
    forward: Dict[str, Set[str]],
    nodes: Iterable[str],
    damping: float = 0.85,
    max_iter: int = 50,
    tol: float = 1e-6,
) -> Dict[str, float]:
    """Run power-iteration PageRank.

    Args:
        forward: node -> set of nodes it points to (outgoing edges)
        nodes: full node set (used to size the rank vector)
        damping: random-jump factor (0.85 is the classical default)
        max_iter: hard cap on iterations
        tol: L1 convergence threshold
    """
    node_list = list(nodes)
    n = len(node_list)
    if n == 0:
        return {}

    base_jump = (1.0 - damping) / n
    rank: Dict[str, float] = {node: 1.0 / n for node in node_list}

    # Pre-compute outgoing edges once for efficiency.
    out_edges: Dict[str, List[str]] = {
        node: list(forward.get(node, set())) for node in node_list
    }
    sinks = [node for node, edges in out_edges.items() if not edges]

    for _ in range(max_iter):
        # baseline from random jumps + sink redistribution
        sink_mass = sum(rank[s] for s in sinks) / n
        new_rank: Dict[str, float] = {
            node: base_jump + damping * sink_mass for node in node_list
        }

        # propagate rank along outgoing edges
        for node in node_list:
            edges = out_edges[node]
            if not edges:
                continue
            share = damping * rank[node] / len(edges)
            for target in edges:
                if target in new_rank:
                    new_rank[target] += share

        diff = sum(abs(new_rank[node] - rank[node]) for node in node_list)
        rank = new_rank
        if diff < tol:
            break

    return rank


def rank_files(
    files: Iterable[str],
    rank_table: Dict[str, float],
) -> List[Tuple[str, float]]:
    """Sort `files` by descending PageRank, returning (file, score) pairs."""
    return sorted(
        ((f, rank_table.get(f, 0.0)) for f in files),
        key=lambda pair: (-pair[1], pair[0]),
    )
