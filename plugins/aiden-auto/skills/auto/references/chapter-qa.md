---
name: chapter-qa
category: QA
pipeline: [triage, chapter-qa]
next-skill: null
handoff: .claude/state/auto/qa-{slug}.md
agent_team: [qa-tester, architect, executor, test-engineer, security-reviewer, verifier]
phase_path: [-2, -1.5, -1, 0, 3, 4, cleanup]
---

# Chapter: QA — 테스트 / E2E / 검증

> **카테고리**: QA
> **트리거 키워드**: 테스트, test, E2E, 검증, QA, regression, 회귀, 품질
> **v27.2 강화**: XML 구조화 + Multi-perspective + Cleanup + verifier 게이트

<Purpose>
사용자의 검증 요구를 받아 단위→통합→E2E→보안→성능 사이클로 자율 처리. 실패 시 D0-D4 디버깅 + Iteration Loop 자동 진입.
</Purpose>

<Use_When>
- 전체 테스트 ("테스트 돌려줘")
- E2E 시나리오 ("E2E 돌려줘")
- 회귀 검사 ("회귀 검사")
- 보안 스캔 ("보안 점검")
- 성능 측정 ("벤치마크")
</Use_When>

<Do_Not_Use_When>
- 코드 작성 후 검증은 chapter-code Phase 3에서 자동 처리됨
- 단순 "이 함수 동작 확인" → !quick magic word
- drift 검증은 chapter-iteration
</Do_Not_Use_When>

<Workflow_Diagram>

```
[Triage: QA]
      │
      ▼
Phase 0 (검증 종류 결정)
   단위 | 통합 | E2E | 회귀 | 보안 | 성능 | 전부
      │
      ▼
Phase 3 (Multi-perspective QA, 병렬)
   ├── qa-tester: pytest/jest/flutter test
   ├── test-engineer: flaky 검사 + 커버리지 분석
   ├── security-reviewer: 보안 스캔 (선택)
   └── architect: 결과 해석
   실패 시 → Systematic Debugging D0-D4
      │
      ▼
Phase 3.5 (Verifier — fresh evidence)
      │
      ▼
Phase 4 (qa_report.md + 보고)
      │
      ▼
Phase Cleanup (NEW v27.2)
```

</Workflow_Diagram>

<Steps>

## Phase 0 — 검증 종류 결정

| 입력 | 종류 | 도구 |
|------|------|------|
| "테스트" | 단위/통합 | pytest, jest, vitest |
| "E2E" | 시나리오 | Playwright |
| "회귀" | regression | 최근 PR 영향 범위 |
| "보안" | OWASP | npm audit, bandit, gitleaks |
| "성능" | benchmark | 프로파일링 + 비교 baseline |

## Phase 3 — Multi-perspective QA (NEW v27.2, 병렬, F15 정합 v3)

```
4 핵심 agent (필수, ALL PASS 집계):
┌─────────────────────────┐
│ qa-tester               │  ← 실제 test 실행
├─────────────────────────┤
│ test-engineer           │  ← flaky 패턴 + coverage gap 분석
├─────────────────────────┤
│ architect               │  ← 결과 해석 + 우선순위 ranking
├─────────────────────────┤
│ verifier (Phase 3.5)    │  ← fresh evidence 재검증
└─────────────────────────┘

2 ad-hoc agent (선택, 검증 종류별 추가):
- security-reviewer (보안 검증 종류 시)
- executor (D3 수정 단계 시)

집계 (Aggregation Logic):
  ALL PASS (4 core) → Phase 4 진입
  ANY FAIL (core)   → D0-D4 systematic debugging
  REJECT 2회 누적   → 사용자 알림 (Circuit Breaker)

실패 시:
  D0 — 재현 가능?
  D1 — 가설 3개 (architect)
  D2 — 가설 검증
  D3 — 수정 (executor)
  D3.5 — Solution Critique (HEAVY)
  D4 — 회귀 검사
```

## Phase 3.5 — Verifier (fresh evidence)

```
verifier 호출:
  - test 결과 재실행 (fresh evidence)
  - "0 failed" 확인
  - skipped count 합리적인지
  - flaky test 격리 확인
  
  VERIFIED → Phase 4
  INSUFFICIENT_EVIDENCE → 재실행
```

## Phase 4 — 보고서 + Cleanup

```
qa_report.md 생성
git commit: docs(qa): {scope} 검증 보고서

Cleanup:
  rm -f .claude/state/auto/qa-{slug}.json
  TeamDelete()
```

</Steps>

<User_Friendly_Explanation>

```
"검증 작업이군요. 이렇게 진행할게요:

  1단계: 어떤 검사가 필요한지 파악
  2단계: 4명 동시 검사
         · 검수원: 실제 테스트 실행
         · 테스트 전략가: flaky 패턴 분석
         · 보안 검사관: 취약점 (보안 종류 시)
         · 건축가: 결과 해석
  3단계: 검증관(verifier)이 결과 진짜인지 확인
  4단계: 보고서 + 정리

  실패 5번 반복 → 사용자 보고 (무한 루프 방지)"
```

</User_Friendly_Explanation>
