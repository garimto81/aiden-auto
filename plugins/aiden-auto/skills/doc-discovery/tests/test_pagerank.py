"""Self-verification suite for PageRank (Week 2)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.pagerank import pagerank, rank_files  # noqa: E402


def test_empty_graph_returns_empty():
    assert pagerank({}, []) == {}


def test_single_node_rank_is_one():
    rank = pagerank({"A": set()}, ["A"])
    assert abs(rank["A"] - 1.0) < 1e-6


def test_ranks_sum_to_one():
    forward = {
        "A": {"B", "C"},
        "B": {"C"},
        "C": set(),
    }
    rank = pagerank(forward, ["A", "B", "C"])
    total = sum(rank.values())
    assert abs(total - 1.0) < 1e-3, f"sum={total} not ≈ 1.0"


def test_central_node_outranks_leaves():
    # B is depended on by both A and C → should outrank A and C
    forward = {
        "A": {"B"},
        "B": set(),
        "C": {"B"},
    }
    rank = pagerank(forward, ["A", "B", "C"])
    assert rank["B"] > rank["A"]
    assert rank["B"] > rank["C"]


def test_disconnected_components_handled():
    forward = {
        "A": {"B"},
        "B": set(),
        "X": {"Y"},
        "Y": set(),
    }
    rank = pagerank(forward, ["A", "B", "X", "Y"])
    # both targets receive rank > base (some incoming mass)
    assert rank["B"] > 0
    assert rank["Y"] > 0


def test_rank_files_sorts_descending():
    rank_table = {"a": 0.1, "b": 0.5, "c": 0.3}
    sorted_pairs = rank_files(["a", "b", "c"], rank_table)
    assert [p for p, _ in sorted_pairs] == ["b", "c", "a"]


def test_rank_files_handles_unknown_files():
    rank_table = {"a": 0.5}
    pairs = rank_files(["a", "missing"], rank_table)
    # missing gets 0.0, sorts after a
    assert pairs[0] == ("a", 0.5)
    assert pairs[1] == ("missing", 0.0)


def test_convergence_under_max_iter():
    # large-ish chain, should still converge well within 50 iters
    n = 20
    forward = {f"n{i}": {f"n{i+1}"} for i in range(n - 1)}
    forward[f"n{n-1}"] = set()
    nodes = [f"n{i}" for i in range(n)]
    rank = pagerank(forward, nodes, max_iter=50, tol=1e-6)
    # last node accumulates the most rank in a chain
    assert rank[f"n{n-1}"] > rank["n0"]


# ─────────────────── runner ────────────────────

def _run_all() -> int:
    failures = []
    tests = [
        test_empty_graph_returns_empty,
        test_single_node_rank_is_one,
        test_ranks_sum_to_one,
        test_central_node_outranks_leaves,
        test_disconnected_components_handled,
        test_rank_files_sorts_descending,
        test_rank_files_handles_unknown_files,
        test_convergence_under_max_iter,
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
