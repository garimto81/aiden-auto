# Phase -1.5 — Deep Interview

> **목적**: Phase -2 Triage 직후, Phase -1 context-detect 이전. 모호한 의도를 1-3 질문으로 명료화하여 verifiable goal condition을 생성.

## Use_When

- `ambiguity_score ≥ 2` (triage 측정)
- 사용자 평문이 "게임 만들어" 수준의 1줄 추상 요청
- /goal 발화 전 condition 텍스트 미확보

## Skip_When

- `ambiguity_score < 2` (구체 명사 ≥3 + 명시 동사 + 수락 기준 추정 가능)
- 사용자가 `!quick`, `!skip-interview` 우회 키워드 사용
- /goal 명시 입력 시 (사용자가 condition 직접 작성)

## Phase Flow

```
  Phase -2 Triage 완료
      |
      v
  triage-result-{session_id}.json 생성
  + ambiguity_score (0-4)
      |
      v
  +-------------------+
  | ambiguity_score   |
  | >= 2 ?            |
  +---+-----------+---+
      |           |
     NO          YES
      |           |
      v           v
  Phase -1     intake-interviewer 발동
  직진         |
              v
            AskUserQuestion × 1-3개
              |
              v
            응답 결합 → goal_condition text
              |
              v
            goal_writer.py가
            state/active-goal-{session_id}.json 저장
            + 안전절 자동 첨가
              |
              v
            Phase -1 진입
```

## Q4 — 병렬 처리 방식 (공통 마지막 질문, 2026-05-19 추가)

Deep Interview의 **공통 마지막 질문**. domain별 1-3 질문(Q1-Q3) 이후 모든 cycle에서 발화.

### 발화 조건

- 항상 발동 (ambiguity_score 무관). 단:
  - `!quick` / `!just` / `!hotfix` Magic Word → skip
  - 사용자 평문에 multi-session 방식 명시(예: "claude agents로 처리해줘") → skip
  - 직전 cycle에서 동일 사용자가 선택한 방식이 있고 24h 이내 → 자동 재사용 (silent)

### 형식 (단일 추천 + 3 선택지 + 자율 default)

```
"이 작업의 병렬 처리 방식을 정해주세요."

  추천: {Claude 분석 결과 단일 추천안}
  근거: {1줄}

  다른 선택지:
    (A) Claude Agents      — 별도 OS 세션, 진짜 병렬
    (B) Subagent           — 같은 세션, 가장 가벼움
    (C) Superpowers Subagent — plan + 2-stage 자동 리뷰
    (D) Claude 자율         — 추천 그대로 (기본값)
```

### 추천 알고리즘 (의사코드)

**Signal 우선순위 (HARD RULE)**: 1 > 2 > 3 > default. `elif` chain short-circuit. 여러 신호 동시 매칭 시 상위 우선.

```python
def recommend(task):
    if task.estimated_lines < 100:                                       # Signal 1
        return ("B", "작업 작음 → 단발 위임")
    elif task.has_plan and task.independent_tasks_count >= 3:            # Signal 2
        return ("C", "plan + 독립 task 다수 → 2-stage 리뷰")
    elif task.long_running_streams >= 3 and task.estimated_hours >= 8:   # Signal 3
        return ("A", "큰 stream 다수 → 진짜 병렬 필요")
    else:
        return ("B", "scope 불확실 → 가장 가벼움")
```

**Signal 부재 시**: 5개 필드(`estimated_lines`, `has_plan`, `independent_tasks_count`, `long_running_streams`, `estimated_hours`) 중 1개라도 부재 → default(B). triage 산출 책임: `references/triage.md`.

**정본 spec**: `agents/core/intake-interviewer.md` "Q4 — 병렬 처리 방식" 섹션 (조합 매트릭스 + 마이그레이션 규칙 포함). 본 reference 의사코드는 요약.

### 저장

- `state/active-goal-{session_id}.json` 의 `interview_answers.multi_session_method` 필드 저장
- 값: `"A"` / `"B"` / `"C"` / `"D"` (자율 D 선택 시 `multi_session_method_resolved` 보조 필드에 추천 결과 함께 저장 → Phase 0+ 분기에서 재계산 불필요)
- **하위호환**: 옛 `processing_method` 필드(2026-05-15 RESTORED) 호환 매핑:
  - `"1"` (Claude 자율) → `"D"`
  - `"2"` (Parallel Agent in-session) → `"B"` (Subagent)
  - `"3"` (claude agents) → `"A"`
  - `"4"` (Background subagent) → `"B"`
  - `"5"` (Sequential) → `"B"` (보수 fallback)
- Phase 0+ 분기 로직은 3중 fallback 필수 (정본 spec: `agents/core/intake-interviewer.md` "필드명 마이그레이션" 섹션)

### Core Philosophy 정합

- 사용자 standing instruction에 의해 "단일 추천 + 3 선택지" 명시 형식 = 일반 A/B/C 금지 원칙의 **명시 예외**
- 자율 default(D) 선택 시 사용자 진입점 0 (추천 자동 적용)

## Ambiguity Score 산출 (Phase -2 책임)

| 지표 | 평가 | 점수 기여 |
|------|------|----------|
| 구체 명사 개수 | ≥3 / 1-2 / 0 | 0 / 0.5 / 1 |
| 동사 구체성 | 구현/수정/리팩토링 / 일반 / "만들어/해줘" | 0 / 0.5 / 1 |
| 수락 기준 추정 가능 | 명시 / 패턴매칭 / 불가 | 0 / 0.5 / 1 |
| 도메인 명시 | 있음 / 부분적 / 없음 | 0 / 0.5 / 1 |

총합 4점 만점. ≥2 = Deep Interview 발동.

## Output Contract

intake-interviewer 종료 시 다음을 보장:

1. `state/active-goal-{session_id}.json` 존재 + schema_version 1.1 (v1.0 호환 fallback)
2. `goal_condition` 필드가 verifiable terminal state 표현
3. 안전절 자동 첨가 완료 (20 turns / 200k tokens / 5 fails)
4. 사용자 진입점 ≤ 4회 (Q1-Q3 + Q4 multi-session, Q4 자율 default 시 진입점 0)
5. 응답 형식 사용자 비전 정합 (15세 수준 + 일상 비유 + escape)
6. `interview_answers.multi_session_method` 필드 저장 (`"A"`/`"B"`/`"C"`/`"D"` 중 하나)

## 비유

도서관 사서 안내데스크. 손님이 "그냥 책 한 권 주세요"라고 하면 사서가 "어떤 분야? 두꺼운 책? 가벼운 읽기?" 정확히 묻고 책장 위치를 알려줌. 5분의 인터뷰로 1시간 헛걸음 방지.

## 위반 감지

- 4개 이상 질문 시도 → 자동 압축
- escape 옵션 누락 → 자동 추가
- 사용자가 이미 평문에 명시한 항목 재질문 → 차단

## 관련

- `agents/core/intake-interviewer.md` — 실행 agent
- `lib/goal/goal_writer.py` — condition 저장 + 안전절
- `references/triage.md` — ambiguity_score 산출 책임
- Plan Section 2 — 전체 사양
