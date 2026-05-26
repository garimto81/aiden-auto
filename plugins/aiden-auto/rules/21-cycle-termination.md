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
