"""Layer 2 lexical baseline — SQLite FTS5 index over markdown corpora.

Zero external dependencies (stdlib only). Indexes .md files as overlapping
chunks (~1500 chars + 200 overlap), exposes BM25-ranked search. mtime-based
incremental rebuild reuses the cache schema family from Week 2.

Why FTS5 first: BM25 is the strongest deterministic baseline for short doc
collections, and it's already inside Python's stdlib. Embedding-based search
is a multiplier on top, not a prerequisite.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

# Reuse default code/doc walk dirs to keep coverage consistent with Layer 1.
DEFAULT_DOC_DIRS = (
    "docs",
    ".claude/rules",
    ".claude/skills",
    "Command_Center_UI",
)
DEFAULT_EXCLUDES = (
    "node_modules",
    ".git",
    "__pycache__",
    "_generated",
    "_archived",
    "dist",
    "build",
)

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Hit:
    """Single FTS5 search hit."""

    path: str
    chunk_id: int
    score: float
    snippet: str


def _excluded(path: Path) -> bool:
    parts = set(path.parts)
    return any(p in parts for p in DEFAULT_EXCLUDES)


def _iter_md_files(root: Path, dirs: Iterable[str]) -> Iterable[Path]:
    for sub in dirs:
        base = root / sub
        if not base.exists() or not base.is_dir():
            continue
        try:
            for path in base.rglob("*.md"):
                if path.is_file() and not _excluded(path):
                    yield path
        except (OSError, PermissionError):
            continue


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter so it does not dominate FTS5 scoring."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _chunk_text(text: str) -> List[str]:
    """Split into overlapping char-window chunks. Whitespace-collapsed."""
    text = _strip_frontmatter(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _quote_fts5_query(raw: str) -> str:
    """Make a query safe for FTS5: keep alnum + Korean letters, drop the rest."""
    tokens = re.findall(r"[\w가-힣]+", raw, flags=re.UNICODE)
    if not tokens:
        return '""'
    # quoted token-list — no operators, just OR-style match (FTS5 ranks by BM25)
    return " ".join(f'"{t}"' for t in tokens)


class FTS5Index:
    """Persistent FTS5 index for markdown corpora.

    Schema:
        meta(version)
        docs(path PRIMARY KEY, mtime, size)
        chunks(rowid, path, chunk_id, text)            -- regular table
        chunks_fts USING fts5(text, content='chunks',  -- external content
                              content_rowid='rowid')

    Using external-content FTS5 keeps the index 30-40% smaller and lets us
    rebuild incrementally without re-tokenizing unchanged files.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ---------- internal ----------

    def _init_schema(self) -> None:
        with closing(self._conn.cursor()) as c:
            c.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS meta(
                    key TEXT PRIMARY KEY, value TEXT
                );
                CREATE TABLE IF NOT EXISTS docs(
                    path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks(
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    UNIQUE(path, chunk_id)
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                    USING fts5(text, content='chunks', content_rowid='rowid',
                               tokenize='unicode61 remove_diacritics 2');
                """
            )
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema',?)",
                      (str(SCHEMA_VERSION),))
            self._conn.commit()

    def _delete_doc(self, path: str) -> None:
        with closing(self._conn.cursor()) as c:
            c.execute(
                "INSERT INTO chunks_fts(chunks_fts, rowid, text) "
                "SELECT 'delete', rowid, text FROM chunks WHERE path=?",
                (path,),
            )
            c.execute("DELETE FROM chunks WHERE path=?", (path,))
            c.execute("DELETE FROM docs WHERE path=?", (path,))

    def _insert_doc(self, path: str, mtime: float, size: int, chunks: List[str]) -> None:
        with closing(self._conn.cursor()) as c:
            c.execute(
                "INSERT INTO docs(path,mtime,size) VALUES(?,?,?)",
                (path, mtime, size),
            )
            for idx, txt in enumerate(chunks):
                c.execute(
                    "INSERT INTO chunks(path, chunk_id, text) VALUES(?,?,?)",
                    (path, idx, txt),
                )
                rowid = c.lastrowid
                c.execute(
                    "INSERT INTO chunks_fts(rowid, text) VALUES(?,?)",
                    (rowid, txt),
                )

    # ---------- public API ----------

    def build(
        self,
        root: Path,
        dirs: Optional[Iterable[str]] = None,
    ) -> dict:
        """Incrementally (re)build the index. Returns {indexed, skipped, removed}."""
        dirs = tuple(dirs) if dirs else DEFAULT_DOC_DIRS
        root = Path(root).resolve()

        # Track which paths we see this run so stale rows can be removed.
        seen: set[str] = set()
        indexed = skipped = 0

        for md_path in _iter_md_files(root, dirs):
            try:
                rel = str(md_path.resolve().relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            seen.add(rel)
            stat = md_path.stat()

            row = self._conn.execute(
                "SELECT mtime, size FROM docs WHERE path=?", (rel,)
            ).fetchone()
            if row and row["mtime"] == stat.st_mtime and row["size"] == stat.st_size:
                skipped += 1
                continue

            try:
                text = md_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks = _chunk_text(text)
            if not chunks:
                continue
            self._delete_doc(rel)
            self._insert_doc(rel, stat.st_mtime, stat.st_size, chunks)
            indexed += 1

        # Cleanup: anything in DB not seen this run is stale.
        existing = {r["path"] for r in self._conn.execute("SELECT path FROM docs")}
        removed = 0
        for stale in existing - seen:
            self._delete_doc(stale)
            removed += 1

        self._conn.commit()
        return {"indexed": indexed, "skipped": skipped, "removed": removed}

    def search(self, query: str, top_k: int = 10) -> List[Hit]:
        if not query.strip():
            return []
        fts_q = _quote_fts5_query(query)
        if fts_q == '""':
            return []
        rows = self._conn.execute(
            """
            SELECT chunks.path AS path,
                   chunks.chunk_id AS chunk_id,
                   bm25(chunks_fts) AS bm25,
                   snippet(chunks_fts, 0, '<<', '>>', '...', 16) AS snip
            FROM chunks_fts
            JOIN chunks ON chunks.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY bm25 ASC
            LIMIT ?
            """,
            (fts_q, top_k),
        ).fetchall()
        # FTS5 bm25 is "lower is better"; flip sign for downstream RRF/score sort.
        return [
            Hit(path=r["path"], chunk_id=r["chunk_id"],
                score=-float(r["bm25"]), snippet=r["snip"])
            for r in rows
        ]

    def stats(self) -> dict:
        docs = self._conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunks = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"docs": docs, "chunks": chunks, "db_path": str(self.db_path)}

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "FTS5Index":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
