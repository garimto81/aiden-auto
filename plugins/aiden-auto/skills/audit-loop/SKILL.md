---
name: audit-loop
description: skill/command/workflow/agent 4 영역 전수 조사를 자율 반복으로 실행하는 메타 skill. critic mode 로 audit 결과를 5 lens (false negative / false positive / 데이터 무결성 / 자율 안전성 / 재실행 안정성) 검증 후 비파괴 결함만 자율 수정. cycle 종료 조건은 issue=0 또는 cycle 변화 없음 또는 circuit breaker 3 회. "audit loop", "자율 iteration", "전수 조사 반복", "완벽한 검증", "skill/command/workflow 점검", "matrix 정밀 감사" 등이 언급될 때 즉시 사용. 매트릭스 무결성과 model 라우팅 신뢰도가 의심되는 모든 상황에 적극 활용.
---

# Audit Loop — 자율 반복 무결성 검증

## When to use

이 skill 은 다음 상황에 즉시 사용한다:

- 사용자가 "skill/command/workflow 전수 조사", "자율 iteration", "완벽한 설계" 등 요구
- 매트릭스 변경 후 무결성 검증
- 새 plugin 설치 / agent 추가 / hook 등록 후 일괄 검증
- Model routing 이상 (V3 / V4 보고서 같은 측정 갭) 후 종합 점검

핵심 가치: **자율 영역과 사용자 결정 영역을 분리** 하여, 비파괴 자율 수정은 최대화하고 정본 결정은 사용자에게 보존.

## Architecture

```
   ┌─────────────────────────────────────────────────┐
   │ Cycle N (max 3)                                 │
   │                                                 │
   │  1. 5 audit 병렬 실행 (A-26 신규)               │
   │     (agent / skill / command / workflow         │
   │      + plugin-ssot-audit)                        │
   │                                                 │
   │  2. critic (sonnet) self-verify                 │
   │     5 lens: FN / FP / DI / AS / RS              │
   │                                                 │
   │  3. 결함 분류                                    │
   │     A: 자율 수정 가능 (비파괴)                   │
   │     B: 사용자 결정 필요 (정본 모름)              │
   │     C: 외부 결함 (plugin, 격리)                  │
   │                                                 │
   │  4. A 카테고리 자율 수정 적용                    │
   │                                                 │
   │  5. 종료 조건 검증 (A-30 정정 Cycle 24):         │
   │     - 4 audit issue=0 ? → RESOLVED              │
   │     - 변화 없음 ? → 종료 (수렴)                  │
   │     - cycle ≥ 3 ? → 종료 (circuit breaker)      │
   │     - else → Cycle N+1                          │
   │     (plugin-ssot drift = detach 의도, 보고만)   │
   └─────────────────────────────────────────────────┘
```

## Step-by-step procedure

### Step 1 — 5 audit 병렬 실행 (A-26 신규)

```bash
python C:/claude/.claude/skills/agent-matrix-audit/scripts/audit_matrix.py
python C:/claude/.claude/skills/skill-matrix-audit/scripts/audit_skills.py
python C:/claude/.claude/skills/command-matrix-audit/scripts/audit_commands.py
python C:/claude/.claude/skills/workflow-matrix-audit/scripts/audit_workflow.py
python C:/claude/.claude/skills/plugin-ssot-audit/scripts/audit_and_sync.py
```

결과는 `C:/claude/.claude/state/*-matrix-mapping.json` 4 개 +
`C:/claude/.claude/state/plugin-ssot-mapping.json` 1 개 = 총 5 개.

> **A-26 (Cycle 23 critic HIGH-2)**: plugin-ssot-audit 호출 명시.
> plugin-ssot-audit SKILL.md 가 "audit-loop cycle 1 에서 자동 호출" 이라고 선언했으나
> 실제 audit-loop Step 1 에는 호출이 없었음 → 5번째 audit 으로 추가.
>
> **A-30 (Cycle 24 critic Weakness 1+2 정정)**: A-26 의 "is_perfect_mirror" 종료 조건 제거.
> Path α detach 후 project source != marketplaces cache (의도된 비대칭) 이므로
> is_perfect_mirror == False 가 정상 상태. 종료 조건에서 제외, plugin-ssot drift 는 보고만.

