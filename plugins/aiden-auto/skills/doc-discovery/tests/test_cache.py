"""Self-verification suite for the mtime cache (Week 2)."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.cache import EdgeCache  # noqa: E402


def _tmpdb():
    return Path(tempfile.mkdtemp()) / "test.db"


def test_get_returns_none_for_missing():
    cache = EdgeCache(_tmpdb())
    try:
        result = cache.get(Path("missing.py"), 0.0, 0)
        assert result is None
        assert cache.misses == 1 and cache.hits == 0
    finally:
        cache.close()


def test_put_then_get_round_trip():
    cache = EdgeCache(_tmpdb())
    try:
        path = Path("foo.py")
        edges = [("foo.py", "imports", "bar"), ("foo.py", "defines", "symbol:foo::baz")]
        cache.put(path, mtime=100.5, size=42, edges=edges)
        result = cache.get(path, mtime=100.5, size=42)
        assert result == edges
        assert cache.hits == 1 and cache.misses == 0
    finally:
        cache.close()


def test_mtime_change_invalidates():
    cache = EdgeCache(_tmpdb())
    try:
        path = Path("foo.py")
        cache.put(path, 100.0, 10, [("a", "b", "c")])
        # different mtime — must miss
        assert cache.get(path, 200.0, 10) is None
    finally:
        cache.close()


def test_size_change_invalidates():
    cache = EdgeCache(_tmpdb())
    try:
        path = Path("foo.py")
        cache.put(path, 100.0, 10, [("a", "b", "c")])
        # different size — must miss
        assert cache.get(path, 100.0, 999) is None
    finally:
        cache.close()


def test_evict_removes_entry():
    cache = EdgeCache(_tmpdb())
    try:
        path = Path("foo.py")
        cache.put(path, 100.0, 10, [("a", "b", "c")])
        cache.evict(path)
        assert cache.get(path, 100.0, 10) is None
    finally:
        cache.close()


def test_clear_empties_cache():
    cache = EdgeCache(_tmpdb())
    try:
        for i in range(5):
            cache.put(Path(f"file{i}.py"), float(i), i, [])
        assert cache.stats()["entries"] == 5
        cache.clear()
        assert cache.stats()["entries"] == 0
    finally:
        cache.close()


def test_stats_tracks_hit_rate():
    cache = EdgeCache(_tmpdb())
    try:
        path = Path("foo.py")
        cache.put(path, 1.0, 1, [])
        cache.get(path, 1.0, 1)  # hit
        cache.get(path, 1.0, 1)  # hit
        cache.get(Path("missing.py"), 0, 0)  # miss
        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert abs(stats["hit_rate"] - 2 / 3) < 1e-6
    finally:
        cache.close()


def test_persistence_across_close():
    db = _tmpdb()
    cache1 = EdgeCache(db)
    try:
        cache1.put(Path("foo.py"), 1.0, 1, [("a", "b", "c")])
    finally:
        cache1.close()

    cache2 = EdgeCache(db)
    try:
        result = cache2.get(Path("foo.py"), 1.0, 1)
        assert result == [("a", "b", "c")]
    finally:
        cache2.close()


# ─────────────────── runner ────────────────────

def _run_all() -> int:
    failures = []
    tests = [
        test_get_returns_none_for_missing,
        test_put_then_get_round_trip,
        test_mtime_change_invalidates,
        test_size_change_invalidates,
        test_evict_removes_entry,
        test_clear_empties_cache,
        test_stats_tracks_hit_rate,
        test_persistence_across_close,
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
