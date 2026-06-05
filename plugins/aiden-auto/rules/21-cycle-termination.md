# 자율 Cycle 종료 정의 — Design SSOT critic 게이트 (D1 사용자 결정 반영)

> **사용자 결정 2026-05-26 (D1 reply)**: framework 의 "until no more cycles" 종료 조건 공식 정의.

---

## 핵심 정의

자율 cycle 의 **"no more cycle"** 도달은 다음 4 가지 case 중 작업 유형에 해당하는 조건 충족 시 성립:

| Case | 작업 유형 | critic mode 적용 대상 | 종료 조건 |
|:----:|----------|---------------------|----------|
| **1** | 설계 작업 | 전체 design | 모든 결함/부족함 critic 식별 → design 정정 완료 |
| **2** | 구현 작업 | 구현 상태 (vs design) | critic 가 "더 이상 잔여 개발 없음" 확인 |
| **3** | QA 검증 | design (vs 구현 코드) | critic 가 design 의 모든 측면이 코드로 완벽 구현 확인 |
| **4** | 코드 리뷰 | design (vs 코드) | critic 가 design 의 모든 측면이 완벽 구현 확인 |

> **OR 의미**: 4 case 중 **현재 작업 유형에 해당하는 단일 case 충족** 시 종료. 모든 case 누적 통과는 PDCA cycle 전체 완료 (Plan + Do + Check + Act 모두 마무리).

---

## PDCA 정합 다이어그램

```
   ┌────────────────────────────────────────────────────┐
   │  PDCA cycle 의 4 phase ↔ 본 정의의 4 case            │
   ├────────────────────────────────────────────────────┤
   │                                                      │
   │  Plan (설계 phase) ─────► Case 1                    │
   │     "design critic"                                  │
   │     결함 0 도달 시 → Do 진입                          │
   │                                                      │
   │  Do (구현 phase) ───────► Case 2                    │
   │     "implementation status critic"                   │
   │     잔여 개발 0 도달 시 → Check 진입                  │
   │                                                      │
   │  Check (QA phase) ──────► Case 3                    │
   │     "QA verification critic"                         │
   │     design 100% 코드 구현 확인 시 → Act 진입         │
   │                                                      │
   │  Act (코드 리뷰 phase) ──► Case 4                    │
   │     "code review critic"                             │
   │     design 완벽 구현 확인 시 → cycle 완료            │
   └────────────────────────────────────────────────────┘
```

---

## 핵심 원칙

### 1. Design 이 SSOT

모든 critic mode 의 검증 기준은 **design 문서**. PRD / design.md / spec.md 등 design 자산이 정본.

```
   design (정본)
      │
      ├─► Case 1: design 자체 결함 검증
      ├─► Case 2: 구현 진행도 vs design 갭 검증
      ├─► Case 3: QA test 가 design 의 모든 측면 cover 하는지
      └─► Case 4: code 가 design 의 모든 측면 구현했는지
```

### 2. Critic Mode 는 모든 phase 의 게이트

```
   각 phase 진입 전:                각 phase 종료 시:
   ─────────────────              ─────────────────
   (no gate)                       critic mode 통과
                                   → 다음 phase 진입
```

### 3. 4 case 의 OR 관계

| 작업 유형 | 적용 case | 다른 case |
|----------|:---------:|:---------:|
| design 작성 / 수정 | Case 1 | 미적용 |
| 코드 구현 | Case 2 | 미적용 |
| QA 검증 | Case 3 | 미적용 |
| 코드 리뷰 / PR | Case 4 | 미적용 |
| full PDCA cycle | 1 + 2 + 3 + 4 모두 | — |

### 4. Paradox 영역 별도 처리 (G7, R1 정합)

design 자체에 paradox / self-referential 결함이 있는 경우 (예: rule 이 자기 자신을 정정하는 무한 루프) → **framework-critic 의 6th lens (self_referential_check) 적용** → "intentional residue" 분류 → 결함 카운트 제외.

### 5. Confirmed 비파괴 findings 는 종료 전 적용 (Continuation forcing-function — 2026-06-04)

자율 cycle 이 산출한 **confirmed (critic·adversarial 검증 통과) 비파괴 개선** 은 *같은 cycle 내* 적용해야 종료 가능:

| tier | 종료 전 의무 |
|:----:|------------|
| **T1** (≤3파일·비파괴 additive·행위 무변경) | **즉시 적용** (정본 ~/.claude 편집 → SessionEnd 자동 배포). backlog 불가 |
| **T2** (범위 한정 의미 변경) | **즉시 적용 또는 Draft PR**. backlog 불가 |
| **T3** (아키텍처/정책/모호/설계 필요) | backlog 허용 — 단 **premise-verified 사유 inline 명시 의무** |

