export type HallucinationKind = 'H1' | 'H3' | 'H4' | 'H7'
export type Severity = 'critical' | 'warn' | 'info'

export interface Hallucination {
  id: string
  kind: HallucinationKind
  severity: Severity
  file: string
  line: number
  endLine?: number
  symbol?: string
  message: string
  evidence: Record<string, unknown>
}

export interface RunSummary {
  runId: string
  targetDir: string
  startedAt: string
  finishedAt: string
  fileCount: number
  nodeCount: number
  byKind: Record<HallucinationKind, number>
}

export interface Progress {
  phase: string
  done: number
  total: number
}

export type ProgressCallback = (p: Progress) => void

export type {
  Graph,
  GraphNode,
  GraphEdge,
  NodeKind,
  NodeStatus,
  EdgeKind,
  EdgeStatus,
} from './graph.js'
