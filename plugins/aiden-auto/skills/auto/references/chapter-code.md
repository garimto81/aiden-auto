---
name: chapter-code
category: CODE
pipeline: [triage, chapter-code]
next-skill: null
handoff: .claude/state/auto/code-{slug}.md
agent_team: [executor, architect, code-reviewer, qa-tester, security-reviewer, test-engineer, verifier]
phase_path: [-2, -1.5, -1, 0, 1, 2, 3, 4, cleanup]
---

# Chapter: CODE — 기능 구현 / 수정 / 리팩토링

> **카테고리**: CODE
> **트리거 키워드**: 구현, 추가, 만들어, fix, 수정, refactor, 리팩토링, build, 코드, 기능
> **v27.2 강화**: XML 구조화 + Multi-perspective parallel validation + Cleanup phase

<Purpose>
사용자의 코드 작업 요구를 받아 Plan→Build→Verify→Close 사이클로 자율 처리. TDD 우선, 다중 검증 게이트, 작업 종료 후 잔재물 정리까지 포함.
</Purpose>

<Use_When>
- 새 기능 구현 ("로그인 추가해줘")
- 버그 수정 ("결제 API 500 에러 fix")
- 리팩토링 ("utils/date.ts 함수 분리")
- 의존성 업데이트 + 코드 적응
- 다중 파일 영향 변경
</Use_When>

<Do_Not_Use_When>
- 기획 문서 작성만 → chapter-doc
- 테스트 실행만 → chapter-qa
- 반복 cycle 필요 → chapter-iteration
- 단순 read 또는 1줄 오타 → !quick magic word 사용
</Do_Not_Use_When>

<Why_This_Exists>
코드 작업은 단계마다 다른 전문성 필요: 계획(planner) → 구현(executor) → 다중 시각 검증(architect+security+code-reviewer 병렬) → 테스트(qa-tester+test-engineer) → 완료 검증(verifier). 한 agent가 다 하면 품질 누락 발생.
</Why_This_Exists>

<Workflow_Diagram>

```
[Triage: CODE]
      │
      ▼
Phase -1 (컨텍스트 감지)
      │
      ▼
Phase 0 (복잡도 + 모드 선택)
   ├─ DIRECT (1 파일)
   ├─ LITE (2-3)
   └─ TEAM (4+)
      │
      ▼
Phase 1 (PRD + 사전 분석)
   ├─ planner: 영향 분석
   ├─ test-engineer: test strategy 설계
   ├─ critic-lite: 약점 (STANDARD+)
   └─ architect: 기술 검증
      │
      ▼
Phase 2 (구현 — TDD)
   ├─ qa-tester: Red (실패 test)
   ├─ executor: Green (통과 코드)
   ├─ executor: Refactor
   └─ code-reviewer: 코드 리뷰
      │
      ▼
Phase 3 (Multi-perspective Validation, 병렬)
   ├── architect (functional)        ┐
   ├── security-reviewer (vuln)      │ 병렬
   ├── code-reviewer (quality)       │ 실행
   └── qa-tester (E2E)               ┘
   ALL APPROVE → next, ANY REJECT → fix loop
      │
      ▼
Phase 3.5 (Verifier — fresh evidence)
   verifier: 모든 주장 재검증
      │
      ▼
Phase 4 (CLOSE — 보고서 + 커밋)
      │
      ▼
Phase Cleanup (NEW v27.2)
   · state file 삭제
   · 좀비 세션 차단
```

</Workflow_Diagram>

<Execution_Policy>
- TDD 우선 (실패 test 없이 코드 금지)
- Phase 3 multi-perspective는 병렬 실행 필수 (순차 X)
- ALL agents APPROVE 필수 (architect + security + code-reviewer + qa-tester)
- ANY REJECT → 해당 issue만 fix → 그 agent만 재검증
- Phase 3.5 verifier는 다른 agent 결과를 메타 검증
- Cleanup phase는 무조건 실행 (성공/실패 무관)
</Execution_Policy>

<Steps>

## Phase 1 — PRD + 사전 분석

### Step 1.1: PRD 확인/생성
- `.claude/rules/13-requirements-prd.md` 준수
- `docs/00-prd/`에서 관련 PRD 탐색
- 없으면 신규 생성

