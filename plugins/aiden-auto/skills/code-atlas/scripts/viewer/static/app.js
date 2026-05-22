/* eslint-disable */
/* global mermaid */

(function () {
  const state = {
    run: null,
    graph: null,
    hallucinations: [],
    halluById: new Map(),
    nodeIdToMermaidId: new Map(),
    selectedNodeId: null,
    selectedHalluId: null,
  }

  function qs(sel) { return document.querySelector(sel) }

  async function init() {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: 'dark',
      flowchart: { htmlLabels: true, curve: 'basis', nodeSpacing: 40, rankSpacing: 60 },
      fontFamily: '-apple-system, Segoe UI, Noto Sans KR, Roboto, sans-serif',
    })
    await loadRun()
  }

  async function loadRun() {
    const res = await fetch('/api/run')
    if (!res.ok) {
      qs('#graph-status').textContent = '아직 스캔 결과가 없습니다. 터미널에서 /code-atlas 를 실행해 주세요.'
      return
    }
    const data = await res.json()
    state.run = data.summary
    state.graph = data.graph
    state.hallucinations = data.hallucinations || []
    state.halluById = new Map(state.hallucinations.map((h) => [h.id, h]))

    renderMeta()
    await renderGraph()
  }

  function renderMeta() {
    const s = state.run
    if (!s) return
    const c = s.byKind
    qs('#run-meta').textContent =
      `${s.fileCount} 파일 분석 · ` +
      `🔴 없음 ${c.H1} · ⚪ 빈 껍데기 ${c.H3} · 🟠 중복 ${c.H4} · 🔵 DB 안 감 ${c.H7}`
  }

  async function renderGraph() {
    const g = state.graph
    const graphEl = qs('#mermaid-target')
    const statusEl = qs('#graph-status')

    if (!g || !g.nodes || g.nodes.length === 0) {
      statusEl.textContent =
        '감지된 화면/함수/API 가 없습니다. TypeScript/JavaScript 프로젝트가 맞는지 확인해 주세요.'
      graphEl.textContent = ''
      return
    }

    statusEl.textContent = ''
    const mermaidSrc = buildMermaidSource(g)
    try {
      const { svg, bindFunctions } = await mermaid.render('atlas-diagram', mermaidSrc)
      qs('#mermaid-wrapper').innerHTML = svg
      if (bindFunctions) bindFunctions(qs('#mermaid-wrapper'))
      wireNodeClicks()
    } catch (e) {
      statusEl.textContent = '다이어그램 렌더 실패: ' + (e && e.message)
      console.error(e, '\n--- mermaid source ---\n', mermaidSrc)
    }
  }

  function sanitizeId(id) {
    // Short deterministic hash to avoid 100+ char mermaid identifiers
    let h = 5381
    const s = String(id)
    for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0
    return 'n' + (h >>> 0).toString(36)
  }

  function buildMermaidSource(g) {
    const lines = ['flowchart TD']
    state.nodeIdToMermaidId.clear()

    for (const node of g.nodes) {
      const mid = sanitizeId(node.id)
      state.nodeIdToMermaidId.set(node.id, mid)
      const icon = kindIcon(node.kind, node.status)
      const label = esc(`${icon} ${node.label}`)
      const shape = shapeFor(node.kind)
      lines.push(`  ${mid}${shape.open}"${label}"${shape.close}`)
      lines.push(`  class ${mid} ${node.status}`)
    }

    g.edges.forEach((e) => {
      const from = state.nodeIdToMermaidId.get(e.from)
      const to = state.nodeIdToMermaidId.get(e.to)
      if (!from || !to) return
      const label = esc(e.label)
      const arrow = arrowFor(e.status)
      lines.push(`  ${from} ${arrow}|"${label}"| ${to}`)
    })

    lines.push(`  classDef normal    fill:#1a2330,stroke:#3c8bcf,color:#e6e6e6`)
    lines.push(`  classDef phantom   fill:#2a0000,stroke:#ff4a4a,color:#ffc6c6,stroke-dasharray:5 3`)
    lines.push(`  classDef hollow    fill:#1a1a1a,stroke:#9e9e9e,color:#d8d8d8`)
    lines.push(`  classDef duplicate fill:#2a1800,stroke:#ffa64a,color:#ffe0b0`)
    lines.push(`  classDef dangling  fill:#001a2a,stroke:#4aa8ff,color:#bfe0ff,stroke-dasharray:4 3`)

    return lines.join('\n')
  }

  function kindIcon(kind, status) {
    if (status === 'phantom') return '🔴'
    if (status === 'hollow') return '⚪'
    if (status === 'duplicate') return '🟠'
    if (status === 'dangling') return '🔵'
    switch (kind) {
      case 'screen':    return '🖥'
      case 'api':       return '🔌'
      case 'component': return '🧩'
      case 'function':  return 'ƒ'
      case 'db':        return '🗄'
      case 'missing':   return '❌'
      default:          return '•'
    }
  }

  function shapeFor(kind) {
    switch (kind) {
      case 'screen':   return { open: '[[', close: ']]' }
      case 'api':      return { open: '([', close: '])' }
      case 'db':       return { open: '[(', close: ')]' }
      case 'missing':  return { open: '{{', close: '}}' }
      default:         return { open: '[',  close: ']'  }
    }
  }

  function arrowFor(status) {
    if (status === 'broken') return '-. x .->'
    if (status === 'dangling') return '-.->'
    return '-->'
  }

  function esc(s) {
    return String(s).replace(/"/g, '＂').replace(/[<>]/g, '').replace(/\n/g, ' ')
  }

  function wireNodeClicks() {
    const svg = qs('#mermaid-wrapper svg')
    if (!svg) return
    const mermaidToGraphId = new Map()
    for (const [graphId, mermaidId] of state.nodeIdToMermaidId) {
      mermaidToGraphId.set(mermaidId, graphId)
    }
    svg.querySelectorAll('g.node').forEach((el) => {
      const idAttr = el.id || ''
      const match = idAttr.match(/(n_[a-zA-Z0-9_]+)/)
      if (!match) return
      const gid = mermaidToGraphId.get(match[1])
      if (!gid) return
      el.style.cursor = 'pointer'
      el.addEventListener('click', (ev) => {
        ev.stopPropagation()
        selectNode(gid)
      })
    })
  }

  function findNode(id) {
    return (state.graph?.nodes ?? []).find((n) => n.id === id) ?? null
  }

  function selectNode(nodeId) {
    state.selectedNodeId = nodeId
    const node = findNode(nodeId)
    const hallu = pickHallucinationForNode(node)
    state.selectedHalluId = hallu?.id ?? null

    const svg = qs('#mermaid-wrapper svg')
    if (svg) {
      svg.querySelectorAll('g.node').forEach((el) => el.classList.remove('selected'))
      const mid = state.nodeIdToMermaidId.get(nodeId)
      if (mid) {
        svg.querySelectorAll(`g.node[id*="${mid}"]`).forEach((el) => el.classList.add('selected'))
      }
    }

    renderEvidence(node, hallu)
    qs('#action-dock').classList.toggle('hidden', !hallu)
  }

  function pickHallucinationForNode(node) {
    if (!node || !node.hallucinationIds || node.hallucinationIds.length === 0) return null
    return state.halluById.get(node.hallucinationIds[0]) ?? null
  }

  function renderEvidence(node, hallu) {
    const panel = qs('#evidence-panel')
    if (!node) {
      panel.innerHTML = '<h3>🔍 세부 정보</h3><div class="empty">박스를 클릭하세요.</div>'
      return
    }
    const statusLabelMap = {
      normal: '정상',
      phantom: '없는 파일',
      hollow: '빈 껍데기',
      duplicate: '중복',
      dangling: 'DB 에 안 감',
    }
    const badge = node.status !== 'normal'
      ? `<span class="evidence-badge ${node.status}">${statusLabelMap[node.status]}</span>`
      : ''
    let html = `<h3>🔍 세부 정보</h3>
      <div class="evidence-title">${escHtml(node.label)}</div>
      <div class="evidence-sub">${badge}${escHtml(node.originalName || '')}${node.file ? ' · ' + escHtml(node.file) : ''}${node.line ? ':' + node.line : ''}</div>`

    if (node.status === 'normal') {
      html += `<div class="evidence-section"><h4>상태</h4><pre>이 박스는 지금 정상 작동합니다. 위의 다른 박스를 클릭해 주세요.</pre></div>`
    }

    if (hallu) {
      html += `<div class="evidence-section"><h4>무슨 문제인가요</h4><pre>${escHtml(hallu.message)}</pre></div>`
      html += `<div class="evidence-section"><h4>증거</h4><pre>${escHtml(prettyEvidence(hallu))}</pre></div>`
      html += `<div class="evidence-section"><h4>이 노드의 식별자</h4><pre>${escHtml(hallu.id)}</pre></div>`
    }

    panel.innerHTML = html
  }

  function prettyEvidence(h) {
    const ev = h.evidence || {}
    const lines = []
    if (ev.claimedPath) lines.push(`AI 주장 경로: ${ev.claimedPath}`)
    if (ev.callerFile) lines.push(`호출 위치: ${ev.callerFile}:${ev.callerLine ?? ''}`)
    if (ev.symbol) lines.push(`대상 심볼: ${ev.symbol}`)
    if (ev.bodySnippet) lines.push(`본문 미리보기:\n${ev.bodySnippet}`)
    if (ev.members) {
      lines.push('중복 멤버:')
      for (const m of ev.members) lines.push(`  · ${m.name} (${m.file}:${m.line})`)
    }
    if (ev.apiPath) lines.push(`API 경로: ${ev.apiPath}`)
    if (ev.uiFile) lines.push(`UI 호출: ${ev.uiFile}:${ev.uiLine ?? ''}`)
    if (ev.handlerFile) lines.push(`핸들러: ${ev.handlerFile}`)
    if (ev.handlerSnippet) lines.push(`핸들러 미리보기:\n${ev.handlerSnippet}`)
    if (lines.length === 0) return JSON.stringify(ev, null, 2)
    return lines.join('\n')
  }

  async function copyPrompt() {
    if (!state.selectedHalluId) return
    const res = await fetch('/api/action/prompt/' + encodeURIComponent(state.selectedHalluId))
    const text = await res.text()
    try {
      await navigator.clipboard.writeText(text)
      setStatus('지시서가 복사되었습니다. 새 Claude Code 세션에 붙여넣으세요.', false)
    } catch {
      setStatus('클립보드 권한 없음. 아래에서 수동으로 복사하세요.', true)
      const panel = qs('#evidence-panel')
      panel.innerHTML += `<div class="evidence-section"><h4>복사 대상</h4><pre id="manual-copy">${escHtml(text)}</pre></div>`
      const el = document.getElementById('manual-copy')
      const range = document.createRange()
      range.selectNodeContents(el)
      const sel = window.getSelection()
      sel.removeAllRanges()
      sel.addRange(range)
    }
  }

  async function createIssue() {
    if (!state.selectedHalluId) return
    const res = await fetch('/api/action/issue/' + encodeURIComponent(state.selectedHalluId), { method: 'POST' })
    const data = await res.json()
    if (data.success) setStatus('이슈 생성됨: ' + data.url, false)
    else setStatus('이슈 생성 실패: ' + (data.error || 'unknown'), true)
  }

  async function markFp() {
    if (!state.selectedHalluId) return
    await fetch('/api/action/fp/' + encodeURIComponent(state.selectedHalluId), { method: 'POST' })
    setStatus('오탐으로 표시됨. 재스캔 시 제외됩니다.', false)
    loadRun()
  }

  function setStatus(msg, err) {
    const el = qs('#action-status')
    el.textContent = msg
    el.className = 'status' + (err ? ' err' : '')
    setTimeout(() => (el.textContent = ''), 6000)
  }

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
  }

  qs('#btn-prompt').addEventListener('click', copyPrompt)
  qs('#btn-issue').addEventListener('click', createIssue)
  qs('#btn-fp').addEventListener('click', markFp)

  init()
})()
