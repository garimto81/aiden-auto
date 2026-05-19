# /goal 운영 가이드 — aiden-auto v28.3 Loop Driver

> **Phase 6C**: aiden-auto의 자가반복 루프를 구동하는 `/goal` 명령어의 사용, 스키마, 자동 평가 흐름을 정의.

## Overview

**`/goal`** 은 Claude Code 빌트인 명령어로, 사용자가 원하는 최종 상태를 정의하면 
CC가 자동으로 반복 시도하여 목표 달성까지 루프.

**aiden-auto에서의 역할**: `/auto` PDCA 사이클의 **Loop Driver**

```
사용자 요청 (구현/분석/설계 등)
      ↓
/auto Phase 1-3 (plan/implement/verify)
      ↓
Match Rate < 90% 또는 미완성 신호 감지
      ↓
harness-critic: "목표 달성 조건 명확한가?" 판정
      ↓
harness-applier: /goal 자동 실행
      └─> /goal --condition "{조건}" --max-iterations 5
      ↓
CC 자동 루프 (iteration-runner 통합)
      ↓
목표 달성 또는 max-iterations 도달
      ↓
Loop 완료, Phase 4 Close
```

---

## 1. /goal 기본 문법

### Claude Code 공식 문법 (CC v2.1.138+)

```bash
/goal [goal description]

Options:
  --condition "{boolean expression}"   # 성공 조건 명시
  --max-iterations N                   # 반복 제한 (기본 10)
  --on-failure {HALT | RETRY | SKIP}   # 실패 시 동작
```

### 예시

```bash
# 기본: 텍스트 기술
/goal "실패 테스트 통과하도록 코드 수정"

# 명시적 조건: 테스트 통과 + 카버리지 80%
/goal "실패 테스트 통과" --condition "test_pass == true AND coverage >= 80"

# 최대 5회 반복 후 포기
/goal "리팩토링 완료" --max-iterations 5 --on-failure HALT
```

---

## 2. aiden-auto Stop Hook 통합

### Stop Hook가 /goal 조건 평가

harness-applier가 `/goal` 실행 시, 다음 조건을 자동으로 평가하는 **Stop Hook** 장착:

```yaml
# plugins/aiden-auto/hooks/stop_goal_evaluator.py
hook: PostToolUse
trigger: "Bash command contains '/goal'"
action: |
  1. /goal --condition 파싱
  2. 조건식 변수 수집 (test_pass, coverage, drift, etc.)
  3. 변수 계산 (pytest 실행 후 결과 읽기 등)
  4. 조건식 평가 → true/false
  5. events.jsonl 에 "GOAL_CONDITION: true|false" 이벤트 기록
  6. false → harness-critic에 "목표 미달성" 신호 → 수동 개입 가이드
```

### 사용 가능한 변수

aiden-auto에서 자동 수집:

| 변수 | 계산 방법 | 예시 |
|------|---------|------|
| `test_pass` | `pytest tests/ -q` 성공 여부 | true / false |
| `coverage` | `pytest --cov` 출력 파싱 | 85.2 |
| `lint_clean` | `ruff check src/` 결과 | true / false |
| `files_changed` | `git diff --name-only` count | 5 |
| `drift` | 우리 framework vs external harness | 0.3 (30%) |
| `reimplementability` | Phase 3 QA 점수 | 92 |
| `circuit_breaker_trips` | state/circuit-breaker.json | 0 |

### 예시: aiden-auto 표준 /goal 정의

```bash
# 패턴 1: 테스트만 필수
/goal "기능 구현" --condition "test_pass == true"

# 패턴 2: 테스트 + 품질
/goal "기능 구현" --condition "test_pass == true AND lint_clean == true"

# 패턴 3: 테스트 + 커버리지 + drift 제어
/goal "기능 구현" \
  --condition "test_pass == true AND coverage >= 80 AND drift < 0.2" \
  --max-iterations 5

# 패턴 4: reimplementability (Phase 3 품질)
/goal "기능 구현 및 검증" \
  --condition "reimplementability >= 90 AND circuit_breaker_trips == 0"
```

---

## 3. active-goal.json 스키마

### 파일 위치
```
C:\claude\plugins\aiden-auto\state\active-goal.json
```

### 스키마

```json
{
  "version": "1.0.0",
  "goal_id": "goal-20260514-001",
  "created_at": "2026-05-14T10:00:00Z",
  "user_request": "비밀번호 표시 토글 기능 추가",
  "goal_description": "React 컴포넌트에 비밀번호 보이기/숨기기 토글 추가",
  "goal_condition": "test_pass == true AND coverage >= 80",
  "max_iterations": 5,
  "current_iteration": 1,
  "on_failure": "HALT",
  "status": "IN_PROGRESS" | "COMPLETED" | "FAILED" | "HALTED",
  "variables": {
    "test_pass": false,
    "coverage": 72.5,
    "lint_clean": true,
    "files_changed": 3,
    "drift": 0.05,
    "reimplementability": 85
  },
  "iteration_history": [
    {
      "iteration": 1,
      "timestamp": "2026-05-14T10:00:15Z",
      "action": "editor: src/PasswordToggle.tsx 작성",
      "condition_eval": false,
      "reason": "coverage 72.5 < 80"
    }
  ],
  "completed_at": null,
  "final_result": null,
  "manual_override": {
    "reason": null,
    "approved_by": null,
    "timestamp": null
  }
}
```

