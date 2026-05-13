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

1. `state/active-goal-{session_id}.json` 존재 + schema_version 1.0
2. `goal_condition` 필드가 verifiable terminal state 표현
3. 안전절 자동 첨가 완료 (20 turns / 200k tokens / 5 fails)
4. 사용자 진입점 ≤ 3회 (최대 3개 질문)
5. 응답 형식 사용자 비전 정합 (15세 수준 + 일상 비유 + escape)

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
