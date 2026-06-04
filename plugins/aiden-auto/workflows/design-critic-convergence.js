export const meta = {
  name: 'design-critic-convergence',
  description: 'Design⟲Critic convergence loop: critique an architecture from multiple independent lenses, redesign to resolve every HIGH/MED issue, repeat until critics find no blocking issues (converged). Then emit a concrete tier-tagged implementation plan. Encodes the "build confidence via convergence BEFORE autonomous implementation" directive (2026-06-04).',
  phases: [
    { title: 'Critique', detail: 'parallel adversarial critics, one per lens, find HIGH/MED/LOW issues' },
    { title: 'Redesign', detail: 'architect revises the design to resolve every blocking issue, minimally' },
    { title: 'Plan', detail: 'emit concrete tier-tagged implementation plan + confidence statement' },
  ],
}

// ── Defensive arg parse (runtime may deliver args as a JSON string) ─────────
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
A = A || {}
const context = A.context || ''
const lenses = Array.isArray(A.lenses) && A.lenses.length
  ? A.lenses
  : ['robustness-failure-modes', 'agentic-laziness-recurrence', 'confidence-instillation',
     'over-engineering', 'convergence-termination', 'universal-deployment-ssot', 'integration-coherence']
const maxRounds = Number.isInteger(A.maxRounds) ? A.maxRounds : 4
let design = A.artifact || ''

log(`design-critic-convergence: artifact ${design.length} chars, ${lenses.length} lenses, maxRounds ${maxRounds}`)
if (!design) { return { error: 'no artifact provided', converged: false } }

const ISSUES_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['HIGH', 'MED', 'LOW'] },
          where: { type: 'string', description: 'which part of the architecture' },
          why: { type: 'string', description: 'concrete failure mode / weakness' },
          suggested_fix: { type: 'string' },
        },
        required: ['title', 'severity', 'why', 'suggested_fix'],
      },
    },
  },
  required: ['issues'],
}

const REDESIGN_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    revised_architecture: { type: 'string', description: 'full revised architecture description' },
    changes_made: { type: 'array', items: { type: 'string' } },
  },
  required: ['revised_architecture', 'changes_made'],
}

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    implementation_plan: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          file: { type: 'string' },
          change: { type: 'string' },
          tier: { type: 'string', enum: ['T1', 'T2', 'T3'] },
          rationale: { type: 'string' },
        },
        required: ['file', 'change', 'tier'],
      },
    },
    confidence_statement: { type: 'string', description: 'why the converged design is trustworthy enough for autonomous implementation, OR why no-change is the confident call' },
    no_change_recommended: { type: 'boolean', description: 'true if no confident improvement — forgo changes this cycle' },
    no_change_reason: { type: 'string' },
  },
  required: ['implementation_plan', 'confidence_statement'],
}

const criticPrompt = (lens, d, round) =>
  `ultrathink\n\n` +
  `You are an ADVERSARIAL architecture critic. Lens = "${lens}". Round ${round}.\n\n` +
  `=== CONTEXT (framework inventory) ===\n${context}\n\n` +
  `=== ARCHITECTURE UNDER REVIEW (self-improvement workflow) ===\n${d}\n\n` +
  `=== TASK ===\nThrough the "${lens}" lens ONLY, find concrete weaknesses / failure modes / risks in THIS architecture. ` +
  `Be specific and skeptical — name the exact part, the exact way it breaks, and a concrete fix. ` +
  `Severity: HIGH = will break / defeats the goal; MED = real weakness worth fixing now; LOW = polish. ` +
  `Do NOT invent issues to seem thorough — if the lens finds nothing blocking, return an empty or LOW-only list (this is how convergence is reached). ` +
  `Return your result ONLY via the StructuredOutput tool.`

const redesignPrompt = (d, blocking, round) =>
  `You are the framework ARCHITECT. Round ${round} redesign.\n\n` +
  `=== CONTEXT ===\n${context}\n\n` +
  `=== CURRENT ARCHITECTURE ===\n${d}\n\n` +
  `=== BLOCKING ISSUES (HIGH/MED) the critics found ===\n${JSON.stringify(blocking, null, 1)}\n\n` +
  `=== TASK ===\nProduce a REVISED architecture that resolves EVERY HIGH/MED issue above. ` +
  `Stay MINIMAL — resolve the issues without adding over-engineering, new gates, or scope the issues didn't demand (over-engineering is itself a critiqued failure mode). ` +
  `Preserve everything that already works. Output the FULL revised architecture (self-contained) plus a list of the concrete changes you made. ` +
  `Return ONLY via the StructuredOutput tool.`

