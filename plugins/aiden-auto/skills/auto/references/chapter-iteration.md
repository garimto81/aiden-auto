---
name: chapter-iteration
category: ITERATION
pipeline: [triage, chapter-iteration]
next-skill: chapter-code  # iteration 종료 후 후속 작업 가능
handoff: .claude/state/auto/iteration-{slug}.md
agent_team:
  - iteration-curator-a
  - iteration-curator-b
  - iteration-drift-reconciler
  - iteration-runner
  - tracer
  - executor
  - architect
  - verifier
phase_path: [-2, -1.5, -1, 0, 1, 2, 3, iteration-loop, 4, cleanup]
---

# Chapter: ITERATION — 반복 cycle / Drift / Hot-swap

> **카테고리**: ITERATION (구 /iteration 흡수)
> **트리거 키워드**: 반복, cycle, 미구현, drift, 누적, iteration, iterate
> **v27.2 강화**: XML 구조화 + tracer 통합 + verifier + Cleanup

<Purpose>
미구현 list 처리 OR drift 감지 OR e2e fail 발생 시 자율적으로 반복 cycle을 돌려 e2e zero-error까지 수정-검증 반복. 매 phase 종료 시 hot-swap curator가 prompt 1회 자동 개선.
</Purpose>

<Use_When>
- 미구현 list > 0 ("미구현 5개 처리")
- Drift 감지 ("drift 검증")
- e2e fail 누적
- 신규 기획부터 구현까지 ("결제 모듈 추가")
- 사용자 결정 archive
</Use_When>

<Do_Not_Use_When>
- 단일 작업 1회 처리 → chapter-code
- 단순 검증 → chapter-qa
</Do_Not_Use_When>

<Workflow_Diagram>

```
[Triage: ITERATION]
      │
      ▼
phase-strategist (트리거 분류)
      │
   ┌──┴──┐
   ▼     ▼
Workflow A    Workflow B
Impl-first    Spec-first
7-step        5-step
      │
      ▼
Iteration Loop:
   매 phase 종료 시:
   ├─ tracer: 인과 추적 (NEW v27.2)
   ├─ verifier: fresh evidence (NEW v27.2)
   ├─ exit_criteria 확인
   ├─ Hot-swap curator a/b 교체
   └─ rotation_log append
      │
      ▼
exit_criteria 충족 → Phase 4 + Cleanup
미충족 → 다음 iteration
```

</Workflow_Diagram>

<Workflow_A>

## Impl-first 7-step (미구현 처리)

```
1. 프로토타입 구현
   executor + architect + code-reviewer
2. 문제점 감지
   qa-tester + iteration-e2e-orchestrator + tracer (NEW v27.2)
3. SSOT vs 코드 결정 ★
   iteration-drift-reconciler + iteration-spec-validator
4a. 기획 수정 (additive)        4b. 코드 수정
    writer + critic              executor + code-reviewer
5. e2e 검증
   iteration-e2e-orchestrator + qa-tester
6. 스크린샷 (UI 시)
   iteration-screenshot-verifier
7. 체크포인트
   verifier (fresh evidence) → exit OR Step 1
```

</Workflow_A>

<Workflow_B>

## Spec-first 5-step (신규 기획)

```
1. 인텐트 → spec
   iteration-spec-author + planner
2. spec 검증
   iteration-spec-validator + iteration-spec-classifier
3. 충돌 검사
   iteration-spec-coherence + critic
4. 구현 진입
   → /auto sub-call (chapter-code)
5. 결정 영구 기록
   iteration-decision-archivist
```

</Workflow_B>

<Hot_Swap_Mechanism>

```
[Phase N 종료]
      │
      ▼
ACTIVE: curator-a / STANDBY: curator-b
      │
      ▼
swap 직전 (1회만):
  1. STANDBY가 ACTIVE 검사
  2. STANDBY가 prompt 개선
      │
      ▼
ACTIVE ↔ STANDBY 교체
rotation_log append
```

| 항목 | 규칙 |
|------|------|
| 자동 교체 | phase 종료 시 항상 |
| 검사 횟수 | swap 직전 1회 |
| 개선 횟수 | swap 직전 1회 (hard-cap) |
| 무한 진화 방지 | 매 phase 1회 hard-cap |

</Hot_Swap_Mechanism>

<Drift_Detection>

```
스크립트: ${SKILL_DIR}/scripts/spec_drift_check.py
실행: 매 phase 종료 시 자동

threshold:
  > 0.1 → 알림
  > 0.3 → Step 3 자동 진입
  > 0.5 → 사용자 보고 + 일시 중단
```

</Drift_Detection>

<Exit_Criteria>

```python
# v3 (F22 정정 — oscillation 허용):
exit = (
    reimplementability_pass_rate >= 0.9
    AND current_drift < 0.1  # 절대값 임계
    AND drift_improved_consecutive_cycles >= 3  # 진동 허용 — 3 연속 개선만 요구
    AND missing == 0
    AND e2e_status == "PASS"
    AND verifier_status == "VERIFIED"  # NEW v27.2
) OR user_explicit_stop in ["멈춰", "stop", "ok"]
  OR circuit_breaker(5_same_fail)

# 폐기 (F22 결함):
# AND drift_direction == "decreasing"  # 진동 (0.3→0.2→0.3) 시 무한 loop 발생
```

> **oscillation tolerance (F22 v3)**: 이전 정책 `drift_direction == "decreasing"` 은 매 cycle 단조 감소 요구 → 진동 시 exit 차단. v3 정정: 절대값 < 0.1 임계 + 3 연속 개선 누적 → 진동 허용하되 추세 보장.

</Exit_Criteria>

<Iteration_Loop_Control>

```python
iteration_count = 0
MAX_CUMULATIVE_ITERATIONS = 10
SAME_FAIL_LIMIT = 5

Loop:
  iteration_count += 1
  
  if iteration_count >= MAX_CUMULATIVE_ITERATIONS:
    report_to_user("최대 반복 도달")
    cleanup()  # NEW v27.2: 무조건 cleanup
    break
  
  if phase_ended:
    swap_curators()
    log_rotation()
  
  result = execute_current_workflow()
  
  if result == previous_result:
    same_fail_count += 1
    if same_fail_count >= SAME_FAIL_LIMIT:
      report_to_user("동일 실패 5회")
      cleanup()
      break
  
  if check_exit_criteria():
    cleanup()
    break
```

</Iteration_Loop_Control>

<Phase_Cleanup>

```bash
# 무조건 실행 (성공/실패/타임아웃 무관)
rm -f .claude/state/auto/iteration-{slug}.json
rm -f .claude/state/auto/iteration-loop-{slug}.json
rm -f .claude/state/iteration/v10_metrics.yml.tmp
TeamDelete()  # 13개 iteration- agents 정리

# rotation_log는 보존 (글로벌 누적)
```

</Phase_Cleanup>

<User_Friendly_Explanation>

```
"반복 검증 작업이군요. 이렇게 진행할게요:

  1단계: 무슨 문제가 있는지 자동 진단 (인과 추적관 추가)
  2단계: 기획 vs 코드 어느 쪽이 문제인지 판단
  3단계: 알아서 고치고 다시 검증
  4단계: 통과할 때까지 반복 (매번 더 똑똑해짐)
  5단계: 검증관이 결과 진짜인지 확인
  6단계: 작업 흔적 정리

  안전장치:
   · 5회 동일 실패 → 사용자 보고
   · 10회 누적 → 강제 중단
   · 무한 루프 방지"
```

</User_Friendly_Explanation>
