"""Reciprocal Rank Fusion — combine multiple ranked lists into one.

Standard formula (Cormack et al. 2009):
    rrf_score(d) = sum_i 1 / (k + rank_i(d))

Default k=60 follows the paper. The fusion does NOT depend on the absolute
score scales of the input rankings, which is why it works equally well for
BM25 + cosine similarity even though the two scales are unrelated.

Each input is a list of (key, score) sorted by descending score. Output is
a list of (key, fused_score) sorted by descending fused score, deduped on
key.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

DEFAULT_K = 60


def fuse(
    rankings: Sequence[Sequence[Tuple[str, float]]],
    *,
    k: int = DEFAULT_K,
    top_n: int | None = None,
) -> List[Tuple[str, float]]:
    """Combine N ranked lists with RRF.

    Args:
        rankings: tuple of ranked lists. Each item is (key, score), sorted
            by score descending.
        k: RRF damping constant. Default 60.
        top_n: trim final fused list to N entries. None = no trim.

    Returns:
        Fused list sorted by descending RRF score.
    """
    if not rankings:
        return []
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (key, _score) in enumerate(ranking, start=1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    out = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
    if top_n is not None:
        out = out[:top_n]
    return out


def fuse_with_weights(
    rankings: Sequence[Sequence[Tuple[str, float]]],
    weights: Sequence[float],
    *,
    k: int = DEFAULT_K,
    top_n: int | None = None,
) -> List[Tuple[str, float]]:
    """Weighted variant — same shape but each ranking contributes w_i / (k+rank)."""
    if len(rankings) != len(weights):
        raise ValueError(
            f"rankings ({len(rankings)}) and weights ({len(weights)}) length mismatch"
        )
    if not rankings:
        return []
    fused: dict[str, float] = {}
    for ranking, w in zip(rankings, weights):
        if w == 0:
            continue
        for rank, (key, _score) in enumerate(ranking, start=1):
            fused[key] = fused.get(key, 0.0) + w * (1.0 / (k + rank))
    out = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
    if top_n is not None:
        out = out[:top_n]
    return out