### 키 설명

| 키 | 의미 | 관리자 |
|----|------|--------|
| `goal_id` | 글로벌 unique ID (date-based) | harness-applier 생성 |
| `goal_condition` | /goal --condition 인수 | 사용자 또는 harness-critic |
| `current_iteration` | 현재 루프 번호 | Stop Hook 자동 갱신 |
| `variables` | 모든 조건식 변수 현재값 | Stop Hook 자동 갱신 |
| `iteration_history` | 각 반복 결과 기록 | Stop Hook append |
| `status` | COMPLETED / FAILED / HALTED | Stop Hook |
| `manual_override` | 사용자 강제 승인 (목표 미달성도 완료 처리) | 사용자 |

---

## 4. Stop Hook 자동 평가 흐름

### Loop Iteration (반복 한 주기)

```
Iteration N 시작
      ↓
executor 또는 자동 도구 실행
      ↓
Stop Hook (PostToolUse)
      ├─ 변수 재계산 (test_pass, coverage, etc.)
      ├─ active-goal.json 갱신: variables + iteration_history
      ├─ 조건식 평가: `test_pass AND coverage >= 80`?
      │
      ├─ ✅ true 면:
      │  └─> status = "COMPLETED"
      │      Loop 종료 → Phase 4 Close
      │
      └─ ❌ false 면:
         ├─ current_iteration >= max_iterations?
         │  ├─ YES → on_failure 처리 (HALT / RETRY / SKIP)
         │  │        → "최대 반복 도달, 수동 검토 필요" 보고
         │  └─ NO → Iteration N+1 재시도 신호
         │
         └─> events.jsonl 기록:
             {
               "type": "GOAL_CHECK",
               "iteration": N,
               "condition": "test_pass AND coverage >= 80",
               "eval_result": false,
               "variables": {...},
               "next_action": "RETRY | HALT"
             }
```

### 실패 처리 정책 (on_failure)

| 값 | 동작 | 사용 케이스 |
|----|------|-----------|
| **HALT** | max_iterations 도달 시 정지, 사용자 판단 요청 | 복잡한 기능, 판단 필요 |
| **RETRY** | 계속 반복 시도 (max_iterations 무시) | 단순 반복 작업 |
| **SKIP** | 목표 미달성도 완료 처리, 다음 Phase 진행 | 부분 성공 허용 케이스 |

---

## 5. 운영 패턴

### 패턴 1: 테스트 기반 자동 루프 (가장 흔함)

**상황**: 기능 구현 후 테스트 실패 몇 건

**흐름**:
```
사용자: "비밀번호 토글 기능 추가"
         ↓
/auto Phase 1-3 (실패 테스트만 작성)
         ↓
executor: src/PasswordToggle.tsx 기본 구현
         ↓
pytest 실행 → 2건 실패 (coverage 72%)
         ↓
harness-critic: "테스트 + coverage 80% 필수" 판정
         ↓
harness-applier: /goal "기능 구현" \
                  --condition "test_pass == true AND coverage >= 80" \
                  --max-iterations 3
         ↓
Loop 1: executor가 실패 원인 분석 후 수정
        pytest → 1건 실패 (coverage 75%) → 조건 false
         ↓
Loop 2: 추가 로직 보강
        pytest → 전부 통과 (coverage 82%) → 조건 true
         ↓
/goal COMPLETED
Phase 4 Close
```

### 패턴 2: 도구 검증 루프

**상황**: 새 hook/utility 추가 후 모든 기존 테스트가 여전히 통과해야 함

**/goal 정의**:
```bash
/goal "Hook 추가 및 회귀 검증" \
  --condition "test_pass == true AND drift == 0" \
  --max-iterations 2 \
  --on-failure HALT
```

### 패턴 3: 수동 Override (예외)

**상황**: 목표 조건이 너무 엄격해서 비합리적. 예: coverage 95% 필수인데 현재 88% 달성 가능한 한계

**처리**:
```json
{
  "status": "IN_PROGRESS",
  "current_iteration": 5,
  "manual_override": {
    "reason": "coverage 88%는 충분함. 95% 목표는 과도함",
    "approved_by": "사용자",
    "timestamp": "2026-05-14T10:30:00Z"
  }
  // → status를 "COMPLETED" 로 변경
}
```

Stop Hook이 override를 감지하면 COMPLETED로 처리.

---

