---
name: goal-operation
phase: goal-loop
version: v28.8
loaded_from: skill-auto
purpose: /goal 자율 iteration loop 정의 + 3 멈춤 조건 + state 추적 + Phase 4 QA Gate
---

# /goal 자율 Iteration Loop — 운영 정의 (v28.8+)

## 본질 정의

> **/goal = "자율 다음 단계 진행 + 자율 판단 다음 단계 처리 + 자율 처리할 게 없을 때 QA + 스크린샷 엄격 검증 + 모든 단계 통과 시 사용자 보고"**

Phase -1.5 Deep Interview 직후 시동. Phase 4 close 까지 자율 진행.

## 3 멈춤 조건 (Loop Termination Triggers)

### 조건 1: 자율 처리할 게 더 없음 (정상 종료)
- 모든 Phase 통과 + 검증 완료 → Phase 4 QA Gate 진입
- `goal_state.next_action == null` 이고 `goal_state.pending == []`

### 조건 2: 안전절 트립 (Circuit Breaker)
다음 중 **하나라도** 충족 시 강제 멈춤 + 사용자 보고:

| 항목 | 한계 | 측정 |
|------|:----:|------|
| turn counter | 20 | 매 Agent() 호출 후 +1 |
| token counter | 200,000 | Claude API usage 누적 |
| fail counter | 5 | Agent() result error / Phase 검증 REJECT 누적 |

상태 저장: `~/.claude/state/auto/goal-loop-{session_id}.json`

### 조건 3: 진짜 막힘 (외부 정보 필요)
사용자 결정 영역 진입 시:
- 외부 API key / 자격증명 부재
- 사용자 의도 모호성 점수 0.8+ (재명료화 필요)
- 의미 차원 결정 (구현 방식 선택 등)

→ 1줄 보고 후 loop 정지.

## State 추적 메커니즘

### State File 구조

`~/.claude/state/auto/goal-loop-{session_id}.json`:

```json
{
  "session_id": "20260523-050000",
  "started_at": "2026-05-23T05:00:00Z",
  "category": "CODE",
  "chapter": "chapter-code",
  "current_phase": "2",
  "counters": {
    "turn": 7,
    "token_used": 45230,
    "token_limit": 200000,
    "fail": 0,
    "fail_limit": 5,
    "turn_limit": 20
  },
  "phase_history": [
    {"phase": "-2", "completed_at": "2026-05-23T05:00:15Z"},
    {"phase": "-1.5", "completed_at": "2026-05-23T05:01:30Z"},
    {"phase": "-1", "completed_at": "2026-05-23T05:02:00Z"},
    {"phase": "0", "completed_at": "2026-05-23T05:03:00Z"},
    {"phase": "1", "completed_at": "2026-05-23T05:05:00Z"}
  ],
  "active_goal": {
    "summary": "결제 모듈 구현",
    "acceptance_criteria": ["Stripe API 통합", "결제 실패 처리", "PCI-DSS 준수"]
  },
  "pending": [
    {"phase": "2", "action": "Stripe SDK 통합 코드 작성"}
  ],
  "next_action": "Stripe SDK 통합",
  "trip_status": "RUNNING",
  "trip_reason": null
}
```

### Counter 갱신 메커니즘

| 이벤트 | 갱신 |
|--------|------|
| Agent() 호출 시작 | turn += 1, last_agent_call = now() |
| Agent() 호출 종료 (성공) | token_used += result.usage.total_tokens |
| Agent() 호출 종료 (실패) | fail += 1, token_used += partial_usage |
| Phase 완료 | phase_history.append({phase, completed_at}) |

→ `~/.claude/scripts/goal_loop_state.py` (구현 도구)

### Safety Trip Detector (자동 감지)

PreToolUse hook 패턴:
```
매 Agent() 호출 직전:
  state = load(goal-loop-{session}.json)
  if state.counters.turn >= state.counters.turn_limit:
    trip("TURN_LIMIT")
  if state.counters.token_used >= state.counters.token_limit:
    trip("TOKEN_LIMIT")
  if state.counters.fail >= state.counters.fail_limit:
    trip("FAIL_LIMIT")

trip(reason):
  state.trip_status = "TRIPPED"
  state.trip_reason = reason
  save(state)
  → Lead 에게 강제 멈춤 신호 + 사용자 보고
```