### Step 1.2: 영향 분석 (planner)
```
planner 호출:
  prompt: 요구사항 + 영향 받는 파일 목록 + 구현 순서
  output: PlanContract (requirements, affected_files, acceptance_criteria)
```

### Step 1.3: Test Strategy 설계 (test-engineer, NEW v27.2)
```
test-engineer 호출:
  목적: test pyramid 설계 (unit 70 / integ 20 / e2e 10)
  critical paths 식별 (95% coverage 필수)
  flaky test 패턴 확인
  output: TestStrategy (pyramid, critical_paths, hardening_plan)
```

### Step 1.4: 약점 분석 (STANDARD+)
```
critic-lite 호출:
  대상: planner 출력
  목적: 누락/모순/리스크 감지
```

### Step 1.5: 기술 검증 (architect)
- READ-ONLY 검증
- HEAVY: Planner-Critic Loop (max 5회)

## Phase 2 — 구현 (TDD)

### Step 2.1: Red — 실패 test 작성
```
qa-tester 호출:
  prompt: TestStrategy 기반 실패 test 작성
  검증: pytest/jest exit code = 1 (실패 확인)
```

### Step 2.2: Green — 통과 코드 작성
```
executor 호출 (LITE/TEAM 시 impl-manager로 승격):
  prompt: PlanContract + 실패 test 통과 최소 코드
  output: BuildContract
```

### Step 2.3: Refactor — 코드 개선
```
executor 호출:
  prompt: 코드 개선 (test 유지)
  검증: 모든 test 여전히 통과
```

### Step 2.4: Code Review
```
code-reviewer 호출:
  대상: BuildContract.changed_files
  output: APPROVE | CHANGES_REQUESTED (max 3회)
```

## Phase 3 — Multi-perspective Validation (NEW v27.2, 병렬)

```
4개 agent 동시 호출 (Agent Teams 패턴):

┌─────────────────────────┐
│ architect (READ-ONLY)   │  ← 기능 완전성, gap-detector ≥90%, Iron Laws
├─────────────────────────┤
│ security-reviewer       │  ← OWASP Top 10, 취약점, secret leak
├─────────────────────────┤
│ code-reviewer           │  ← 코드 품질 재검토
├─────────────────────────┤
│ qa-tester (E2E)         │  ← Playwright 시나리오
└─────────────────────────┘

집계:
  ALL APPROVE → Phase 3.5
  ANY REJECT → 해당 agent의 finding만 fix → 그 agent만 재호출
  2회 REJECT → 사용자 알림
```

OMC autopilot Phase 4 패턴 차용. 단일 검증 게이트보다 더 안정적.

## Phase 3.5 — Verifier (NEW v27.2, fresh evidence)

```
verifier 호출:
  목적: 다른 agent들의 "완료" 주장 재검증
  검증:
    - test 결과: 실제 명령 재실행
    - build 결과: 실제 빌드 재실행
    - lint 결과: 실제 lint 재실행
    - PR 상태: gh pr view 확인
    - gap_score: gap-detector 재실행
  
  output:
    VERIFIED → Phase 4 진행
    REJECTED → 해당 phase 재실행
    INSUFFICIENT_EVIDENCE → 추가 증거 수집
```

ralph 패턴 + Iron Law의 Verification 강제 집행.

## Phase 3.6 — pdca-iterator 자동 트리거 (NEW v27.4)

verifier 결과 + gap 측정 → 임계값 미달 시 사용자 입력 없이 자율 ITERATION 진입:

```
[Phase 3.5 verifier 완료]
       │
       ▼
gap_score = gap-detector(BuildContract) 재실행
       │
       ▼
gap_score < 0.9 OR verifier == REJECTED?
       │
   YES │ NO
       ▼
[pdca-iterator 자동 호출]
       │
       │ → chapter-iteration 자율 진입
       │ → max 5 iterations
       │ → re-run gap-detector after each fix
       │
       ▼
gap_score >= 0.9 OR circuit_breaker
       │
       ▼
[Phase 4 CLOSE 자동 진행]
```

**자율 적용 룰** (사용자 결정 떠넘기기 금지):
- gap < 0.9 시 즉시 pdca-iterator 발동 (질문 X)
- 5회 반복 후에도 미달 시에만 사용자 보고
- 성공 시 별도 보고 없이 Phase 4 진행 (메트릭에만 기록)

