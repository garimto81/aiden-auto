import { Node, CallExpression, SourceFile } from 'ts-morph'
import type { TargetContext } from './project.js'
import { relPath } from './project.js'
import type { Hallucination } from './types.js'
import { fingerprint } from './fingerprint.js'
import { basename } from 'node:path'

const DB_ACCESS_PATTERNS = [
  /supabase\s*\.\s*from\s*\(/,
  /prisma\s*\.\s*\w+\s*\.\s*(find|create|update|delete|upsert)/,
  /\.\s*query\s*\(/,
  /\.\s*exec\s*\(/,
  /db\s*\.\s*\w+\s*\(/,
  /mongoose\s*\.\s*model\s*\(/,
  /drizzle\s*\(/,
  /fetch\s*\(\s*['"]http/,
]

/**
 * H7 — Dangling Edge (Next.js App Router focus)
 * UI → fetch('/api/foo') → api/foo/route.ts handler.
 * If handler has no DB/network call but returns mock, flag H7.
 */
export function detectDanglingEdges(ctx: TargetContext): Hallucination[] {
  if (!ctx.hasNextJs) return []

  const handlers = collectApiHandlers(ctx)
  if (handlers.size === 0) return []

  const fetches = collectUiFetches(ctx)
  const out: Hallucination[] = []

  for (const fetch of fetches) {
    const apiPath = normalizeApiPath(fetch.path)
    const handler = handlers.get(apiPath)
    if (!handler) continue
    if (handlerReachesBackend(handler.sf)) continue
    const file = fetch.file
    const id = fingerprint('H7', file, fetch.line, apiPath)
    out.push({
      id,
      kind: 'H7',
      severity: 'warn',
      file,
      line: fetch.line,
      symbol: apiPath,
      message: `UI → ${apiPath} 호출은 있으나 라우트 핸들러가 DB/외부 API 에 닿지 않음 (mock 반환 추정)`,
      evidence: {
        uiFile: file,
        uiLine: fetch.line,
        apiPath,
        handlerFile: handler.file,
        handlerSnippet: handler.snippet,
      },
    })
  }

  return out
}

interface ApiHandler {
  sf: SourceFile
  file: string
  snippet: string
}

function collectApiHandlers(ctx: TargetContext): Map<string, ApiHandler> {
  const map = new Map<string, ApiHandler>()
  for (const sf of ctx.project.getSourceFiles()) {
    const fp = sf.getFilePath()
    if (fp.includes('node_modules')) continue
    const match = fp.match(/\/api\/(.+?)\/route\.(ts|js|tsx|jsx)$/)
    if (!match) continue
    const apiPath = '/api/' + match[1].replace(/\\/g, '/')
    map.set(apiPath, {
      sf,
      file: relPath(ctx, fp),
      snippet: sf.getText().slice(0, 280),
    })
  }
  return map
}

interface FetchCall {
  path: string
  file: string
  line: number
}

function collectUiFetches(ctx: TargetContext): FetchCall[] {
  const out: FetchCall[] = []
  for (const sf of ctx.project.getSourceFiles()) {
    const fp = sf.getFilePath()
    if (fp.includes('node_modules')) continue
    if (fp.match(/\/api\/.*\/route\.(ts|js|tsx|jsx)$/)) continue

    sf.forEachDescendant((node) => {
      if (!Node.isCallExpression(node)) return
      if (!isFetchCall(node)) return
      const arg = node.getArguments()[0]
      if (!arg) return
      const arg0 = arg.getText()
      const m = arg0.match(/['"`](\/api\/[^'"`?]+)['"`]/)
      if (!m) return
      out.push({
        path: m[1],
        file: relPath(ctx, fp),
        line: node.getStartLineNumber(),
      })
      // implicit return undefined — keep traversing
    })
  }
  return out
}

function isFetchCall(call: CallExpression): boolean {
  const expr = call.getExpression()
  const text = expr.getText()
  return text === 'fetch' || text.endsWith('.fetch') || text === 'axios' || text.endsWith('.get') || text.endsWith('.post')
}

function handlerReachesBackend(sf: SourceFile): boolean {
  const text = sf.getText()
  return DB_ACCESS_PATTERNS.some((rx) => rx.test(text))
}

function normalizeApiPath(p: string): string {
  // Remove trailing slash and query/hash
  return p.replace(/[?#].*$/, '').replace(/\/$/, '')
}