## Phase 4 QA Gate

자율 처리 종료 후 (조건 1) Phase 4 진입 시 추가 QA:

### Visual 작업 (chapter == MEDIA OR session.kind == "VISUAL_INTERACTION")

스크린샷 **≥ 3장 의무**. 위반 시 Phase 4 차단.

```
Phase 4 진입
  ↓
session.kind 확인 (LOGIC_DATA vs VISUAL_INTERACTION)
  ↓ VISUAL_INTERACTION 시
agent("iteration-screenshot-verifier") 호출
  ↓
스크린샷 캡처 (≥3장):
  · 작업 전 (before)
  · 작업 후 (after)
  · 핵심 인터랙션 (interaction)
  ↓
test-results/*.png 저장 + Phase 4 통과
```

### Logic/Data 작업 (session.kind == "LOGIC_DATA")

스크린샷 강제 **금지** (사용자 비전 §3.B). 대신:
- unit tests 결과 (pass count + failed count)
- log analysis (error / warning trace 0)
- status code matrix (200/4xx/5xx 분포)

→ agent("e2e-qa-prover") 호출 (LOGIC_DATA 분기).

## /goal Loop 흐름 다이어그램

```
   사용자 평문 / /auto / /goal
            │
            ▼
   Phase -2 (Triage)
            │
            ▼
   Phase -1.5 Deep Interview (Part A~E)
            │
            ▼
   goal-loop state 초기화
   ~/.claude/state/auto/goal-loop-{session}.json 생성
            │
            ▼
   ┌──────────────────────────────────┐
   │  LOOP ENTRY (자율 iteration)      │
   │                                  │
   │  1. next_action 결정              │
   │  2. Agent() 호출                  │
   │  3. result 처리                   │
   │  4. counter 갱신 (turn/token/fail)│
   │  5. safety trip 검사              │
   │      ├─ TRIP → 강제 멈춤 + 보고   │
   │      └─ OK  → 6                   │
   │  6. pending 갱신                  │
   │  7. 조건 1 (pending=0) 확인       │
   │      ├─ YES → Phase 4 QA Gate     │
   │      └─ NO  → 1 (continue)        │
   └──────────────────────────────────┘
            │ (Phase 4 QA Gate 통과)
            ▼
   Phase 4 (Close)
   사용자 보고 (성공) — 사용자 진입점 1회
```

## 자율 영역 vs 사용자 결정 영역

| 작업 | 영역 |
|------|:----:|
| Agent() 호출 / 결과 처리 | **자율** |
| Counter 갱신 | **자율** (goal_loop_state.py 자동) |
| Safety trip 감지 | **자율** (PreToolUse hook) |
| Phase 전환 | **자율** |
| Phase 4 QA Gate 통과 | **자율** (스크린샷 ≥ 3장 자동 검증) |
| 조건 2 (안전절 트립) 시 보고 | **사용자 결정** (다음 행동 — reset / abort / 재정의) |
| 조건 3 (진짜 막힘) 시 보고 | **사용자 결정** (외부 정보 제공) |
| Phase 4 close 사용자 보고 | **사용자 진입점 1회** (최종 산출물 검토) |

## 글로벌 정책 정합

- 글로벌 CLAUDE.md § Iron Laws (5 항목 보장)
- 글로벌 CLAUDE.md § Circuit Breaker (rule 17) 4 counter 통합
- 글로벌 CLAUDE.md § Universal Deployment Premise (HIGHEST PRIORITY) 6 기준 준수

## 관련 자산

| 자산 | 위치 |
|------|------|
| State tracker | `~/.claude/scripts/goal_loop_state.py` |
| Safety trip hook | `~/.claude/hooks/auto_workflow_enforcer.py` (PreToolUse) |
| State file | `~/.claude/state/auto/goal-loop-{session_id}.json` |
| Phase 4 QA Gate | `agents/verification/perfect-output-validator.md` + `e2e-qa-prover.md` + `iteration-screenshot-verifier.md` |
| Circuit Breaker 통합 | `~/.claude/state/circuit-breaker.json` |
