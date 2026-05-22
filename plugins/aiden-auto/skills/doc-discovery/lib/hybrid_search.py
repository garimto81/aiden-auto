"""Layer 2 orchestrator — FTS5 lexical + (optional) embedding semantic, fused with RRF.

Why this exists:
    Layer 1 graph traversal misses files that ARE related to a change but
    don't reference it via frontmatter / imports. Layer 2 is the safety net
    for those: it ranks "files semantically similar to the query" so a doc
    on "auth tokens" surfaces when the user asks about "session secrets".

Decision rule (CRAG-style):
    - Layer 1 returns N>0 → no need to fall back. Trust the graph.
    - Layer 1 returns 0   → run Layer 2 with confidence score:
        * confidence ≥ 0.7 → present results normally
        * 0.4 ≤ c < 0.7   → present with "manual review recommended" flag
        * c < 0.4         → tell the user "no strong match, verify manually"
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .embedder import Embedder, cosine
from .fts5_index import FTS5Index, Hit
from .rrf import fuse_with_weights


CONFIDENCE_HIGH = 0.7
CONFIDENCE_LOW = 0.4


@dataclass
class FusedHit:
    """Single fused result — file path + chunk + fused score + provenance."""

    path: str
    chunk_id: int
    score: float
    snippet: str
    confidence: float
    sources: List[str]  # which rankers contributed: ['fts'], ['fts','embed']


@dataclass
class SearchReport:
    """Top-level search response."""

    query: str
    hits: List[FusedHit]
    confidence: float
    confidence_band: str  # 'high' | 'medium' | 'low'
    backend: str  # describe which rankers ran
    notes: List[str]


def _confidence_from_scores(scores: Sequence[float]) -> float:
    """Backwards-compat shim — kept so existing tests still call it.

    The real signal is in `_confidence_from_hits` below, which considers
    multi-ranker consensus. This function is now a fallback for callers
    that only have raw scores.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return 0.7
    top = scores[0]
    if top <= 0:
        return 0.0
    midpoint = scores[len(scores) // 2]
    return max(0.0, min(1.0, (top - midpoint) / top))


def _confidence_from_hits(hits: Sequence["FusedHit"]) -> float:
    """RRF-aware confidence — ranker consensus is the primary signal.

    Why this exists:
        Pure score-spread (top - median)/top is meaningless for RRF because
        RRF scores are inherently small and tightly clustered. The actually
        informative signal is "did multiple rankers agree?" — when both
        BM25 and embedding return the same hit, that's a strong signal even
        if the numerical spread is tiny.

    Tiers:
        - All hits have ≥ 2 ranker sources  → 0.85 (high)
        - Majority (≥ 50%) multi-source     → 0.65 (medium)
        - Some multi-source (> 0)           → 0.50 (medium)
        - Single-ranker only, multiple hits → 0.35 (medium-low)
        - Single-ranker, single hit         → 0.30
        - No hits                           → 0.0
    """
    if not hits:
        return 0.0
    multi = sum(1 for h in hits if len(h.sources) >= 2)
    ratio = multi / len(hits)
    if ratio >= 0.99:
        return 0.85
    if ratio >= 0.5:
        return 0.65
    if ratio > 0:
        return 0.50
    if len(hits) >= 3:
        return 0.35
    return 0.30


def _band(c: float) -> str:
    if c >= CONFIDENCE_HIGH:
        return "high"
    if c >= CONFIDENCE_LOW:
        return "medium"
    return "low"


def hybrid_search(
    query: str,
    *,
    fts: FTS5Index,
    embedder: Optional[Embedder] = None,
    top_k: int = 10,
    fts_weight: float = 1.0,
    embed_weight: float = 1.0,
) -> SearchReport:
    """Run lexical + (optional) semantic, fuse with RRF, build report."""

    notes: List[str] = []

    # 1) lexical
    fts_hits: List[Hit] = fts.search(query, top_k=top_k * 2)
    fts_ranking = [(f"{h.path}::{h.chunk_id}", h.score) for h in fts_hits]
    by_key = {f"{h.path}::{h.chunk_id}": h for h in fts_hits}

    # 2) semantic (optional)
    embed_ranking: List[tuple[str, float]] = []
    if embedder is not None and embedder.available and fts_hits:
        try:
            chunk_texts = [h.snippet.replace("<<", "").replace(">>", "") for h in fts_hits]
            qv = embedder.embed([query])[0]
            cv = embedder.embed(chunk_texts)
            sims = [(f"{h.path}::{h.chunk_id}", cosine(qv, v))
                    for h, v in zip(fts_hits, cv)]
            sims.sort(key=lambda kv: -kv[1])
            embed_ranking = sims
            backend = f"fts+{embedder.info.backend}"
        except Exception as e:  # noqa: BLE001
            notes.append(f"embedding failed, falling back to FTS-only: {e!s}")
            backend = "fts"
    else:
        if embedder is None:
            backend = "fts"
        elif not embedder.available:
            backend = "fts (no embedding backend installed)"
            notes.append(
                "Tip: pip install fastembed or sentence-transformers for "
                "semantic retrieval."
            )
        else:
            backend = "fts"

    # 3) fuse
    if embed_ranking:
        fused = fuse_with_weights(
            [fts_ranking, embed_ranking],
            weights=[fts_weight, embed_weight],
            top_n=top_k,
        )
    else:
        fused = fuse_with_weights(
            [fts_ranking], weights=[fts_weight], top_n=top_k
        )

    hits: List[FusedHit] = []
    in_embed = {k for k, _ in embed_ranking}
    for key, score in fused:
        if key not in by_key:
            continue
        h = by_key[key]
        sources = ["fts"]
        if key in in_embed:
            sources.append("embed")
        hits.append(FusedHit(
            path=h.path, chunk_id=h.chunk_id, score=score,
            snippet=h.snippet, confidence=0.0,  # filled in below
            sources=sources,
        ))

    overall = _confidence_from_hits(hits)
    for h in hits:
        h.confidence = overall

    return SearchReport(
        query=query, hits=hits,
        confidence=overall, confidence_band=_band(overall),
        backend=backend, notes=notes,
    )


# ─────────────── Layer 1 → Layer 2 fallback gate ───────────────


def should_fallback(layer1_total: int, *, threshold: int = 0) -> bool:
    """Layer 2 should fire only when Layer 1 returned ≤ threshold matches."""
    return layer1_total <= threshold


def default_index_path() -> Path:
    """Standard cache location, alongside Week 2 mtime cache."""
    base = Path.home() / ".claude" / "skills" / "doc-discovery" / ".cache"
    return base / "fts5.db"
