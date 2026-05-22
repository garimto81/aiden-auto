import type { Hallucination, RunSummary } from '../analyzer/types.js'

/**
 * Build a self-contained Claude Code prompt that a non-developer can paste
 * into a fresh Claude session to trigger a fix. Includes all context needed
 * for the fix to be actionable without round-trips.
 */
export function buildClaudePrompt(
  h: Hallucination,
  summary: Pick<RunSummary, 'targetDir'>,
): string {
  const header = `# Context
레포 루트: ${summary.targetDir}
감지 도구: Code Atlas (local)

# ${emoji(h.kind)} ${h.kind} — ${titleFor(h.kind)}
**위치**: \`${h.file}\`:${h.line}${h.endLine ? `–${h.endLine}` : ''}
**심볼**: ${h.symbol ?? '-'}
**메시지**: ${h.message}

`

  const evidence =
    `# 증거\n\`\`\`json\n${JSON.stringify(h.evidence, null, 2)}\n\`\`\`\n\n`

  const directive =
    `# 수정 지시\n` +
    `다음을 수행해주세요:\n\n` +
    stepsFor(h) +
    `\n\n` +
    `# 검증 기준\n` +
    `- 이 위치의 환각이 재감지되지 않는다 (같은 fingerprint 미생성)\n` +
    `- 기존 테스트가 모두 통과한다 (\`npx vitest run\`)\n` +
    `- TypeScript 컴파일 통과 (\`npx tsc --noEmit\`)\n\n` +
    `# 완료 후\n` +
    `커밋 메시지 예시: \`fix(atlas): ${h.kind} at ${h.file}:${h.line}\`\n`

  return header + evidence + directive
}

function titleFor(kind: Hallucination['kind']): string {
  return {
    H1: 'Phantom Reference (존재하지 않는 참조)',
    H3: 'Hollow Stub (빈 껍데기 구현)',
    H4: 'Silent Duplicate (의미적 중복)',
    H7: 'Dangling Edge (UI→API→DB 단절)',
  }[kind]
}

function emoji(kind: Hallucination['kind']): string {
  return { H1: '🔴', H3: '⚪', H4: '🟠', H7: '🔵' }[kind]
}

function stepsFor(h: Hallucination): string {
  switch (h.kind) {
    case 'H1':
      return `1. 주장된 경로 \`${(h.evidence as any).claimedPath}\` 가 실제 존재하는지 확인\n` +
        `2. 다음 옵션 중 선택:\n` +
        `   (a) 유사한 이름의 실존 파일이 있으면 rename 또는 경로 수정\n` +
        `   (b) 신규 파일을 작성하여 해당 심볼 export\n` +
        `   (c) 사용부를 제거하고 인라인 구현으로 대체`
    case 'H3':
      return `1. \`${h.symbol}\` 가 의도된 기능을 실제로 구현하도록 본문 작성\n` +
        `2. 호출부를 찾아 (\`Grep "${h.symbol}"\`) 반환값에 대한 가정이 맞는지 점검`
    case 'H4': {
      const members = (h.evidence as any).members as Array<{ file: string; line: number; name: string }>
      const memberList = members.map((m) => `   - \`${m.file}:${m.line}\` \`${m.name}\``).join('\n')
      return `1. 다음 중복 후보들의 실제 기능을 비교:\n${memberList}\n` +
        `2. 가장 성숙한 구현 하나를 선택하고 공용 모듈로 추출\n` +
        `3. 나머지는 해당 모듈을 import 하도록 리팩토링\n` +
        `4. 제거 대상이 다른 맥락(테스트·픽스처)에서 참조되는지 확인`
    }
    case 'H7':
      return `1. \`${(h.evidence as any).handlerFile}\` 의 라우트 핸들러 본문 확인\n` +
        `2. 실제 DB/외부 API 호출을 추가 (프로젝트 컨벤션에 맞게 Supabase/Prisma/fetch 선택)\n` +
        `3. UI 호출부가 기대하는 응답 shape 를 유지`
  }
}