> **TODO (A-25, Cycle 20 critic LOW)**: workflow audit 의 cross-reference 무결성 검증 미해소.
> SKILL.md → agent 호출 / command → skill 호출 chain 이 실제 존재하는지 검증 필요.
> 별도 audit script (`audit_cross_reference.py`) 또는 workflow audit 확장으로 처리.
> Cycle 7 부터 잔존 — critic ROI 분석 결과 LOW priority (현재 결함 영향 없음).

### Step 2 — critic self-verify (sonnet)

`Agent(subagent_type="critic", model="sonnet")` 로 호출. 5 lens 검증:

| Lens | 검증 항목 |
|------|----------|
| **FN** (False Negative) | audit script 가 놓치는 결함 케이스 |
| **FP** (False Positive) | 정상인데 issue 로 잘못 분류된 케이스 |
| **DI** (Data Integrity) | JSON 스키마 일관성, 경로 정규화 |
| **AS** (Autonomy Safety) | 자율 수정 시 위험한 카테고리 |
| **RS** (Re-run Stability) | 재실행 시 같은 결과 보장 |

### Step 3 — 결함 분류 매트릭스

| 결함 유형 | 분류 | 자율 처리 |
|----------|------|:---------:|
| PHANTOM (호출 흔적 없음) | A | ✓ |
| PHANTOM (호출 흔적 있음, broken caller) | A | ✓ (caller 수정) |
| audit script 자체 결함 (FN/FP) | A | ✓ (script patch) |
| DUPLICATE (project + global) | B | ✗ |
| DUPLICATE (project + plugin) | B | ✗ |
| BUILT_IN_SHADOWED | B | ✗ |
| NAME_MISMATCH (외부 plugin) | C | ✗ (분류만) |
| 외부 plugin STUB | C | ✗ (분류만) |

### Step 4 — 자율 수정 적용

A 카테고리만:
- enforcer.py 매트릭스에서 PHANTOM 라인 제거 (Edit)
- broken caller 파일 수정 (Edit, 우리 권한 파일만)
- audit script patch (Edit)

각 수정 후 즉시 해당 audit 재실행하여 정합 확인.

### Step 5 — 종료 조건 검증 (2026-05-26 R2 — plateau auto-detect 강화)

```python
# A-26 (Cycle 23): plugin-ssot-audit 통합. is_perfect_mirror 종료 조건은
# A-30 (Cycle 24 critic Weakness 1+2) 에서 재정의됨.
#
# A-30 정정: Path α detach 후 project source != marketplaces cache (의도된 비대칭).
# is_perfect_mirror 는 항상 False 가 정상 → 종료 조건에서 제외.
# 대신 4 audit (agent/skill/command/workflow) 의 real issues == 0 이면 RESOLVED.
# plugin-ssot drift 는 detach 의도 정보로 보고만 (종료 조건 영향 0).
#
# R2 (2026-05-26): plateau 자동 감지 강화. 직전 12 self-critic cycle 에서
# 결함 추세 14→12→8→6→3→3→1 패턴 발견 — 3 cycle 동일 결함 수 = plateau 신호.
# 단일 cycle 비교 (이전 vs 현재) 만으로는 plateau 놓침.
#
# 3-cycle rolling window 비교로 plateau 정량 검출.
if issues_current == 0:
    return "RESOLVED"  # 4 audit 결함 0 + plugin-ssot drift 는 detach 의도 (정상)

if cycle >= 3 and issues_history[-3:] == [issues_current] * 3:
    return "PLATEAU"  # 3 cycle 동일 → 자율 영역 소진 (R2 신규)

if issues_current == issues_previous:
    return "CONVERGED"  # 2 cycle 동일 (PLATEAU 보다 약한 신호, 보존)

if cycle >= 3:
    return "CIRCUIT_BREAKER"  # max recursion (A-33: audit-loop 로컬 카운터)

# paradox 영역 (6th lens R1) 만 잔여 → 자율 정정 불가
if all(d.get("paradox_classification") != "none" for d in remaining_defects):
    return "PARADOX_ONLY"  # 의도적 잔여, user escalate

return "CONTINUE"
```

