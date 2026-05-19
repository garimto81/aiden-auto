# Phase -1.5 — Deep Interview (v28.4 재작성)

> **목적**: 평문 직후 즉시 발동. **superpowers:brainstorming (의도 명료화) + @ (multi-session 처리 방식 선택)** 로 구성. 산출 → /goal 자율 iteration 시동.

## 사용자 정의 (2026-05-19)

> "Deep Interview는 평문 직후 최초 분석 후 바로 호출. superpowers의 brainstorming + @ 로 처리."
>
> "@ = /goal + 멀티 세션 처리 방식 선택지"

## Use_When (발동 조건)

- 평문 작업 요청 (단순 질문/파일 읽기 제외)
- /auto 자동 트리거 영역
- Phase -2 ambiguity_score 측정과 **병렬 또는 직후 즉시 발동**

## Skip_When

- `!quick` / `!just` / `!hotfix` Magic Word
- `/goal "<condition>"` 명시 입력 (condition 직접 작성됨)
- 사용자 평문에 multi-session 방식 명시 (예: "claude agents로 처리")
- 직전 cycle 24h 이내 동일 사용자 동일 multi_session_method 선택 → silent 재사용

## Phase Flow

```
   사용자 평문
        │
        ▼
   Phase -2: 평문 1차 분석 (카테고리 + ambiguity_score)
        │
        ▼
   ┌──────────────────────────────────────────┐
   │ Phase -1.5: Deep Interview               │
   │                                          │
   │ Part A: brainstorming (의도 명료화)        │
   │   Skill("superpowers:brainstorming")      │
   │   · 1 question at a time                  │
   │   · 2-3 approaches + 사용자 승인           │
   │   · 산출: docs/superpowers/specs/         │
   │           YYYY-MM-DD-<topic>-design.md   │
   │                                          │
   │ Part B: @ (multi-session 선택)            │
   │   추천 알고리즘 (Signal 1>2>3>default):    │
   │   · est_lines < 100 → B                   │
   │   · plan + tasks ≥3 → C                   │
   │   · streams ≥3 + hours ≥8 → A             │
   │   · default → B                           │
   │                                          │
   │   4 선택지:                                │
   │   A. Claude Agents (별도 OS 세션)          │
   │   B. Subagent (같은 세션)                  │
   │   C. Superpowers Subagent (2-stage)       │
   │   D. Claude 자율 (추천 그대로, 기본값)      │
   └──────────────────┬───────────────────────┘
                      │
                      ▼ spec → active-goal.json 변환
   /goal 자율 iteration 시동
   (multi_session_method 따라 분기)
        │
        ▼
   Phase -1 Context Detect → Phase 0+
```

## Part A — brainstorming (의도 명료화)

### 위임 메커니즘

```
Skill("superpowers:brainstorming")
```

위치: `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/skills/brainstorming/SKILL.md`

### 동작 (브랜드 그대로 적용)

1. **Explore project context** — 파일/문서/최근 commit 확인
2. **Offer Visual Companion** (시각 질문 예상 시) — 별도 메시지
3. **Ask clarifying questions** — **1 question at a time** (multiple choice 우선)
4. **Propose 2-3 approaches** — trade-off + 추천 + 이유
5. **Present design** — 섹션 별 사용자 승인 후 진행
6. **Write design doc** — `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
7. **Spec self-review** — placeholder / 일관성 / scope / 모호성 4 항목
8. **User reviews spec** — 사용자 승인 게이트
9. **Transition** → writing-plans skill (우리 시스템에서는 Part B 후 /goal 시동)

### 우리 시스템 정합 (5원칙 #1: 참조만, 복사 X)

- brainstorming spec 그대로 호출. 내부 로직 복사하지 않음.
- 우리 시스템은 호출 + 결과 spec 받음 + active-goal.json 변환

## Part B — @ (Multi-Session 처리 방식 선택)

### 의미 (사용자 명확화 2026-05-19)

> **@ = /goal + multi-session 처리 방식 선택지**
>
> brainstorming 종료 후 별도 단계로 발동. 사용자가 A/B/C/D 중 선택. /goal 자율 iteration 시동 시 분기 기준.

### 추천 알고리즘 (Signal 우선순위 HARD RULE)

```python
def recommend_multi_session(task_signals: dict) -> tuple[str, str]:
    if task_signals.get("estimated_lines", float("inf")) < 100:
        return ("B", "작업 작음 → 단발 위임")
    elif (task_signals.get("has_plan")
          and task_signals.get("independent_tasks_count", 0) >= 3):
        return ("C", "plan + 독립 task 다수 → 2-stage 리뷰")
    elif (task_signals.get("long_running_streams", 0) >= 3
          and task_signals.get("estimated_hours", 0) >= 8):
        return ("A", "큰 stream 다수 → 진짜 병렬")
    else:
        return ("B", "scope 불확실 → 가장 가벼움")
```

`elif` chain short-circuit. 우선순위 1>2>3>default.

### 4 선택지 + 사용자 표시 형식

```
"이 작업의 병렬 처리 방식을 정해주세요"

  추천: {Claude 분석 결과}
  근거: {1줄}

  다른 선택지:
    (A) Claude Agents      — 별도 OS 세션, 진짜 병렬
    (B) Subagent           — 같은 세션, 가장 가벼움
    (C) Superpowers Subagent — plan + 2-stage 자동 리뷰
    (D) Claude 자율         — 추천 그대로 (기본값)
