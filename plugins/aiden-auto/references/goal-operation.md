# /goal 운영 가이드 — aiden-auto v28.4 자율 Iteration Loop

> **Phase 6C/D**: aiden-auto 의 자가반복 루프를 구동하는 `/goal` 명령어의 본질, 멈춤 조건, QA 게이트, 보고 시점을 정의.

## 사용자 정의 (2026-05-19)

> "/goal = Conduct true autonomous iteration. Proceed autonomously to the next step, then handle the step after that based on autonomous judgment. When the moment arrives where there is no longer anything left to handle autonomously, perform QA on the deliverables and rigorously verify them based on screenshots. Report to the user if all steps pass."

핵심:
1. **자율 다음 단계 진행**
2. **자율 판단으로 그 다음 단계 처리**
3. **자율 처리할 게 없을 때 QA 수행**
4. **스크린샷 기반 엄격 검증**
5. **모든 단계 통과 시 사용자 보고 (1회)**

## Overview

**`/goal`** 은 Phase -1.5 Deep Interview 완료 후 자동 시동되는 자율 iteration loop. brainstorming spec + multi_session_method (A/B/C/D) 기반.

```
   사용자 명료한 의도 (brainstorming 완료)
        │
        ▼
   /goal 시동 — active-goal-{sid}.json 생성
        │
        ▼
   ┌────────────────────────────────────────┐
   │ 자율 iteration loop                    │
   │  ├─ 다음 단계 자율 진행                 │
   │  ├─ 그 다음 단계 자율 판단              │
   │  ├─ Phase -1 → 0 → 1 → 2 → 3 → 4       │
   │  └─ 멈춤 조건 (3가지) 충족까지         │
   └────────────────┬───────────────────────┘
                    │
                    ▼
   멈춤 조건 분기:
     ① 자율 처리할 게 없음 → QA 단계
     ② 안전절 트립 → 강제 멈춤 + 보고
     ③ 진짜 막힘 → 사용자 결정 1줄 보고
                    │
                    ▼ ① 만 다음 단계
   QA 수행 (Phase 4 Gate 1+2):
     · perfect-output-validator (7 항목)
     · e2e-qa-prover (logic OR visual)
                    │
                    ▼ Visual 작업 시
   스크린샷 검증 (≥ 3장 의무):
     · screenshot 1: 초기 상태
     · screenshot 2: 작동 중 / 진행 상태
     · screenshot 3: 완료 / 결과
                    │
                    ▼ 모두 통과
   사용자 보고 (1회) — user-friendly-reporter 통과
                    │
                    ▼ 미통과
   자율 정정 사이클 재진입 (Phase 3)
```

## 1. /goal 기본 문법

### CC 빌트인 (참조만, 5원칙 #1)

```bash
/goal [goal description]

Options:
  --condition "{boolean expression}"   # 성공 조건 명시
  --max-iterations N                   # 반복 제한 (기본 10)
  --on-failure {HALT | RETRY | SKIP}   # 실패 시 동작
  --builtin                            # CC 공식 직결 (우리 wrapper 우회)
```

### aiden-auto 자동 발동

```
평문 → brainstorming → @ → /goal 자동 시동 (사용자 명시 호출 불필요)
```

## 2. 3 멈춤 조건 (HARD RULE)

| # | 조건 | 감지 방법 | 동작 |
|:-:|------|----------|------|
| 1 | **자율 처리할 게 더 없음** | transcript에 "all phase complete" / "no more steps" 마커 + active-goal.json achieved=false | QA + 스크린샷 검증으로 진입 |
| 2 | **안전절 트립** | turn_count ≥ 20 OR tokens_consumed ≥ 200k OR perfect_output_fails ≥ 5 | 강제 멈춤 + 보고 |
| 3 | **진짜 막힘** | 외부 정보 필요 (회사 GitHub URL / 사용자 비전 / 도구 권한 등) | 사용자 결정 영역 1줄 보고 |

### 멈춤 조건 1: 자율 처리 완료 감지

`hooks/goal_stop_evaluator.py` 가 매 turn 종료 시 평가:

```python
# 자율 처리 완료 markers
autonomous_complete_markers = [
    "all phases complete",
    "phase 4 close",
    "implementation finished",
    "all tasks completed",
    "no more autonomous steps",
]

# 진짜 막힘 markers
truly_blocked_markers = [
    "user input required",
    "external information needed",
    "company-specific data",
    "permission denied",
]
```

### 멈춤 조건 2: 안전절 (자동 첨가)

`lib/goal/goal_writer.py` 의 `DEFAULT_SAFETY_CLAUSES`:

```python
DEFAULT_SAFETY_CLAUSES = [
    "or stop after 20 turns",
    "or stop after 200k tokens consumed",
    "or stop if Perfect Output Gate FAIL 5 times consecutively",
]
```

### 멈춤 조건 3: 진짜 막힘 — 명시 요건

사용자 결정이 필요한 영역만 멈춤:
- 외부 환경 정보 (회사 ID, 도메인 URL 등)
- 사용자 비전 (브랜드 색상, 톤앤매너 등)
- 권한 부족 (관리자 접근 등)

→ 1줄 보고 + 사용자 결정 영역 명시. **A/B/C 옵션 나열 금지** (Core Philosophy).

## 3. QA + 스크린샷 게이트 (Phase 4)

### Gate 1: perfect-output-validator (7 항목)

- frontmatter 정합
- 모든 필드 존재 + 타입
- 안전절 3개 첨가됨
- schema_version 정확
- 산출물 path 존재
- file_exists 검증
- 5원칙 부합

