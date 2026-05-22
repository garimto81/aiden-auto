---
paths:
  - ".claude/skills/**/*"
  - ".claude/commands/**/*"
  - "src/agents/**/*"
---

# Task 분해 표준 패턴

## 핵심 원칙

**복합 작업은 Agent Teams(TeamCreate → Task(team_name) → SendMessage → TeamDelete)로 관리**

| 규칙 | 내용 |
|------|------|
| **개별 Task 생성** | 복합 작업은 TaskCreate로 분해 |
| **명시적 종속성** | addBlockedBy로 순서 정의 |
| **독립 Task 병렬** | 종속성 없는 Task는 병렬 실행 |
| **단일 책임** | 1 Task = 1 에이전트 역할 |

## 표준 패턴

### PRD 문서 자동화 (3단계 순차)

```
Task 1: HTML 목업 생성
  - 에이전트: designer
  - 모델: sonnet

Task 2: Playwright 스크린샷 캡처
  - 에이전트: qa-tester
  - 모델: sonnet
  - blockedBy: Task 1

Task 3: PRD 문서에 이미지 첨부
  - 에이전트: writer
  - 모델: haiku
  - blockedBy: Task 2
```

### 기능 구현 (병렬 + 순차 혼합)

```
Task 1: 코드베이스 탐색       (explore, haiku)       - 독립
Task 2: 테스트 작성           (executor, sonnet)     - 독립
Task 3: 기능 구현             (executor, sonnet)     - blockedBy: Task 1, Task 2
Task 4: 코드 리뷰             (architect, opus)      - blockedBy: Task 3
```

**실행 순서:**
1. Task 1, Task 2 병렬 실행
2. 둘 다 완료 후 Task 3 실행
3. Task 3 완료 후 Task 4 실행

### PDCA 워크플로우 (5단계 순차)

```
Task 1: Plan 문서 생성        (planner, opus)
Task 2: Design 문서 생성      (architect, opus)      - blockedBy: Task 1
Task 3: 구현                  (executor, sonnet)     - blockedBy: Task 2
Task 4: 이중 검증             (architect, opus)      - blockedBy: Task 3
Task 5: 보고서 생성           (writer, haiku)        - blockedBy: Task 4
```

## 에이전트 라우팅

| 작업 유형 | 에이전트 | 모델 | 병렬 가능 |
|----------|----------|------|----------|
| 독립 탐색 | explore | haiku | ✅ |
| 기능 구현 | executor | sonnet | ⚠️ 파일 충돌 확인 |
| 복잡 분석 | architect | opus | ✅ |
| 문서 작성 | writer | haiku | ✅ |
| UI 작업 | designer | sonnet | ⚠️ 스타일 충돌 확인 |
| 테스트 | qa-tester | sonnet | ✅ |

## 종속성 설정 예시

### 잘못된 예

```python
# ❌ 구 subagent 패턴 (team_name 없음)
Task(subagent_type="designer", model="sonnet", prompt="...")
Task(subagent_type="qa-tester", model="sonnet", prompt="...")
```

### 올바른 예

```python
# ✅ Agent Teams 패턴 (team_name + 명시적 종속성)
TeamCreate(team_name="feature-session")
TaskCreate(subject="목업 생성", description="...")
TaskCreate(subject="스크린샷 캡처", description="...")
TaskUpdate(taskId="2", addBlockedBy=["1"])
Agent(subagent_type="designer", name="designer", description="목업 생성",
      team_name="feature-session", model="sonnet", prompt="...")
SendMessage(to="designer", summary="Task #1 할당", message="Task #1 할당.")
# designer 완료 후 →
Agent(subagent_type="qa-tester", name="tester", description="스크린샷 캡처",
      team_name="feature-session", model="sonnet", prompt="...")
SendMessage(to="tester", summary="Task #2 할당", message="Task #2 할당.")
# 완료 → SendMessage(to="designer", message={type: "shutdown_request"})
#       → SendMessage(to="tester", message={type: "shutdown_request"})
#       → TeamDelete()
```

## 금지 사항

| 금지 | 이유 | 대안 |
|------|------|------|
| ❌ TaskCreate 없이 암묵적 종속성 | 실행 순서 보장 안 됨 | blockedBy 명시 |
| ❌ blockedBy 미지정 순차 실행 | 병렬화 기회 상실 | 독립 Task 확인 |
| ❌ 단일 Task에 2개+ 에이전트 | 책임 불명확 | Task 분리 |
| ❌ 파일 충돌 Task 병렬 실행 | Race condition | blockedBy 설정 |

## 강제 수단

- Hook: 없음
- 검증: 워크플로우 기반
- 영향도: **HIGH**
