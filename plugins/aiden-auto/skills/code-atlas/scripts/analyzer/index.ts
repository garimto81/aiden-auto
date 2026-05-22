import { loadTargetProject } from './project.js'
import { detectPhantomRefs } from './phantom.js'
import { detectHollowStubs } from './hollow.js'
import { detectDuplicates } from './duplicate.js'
import { detectDanglingEdges } from './dangling.js'
import { buildGraph } from './graph.js'
import type {
  Hallucination,
  HallucinationKind,
  ProgressCallback,
  RunSummary,
  Graph,
} from './types.js'
import { randomUUID } from 'node:crypto'

export interface ScanResult {
  summary: RunSummary
  hallucinations: Hallucination[]
  graph: Graph
}

export async function runScan(
  targetDir: string,
  onProgress?: ProgressCallback,
): Promise<ScanResult> {
  const runId = randomUUID()
  const startedAt = new Date().toISOString()

  onProgress?.({ phase: 'load', done: 0, total: 6 })
  const ctx = loadTargetProject(targetDir)

  onProgress?.({ phase: 'phantom', done: 1, total: 6 })
  const h1 = detectPhantomRefs(ctx)

  onProgress?.({ phase: 'hollow', done: 2, total: 6 })
  const h3 = detectHollowStubs(ctx)

  onProgress?.({ phase: 'duplicate', done: 3, total: 6 })
  const h4 = detectDuplicates(ctx)

  onProgress?.({ phase: 'dangling', done: 4, total: 6 })
  const h7 = detectDanglingEdges(ctx)

  const hallucinations = [...h1, ...h3, ...h4, ...h7]
  const byKind: Record<HallucinationKind, number> = { H1: 0, H3: 0, H4: 0, H7: 0 }
  for (const h of hallucinations) byKind[h.kind]++

  onProgress?.({ phase: 'graph', done: 5, total: 6 })
  const graph = buildGraph(ctx, hallucinations)

  const finishedAt = new Date().toISOString()
  const fileCount = ctx.srcFiles.length

  onProgress?.({ phase: 'complete', done: 6, total: 6 })

  return {
    summary: {
      runId,
      targetDir: ctx.rootDir,
      startedAt,
      finishedAt,
      fileCount,
      nodeCount: hallucinations.length,
      byKind,
    },
    hallucinations,
    graph,
  }
}
