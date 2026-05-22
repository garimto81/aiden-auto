import { createServer, IncomingMessage, ServerResponse } from 'node:http'
import { readFileSync, existsSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { AtlasDb } from '../storage/db.js'
import { buildClaudePrompt } from '../action/prompt.js'
import { createGitHubIssue } from '../action/issue.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const STATIC_DIR = resolve(__dirname, 'static')

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
}

function mimeFor(path: string): string {
  const ext = path.slice(path.lastIndexOf('.'))
  return MIME[ext] ?? 'application/octet-stream'
}

function json(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(body))
}

async function readBody(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks).toString('utf8')
}

export interface ServerConfig {
  db: AtlasDb
  targetDir: string
  port?: number
}

export function startServer(cfg: ServerConfig): Promise<{ url: string; close: () => void }> {
  const server = createServer(async (req, res) => {
    try {
      await route(req, res, cfg)
    } catch (e) {
      json(res, 500, { error: String(e) })
    }
  })

  return new Promise((resolveP, rejectP) => {
    server.on('error', rejectP)
    server.listen(cfg.port ?? 0, '127.0.0.1', () => {
      const addr = server.address()
      if (!addr || typeof addr === 'string') {
        rejectP(new Error('failed to bind'))
        return
      }
      const url = `http://localhost:${addr.port}`
      resolveP({ url, close: () => server.close() })
    })
  })
}

async function route(req: IncomingMessage, res: ServerResponse, cfg: ServerConfig) {
  const url = new URL(req.url ?? '/', 'http://localhost')
  const path = url.pathname
  const method = req.method ?? 'GET'

  if (path === '/api/run' && method === 'GET') {
    const runId = cfg.db.latestRunId()
    if (!runId) return json(res, 404, { error: 'no run' })
    const summary = cfg.db.getRun(runId)
    const hallu = cfg.db.listHallucinations(runId)
    const visible = hallu.filter((h) => !cfg.db.isFalsePositive(h.id))
    const graph = cfg.db.getGraph(runId)
    return json(res, 200, { summary, hallucinations: visible, graph })
  }

  if (path.startsWith('/api/action/prompt/') && method === 'GET') {
    const id = decodeURIComponent(path.slice('/api/action/prompt/'.length))
    const runId = cfg.db.latestRunId()
    if (!runId) return json(res, 404, { error: 'no run' })
    const hallu = cfg.db.listHallucinations(runId).find((h) => h.id === id)
    const summary = cfg.db.getRun(runId)
    if (!hallu || !summary) return json(res, 404, { error: 'not found' })
    const prompt = buildClaudePrompt(hallu, summary)
    res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' })
    return res.end(prompt)
  }

  if (path.startsWith('/api/action/issue/') && method === 'POST') {
    const id = decodeURIComponent(path.slice('/api/action/issue/'.length))
    const runId = cfg.db.latestRunId()
    if (!runId) return json(res, 404, { error: 'no run' })
    const hallu = cfg.db.listHallucinations(runId).find((h) => h.id === id)
    const summary = cfg.db.getRun(runId)
    if (!hallu || !summary) return json(res, 404, { error: 'not found' })
    const result = createGitHubIssue(hallu, summary)
    return json(res, result.success ? 200 : 500, result)
  }

  if (path.startsWith('/api/action/fp/') && method === 'POST') {
    const id = decodeURIComponent(path.slice('/api/action/fp/'.length))
    cfg.db.markFalsePositive(id)
    return json(res, 200, { ok: true })
  }

  // Static
  const filePath = path === '/' ? 'index.html' : path.slice(1)
  const full = join(STATIC_DIR, filePath)
  if (!full.startsWith(STATIC_DIR)) {
    return json(res, 403, { error: 'forbidden' })
  }
  if (!existsSync(full)) {
    return json(res, 404, { error: 'not found' })
  }
  res.writeHead(200, { 'content-type': mimeFor(full), 'cache-control': 'no-cache' })
  res.end(readFileSync(full))
}
