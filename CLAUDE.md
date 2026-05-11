# aiden-auto v28.0 — 통합 슈퍼 플러그인

> **Core Philosophy**: 사용자 진입점 최소화 + 자율 이터레이션 최대화. 가장 완벽한 산출물을 만든다.

## 진입 경로

```
사용자 메시지
      ↓
Rule 16 자동 트리거 판단 (작업 요청이면 /auto)
      ↓
Step 0: Index Lookup (references/index.yml)
      ↓
Phase -2 Triage (모호 시만)
      ↓
Phase -1 Context Detect (OS/profile/eco 감지)
      ↓
Chapter 1개 로드 (chapter-{CAT}.md)
      ↓
Phase 0~4 (chapter 지정 경로)
      ↓
Phase 3 검증 — Multi-perspective Parallel (architect + security + test + verifier)
      ↓
pdca-iterator (Match Rate <90% 시 iteration-runner 자동)
      ↓
Phase 4 Close
```

## Components

| 컴포넌트 | 개수 | 핵심 출처 |
|---------|:----:|----------|
| skills | 25 | aiden-auto chapter 분할 + C:\claude 자체 완결 |
| agents | 34 | aiden-auto iteration V10.0 + C:\claude creative |
| hooks | 25 | C:\claude 압도적 |
| rules | 8 | rule 16 (C:\claude active) + rule 17 (aiden-auto) |
| references | 25 | 양쪽 union (chapter + skill-causality-graph 핵심) |
| commands | 20 | C:\claude 그대로 |
| lib | 15 | C:\claude 압도적 (advisor, ai_auth, confluence, workflow_critic 고유) |

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
