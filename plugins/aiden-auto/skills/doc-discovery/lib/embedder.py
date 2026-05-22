"""Optional embedding adapter — backend-agnostic with graceful degradation.

Goal: hybrid_search.py should work whether or not the user has any
embedding library installed. If `fastembed`, `sentence_transformers`, or
`openai` are present, we use them. Otherwise we return None and the
hybrid search falls back to FTS5-only.

Backend selection priority (cheapest local-first → heavier):
    1. fastembed         — ONNX runtime, ~50 MB model, no GPU
    2. sentence_transformers — PyTorch, larger but more accurate
    3. openai            — remote API (requires OPENAI_API_KEY)
    4. None              — graceful degradation, FTS5-only
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence


def _try_fastembed():
    try:
        from fastembed import TextEmbedding  # type: ignore
        return TextEmbedding
    except Exception:
        return None


def _try_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        return SentenceTransformer
    except Exception:
        return None


def _try_openai():
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI  # type: ignore
        return OpenAI
    except Exception:
        return None


@dataclass
class EmbedderInfo:
    """Lightweight description of which backend (if any) is active."""

    backend: str  # 'fastembed' | 'sentence_transformers' | 'openai' | 'none'
    model: str
    dim: Optional[int]


class Embedder:
    """Wraps whichever backend is available. ``embed`` returns
    list[list[float]] of unit-normalized vectors so cosine == dot product.

    If backend == 'none' the embed() raises RuntimeError. Always check
    `.available` before calling.
    """

    def __init__(self, prefer: Optional[str] = None):
        self._impl = None
        self._info = EmbedderInfo(backend="none", model="", dim=None)

        order = ["fastembed", "sentence_transformers", "openai"]
        if prefer and prefer in order:
            order.remove(prefer)
            order.insert(0, prefer)

        for name in order:
            if name == "fastembed":
                cls = _try_fastembed()
                if cls is None:
                    continue
                model_name = "BAAI/bge-small-en-v1.5"
                try:
                    self._impl = cls(model_name=model_name)
                    self._info = EmbedderInfo(
                        backend="fastembed", model=model_name, dim=384
                    )
                    return
                except Exception:
                    continue
            elif name == "sentence_transformers":
                cls = _try_sentence_transformers()
                if cls is None:
                    continue
                model_name = "BAAI/bge-small-en-v1.5"
                try:
                    self._impl = cls(model_name)
                    dim = int(self._impl.get_sentence_embedding_dimension() or 384)
                    self._info = EmbedderInfo(
                        backend="sentence_transformers", model=model_name, dim=dim
                    )
                    return
                except Exception:
                    continue
            elif name == "openai":
                cls = _try_openai()
                if cls is None:
                    continue
                model_name = os.environ.get(
                    "DOC_DISCOVERY_OPENAI_MODEL", "text-embedding-3-small"
                )
                try:
                    self._impl = cls()
                    self._info = EmbedderInfo(
                        backend="openai", model=model_name, dim=1536
                    )
                    return
                except Exception:
                    continue

    @property
    def available(self) -> bool:
        return self._impl is not None

    @property
    def info(self) -> EmbedderInfo:
        return self._info

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not self.available:
            raise RuntimeError("no embedding backend available")
        if self._info.backend == "fastembed":
            vecs = list(self._impl.embed(list(texts)))
            return [_normalize(list(map(float, v))) for v in vecs]
        if self._info.backend == "sentence_transformers":
            arr = self._impl.encode(
                list(texts), normalize_embeddings=True, convert_to_numpy=False
            )
            return [list(map(float, v)) for v in arr]
        if self._info.backend == "openai":
            resp = self._impl.embeddings.create(  # type: ignore[attr-defined]
                model=self._info.model, input=list(texts)
            )
            return [_normalize(list(map(float, d.embedding))) for d in resp.data]
        raise RuntimeError(f"unknown backend: {self._info.backend}")


def _normalize(v: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Dot product of unit-normalized vectors == cosine similarity."""
    return sum(x * y for x, y in zip(a, b))