**bkit-claude-code 영감**: Evaluator-Optimizer 패턴 (gap-detector + iteration 자동 결합).

## Phase 4 — CLOSE (보고서 + 커밋)

| 단계 | 동작 |
|------|------|
| 4.0 | 변경사항 정리 + 메트릭 수집 |
| 4.1 | git commit: `feat({feature}): 구현 완료` 또는 `fix({feature}): {버그}` |
| 4.2 | 사용자 보고 (변경 파일 N개, 테스트 통과 K건, 커버리지 X%) |

## Phase Cleanup — NEW v27.2 (state file 정리)

OMC autopilot Phase 5 패턴 차용. 좀비 세션 차단:

```bash
# 무조건 실행 (성공/실패 무관)
rm -f .claude/state/auto/code-{slug}.json
rm -f .claude/state/auto/build-{slug}.json
rm -f .claude/state/auto/verify-{slug}.json
rm -f .claude/state/sessions/{sessionId}/code.json
TeamDelete()  # Agent Teams 정리

# 잔재물 검증
ls .claude/state/ | grep {slug} | wc -l  # 0이어야 함
```

자율 실행 정책:
- Phase 4 성공 후 → 즉시 cleanup
- Phase 3 실패 시 (5회 재시도 후) → 진단 보고서 저장 + cleanup
- 사용자 /auto stop 시 → 즉시 cleanup
- 컨텍스트 compaction 후 resume 실패 시 → cleanup + 사용자 알림

</Steps>

<Tool_Usage>
- 모든 agent 호출은 Agent Teams 패턴: `TeamCreate → Agent → SendMessage(timeout=60) → TeamDelete`
- Phase 3 4개 agent는 같은 SendMessage round로 병렬 발사
- Phase 3.5 verifier는 sequential (다른 결과를 받아 메타 검증)
- Cleanup은 hook이 아니라 chapter 자체에서 실행 (보장)
</Tool_Usage>

<Examples>

<Good>
User: "사용자 프로필 페이지에 아바타 업로드 기능 추가"
처리: Phase 0 복잡도 4점 (TEAM) → Phase 1-4 + Cleanup
agent team: 7개 (planner, test-engineer, executor, code-reviewer, architect, security-reviewer, qa-tester, verifier)
종료 후: state file 자동 삭제
</Good>

<Good>
User: "결제 API 500 에러 fix"
처리: Phase 0 복잡도 2점 (LITE) → Phase 1 PRD 스킵 → Phase 2-3 + Cleanup
multi-perspective: security-reviewer가 결제 관련이니 필수 포함
</Good>

<Bad>
User: "이 파일 뭐야?"
처리: ❌ chapter-code 발동 X (단순 read, 평문 트리거 disabled)
</Bad>

</Examples>

<Termination_Conditions>
- 모든 test 통과
- code-reviewer APPROVE
- architect APPROVE (gap ≥ 90%)
- security-reviewer APPROVE (Critical 0 + Major 0)
- E2E 통과 (UI 작업 시)
- verifier VERIFIED
- Cleanup 완료 (state file 0개)
- 사용자 거부 패턴 부재
</Termination_Conditions>

<User_Friendly_Explanation>

15세 기준 친절 설명 (모든 응답에 적용):

```
"코드 작업이군요. 이렇게 진행할게요:

  1단계: 어떤 파일들을 건드릴지 파악 + 테스트 전략 설계
  2단계: 테스트부터 짜고 (안전장치) 코드 작성
  3단계: 4명 검토팀이 동시에 검토
         · 건축가(architect): 설계 맞나?
         · 보안 검사관(security): 취약점 없나?
         · 품질 검수관(code-reviewer): 코드 깔끔한가?
         · 검수원(qa-tester): 화면에서 잘 작동하나?
  4단계: 검증관(verifier)이 결과 진짜인지 다시 확인
  5단계: 커밋 + 보고서
  6단계: 작업 흔적 정리 (좀비 차단)

  중간에 변경할 게 생기면 알아서 결정하고 결과만 알려드릴게요."
```

</User_Friendly_Explanation>
