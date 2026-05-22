#!/usr/bin/env node
import { resolve } from 'node:path'
import { existsSync } from 'node:fs'
import { runScan } from './analyzer/index.js'
import { openDb } from './storage/db.js'
import { startServer } from './viewer/server.js'
import { openUrl } from './utils/open-url.js'

interface CliArgs {
  target: string
  port?: number
  noOpen: boolean
  noServer: boolean
}

function parseArgs(argv: string[]): CliArgs {
  let target = process.cwd()
  let port: number | undefined
  let noOpen = false
  let noServer = false

  const rest = argv.slice()
  for (let i = 0; i < rest.length; i++) {
    const a = rest[i]
    if (a === '--no-open') noOpen = true
    else if (a === '--no-server') noServer = true
    else if (a === '--port' && rest[i + 1]) {
      port = Number(rest[++i])
    } else if (!a.startsWith('-')) {
      target = a
    }
  }
  target = resolve(target)
  if (!existsSync(target)) {
    throw new Error(`Target directory not found: ${target}`)
  }
  return { target, port, noOpen, noServer }
}

function formatProgress(phase: string, done: number, total: number) {
  const bar = '█'.repeat(done) + '░'.repeat(total - done)
  return `[${bar}] ${phase.padEnd(10)} ${done}/${total}`
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  process.stdout.write(`\n🗺 Code Atlas v2.0.0 — scanning ${args.target}\n\n`)

  const result = await runScan(args.target, ({ phase, done, total }) => {
    process.stdout.write('\r' + formatProgress(phase, done, total))
  })
  process.stdout.write('\n')

  const db = openDb(args.target)
  db.saveRun(result.summary, result.hallucinations, result.graph)

  const c = result.summary.byKind
  process.stdout.write(
    `\n📦 ${result.summary.fileCount} TS/JS files analyzed\n` +
      `✅ Scan complete — ${result.summary.nodeCount} hallucinations\n` +
      `   🔴 H1 Phantom Reference: ${c.H1}\n` +
      `   ⚪ H3 Hollow Stub:        ${c.H3}\n` +
      `   🟠 H4 Silent Duplicate:   ${c.H4}\n` +
      `   🔵 H7 Dangling Edge:      ${c.H7}\n\n`,
  )

  if (result.summary.fileCount === 0) {
    process.stdout.write(
      `⚠ 분석 가능한 TypeScript/JavaScript 파일이 없습니다.\n` +
        `   타겟: ${args.target}\n\n` +
        `   가능한 원인:\n` +
        `   • 프로젝트가 Flutter/Dart, Python, Go, Rust 등 타 언어 (v2 미지원)\n` +
        `   • Monorepo 루트 지정 — 하위 서브프로젝트 경로로 다시 실행해보세요\n\n`,
    )
  }

  if (args.noServer) {
    process.stdout.write(`Results saved to ${args.target}/.code-atlas/atlas.db\n`)
    db.close()
    return
  }

  const { url, close } = await startServer({ db, targetDir: args.target, port: args.port })
  process.stdout.write(`🌐 Viewer: ${url}\n`)

  if (!args.noOpen) {
    await openUrl(url)
  }

  // Keep alive until SIGINT
  process.on('SIGINT', () => {
    close()
    db.close()
    process.stdout.write('\n👋 bye\n')
    process.exit(0)
  })
}

main().catch((e) => {
  process.stderr.write('error: ' + (e?.message ?? String(e)) + '\n')
  process.exit(1)
})
