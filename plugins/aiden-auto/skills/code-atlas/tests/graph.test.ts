import { describe, it, expect } from 'vitest'
import { resolve } from 'node:path'
import { runScan } from '../scripts/analyzer/index.js'

const FIXTURE = resolve(__dirname, 'fixtures/bad-repo')

describe('graph builder', () => {
  it('produces nodes and edges from fixture', async () => {
    const result = await runScan(FIXTURE)
    expect(result.graph).toBeDefined()
    expect(result.graph.nodes.length).toBeGreaterThan(0)
  })

  it('H1 phantom creates a missing node and a broken edge', async () => {
    const result = await runScan(FIXTURE)
    const missing = result.graph.nodes.filter((n) => n.kind === 'missing')
    expect(missing.length).toBeGreaterThanOrEqual(1)
    const broken = result.graph.edges.filter((e) => e.status === 'broken')
    expect(broken.length).toBeGreaterThanOrEqual(1)
  })

  it('H3 hollow marks the symbol node status=hollow', async () => {
    const result = await runScan(FIXTURE)
    const hollowNodes = result.graph.nodes.filter((n) => n.status === 'hollow')
    const names = hollowNodes.map((n) => n.originalName)
    expect(names).toContain('processPayment')
    expect(names).toContain('sendNotification')
    expect(names).toContain('computeTax')
  })

  it('H4 duplicate connects cluster members with ≈ edges', async () => {
    const result = await runScan(FIXTURE)
    const dupNodes = result.graph.nodes.filter((n) => n.status === 'duplicate')
    const dupNames = dupNodes.map((n) => n.originalName)
    expect(dupNames).toContain('UserCard')
    expect(dupNames).toContain('CustomerCard')

    const dupEdges = result.graph.edges.filter((e) => e.label === '≈ 중복')
    expect(dupEdges.length).toBeGreaterThanOrEqual(1)
  })

  it('Korean labels are applied', async () => {
    const result = await runScan(FIXTURE)
    const hollow = result.graph.nodes.find((n) => n.originalName === 'processPayment')
    // processPayment → 결제 처리 (dict hit)
    expect(hollow?.label).toBe('결제 처리')
    const userCard = result.graph.nodes.find((n) => n.originalName === 'UserCard')
    // UserCard → 사용자 카드 (dict hit), kept because status=duplicate
    expect(userCard?.label).toBe('사용자 카드')
  })

  it('isolated normal nodes are pruned', async () => {
    const result = await runScan(FIXTURE)
    const realFn = result.graph.nodes.find((n) => n.originalName === 'realFunction')
    // realFunction has no inbound/outbound edges and no hallucination → pruned
    expect(realFn).toBeUndefined()
  })
})
