---
name: critic-protocol-unified
version: v1.0
loaded_from: skill-auto
purpose: 5+ critic agent 의 verdict 매핑 + critic-to-critic chain 차단 (F21 결함 해소)
---

# Critic Protocol Unified (v3 — F21 해소)

## 본 문서의 위치

/auto framework 의 모든 critic 계열 agent 의 verdict 통합 매트릭스 + 집계 layer 의 bridge 정의.

## 등록된 critic agents (6종)

| ID | Agent | 역할 | Verdict 종류 |
|----|-------|------|-------------|
| C1 | `critic` (doc-critic) | 18세 일반인 이해도, 비약 감지 | APPROVE / REJECT / QUESTION |
| C2 | `code-reviewer` | 코드 품질 + 스타일 | APPROVE / CHANGES_REQUESTED |
| C3 | `test-engineer` | 테스트 커버리지 + flaky | APPROVE / NEEDS_REVISION |
| C4 | `compaction-critic` | context 5 IL 검증 | APPROVE / REJECT / QUESTION / SURVIVED / DESTROYED |
| C5 | `security-reviewer` | OWASP Top 10 / secret leak | APPROVE / BLOCK |
| C6 | `reader-experience` | P7 Hook/Thesis/Anchor/Rhythm/Arc (DOC) | APPROVE / REJECT (P7-A~E) |

추가 (advisor-pattern):
- `harness-critic` (외부 framework update) — APPROVE / DEFER / REJECT
- `framework-critic` (~/.claude/ 변경) — APPROVE / DEFER / REJECT
- `cc-auth-advisor` / `atlassian-auth-advisor` / `quota-advisor` (verdict 4종 — 자체 advisor 패턴)

## Verdict Bridge — 5종 ↔ 4종 매핑

### 원본 verdict (compaction-critic 의 5종)

| Verdict | 의미 |
|---------|------|
| APPROVE | 모든 IL 통과, 그대로 진행 |
| REJECT | 위반 발견, 수정 필요 |
| QUESTION | 모호 — 사용자 결정 필요 |
| SURVIVED | 일부 위반 + 사용자가 명시 허용 시 진행 |
| DESTROYED | 치명적 결함, 복구 불가 |

### 일반 critic verdict (4종 — C1, C2, C3, C5)

| Verdict | 의미 |
|---------|------|
| APPROVE | 통과 |
| REJECT | 거부 (재작성 / 수정 필요) |
| CHANGES_REQUESTED | 일부 수정 (C2) |
| BLOCK | 치명 (C5 — 보안) |

### Bridge 매트릭스 (집계 layer 변환 룰)

| 5종 (compaction) | → 4종 (general) | 처리 |
|:--:|:--:|------|
| APPROVE | APPROVE | 그대로 진행 |
| REJECT | REJECT | 재작성 / 수정 (max 2회) |
| QUESTION | REJECT + 사용자 알림 | 사용자 1줄 안내 후 결정 대기 |
| SURVIVED | APPROVE (with warning) | 경고 로깅 + 진행 |
| DESTROYED | BLOCK | 차단 + 사용자 escalate (Circuit Breaker) |

## 집계 layer (Multi-perspective Validation)

### Chapter 별 critic 집계 패턴

| Chapter | Critic 4 agent | 집계 룰 |
|---------|---------------|--------|
| DOC | critic + architect + document-specialist + reader-experience | ALL APPROVE → Phase 4 |
| CODE | architect + security-reviewer + code-reviewer + reader-experience | ALL APPROVE → Phase 3.5 |
| QA | qa-tester + test-engineer + architect + verifier | ALL PASS → Phase 4 |
| ITERATION | iteration-curator + drift-reconciler + critic + verifier | exit_criteria 충족 → Phase 4 |
| RESEARCH | researcher + analyst + critic | majority APPROVE → Phase 4 |
| MEDIA | designer + critic + verifier | ALL APPROVE → Phase 4 |

### Verdict 충돌 처리

1. **모든 verdict 4종으로 변환** (bridge 적용)
2. ALL APPROVE 시 통과
3. ANY REJECT 시:
   - 해당 agent 의 finding 만 fix → 그 agent 만 재호출
   - 2회 REJECT 누적 시 → Circuit Breaker `pdca_iterator` +1 → 5회 누적 시 사용자 escalate
4. ANY BLOCK 시: 즉시 차단 + 사용자 보고 (보안 / DESTROYED)
5. QUESTION 만 발생 시: 모호성 사용자에게 1줄 보고

## Critic-to-Critic Chain 금지 (HARD ENFORCE)

> **critic A 가 critic B 의 산출물을 검토하는 chain 금지**.

### 이유

- 순환 의존성 발생 가능
- verdict 통합 logic 복잡화
- 사용자 진입점 증가

### 허용 패턴

- ✅ critic A + critic B 병렬 호출 → 집계 layer 가 verdict 통합
- ✅ executor → critic A 검토 → 수정 → critic A 재호출
- ❌ critic A → critic B 가 critic A 산출물 검토
- ❌ critic A → critic B → critic A 순환

### 강제 메커니즘

- `forbidden_pattern_check.py` 의 패턴 후보 (별도 cycle):
  - critic 호출 후 다른 critic 호출 시 직접 의존 (A의 output → B의 prompt)

## Verdict 기록 (state file)

각 critic 호출 결과 자동 기록:

```
~/.claude/state/auto/critic-decisions-{slug}-{date}.json
```

```json
{
  "session_id": "...",
  "decisions": [
    {
      "critic": "doc-critic",
      "verdict": "APPROVE",
      "bridge_verdict": "APPROVE",
      "rationale": "...",
      "at": "2026-05-23T..."
    },
    {
      "critic": "compaction-critic",
      "verdict": "SURVIVED",
      "bridge_verdict": "APPROVE",
      "rationale": "with warning",
      "at": "..."
    }
  ]
}
```

## 통합 점수 정합 (v3 메타-결함 정합)

본 protocol 의 verdict 통합 결과를 `framework_content_audit.py` 의 M1 (구조 완성도) 계산에 자동 반영:

- ALL APPROVE → +1 M1 score
- ANY REJECT → -1 M1 score
- BLOCK 발생 → M1 = 0 강제 (치명 결함)

## Iron Laws 정합

| Iron Law | 본 protocol 정합 |
|----------|-----------------|
| IL-1 TDD | qa-tester / test-engineer REJECT 시 자동 차단 |
| IL-2 Debugging | D0-D4 + critic verdict REJECT 시 root cause 요구 |
| IL-3 Verification | verifier APPROVE 없이 Phase 4 진입 불가 |
| IL-4 Architect Approval | architect REJECT 시 executor 재호출 불가 (architect_reject counter +1) |
| IL-5 Bypass 금지 | critic verdict 우회 시 forbidden_pattern_check 감지 |

## 변경 이력

| 날짜 | 변경 |
|------|------|
| 2026-05-23 | v1.0 신규 — F21 결함 해소 (verdict bridge + critic-to-critic chain 금지) |