### Plateau vs Converged vs Circuit Breaker 구분

| 신호 | 정의 | 의미 |
|------|------|------|
| `RESOLVED` | issues=0 | 자율 영역 완전 처리 |
| `PLATEAU` | 3 cycle 동일 issues 수 | 자율 영역 소진 (R2 신규) |
| `CONVERGED` | 2 cycle 동일 | 일시적 정체 (다음 cycle 진행) |
| `PARADOX_ONLY` | 잔여 결함 모두 paradox | 의도적 잔여 (6th lens R1) |
| `CIRCUIT_BREAKER` | cycle ≥ 3 + 변화 있음 | 강제 종료 |

### Cycle 종료 4 case 매핑 (D1 사용자 결정 — rule 21 정합)

본 audit-loop 의 종료 신호는 rule 21 `cycle-termination.md` 의 4 case 와 정합:

| 작업 유형 | rule 21 case | audit-loop critic 적용 대상 | 종료 신호 |
|----------|:------------:|---------------------------|----------|
| 설계 작업 (PRD / design) | Case 1 | design 자체 결함 | `RESOLVED` (design 결함 0) 또는 `PARADOX_ONLY` |
| 구현 작업 (executor) | Case 2 | 구현 진행도 vs design 갭 | `RESOLVED` (잔여 개발 0) |
| QA 검증 (test) | Case 3 | QA test 의 design 정합 | `RESOLVED` (design 100% 코드 구현 확인) |
| 코드 리뷰 (PR) | Case 4 | code 의 design 정합 | `RESOLVED` (code 완벽 구현 확인) |

→ design SSOT 가 모든 case 의 검증 기준. design 자체에 결함 있으면 Case 1 로 회귀 후 다른 case 재진입.

### Step 6 — 최종 보고

`Agent(subagent_type="writer", model="sonnet")` 로 통합 보고서 작성. 포함:
- cycle 별 issue 변화 추이
- 자율 수정 내역
- 사용자 결정 영역 (B 카테고리)
- 외부 격리 목록 (C 카테고리)
- model 사용 매트릭스 (각 단계 명시)

## Output format

```
Cycle 1: 226 → 211 issues (자율 16 처리)
Cycle 2: 211 → 211 issues (CONVERGED — 자율 영역 소진)

자율 처리 완료: 16
사용자 결정 보존: 18 DUPLICATE + 1 SHADOWED
외부 격리: 9 NAME_MISMATCH + 33 DUPLICATE (의도된 3-layer)
```

## Limitations

- B 카테고리 (DUPLICATE) 는 정본 판단 불가 → 사용자 결정 영역
- C 카테고리 (외부 plugin) 는 우리 권한 밖 → 격리만
- circuit breaker 3 cycle 이후엔 강제 종료 (무한 루프 방지)
- audit script 결함 수정 시 다음 cycle 부터 정합 보장 (이전 cycle 의 false positive/negative 는 분류된 그대로)
- **A-33 (Cycle 25 critic LOW-1)**: audit-loop 의 `cycle >= 3 → CIRCUIT_BREAKER` 카운터는 Lead 의 로컬 변수이며,
  `~/.claude/state/circuit-breaker.json` (rule 17 의 architect_reject / pdca_iterator / continuation_loop / auto_recursion 카운터) 와 **별도 mechanism**.
  audit-loop cycle 카운터는 본 skill 내부에서만 추적, plugin hook 의 circuit_breaker.json 과 무관.
