import { describe, it, expect } from 'vitest'
import { runScan } from '../scripts/analyzer/index.js'
import { resolve } from 'node:path'

const FIXTURE = resolve(__dirname, 'fixtures/bad-repo')

describe('H1 phantom', () => {
  it('detects unresolved imports', async () => {
    const result = await runScan(FIXTURE)
    const h1 = result.hallucinations.filter((h) => h.kind === 'H1')
    expect(h1.length).toBeGreaterThanOrEqual(2)
    const claimed = h1.map((h) => (h.evidence as any).claimedPath)
    expect(claimed).toContain('@/lib/hooks/useAuth')
    expect(claimed).toContain('./nonexistent-helper')
  })
})

describe('H3 hollow', () => {
  it('detects empty-body functions', async () => {
    const result = await runScan(FIXTURE)
    const h3 = result.hallucinations.filter((h) => h.kind === 'H3')
    const symbols = h3.map((h) => h.symbol)
    expect(symbols).toContain('processPayment') // return false + TODO
    expect(symbols).toContain('sendNotification') // FIXME comment
    expect(symbols).toContain('computeTax') // throw not implemented
    expect(symbols).not.toContain('realFunction') // real logic
  })
})

describe('H4 duplicate', () => {
  it('clusters UserCard and CustomerCard as duplicate', async () => {
    const result = await runScan(FIXTURE)
    const h4 = result.hallucinations.filter((h) => h.kind === 'H4')
    expect(h4.length).toBeGreaterThanOrEqual(1)
    const members = (h4[0].evidence as any).members.map((m: any) => m.name)
    expect(members).toContain('UserCard')
    expect(members).toContain('CustomerCard')
    expect(members).not.toContain('unrelatedHelper')
  })
})
