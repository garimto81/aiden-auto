import { spawnSync } from 'node:child_process'

export interface BlameInfo {
  sha: string
  author: string
  date: string
  summary: string
}

export function gitBlameLine(cwd: string, file: string, line: number): BlameInfo | null {
  const result = spawnSync(
    'git',
    ['log', '-1', '--format=%H%x09%an%x09%ad%x09%s', '-L', `${line},${line}:${file}`],
    { encoding: 'utf8', cwd },
  )
  if (result.status !== 0 || !result.stdout) return null
  const firstLine = result.stdout.trim().split('\n').find((l) => l.includes('\t'))
  if (!firstLine) return null
  const [sha, author, date, summary] = firstLine.split('\t')
  return { sha, author, date, summary }
}
