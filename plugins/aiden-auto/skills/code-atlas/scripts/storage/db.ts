import Database from 'better-sqlite3'
import { join } from 'node:path'
import { mkdirSync } from 'node:fs'
import type { Graph, Hallucination, RunSummary } from '../analyzer/types.js'

const SCHEMA = `
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  target_dir TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  file_count INTEGER,
  node_count INTEGER,
  counts_json TEXT,
  graph_json TEXT
);

CREATE TABLE IF NOT EXISTS hallucinations (
  id TEXT NOT NULL,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  file TEXT NOT NULL,
  line INTEGER NOT NULL,
  end_line INTEGER,
  symbol TEXT,
  message TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  PRIMARY KEY (run_id, id)
);
CREATE INDEX IF NOT EXISTS idx_hallu_run ON hallucinations(run_id);
CREATE INDEX IF NOT EXISTS idx_hallu_kind ON hallucinations(kind);

CREATE TABLE IF NOT EXISTS false_positives (
  fingerprint TEXT PRIMARY KEY,
  marked_at TEXT NOT NULL
);
`

// Additive migration: add graph_json column if the table existed before v2.2.
function migrate(db: Database.Database): void {
  try {
    db.prepare(`SELECT graph_json FROM runs LIMIT 1`).get()
  } catch {
    try {
      db.exec(`ALTER TABLE runs ADD COLUMN graph_json TEXT`)
    } catch {
      // column already exists OR table absent — the next CREATE TABLE IF NOT EXISTS handles it
    }
  }
}

export interface AtlasDb {
  saveRun(summary: RunSummary, hallucinations: Hallucination[], graph: Graph): void
  latestRunId(): string | null
  getRun(runId: string): RunSummary | null
  getGraph(runId: string): Graph | null
  listHallucinations(runId: string): Hallucination[]
  markFalsePositive(fingerprint: string): void
  isFalsePositive(fingerprint: string): boolean
  close(): void
}

export function openDb(targetDir: string): AtlasDb {
  const atlasDir = join(targetDir, '.code-atlas')
  mkdirSync(atlasDir, { recursive: true })
  const dbPath = join(atlasDir, 'atlas.db')
  const db = new Database(dbPath)
  db.pragma('journal_mode = WAL')
  db.exec(SCHEMA)
  migrate(db)

  const insertRun = db.prepare(
    `INSERT INTO runs (id, target_dir, started_at, finished_at, file_count, node_count, counts_json, graph_json)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  )
  const insertHallu = db.prepare(
    `INSERT OR REPLACE INTO hallucinations
     (id, run_id, kind, severity, file, line, end_line, symbol, message, evidence_json)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
  const getLatest = db.prepare(
    `SELECT id FROM runs ORDER BY started_at DESC LIMIT 1`,
  )
  const getRunStmt = db.prepare(`SELECT * FROM runs WHERE id = ?`)
  const getGraphStmt = db.prepare(`SELECT graph_json FROM runs WHERE id = ?`)
  const listHallu = db.prepare(
    `SELECT * FROM hallucinations WHERE run_id = ? ORDER BY kind, file, line`,
  )
  const markFpStmt = db.prepare(
    `INSERT OR REPLACE INTO false_positives (fingerprint, marked_at) VALUES (?, ?)`,
  )
  const checkFpStmt = db.prepare(
    `SELECT fingerprint FROM false_positives WHERE fingerprint = ?`,
  )

  return {
    saveRun(summary, hallucinations, graph) {
      const tx = db.transaction(() => {
        insertRun.run(
          summary.runId,
          summary.targetDir,
          summary.startedAt,
          summary.finishedAt,
          summary.fileCount,
          summary.nodeCount,
          JSON.stringify(summary.byKind),
          JSON.stringify(graph),
        )
        for (const h of hallucinations) {
          insertHallu.run(
            h.id,
            summary.runId,
            h.kind,
            h.severity,
            h.file,
            h.line,
            h.endLine ?? null,
            h.symbol ?? null,
            h.message,
            JSON.stringify(h.evidence),
          )
        }
      })
      tx()
    },
    latestRunId() {
      const row = getLatest.get() as { id: string } | undefined
      return row?.id ?? null
    },
    getRun(runId) {
      const row = getRunStmt.get(runId) as any
      if (!row) return null
      return {
        runId: row.id,
        targetDir: row.target_dir,
        startedAt: row.started_at,
        finishedAt: row.finished_at,
        fileCount: row.file_count,
        nodeCount: row.node_count,
        byKind: JSON.parse(row.counts_json),
      }
    },
    getGraph(runId) {
      const row = getGraphStmt.get(runId) as { graph_json?: string | null } | undefined
      if (!row?.graph_json) return null
      try {
        return JSON.parse(row.graph_json) as Graph
      } catch {
        return null
      }
    },
    listHallucinations(runId) {
      const rows = listHallu.all(runId) as any[]
      return rows.map((r) => ({
        id: r.id,
        kind: r.kind,
        severity: r.severity,
        file: r.file,
        line: r.line,
        endLine: r.end_line ?? undefined,
        symbol: r.symbol ?? undefined,
        message: r.message,
        evidence: JSON.parse(r.evidence_json),
      }))
    },
    markFalsePositive(fingerprint) {
      markFpStmt.run(fingerprint, new Date().toISOString())
    },
    isFalsePositive(fingerprint) {
      return checkFpStmt.get(fingerprint) !== undefined
    },
    close() {
      db.close()
    },
  }
}