## 6. 외부 Harness와의 통합

### CC 빌트인 /goal --builtin

Claude Code v2.1.139+ 의 신규 옵션:

```bash
/goal "기능 구현" --builtin
```

**의미**: CC 자체 내부 advisor를 사용하여 자동 평가.
aiden-auto의 custom Stop Hook를 무시하고 CC 공식 정의 사용.

**aiden-auto 정책**: 
- ✅ 기본은 **custom Stop Hook** (우리 5원칙 정합)
- ⚠️ --builtin 옵션은 "참조만" (복사 금지, Rule 1)
- 🔄 harness-watcher가 CC 신규 버전 감지 시 backward compat 평가

### harness-critic의 /goal 평가

critic이 외부 update를 검토할 때, "/goal 관련 변경"이 있으면:

```
Q1 (진입점 최소화):
  "/goal --builtin 지원?" → +3점 (자동화)
  "새 /goal option 필수?" → -2점 (복잡성)

Q2 (자율 이터레이션):
  "자동 루프 가능?" → +4점

Q4 (참조 가능성):
  "우리가 /goal 로직을 복사했는가?" → -5점 (복사 금지)
  "우리가 CC /goal을 호출만 하는가?" → +5점 (참조)
```

---

## 7. 문제 해결 (Troubleshooting)

### Issue 1: /goal loop가 무한 반복

**원인**: max_iterations 설정 누락, on_failure = RETRY

**해결**:
```json
// active-goal.json에서
"max_iterations": 5,  // 기본값 10에서 5로 낮춤
"on_failure": "HALT"  // RETRY 대신 HALT
```

### Issue 2: 조건식이 항상 false

**원인**: 변수 이름 오타, 또는 계산 로직 오류

**디버깅**:
```bash
# active-goal.json의 variables 섹션 확인
"variables": {
  "test_pass": false,
  "coverage": 72.5,
  ...
}

# 실제 값을 Stop Hook에서 재계산해서 일치하는지 확인
pytest tests/ -q  # 수동 실행으로 검증
```

### Issue 3: Circuit Breaker가 /goal 반복을 차단

**원인**: 동일 실패 3회 누적

**해결**: 
```json
{
  "manual_override": {
    "reason": "circuit breaker false positive",
    "approved_by": "사용자",
    "timestamp": "2026-05-14T10:30:00Z"
  }
}
```

---

## 8. 모니터링 및 로깅

### events.jsonl 기록

매 /goal 루프가 events.jsonl에 기록:

```jsonl
{"type":"GOAL_START","id":"goal-20260514-001","max_iterations":5}
{"type":"GOAL_CHECK","iteration":1,"eval_result":false,"variables":{...}}
{"type":"GOAL_CHECK","iteration":2,"eval_result":true}
{"type":"GOAL_COMPLETED","id":"goal-20260514-001","iterations":2}
```

### statusline 출력

aiden-auto statusline이 /goal 상태 표시:

```
[5/14 10:30] [Phase 3 Verify] goal: password-toggle (2/5 iterations, coverage 82%) ✓
```

### telemetry.json 기록

일일 집계:

```json
{
  "date": "2026-05-14",
  "goals": {
    "total_started": 3,
    "completed": 2,
    "failed": 1,
    "avg_iterations": 2.3
  }
}
```

---

## 9. Best Practices

### ✅ 해야 할 것

1. **조건식 명시** — `--condition`을 항상 사용. 모호한 "완료" 판단 금지
2. **max_iterations 설정** — 기본값 10은 너무 많음. 3~5로 제한
3. **변수 모니터링** — `coverage`, `test_pass` 같은 측정 가능한 변수만 사용
4. **실패 원인 분석** — /goal fail 시 iteration_history 기록 읽고 원인 파악

### ❌ 하지 말아야 할 것

1. ❌ `/goal --builtin` 남용 — CC 공식만 믿지 말고, 우리 custom 가이드도 함께 사용
2. ❌ 무한 반복 설정 (max_iterations 무한) — circuit breaker와 충돌
3. ❌ 조건식이 불가능한 상태 — 예: "drift == 0" (항상 약간의 drift 존재)
4. ❌ on_failure = SKIP 남용 — 실패를 무시하는 것은 위험

---

## 10. 결론

**/goal은 aiden-auto의 Loop Driver**

- **진입점**: 최소 (자동 /goal 실행 by applier)
- **자율성**: 최대 (조건 달성까지 자동 반복)
- **안전성**: Circuit Breaker + max_iterations으로 제어

**사용자가 해야 할 일**: `/goal` 명령어 사용 안 함. harness-applier가 자동 호출하도록 두기.
(예외: 수동 테스트 시 임시 사용 가능)

---

**Generated**: 2026-05-14 Phase 6C  
**Framework**: aiden-auto v28.3  
**Stop Hook Integration**: Complete  
**Pattern Support**: 3 standard patterns + manual override