### Gate 2: e2e-qa-prover (session type 분기)

| Session Type | 검증 |
|--------------|------|
| **VISUAL_INTERACTION** | Playwright 스크린샷 ≥ 3장 의무 |
| **LOGIC_DATA** | unit tests + log analysis + status code matrix |

### Gate 2 스크린샷 정책 (VISUAL_INTERACTION)

```
screenshot 1: 초기 상태 (작업 시작 전)
screenshot 2: 작동 중 / 진행 상태 / 변화
screenshot 3: 완료 결과 / 최종 화면
```

추가 screenshot 가능 (테스트 통과 / error 처리 / edge case 등).

### Gate 5: user-friendly-reporter (v28.3+)

모든 사용자 향 보고 통과 의무. 비개발자 친화 검증.

## 4. active-goal.json 스키마 v1.1

```json
{
  "schema_version": "1.1",
  "id": "goal-{8-char hash}",
  "session_id": "...",
  "condition": "...",
  "raw_user_request": "...",
  "brainstorming_spec_path": "docs/superpowers/specs/...",
  "interview_answers": {
    "domain": "...",
    "acceptance": "...",
    "approach": "...",
    "multi_session_method": "A|B|C|D"
  },
  "multi_session_method_resolved": "A|B|C",
  "safety_clauses_applied": [
    "or stop after 20 turns",
    "or stop after 200k tokens consumed",
    "or stop if Perfect Output Gate FAIL 5 times consecutively"
  ],
  "created_at": "ISO-8601",
  "achieved": false,
  "achieved_at": null,
  "autonomous_complete": false,
  "qa_gate_passed": false,
  "screenshot_count": 0,
  "turn_count": 0,
  "tokens_consumed": 0,
  "perfect_output_fails": 0
}
```

## 5. 보고 시점

| 시점 | 보고 형식 |
|------|----------|
| 자율 처리 중 | **보고 없음** (사용자 진입점 0) |
| 멈춤 조건 1 도달 (자율 끝) | QA 진입 (사용자 보고 X) |
| QA Gate 모두 통과 | **사용자 보고 1회** (user-friendly-reporter 통과) |
| QA 실패 | 자율 정정 사이클 재진입 (보고 X) |
| 안전절 트립 | 사용자 보고 + 현황 |
| 진짜 막힘 | 사용자 결정 1줄 보고 |

## 6. multi_session_method 분기 동작

| method | 동작 |
|:------:|------|
| A | `claude --bg "stream-N"` 자동 dispatch (별도 OS 세션) |
| B | `Agent(subagent_type=..., model=plan[...])` 단발 호출 |
| C | `Skill("superpowers:subagent-driven-development")` 위임 |
| D | `multi_session_method_resolved` 값 사용 (재계산 X) |

## 7. 비유 (도서관)

```
   책 카드 발급 (active-goal.json)
        │
        ▼
   ┌────────────────────────────────────┐
   │ 사서들이 자율적으로 진행:          │
   │  · 책 찾기                          │
   │  · 보관 위치 결정                   │
   │  · 손님께 안내 준비                  │
   │  · ... 모든 단계 자동                │
   │  → 더 자율 처리할 게 없음           │
   └─────────────┬──────────────────────┘
                 │
                 ▼
   QA 검수 (책 상태 + 위치 + 안내문)
                 │
                 ▼ 시각 검수 (≥ 3 사진)
                 │
                 ▼ 모두 통과
   손님께 결과 안내 (1회만)
```

## 8. 비교: v28.3 → v28.4

| 영역 | v28.3 (이전) | v28.4 (현재) |
|------|-------------|-------------|
| 멈춤 조건 | 안전절 3개만 | 안전절 3 + **"자율 처리 완료"** 신규 |
| QA Gate 2 | e2e-qa-prover | **스크린샷 ≥ 3장 명시** (Visual) |
| 자율성 정의 | 작업 처리 | **"true autonomous iteration"** (사용자 정의) |
| 보고 시점 | Phase 4 close | **QA 통과 후 1회만** |
| Phase -1.5 통합 | ambiguity ≥ 2 시 | **평문 직후 즉시 + brainstorming 위임** |

## 9. 외부 framework 참조 (5원칙 #1)

- **claude-code-goal** (anthropics) — CC 빌트인 /goal 원조. 본 정의의 본질
- **superpowers:brainstorming** — Phase -1.5 Part A 위임
- **superpowers:subagent-driven-development** — multi_session method C 위임
- 우리 wrapper = safety + multi-session 분기 + QA + 비개발자 보고

상세: `references/external-harness-registry.md`.

## 10. Best Practices

### ✅ 해야 할 것
1. 평문 직후 brainstorming + @ 즉시 발동
2. /goal 시동 후 자율 처리 (사용자 진입점 0)
3. 멈춤 조건 1 도달 시 QA로 진입
4. Visual 작업 시 스크린샷 ≥ 3장
5. user-friendly-reporter 통과 후 보고

### ❌ 하지 말아야 할 것
1. 자율 처리 중 사용자 결정 요청 (멈춤 조건 외)
2. QA 없이 완료 선언
3. 스크린샷 부족 + Visual 작업 보고
4. 전문용어 그대로 보고

---

**Generated**: 2026-05-19 Phase 6D
**Framework**: aiden-auto v28.4
**Pattern Support**: 자율 iteration + 3 멈춤 조건 + QA/screenshot 게이트