const planPrompt = (d, didConverge, cbHit) =>
  `You are the implementation planner.\n\n` +
  `=== CONVERGENCE STATUS ===\nconverged=${didConverge}, circuit_breaker_hit=${cbHit}\n\n` +
  `=== CONTEXT ===\n${context}\n\n` +
  `=== ARCHITECTURE (latest) ===\n${d}\n\n` +
  `=== TASK ===\nDerive a CONCRETE implementation plan: specific file-level changes to make the current framework match this architecture. ` +
  `For each: file path, the change, tier (T1=≤3 files non-destructive additive no-behavior-change / T2=scoped semantic / T3=architecture/policy/needs-design), and rationale. Only changes NOT already in place.\n\n` +
  `IMPORTANT — "no change" is a valid and ENCOURAGED outcome (2026-06-04 directive): if the design did NOT converge (circuit_breaker_hit=true), OR the converged design is not materially better than the current framework, OR no definitive conclusion was reached, then return an EMPTY implementation_plan and set no_change_recommended=true with a clear no_change_reason. Do NOT invent changes to appear productive — forgoing improvement this cycle is the correct, confident call when a clear improvement is absent.\n\n` +
  `Also write a one-paragraph confidence_statement (why this is trustworthy enough to implement autonomously, OR why no-change is the confident call). Return ONLY via the StructuredOutput tool.`

const history = []
let converged = false
let round = 0

while (round < maxRounds && !converged) {
  round++
  // 2026-06-04 FALSE-CONVERGENCE FIX (design-critic-convergence 가 자기 자신에게서 발견한 버그):
  // parallel() 은 throw/timeout 한 lens 를 null 로 만든다(Workflow 계약). 옛 .filter(Boolean) 는
  // 그 null 을 조용히 버려 "문제 0건" 으로 오인 → 모든 lens 실패 시 blocking=0 → 거짓 수렴(최악 경로).
  // → 각 lens 를 .catch 로 감싸 실패를 inspectable {ok:false} 로; 모든 dispatched lens 가 valid 일
  //   때만 수렴 선언. lens 누락 round 는 UNKNOWN — 수렴/redesign 안 하고 재비판(maxRounds bound →
  //   circuit_breaker → no-change, 절대 거짓수렴 안 함). quorum/taxonomy subsystem 없음 (over-eng 회피).
  const critiques = await parallel(
    lenses.map((lens) => () =>
      agent(criticPrompt(lens, design, round), { schema: ISSUES_SCHEMA, phase: 'Critique', label: `critic:${lens}·r${round}` })
        .then((r) => ({ ok: true, r }))
        .catch((e) => ({ ok: false, err: String(e) })),
    ),
  )
  const dispatched = lenses.length
  const valid = critiques.filter((c) => c && c.ok && c.r)
  const dropped = dispatched - valid.length
  const issues = valid.flatMap((c) => (c.r && c.r.issues) || [])
  const blocking = issues.filter((i) => i.severity === 'HIGH' || i.severity === 'MED')
  log(`Round ${round}: ${valid.length}/${dispatched} lenses valid, ${issues.length} issues, ${blocking.length} blocking, ${dropped} dropped`)

  if (dropped > 0) {
    // UNKNOWN round — a lens failed. "0 blocking" 신뢰 불가 → 수렴/redesign 금지, 재비판.
    history.push({ round, dropped, status: 'UNKNOWN-relens', total_issues: issues.length, blocking: blocking.length })
    continue
  }

  if (blocking.length === 0) {
    converged = true
    history.push({ round, total_issues: issues.length, blocking: 0, low_issues: issues })
    break
  }

  const rd = await agent(redesignPrompt(design, blocking, round), { schema: REDESIGN_SCHEMA, phase: 'Redesign', label: `redesign·r${round}` })
  history.push({ round, total_issues: issues.length, blocking: blocking.length, blocking_issues: blocking, changes_made: (rd && rd.changes_made) || [] })
  if (rd && rd.revised_architecture) design = rd.revised_architecture
}

const plan = await agent(planPrompt(design, converged, !converged && round >= maxRounds), { schema: PLAN_SCHEMA, phase: 'Plan', label: 'impl-plan' })

return {
  converged,
  rounds_run: round,
  circuit_breaker_hit: !converged && round >= maxRounds,
  final_architecture: design,
  history,
  implementation_plan: (plan && plan.implementation_plan) || [],
  confidence_statement: (plan && plan.confidence_statement) || '',
  no_change_recommended: (plan && plan.no_change_recommended) || false,
  no_change_reason: (plan && plan.no_change_reason) || '',
}