```

### 저장 (active-goal.json 필드)

```json
{
  "interview_answers": {
    "multi_session_method": "C"
  },
  "multi_session_method_resolved": "C"
}
```

D 선택 시 `resolved` 필드에 추천 알고리즘 결과 자동 저장 (Phase 0+ 재계산 방지).

### Phase 0+ 분기

| method | 분기 |
|:------:|------|
| A | `claude --bg "stream-N"` 자동 dispatch |
| B | `Agent(subagent_type=..., model=plan[...])` 단발 호출 |
| C | `Skill("superpowers:subagent-driven-development")` 발동 |
| D | `multi_session_method_resolved` 값 사용 (재계산 X) |

### 하위호환 (옛 processing_method)

```python
LEGACY_MAP = {
    "1": "D",  # Claude 자율 → D
    "2": "B",  # Parallel Agent → B
    "3": "A",  # claude agents → A
    "4": "B",  # Background subagent → B
    "5": "B",  # Sequential → B (보수)
}
```

상세: `agents/core/intake-interviewer.md` "필드명 마이그레이션" 섹션 (DEPRECATED but 보존).

## 산출물 + /goal 시동 변환

### 입력
- brainstorming spec: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Part B 선택: `multi_session_method` ∈ {A, B, C, D}

### 변환 → active-goal-{session_id}.json

```json
{
  "schema_version": "1.1",
  "id": "goal-{hash}",
  "session_id": "...",
  "condition": "<brainstorming spec acceptance criteria>. 모든 unit test PASS, console error 0건. or stop after 20 turns. or stop after 200k tokens consumed. or stop if Perfect Output Gate FAIL 5 times consecutively.",
  "raw_user_request": "<원문>",
  "brainstorming_spec_path": "docs/superpowers/specs/...",
  "interview_answers": {
    "domain": "<spec excerpt>",
    "acceptance": "<spec excerpt>",
    "approach": "<spec excerpt>",
    "multi_session_method": "<A/B/C/D>"
  },
  "multi_session_method_resolved": "<A/B/C>",
  "safety_clauses_applied": [...],
  "achieved": false,
  "turn_count": 0,
  "tokens_consumed": 0,
  "perfect_output_fails": 0
}
```

변환 함수: `lib/goal/goal_writer.py` `write_goal_from_brainstorming_spec()` (v28.4 신규).

## Output Contract

Phase -1.5 종료 시 보장:

1. `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` 존재 + 사용자 승인 완료
2. `state/active-goal-{session_id}.json` 존재 + schema_version 1.1
3. `multi_session_method` 필드 ∈ {A, B, C, D}
4. `multi_session_method_resolved` 필드 ∈ {A, B, C} (D 선택 시 자동 산출)
5. 안전절 3개 자동 첨가 (20 turns / 200k tokens / 5 fails)
6. 사용자 진입점: brainstorming 1-by-1 질문 + Part B 1 질문 = 가변 (보통 5회 이하)

## Core Philosophy 정합

- **외부 framework 참조만** (superpowers:brainstorming, 5원칙 #1)
- **사용자 진입점 최소화** — D 자율 default 시 Part B 진입점 0
- **자율 iteration** — Part B 후 /goal 자율 시동
- **A/B/C 금지 원칙의 명시 예외 영역** — Part B만 적용 (Part A의 brainstorming은 자체 패턴 따름)

## 폐기 처리 (자체 intake-interviewer)

- `agents/core/intake-interviewer.md` → DEPRECATED 표시 (보존)
- Q1-Q4 한번에 발화 패턴 → brainstorming 1-by-1 패턴으로 위임
- 옛 `processing_method` 필드 → `multi_session_method` 로 LEGACY_MAP 변환

## 비유 (도서관)

```
   손님: "음, 책 좀..."
        │
        ▼
   사서가 평문 분석 (Phase -2)
        │
        ▼
   ┌──────────────────────────────────────┐
   │ 사서가 1 질문씩 (brainstorming)        │
   │  "어떤 분야가 좋으세요?"               │
   │  → "기술서요"                          │
   │  "초보용? 전문가용?"                    │
   │  → "초보용이요"                         │
   │  ... 의도 명료화 완료                   │
   │                                       │
   │ 사서: "도서관 분관 몇 곳에서 책 찾을까요?"│
   │       추천: 1곳 (책 작아서)             │
   │       다른 선택지: 4곳까지 / 협업       │
   │  → "1곳이요" (D 자율)                  │
   └──────────────┬───────────────────────┘
                  │
                  ▼ 책 카드(active-goal.json) 작성
   대출 시작 (/goal 자율 iteration)
```

## 관련

- `Skill("superpowers:brainstorming")` (외부 위임)
- `references/goal-operation.md` (/goal 자율 iteration 본질)
- `agents/core/intake-interviewer.md` (DEPRECATED, 보존)
- `lib/goal/goal_writer.py` (brainstorming spec 변환)
- `projects/{project}/memory/feedback_multi_session_choice.md` (@ 의미 정책)

## 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| v28.4 | 2026-05-19 | brainstorming + @ 통합 재작성. 평문 직후 즉시 발동. superpowers 위임. /goal 시동 연결 |
| v28.3 | 2026-05-13 | 자체 intake-interviewer Q1-Q4 (현재 DEPRECATED) |
