import { spawnSync } from 'node:child_process'
import type { Hallucination, RunSummary } from '../analyzer/types.js'

export interface IssueCreateResult {
  success: boolean
  url?: string
  error?: string
}

/**
 * Create a GitHub issue using the `gh` CLI. Returns failure gracefully if
 * gh is not installed or the user is not authenticated — caller can fall
 * back to clipboard copy.
 */
export function createGitHubIssue(
  h: Hallucination,
  summary: Pick<RunSummary, 'targetDir'>,
): IssueCreateResult {
  const gh = spawnSync('gh', ['--version'], { encoding: 'utf8' })
  if (gh.status !== 0) {
    return { success: false, error: 'gh CLI not installed' }
  }

  const title = `[${h.kind}] ${h.message}`
  const body = buildIssueBody(h, summary)
  const labels = ['ai-hallucination', h.kind.toLowerCase(), `severity-${h.severity}`]

  const args = [
    'issue',
    'create',
    '--title',
    title,
    '--body',
    body,
    '--label',
    labels.join(','),
  ]

  const result = spawnSync('gh', args, {
    encoding: 'utf8',
    cwd: summary.targetDir,
  })

  if (result.status !== 0) {
    return { success: false, error: result.stderr || result.stdout }
  }

  const url = (result.stdout || '').trim().split('\n').pop()
  return { success: true, url }
}

function buildIssueBody(h: Hallucination, summary: Pick<RunSummary, 'targetDir'>): string {
  return [
    `## ${h.kind} Detected`,
    ``,
    `**위치**: \`${h.file}\`:${h.line}${h.endLine ? `-${h.endLine}` : ''}`,
    `**심볼**: ${h.symbol ?? '-'}`,
    `**메시지**: ${h.message}`,
    ``,
    `### 증거`,
    '```json',
    JSON.stringify(h.evidence, null, 2),
    '```',
    ``,
    `---`,
    `감지 도구: [Code Atlas](https://github.com/garimto81/project_master) (local v2.0.0)`,
    `레포 루트: \`${summary.targetDir}\``,
    `Fingerprint: \`${h.id}\``,
  ].join('\n')
}
