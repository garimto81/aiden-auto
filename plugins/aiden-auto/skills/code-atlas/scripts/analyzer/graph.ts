import { Node, SourceFile, CallExpression } from 'ts-morph'
import { basename } from 'node:path'
import type { TargetContext } from './project.js'
import { relPath } from './project.js'
import type { Hallucination } from './types.js'
import { labelForScreen, labelForApi, labelForSymbol, labelForEdge } from './labels.js'

export type NodeKind = 'screen' | 'component' | 'function' | 'api' | 'db' | 'missing'
export type NodeStatus = 'normal' | 'phantom' | 'hollow' | 'duplicate' | 'dangling'
export type EdgeKind = 'imports' | 'calls' | 'fetch' | 'query'
export type EdgeStatus = 'normal' | 'broken' | 'dangling'

export interface GraphNode {
  id: string
  kind: NodeKind
  label: string
  originalName: string
  file?: string
  line?: number
  status: NodeStatus
  /** fingerprints of hallucinations attached to this node */
  hallucinationIds: string[]
}

export interface GraphEdge {
  from: string
  to: string
  kind: EdgeKind
  label: string
  status: EdgeStatus
}

export interface Graph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/**
 * Build a project-level node-edge graph. Identifies screens, API routes,
 * exported components/functions; connects them via imports + fetches + DB calls.
 * Hallucination statuses are overlaid onto nodes & edges.
 */
