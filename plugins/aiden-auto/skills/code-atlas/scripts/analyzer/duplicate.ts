import { Node, SyntaxKind } from 'ts-morph'
import type { TargetContext } from './project.js'
import { relPath } from './project.js'
import type { Hallucination } from './types.js'
import { clusterFingerprint } from './fingerprint.js'

interface CodeUnit {
  file: string
  line: number
  name: string
  kind: 'function' | 'component' | 'method'
  nGrams: Set<string>
  size: number
}

const SIMILARITY_THRESHOLD = 0.75
const MIN_NGRAM_COUNT = 8
const NGRAM_WINDOW = 3

/**
 * H4 — Silent Duplicate
 * Extracts exported functions / React components / class methods, builds
 * AST-kind n-gram bags, computes pairwise Jaccard similarity, clusters.
 * Fully local, no embeddings or API calls.
 */
export function detectDuplicates(ctx: TargetContext): Hallucination[] {
  const units = extractUnits(ctx)
  const clusters = clusterBySimilarity(units)

  return clusters.map((cluster) => {
    const members = cluster.map((u) => `${u.file}:${u.line}:${u.name}`)
    const primary = cluster[0]
    return {
      id: clusterFingerprint('H4', members),
      kind: 'H4',
      severity: 'warn',
      file: primary.file,
      line: primary.line,
      symbol: primary.name,
      message: `의미적 중복 클러스터 (${cluster.length}개): ${cluster.map((u) => u.name).join(', ')}`,
      evidence: {
        clusterSize: cluster.length,
        members: cluster.map((u) => ({
          file: u.file,
          line: u.line,
          name: u.name,
          kind: u.kind,
        })),
        threshold: SIMILARITY_THRESHOLD,
        method: 'jaccard-ast-ngram',
      },
    }
  })
}

function extractUnits(ctx: TargetContext): CodeUnit[] {
  const units: CodeUnit[] = []
  for (const sf of ctx.project.getSourceFiles()) {
    if (sf.getFilePath().includes('node_modules')) continue
    const file = relPath(ctx, sf.getFilePath())

    // Top-level function declarations
    for (const fn of sf.getFunctions()) {
      if (!fn.isExported() && !fn.isDefaultExport()) continue
      const u = buildUnit(fn, file, fn.getName() ?? '<default>', 'function')
      if (u) units.push(u)
    }

    // Exported const = arrow
    for (const vd of sf.getVariableDeclarations()) {
      const stmt = vd.getVariableStatement()
      if (!stmt?.isExported()) continue
      const init = vd.getInitializer()
      if (!init) continue
      if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
        const kind: CodeUnit['kind'] = looksLikeComponent(vd.getName()) ? 'component' : 'function'
        const u = buildUnit(init, file, vd.getName(), kind)
        if (u) units.push(u)
      }
    }

    // Class methods of exported classes
    for (const cls of sf.getClasses()) {
      if (!cls.isExported() && !cls.isDefaultExport()) continue
      for (const m of cls.getMethods()) {
        const u = buildUnit(m, file, `${cls.getName() ?? ''}.${m.getName()}`, 'method')
        if (u) units.push(u)
      }
    }
  }
  return units
}

function buildUnit(
  node: Node,
  file: string,
  name: string,
  kind: CodeUnit['kind'],
): CodeUnit | null {
  const body = (node as any).getBody?.()
  if (!body) return null
  const nGrams = collectNGrams(body)
  if (nGrams.size < MIN_NGRAM_COUNT) return null
  return {
    file,
    line: node.getStartLineNumber(),
    name,
    kind,
    nGrams,
    size: nGrams.size,
  }
}

function collectNGrams(root: Node): Set<string> {
  const sequence: number[] = []
  // forEachDescendant stops if callback returns truthy. Array.push returns
  // the new length (a truthy number), so we wrap in a block to return undefined.
  root.forEachDescendant((n) => {
    sequence.push(n.getKind())
  })
  const grams = new Set<string>()
  for (let i = 0; i + NGRAM_WINDOW <= sequence.length; i++) {
    grams.add(sequence.slice(i, i + NGRAM_WINDOW).join(','))
  }
  return grams
}

function looksLikeComponent(name: string): boolean {
  return /^[A-Z]/.test(name)
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0
  let inter = 0
  const [smaller, larger] = a.size <= b.size ? [a, b] : [b, a]
  for (const g of smaller) if (larger.has(g)) inter++
  return inter / (a.size + b.size - inter)
}

function clusterBySimilarity(units: CodeUnit[]): CodeUnit[][] {
  const n = units.length
  const parent = Array.from({ length: n }, (_, i) => i)
  const find = (x: number): number => (parent[x] === x ? x : (parent[x] = find(parent[x])))
  const union = (x: number, y: number) => {
    const px = find(x)
    const py = find(y)
    if (px !== py) parent[px] = py
  }

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (jaccard(units[i].nGrams, units[j].nGrams) >= SIMILARITY_THRESHOLD) {
        union(i, j)
      }
    }
  }

  const groups = new Map<number, CodeUnit[]>()
  for (let i = 0; i < n; i++) {
    const root = find(i)
    if (!groups.has(root)) groups.set(root, [])
    groups.get(root)!.push(units[i])
  }

  return [...groups.values()].filter((g) => g.length >= 2)
}

export { SyntaxKind }