**금지 패턴 (agentic laziness)**: confirmed T1/T2 를 "보고 후 사용자 지시 대기" 또는 backlog 로 미루는 것. = Iron Law 3 (Continuation) 위배 + Core Philosophy (자율 = 의도 정합 위한 수단) 위배.

> **근거 (premise 검증, 2026-06-04)**: blog 증분 cycle 에서 confirmed LOW 개선(blog 증분 #3 — PRD Surfaced Assumptions 섹션)을 적용 안 하고 backlog 후 사용자 지시 대기 → 사용자가 결함 지적. 블로그 "A harness for every task" 가 명명한 **agentic laziness** 실패 모드 실측 1건. → 본 clause 신설. 반대 결함(검증 안 된 큰 변경 무분별 적용)도 금지 — T3 는 backlog 정당.
>
> 상세: `~/.claude/projects/C--claude/memory/feedback_apply_verified_findings.md`

**'confirmed' 정의 (verdict-binding + fail-closed, 2026-06-04 design-critic-convergence 결과)**: confirmed = 검증자(verifier)가 *실제로 실행되어* Lead 가 *이번 cycle 안에서 PASS verdict 를 관찰*한 경우만 (harness-critic APPROVE≥95 / blog adversarial-skeptic confirmed:true / design-critic-convergence converged:true). verdict 관찰 없음 = **'unknown'** — §5 강제 apply 대상 아님. unknown 은 bounded retry 후에도 verdict 없으면 backlog 'verifier-unavailable' (genuine T3 와 구분 — 검증 실패가 조용히 apply 면제로 둔갑하는 perverse incentive 차단).

**Trigger edge (orphan 방지)**: T3 (파괴적/아키텍처/정책) 자율 개선은 apply 전 **design-critic-convergence 를 수렴(또는 no-change)까지 먼저 실행** (Lead 가 호출 — 이게 엔진의 정식 caller). converged:true → 자율 구현. circuit_breaker_hit / no-change → **이번 cycle 보류 (forgo — 사용자 결정 2026-06-04: "검토해도 확신이 안 서면 안 고치는 것도 정답"). 억지 변경 금지.** design-critic-convergence 는 audit-loop 의 RESOLVED/PLATEAU 와 **다른 기계** — 자체 {converged, circuit_breaker_hit} 반환만 사용 (문자열 homograph 혼동 금지).

**Forgone-approach 기록 (negative-results)**: forgo (circuit_breaker_hit / no-change) 또는 critic 이 over-engineering 으로 기각한 approach 는 Lead 가 `~/.claude/state/negative-results.json` 에 append 하고, 재제안 전 조회한다 (동일 dead-end 매 cycle 반복 방지). improvement-ledger 가 *성공* 만 기록하는 반쪽을 보완 — 블로그 "Negative Results Matter" (2026-06) 정합. 워크플로우는 filesystem-free 라 negative 를 caller 에게 반환만 하고 버리므로, persist 책임은 caller(Lead) 에 있다.

> **자기검증 사례 (2026-06-04)**: design-critic-convergence 를 자가개선 아키텍처 자신에 4 round 돌린 결과 converged=false (circuit_breaker_hit). 검토자들이 **이전 round 들의 over-engineering 을 스스로 잡아냄** (meta-enforcer/quorum subsystem 등 — 실측 발생 0건). 정직한 결론 = 거창한 재설계 폐기, 검증된 최소 수정만. → 본 forgo 원칙의 실증. 단 진짜 코드 버그 1건 발견: 엔진의 `filter(Boolean)` 가 실패한 lens 를 "문제 없음" 으로 오인 → 거짓 수렴 (수정 완료).

---

## audit-loop SKILL 의 종료 조건 (R2 정합)

본 정의는 R2 (audit-loop plateau auto-detect) 의 종료 조건과 정합:

| audit-loop 신호 | 본 정의 매핑 |
|----------------|-------------|
| `RESOLVED` (issues=0) | Case 1-4 중 해당 작업의 결함 0 도달 |
| `PLATEAU` (3 cycle 동일) | critic 가 "더 이상 자율로 줄일 수 없음" 판정 |
| `PARADOX_ONLY` | 잔여 결함 모두 6th lens paradox 영역 → 종료 |
| `CONVERGED` (2 cycle 동일) | 일시적 정체 → 진행 |
| `CIRCUIT_BREAKER` | max recursion → 강제 종료 + 사용자 escalate |

---

## framework-critic 의 4 phase 책임

framework-critic.md (v2 — D1 반영) 는 본 정의의 4 case 각각에서 호출:

```
   framework-critic invocation matrix:
   
   ┌────────────┬─────────────────────────────────┐
   │ Phase      │ critic 책임                       │
   ├────────────┼─────────────────────────────────┤
   │ Plan       │ design 자체 5+1 lens 평가 (R1)  │
   │ Do         │ 구현 진행도 vs design 갭 측정   │
   │ Check      │ QA test 의 design 정합          │
   │ Act        │ code 의 design 정합 + 6 lens    │
   └────────────┴─────────────────────────────────┘
```

---

## 본 정의의 적용 범위

본 룰은 **모든 framework 자율 iteration** 에 적용:

- `audit-loop` skill 의 cycle 종료 조건
- `pdca-iterator` agent 의 max 5 iteration 종료 조건  
- 글로벌 `framework-critic` agent 의 평가 결과 활용
- 사용자 평문 발화의 자율 처리 (Skill("auto") 진입 시)

---

## Tier Progression — 결함 유형 분류 (D2 사용자 결정)

> **D1 패턴 적용**: critic mode 가 모든 게이트 — tier 승격도 critic 판정. 작업 유형별 OR — 각 결함의 본질에 따라 다른 tier 분류.

본 framework 의 improvement-ledger 에 기록되는 결함의 tier 분류:

| Tier | 정의 | 처리 | critic 판정 |
|:----:|------|------|------------|
| **T1** | 단발성 자율 정정 (개별 결함) | 즉시 자율 정정 | 매 cycle critic 확인 |
| **T2** | **반복 패턴 결함** (같은 root cause 3+ 회 재발) | **meta-level 정정** — root cause 분석 + 메커니즘 자체 변경 | T2 승격 시 framework-critic 가 root cause 평가 |
| **T3** | 사용자 결정 필요 (의미 차원) | backlog 보존 → 사용자 escalate | framework-critic NEEDS_INFO 또는 명시 escalate |

### T1 → T2 승격 조건

```
   T2 자율 승격 트리거:
   
   ① improvement-ledger 에 같은 root cause 의 결함이
      3회 이상 등록 (date 기준 30일 이내)
      
   ② audit-loop 의 PLATEAU 신호 발생 시 잔여 결함 중
      반복 패턴 식별 시
      
   ③ critic agent 가 "동일 메커니즘 결함" 으로 판정 시
```

### T2 처리 책임

| 책임 | 행위 |
|------|------|
| framework-critic | root cause 분석 + 메커니즘 변경 권고 |
| critic 의 6th lens | self-referential 패턴 동반 시 paradox 영역 분류 |
| framework-applier | 메커니즘 변경 patch + PR 생성 (T1 보다 큰 변경) |
| 사용자 | 메커니즘 변경 PR 검토 (의미 차원 영향 가능) |

### Tier 분포 목표 (D1 정신 — 정량 가능 기준)

```
   ┌────────────────────────────────────────────────┐
   │ 건강한 framework 의 tier 분포 (목표):           │
   │   T1 60-70%  ← 일상 자율 정정                   │
   │   T2  5-15%  ← 메커니즘 진화 (현재 1% — 부족)  │
   │   T3 20-30%  ← 사용자 결정 (의미 차원)         │
   │                                                 │
   │ 현재 (2026-05-26):                              │
   │   T1 67% / T2 1% / T3 32%                       │
   │   → T2 progression 룰 적용 후 5-15% 도달 예상   │
   └────────────────────────────────────────────────┘
```

### 적용 시점

- audit-loop / audit skill 의 매 cycle Step 3 (결함 분류) 에 본 룰 적용
- framework-critic agent 의 평가 결과에 `tier_recommendation` 필드 추가 (T1/T2/T3 명시)
- improvement-ledger 의 `_meta.tier_semantics` 가 본 정의 참조

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|------|------|------|
| 2026-05-26 | 본 룰 신규 작성 | D1 사용자 결정 (4 case critic 게이트 정의) 반영 |

---

## 관련

- `~/.claude/skills/audit-loop/SKILL.md` (R2 — 종료 조건 정합)
- `~/.claude/agents/meta/framework-critic.md` (R1 — 6th lens + 4 phase 책임)
- `~/.claude/state/audit/cycle-summary.json` (R4 — cycle 추적)
- `~/.claude/rules/000-CHANGELOG.md` (rules 거버넌스)
- 글로벌 CLAUDE.md "Core Philosophy" (자율 영역 + 사용자 진입점 정합)