export function buildGraph(ctx: TargetContext, hallucinations: Hallucination[]): Graph {
  const nodes = new Map<string, GraphNode>()
  const edges: GraphEdge[] = []
  const missingByPath = new Map<string, string>() // claimed import path → missing node id

  // Lookups by file+name to attach edges back to a canonical id
  const fileSymbolIndex = new Map<string, string>() // file|name → nodeId
  const screenByFile = new Map<string, string>() // file → nodeId for screen pages
  const apiByPath = new Map<string, string>() // "/api/foo" → nodeId
  const DB_NODE_ID = 'db:database'

  for (const sf of ctx.project.getSourceFiles()) {
    const fp = sf.getFilePath()
    if (fp.includes('node_modules')) continue
    const rel = relPath(ctx, fp)

    if (isScreenFile(fp)) {
      const id = `screen:${rel}`
      const node: GraphNode = {
        id,
        kind: 'screen',
        label: labelForScreen(fp),
        originalName: basename(fp),
        file: rel,
        line: 1,
        status: 'normal',
        hallucinationIds: [],
      }
      nodes.set(id, node)
      screenByFile.set(rel, id)
    } else if (isApiFile(fp)) {
      const apiPath = extractApiPath(fp)
      if (apiPath) {
        const id = `api:${apiPath}`
        const node: GraphNode = {
          id,
          kind: 'api',
          label: labelForApi(fp),
          originalName: apiPath,
          file: rel,
          line: 1,
          status: 'normal',
          hallucinationIds: [],
        }
        nodes.set(id, node)
        apiByPath.set(apiPath, id)
      }
    }

    // Exported symbols (components / functions / hooks)
    for (const fn of sf.getFunctions()) {
      if (!fn.isExported() && !fn.isDefaultExport()) continue
      const name = fn.getName()
      if (!name) continue
      registerSymbolNode(nodes, fileSymbolIndex, rel, name, fn.getStartLineNumber())
    }
    for (const vd of sf.getVariableDeclarations()) {
      const stmt = vd.getVariableStatement()
      if (!stmt?.isExported()) continue
      const init = vd.getInitializer()
      if (!init) continue
      if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
        registerSymbolNode(nodes, fileSymbolIndex, rel, vd.getName(), vd.getStartLineNumber())
      }
    }
  }

  // Edges pass: imports + fetch + db
  for (const sf of ctx.project.getSourceFiles()) {
    const fp = sf.getFilePath()
    if (fp.includes('node_modules')) continue
    const rel = relPath(ctx, fp)

    const callerNodeId = resolveCallerNodeId(rel, screenByFile, apiByPath, fileSymbolIndex, fp)
    if (!callerNodeId) continue

    // Import edges
    for (const imp of sf.getImportDeclarations()) {
      const spec = imp.getModuleSpecifierValue()
      if (!spec) continue
      const resolved = imp.getModuleSpecifierSourceFile()
      if (resolved) {
        const relResolved = relPath(ctx, resolved.getFilePath())
        const targetId = findImportTarget(resolved, relResolved, fileSymbolIndex, screenByFile, imp)
        if (targetId && targetId !== callerNodeId) {
          edges.push({
            from: callerNodeId,
            to: targetId,
            kind: 'imports',
            label: labelForEdge('imports'),
            status: 'normal',
          })
        }
      } else {
        // Unresolved — may be phantom; create synthetic missing node
        const isRelative = spec.startsWith('.') || spec.startsWith('/') || spec.startsWith('@/') || spec.startsWith('~/')
        if (!isRelative) continue
        if (isAssetImport(spec)) continue
        const missingId = `missing:${spec}`
        if (!nodes.has(missingId)) {
          nodes.set(missingId, {
            id: missingId,
            kind: 'missing',
            label: guessMissingLabel(spec),
            originalName: spec,
            status: 'phantom',
            hallucinationIds: [],
          })
          missingByPath.set(spec, missingId)
        }
        edges.push({
          from: callerNodeId,
          to: missingId,
          kind: 'imports',
          label: labelForEdge('imports'),
          status: 'broken',
        })
      }
    }

    // fetch('/api/...') edges
    sf.forEachDescendant((node) => {
      if (!Node.isCallExpression(node)) return
      if (!isFetchLikeCall(node)) return
      const arg = node.getArguments()[0]
      if (!arg) return
      const m = arg.getText().match(/['"`](\/api\/[^'"`?]+)['"`]/)
      if (!m) return
      const apiPath = normalizePath(m[1])
      const targetId = apiByPath.get(apiPath) ?? apiByPath.get(apiPath.replace(/\/$/, ''))
      if (!targetId) return
      edges.push({
        from: callerNodeId,
        to: targetId,
        kind: 'fetch',
        label: labelForEdge('fetch'),
        status: 'normal',
      })
    })

    // DB query edges (only for API handlers)
    if (isApiFile(fp)) {
      if (hasDbCall(sf)) {
        if (!nodes.has(DB_NODE_ID)) {
          nodes.set(DB_NODE_ID, {
            id: DB_NODE_ID,
            kind: 'db',
            label: '데이터베이스',
            originalName: 'database',
            status: 'normal',
            hallucinationIds: [],
          })
        }
        edges.push({
          from: callerNodeId,
          to: DB_NODE_ID,
          kind: 'query',
          label: labelForEdge('query'),
          status: 'normal',
        })
      }
    }
  }

  // Overlay hallucinations onto nodes
  for (const h of hallucinations) {
    attachHallucination(nodes, edges, h, screenByFile, apiByPath, fileSymbolIndex)
  }

  const dedup = dedupEdges(edges)
  const pruned = pruneIsolatedNodes([...nodes.values()], dedup)
  return { nodes: pruned, edges: dedup.filter((e) => pruned.some((n) => n.id === e.from) && pruned.some((n) => n.id === e.to)) }
}

/**
 * Remove nodes that are not connected to anything AND have no hallucination.
 * Keeps the graph legible: no orphan dots. Screens / APIs / DB are always kept
 * (they represent structural anchors even if no direct edges hit them).
 */
function pruneIsolatedNodes(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  const connected = new Set<string>()
  for (const e of edges) {
    connected.add(e.from)
    connected.add(e.to)
  }
  return nodes.filter((n) => {
    if (n.status !== 'normal') return true // hallucinations always stay
    if (n.kind === 'screen' || n.kind === 'api' || n.kind === 'db' || n.kind === 'missing') return true
    return connected.has(n.id)
  })
}

function isScreenFile(fp: string): boolean {
  return /\/app\/.+\/page\.(tsx|jsx|ts|js)$/.test(fp) || /\/app\/page\.(tsx|jsx|ts|js)$/.test(fp)
}
function isApiFile(fp: string): boolean {
  return /\/api\/.+\/route\.(ts|tsx|js|jsx)$/.test(fp)
}
function extractApiPath(fp: string): string | null {
  const m = fp.match(/\/api\/(.+?)\/route\.(ts|tsx|js|jsx)$/)
  if (!m) return null
  return '/api/' + m[1].replace(/\\/g, '/')
}
function normalizePath(p: string): string {
  return p.replace(/[?#].*$/, '').replace(/\/$/, '')
}
function isAssetImport(spec: string): boolean {
  return /\.(css|scss|sass|less|json|svg|png|jpg|jpeg|gif|webp|avif|ico|ttf|woff2?|eot|mp4|webm|mp3|wav|pdf|md|txt|yaml|yml|toml)$/i.test(spec)
}

function registerSymbolNode(
  nodes: Map<string, GraphNode>,
  idx: Map<string, string>,
  file: string,
  name: string,
  line: number,
): void {
  const id = `sym:${file}:${name}`
  if (nodes.has(id)) return
  const kind: NodeKind = /^[A-Z]/.test(name) ? 'component' : 'function'
  nodes.set(id, {
    id,
    kind,
    label: labelForSymbol(name),
    originalName: name,
    file,
    line,
    status: 'normal',
    hallucinationIds: [],
  })
  idx.set(`${file}|${name}`, id)
}

function resolveCallerNodeId(
  rel: string,
  screens: Map<string, string>,
  apis: Map<string, string>,
  symbols: Map<string, string>,
  fp: string,
): string | null {
  const screen = screens.get(rel)
  if (screen) return screen
  if (isApiFile(fp)) {
    const apiPath = extractApiPath(fp)
    if (apiPath) {
      const id = apis.get(apiPath)
      if (id) return id
    }
  }
  // Fallback: first exported symbol in this file acts as the caller.
  for (const [k, v] of symbols) {
    if (k.startsWith(rel + '|')) return v
  }
  return null
}

function findImportTarget(
  resolvedSf: SourceFile,
  relResolved: string,
  idx: Map<string, string>,
  screens: Map<string, string>,
  imp: import('ts-morph').ImportDeclaration,
): string | null {
  // Prefer matching a specific named import to a symbol node
  for (const spec of imp.getNamedImports()) {
    const name = spec.getName()
    const hit = idx.get(`${relResolved}|${name}`)
    if (hit) return hit
  }
  const def = imp.getDefaultImport()
  if (def) {
    const screen = screens.get(relResolved)
    if (screen) return screen
  }
  // Fallback: any symbol node in the resolved file
  for (const [k, v] of idx) {
    if (k.startsWith(relResolved + '|')) return v
  }
  return screens.get(relResolved) ?? null
}

function isFetchLikeCall(call: CallExpression): boolean {
  const expr = call.getExpression()
  const text = expr.getText()
  return (
    text === 'fetch' ||
    text.endsWith('.fetch') ||
    text === 'axios' ||
    text.endsWith('axios.get') ||
    text.endsWith('axios.post') ||
    text.endsWith('axios.put') ||
    text.endsWith('axios.delete')
  )
}

function hasDbCall(sf: SourceFile): boolean {
  const text = sf.getText()
  return (
    /supabase\s*\.\s*from\s*\(/.test(text) ||
    /prisma\s*\.\s*\w+\s*\.\s*(find|create|update|delete|upsert)/.test(text) ||
    /\.\s*query\s*\(/.test(text) ||
    /drizzle\s*\(/.test(text) ||
    /mongoose\s*\.\s*model\s*\(/.test(text)
  )
}

function guessMissingLabel(spec: string): string {
  const tail = spec.split('/').pop() ?? spec
  return `${labelForSymbol(tail)} (없음)`
}

function attachHallucination(
  nodes: Map<string, GraphNode>,
  edges: GraphEdge[],
  h: Hallucination,
  screens: Map<string, string>,
  apis: Map<string, string>,
  symbols: Map<string, string>,
): void {
  // For H1: mark the broken edge already exists; nothing else
  if (h.kind === 'H1') return

  if (h.kind === 'H3') {
    const name = (h.evidence as { symbol?: string }).symbol
    if (!name || !h.file) return
    const nodeId = symbols.get(`${h.file}|${name}`)
    const target = nodeId ? nodes.get(nodeId) : undefined
    if (target) {
      target.status = 'hollow'
      target.hallucinationIds.push(h.id)
    }
    return
  }

  if (h.kind === 'H4') {
    const members = (h.evidence as { members?: Array<{ file: string; name: string }> }).members ?? []
    for (const m of members) {
      const id = symbols.get(`${m.file}|${m.name}`)
      if (!id) continue
      const n = nodes.get(id)
      if (!n) continue
      n.status = 'duplicate'
      n.hallucinationIds.push(h.id)
    }
    // Connect duplicates to each other with ≈ edges
    const ids = members
      .map((m) => symbols.get(`${m.file}|${m.name}`))
      .filter((x): x is string => Boolean(x))
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        edges.push({
          from: ids[i],
          to: ids[j],
          kind: 'imports',
          label: '≈ 중복',
          status: 'normal',
        })
      }
    }
    return
  }

  if (h.kind === 'H7') {
    const apiPath = (h.evidence as { apiPath?: string }).apiPath
    const id = apiPath ? apis.get(apiPath) : undefined
    if (!id) return
    const n = nodes.get(id)
    if (!n) return
    n.status = 'dangling'
    n.hallucinationIds.push(h.id)
    // Mark outgoing query edges as dangling; add synthetic dangling edge to DB
    let found = false
    for (const e of edges) {
      if (e.from === id && e.kind === 'query') {
        e.status = 'dangling'
        found = true
      }
    }
    if (!found) {
      const DB_NODE_ID = 'db:database'
      if (!nodes.has(DB_NODE_ID)) {
        nodes.set(DB_NODE_ID, {
          id: DB_NODE_ID,
          kind: 'db',
          label: '데이터베이스',
          originalName: 'database',
          status: 'normal',
          hallucinationIds: [],
        })
      }
      edges.push({
        from: id,
        to: DB_NODE_ID,
        kind: 'query',
        label: labelForEdge('query'),
        status: 'dangling',
      })
    }
  }
}

function dedupEdges(edges: GraphEdge[]): GraphEdge[] {
  const seen = new Set<string>()
  const out: GraphEdge[] = []
  for (const e of edges) {
    const key = `${e.from}::${e.to}::${e.kind}::${e.status}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(e)
  }
  return out
}
