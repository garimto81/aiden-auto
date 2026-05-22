"""mtime-based persistent cache for parsed file edges.

Stores parsed (source, edge_type, target) tuples per file keyed by path
+ mtime + size. Re-parses only when files actually change, so subsequent
build_graph() calls scale O(changed files) instead of O(all files).

Stdlib-only (sqlite3 + json). Default cache path:
~/.claude/skills/doc-discovery/.cache/doc_discovery.db
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple


SCHEMA = """
CREATE TABLE IF NOT EXISTS file_cache (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    edges_json TEXT NOT NULL,
    parsed_at REAL NOT NULL,
    parser_version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_mtime ON file_cache(mtime);
"""

# Bump when edge schema changes. Forces rebuild of all entries.
PARSER_VERSION = 2


def default_cache_path() -> Path:
    return Path.home() / ".claude" / "skills" / "doc-discovery" / ".cache" / "doc_discovery.db"


class EdgeCache:
    """SQLite-backed cache mapping file path -> parsed edges."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or default_cache_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self.hits = 0
        self.misses = 0

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "EdgeCache":
        self._connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def get(
        self,
        path: Path,
        mtime: float,
        size: int,
    ) -> Optional[List[Tuple[str, str, str]]]:
        """Return cached edges if mtime+size match, else None."""
        conn = self._connect()
        row = conn.execute(
            "SELECT mtime, size, edges_json, parser_version FROM file_cache WHERE path = ?",
            (str(path),),
        ).fetchone()
        if row is None:
            self.misses += 1
            return None
        cached_mtime, cached_size, edges_json, parser_version = row
        if (
            parser_version != PARSER_VERSION
            or abs(cached_mtime - mtime) > 1e-6
            or cached_size != size
        ):
            self.misses += 1
            return None
        try:
            edges = json.loads(edges_json)
            self.hits += 1
            return [tuple(e) for e in edges]
        except (json.JSONDecodeError, TypeError):
            self.misses += 1
            return None

    def put(
        self,
        path: Path,
        mtime: float,
        size: int,
        edges: List[Tuple[str, str, str]],
    ) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO file_cache
                (path, mtime, size, edges_json, parsed_at, parser_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(path),
                mtime,
                size,
                json.dumps(edges),
                time.time(),
                PARSER_VERSION,
            ),
        )
        conn.commit()

    def evict(self, path: Path) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM file_cache WHERE path = ?", (str(path),))
        conn.commit()

    def clear(self) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM file_cache")
        conn.commit()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict:
        conn = self._connect()
        total = conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0]
        return {
            "entries": total,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / max(self.hits + self.misses, 1),
            "db_path": str(self.db_path),
        }


@contextmanager
def edge_cache(db_path: Optional[Path] = None, enabled: bool = True) -> Iterator[Optional[EdgeCache]]:
    """Yield an EdgeCache or None when disabled, releasing the connection on exit."""
    if not enabled:
        yield None
        return
    cache = EdgeCache(db_path)
    try:
        cache._connect()
        yield cache
    finally:
        cache.close()
