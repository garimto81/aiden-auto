"""Layer 2 regression tests (Week 6).

Covers:
  1. fts5_index — build, search, incremental rebuild, removal
  2. rrf — fuse / fuse_with_weights edge cases
  3. embedder — graceful degradation when no backend installed
  4. hybrid_search — orchestrator + confidence band + fallback gate
  5. CLI — --fts-build / --semantic-of / --auto-fallback wiring

All tests run without network or extra deps. Embedding-specific paths
are intentionally skipped when no backend is present.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.embedder import Embedder, cosine  # noqa: E402
from lib.fts5_index import FTS5Index, _chunk_text, _strip_frontmatter  # noqa: E402
from lib.hybrid_search import (  # noqa: E402
    _band, _confidence_from_scores, hybrid_search, should_fallback,
)
from lib.rrf import fuse, fuse_with_weights  # noqa: E402

SCRIPT = HERE.parent / "scripts" / "doc_discovery.py"


# ────────────── fts5_index ──────────────


def _seed(root: Path) -> None:
    """Set up a tiny corpus: one doc about auth tokens, one unrelated."""
    (root / "docs" / "00-prd").mkdir(parents=True)
    (root / "docs" / "00-prd" / "Auth.md").write_text(
        "---\ntitle: Auth\n---\n\nThe authentication module manages session "
        "tokens and refresh keys. Tokens are signed with HMAC-SHA256.\n",
        encoding="utf-8",
    )
    (root / "docs" / "00-prd" / "Billing.md").write_text(
        "---\ntitle: Billing\n---\n\nMonthly invoice generation runs on the "
        "first of each month. Uses Stripe webhooks for events.\n",
        encoding="utf-8",
    )


def test_strip_frontmatter_handles_yaml():
    text = "---\ntitle: x\n---\n\nbody"
    assert _strip_frontmatter(text) == "body"


def test_strip_frontmatter_no_yaml_passthrough():
    assert _strip_frontmatter("just body") == "just body"


def test_chunk_text_overlaps():
    text = "x" * 4000
    chunks = _chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 1500 for c in chunks)
    # consecutive chunks share 200-char tail
    assert chunks[0][-200:] == chunks[1][:200]


def test_fts5_build_and_search(tmp_path):
    _seed(tmp_path)
    db = tmp_path / "fts.db"
    with FTS5Index(db) as fts:
        result = fts.build(tmp_path)
        assert result["indexed"] == 2
        hits = fts.search("authentication tokens", top_k=5)
        assert hits, "expected at least one hit for 'authentication tokens'"
        assert any("Auth.md" in h.path for h in hits)
        # billing should NOT outrank auth for an auth query
        top = hits[0]
        assert "Auth.md" in top.path


def test_fts5_incremental_rebuild_skips_unchanged(tmp_path):
    _seed(tmp_path)
    db = tmp_path / "fts.db"
    with FTS5Index(db) as fts:
        first = fts.build(tmp_path)
        assert first["indexed"] == 2 and first["skipped"] == 0
        second = fts.build(tmp_path)
        assert second["indexed"] == 0 and second["skipped"] == 2


def test_fts5_removes_deleted_files(tmp_path):
    _seed(tmp_path)
    db = tmp_path / "fts.db"
    with FTS5Index(db) as fts:
        fts.build(tmp_path)
        (tmp_path / "docs" / "00-prd" / "Billing.md").unlink()
        result = fts.build(tmp_path)
        assert result["removed"] == 1
        assert fts.stats()["docs"] == 1


def test_fts5_empty_query_returns_empty(tmp_path):
    _seed(tmp_path)
    with FTS5Index(tmp_path / "fts.db") as fts:
        fts.build(tmp_path)
        assert fts.search("") == []
        assert fts.search("   ") == []


# ────────────── rrf ──────────────


def test_rrf_fuse_empty():
    assert fuse([]) == []


def test_rrf_fuse_single_ranking():
    out = fuse([[("a", 1.0), ("b", 0.5)]])
    keys = [k for k, _ in out]
    assert keys == ["a", "b"]


def test_rrf_fuse_combines_two():
    r1 = [("a", 1.0), ("b", 0.5)]
    r2 = [("b", 0.9), ("c", 0.4)]
    out = fuse([r1, r2])
    # b appears in both → highest fused score
    assert out[0][0] == "b"
    keys = {k for k, _ in out}
    assert keys == {"a", "b", "c"}


def test_rrf_top_n_trim():
    r = [(f"x{i}", 1.0 - i * 0.1) for i in range(10)]
    assert len(fuse([r], top_n=3)) == 3


def test_rrf_weighted_zero_weight_skips():
    r1 = [("a", 1.0)]
    r2 = [("b", 1.0)]
    out = fuse_with_weights([r1, r2], weights=[1.0, 0.0])
    assert [k for k, _ in out] == ["a"]


def test_rrf_weighted_length_mismatch_raises():
    with pytest.raises(ValueError):
        fuse_with_weights([[("a", 1.0)]], weights=[1.0, 0.5])


# ────────────── embedder ──────────────


def test_embedder_graceful_degradation():
    """Even with no backend installed, Embedder() must not crash."""
    e = Embedder()
    assert isinstance(e.available, bool)
    if not e.available:
        with pytest.raises(RuntimeError):
            e.embed(["test"])


def test_cosine_unit_vectors():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


# ────────────── hybrid_search ──────────────


def test_confidence_from_scores_empty():
    assert _confidence_from_scores([]) == 0.0


def test_confidence_from_scores_single():
    assert _confidence_from_scores([0.5]) == 0.7


def test_confidence_band_thresholds():
    assert _band(0.9) == "high"
    assert _band(0.5) == "medium"
    assert _band(0.1) == "low"


def test_should_fallback_gate():
    assert should_fallback(0) is True
    assert should_fallback(5) is False
    assert should_fallback(0, threshold=2) is True
    assert should_fallback(3, threshold=2) is False


def test_hybrid_search_fts_only(tmp_path):
    _seed(tmp_path)
    with FTS5Index(tmp_path / "fts.db") as fts:
        fts.build(tmp_path)
        report = hybrid_search("authentication tokens", fts=fts, embedder=None, top_k=5)
        assert report.hits, "expected hits"
        assert report.backend == "fts"
        assert report.confidence_band in ("high", "medium", "low")
        assert all(h.sources == ["fts"] for h in report.hits)


def test_hybrid_search_no_match_returns_low_confidence(tmp_path):
    _seed(tmp_path)
    with FTS5Index(tmp_path / "fts.db") as fts:
        fts.build(tmp_path)
        report = hybrid_search("nonexistentwordxyz", fts=fts, embedder=None)
        assert report.hits == []
        assert report.confidence == 0.0
        assert report.confidence_band == "low"


# ────────────── CLI ──────────────


def test_cli_fts_build_and_semantic_search(tmp_path):
    _seed(tmp_path)
    fts_path = tmp_path / "fts.db"

    build = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--fts-build",
            "--root", str(tmp_path),
            "--fts-path", str(fts_path),
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert build.returncode == 0, build.stderr
    assert "FTS5 index built" in build.stdout
    assert fts_path.exists()

    search = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--semantic-of", "authentication tokens",
            "--root", str(tmp_path),
            "--fts-path", str(fts_path),
            "--no-embed",
            "--format", "json",
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert search.returncode == 0, search.stderr
    payload = json.loads(search.stdout)
    assert payload["query"] == "authentication tokens"
    assert payload["hits"], "CLI semantic search should return hits"
    assert any("Auth.md" in h["path"] for h in payload["hits"])


def test_cli_semantic_without_index_errors(tmp_path):
    _seed(tmp_path)
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--semantic-of", "anything",
            "--root", str(tmp_path),
            "--fts-path", str(tmp_path / "missing.db"),
            "--no-embed",
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 2
    assert "FTS5 index not built" in result.stderr
