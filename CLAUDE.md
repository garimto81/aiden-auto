# aiden-auto v28.1 — Index Router

> **Core Philosophy**: 사용자 진입점 최소화 + 자율 이터레이션 최대화. 가장 완벽한 산출물을 만든다.

## 5가지 핵심 원칙 (HARD ENFORCE)

1. **외부 harness framework 그대로 유지** — bkit-claude-code, anthropics/claude-code, vercel, atlassian, superpowers 등은 *복사하지 않고 참조만*. `references/external-harness-registry.md` 등록.
2. **자가개선 critic 사이클** — `agents/meta/harness-watcher` (매일) → `harness-critic` (5원칙 부합 판정) → `harness-applier` (patch + PR).
3. **SKILL.md = 최소 진입점** — `skills/auto/SKILL.md` ≤120줄. 모든 상세는 `references/`로 lazy load. *거대 문서 통째 로드 금지*.
4. **Intent → Chapter 라우팅** — 평문 → `references/index.yml` lookup → chapter 1개만 로드.
5. **스킬/커맨드/워크플로우 = 방대 (슈퍼앱)** — 진입점 작고 도구 풍부.

## 진입 경로

```
사용자 평문 (또는 /auto, /iteration)
      ↓
SKILL.md (≤120줄) Step 0: Index Lookup
      ↓
Phase -2 Triage (모호 시만)
      ↓
Chapter 1개 로드 (chapter-{CAT}.md)
      ↓
Phase 진입 시 해당 phase reference 1개만 lazy load
      ↓
필요 시 plan-design-gate.md / ml-assist.md 조건부 로드
      ↓
Phase 3 검증 — Multi-perspective Parallel (architect + security + test + verifier)
      ↓
pdca-iterator (Match Rate <90% 시 iteration-runner 자동)
      ↓
Phase 4 Close
```

## Components (실측 2026-05-11)

| 컴포넌트 | 개수 | 핵심 출처 |
|---------|:----:|----------|
| skills | 22 | chapter 진입 + 자체 완결 (SKILL_TEMPLATE/checklist 제외) |
| agents | 34 | iteration V10.0 (13) + verification (4) + creative (2) + meta (5, 신규 harness-watcher/critic/applier 포함) + core/domain (10) |
| hooks | 27 | C:\claude 압도적 (PreToolUse Agent matcher는 v28.1에서 비활성 — 옛 패턴 강제 해소) |
| rules | 8 | rule 16 (auto-trigger) + rule 17 (Circuit Breaker) + 6 |
| references | 38 | chapter 6 + phase 5 + 핵심 + v28.1 신규 3 (plan-design-gate, ml-assist, external-harness-registry) |
| commands | 20 | C:\claude 그대로 |
| lib | 13 | advisor, ai_auth, confluence, workflow_critic 고유 |
| **합계** | **162** | v28.0 (156 추정) 대비 실측 +6 (v28.1 신규 reference 3 + agents 3) |

## 범용성 — Adaptive Configuration

| 환경 | 감지 | 활성 profile |
|------|------|------------|
| Windows + Python | platform-detect.yml | python-cli |
| Windows + Next.js | platform-detect.yml | nextjs-app |
| Linux + Rust | platform-detect.yml | rust-system |
| Monorepo | turbo.json 감지 | monorepo |
| Generic | fallback | generic |

## Safety Rules (HARD BLOCK)

- API key 절대 금지 (Browser OAuth only, daily-audit CI 예외)
- Process kill 절대 금지 (kill -9 등)
- 절대 경로만 (Windows: `C:\...`, POSIX: `/...`)
- 충돌 시 사용자에게 질문 (임의 판단 금지)

## Circuit Breaker (Rule 17)

| 카운터 | Hard Limit |
|--------|:---------:|
| architect_reject | 3 |
| pdca_iterator | 5 |
| continuation_loop | 3 |
| auto_recursion | 1 |

상태 파일: `state/circuit-breaker.json` (세션 간 영속, 자동 리셋 금지)
