---
name: root-cause
description: >
  문제의 근본 원인을 추적해서 비개발자도 한눈에 이해하는 보고서로 만들어 주는 스킬.
  에러·테스트 실패·배포 사고·hook/sync 이상·"왜 이렇게 됐지" 같은 의문이 나오면
  반드시 사용한다. 기존 tracer + user-friendly-reporter 를 묶어 "조사 → 완성 보고서 →
  수정 제안" 까지 한 번에 처리한다. 수정은 제안만 하고 직접 적용하지 않는다 (READ-ONLY).
  실제로 뭔가 실패·오작동한 상황의 원인을 찾을 때 적극 사용할 것. 직접 grep 으로 뒤지기 전에 먼저.
  단, "그냥 빨리 고쳐만 줘"(수정만 원함)·"이 파일 보여줘"(읽기)·"왜 GIL 을 쓰나" 같은
  일반 지식 질문에는 쓰지 않는다 (조사할 실제 문제가 있을 때만).
version: 1.0.1
triggers:
  keywords:
    - "root cause"
    - "trace root cause"
    - "근본 원인"
    - "원인 추적"
    - "원인 분석"
    - "왜 이렇게 됐"
    - "이거 왜 안"
    - "왜 안 돼"
    - "왜 실패"
  context:
    - "에러/예외/traceback 의 원인을 알고 싶을 때"
    - "테스트·빌드·배포가 실패한 이유를 찾을 때"
    - "framework hook/sync/agent 라우팅이 이상하게 동작할 때"
auto_trigger: true
dependencies:
  - tracer
  - user-friendly-reporter
token_budget: 1500
---

# Root Cause — 원인 추적 + 비개발자 보고서

증상이 아니라 **근본 원인**을 찾고, 그 결과를 15세도 이해하는 보고서로 만든다.
조사 엔진은 새로 만들지 않고 이미 있는 `tracer` + `user-friendly-reporter` 를 묶는다.

## When to use

- 에러 메시지 / traceback / 테스트 실패 / 잘못된 동작의 "왜" 를 알아야 할 때
- 배포·운영 사고의 원인을 찾을 때
- framework 자체 이상 (hook 안 돔, sync drift, agent 라우팅 오류) 을 추적할 때
- 사용자가 "이거 왜 이래", "왜 안 돼", "근본 원인" 등을 물을 때

> 단순 "이 파일 보여줘" / "이게 뭐야" 같은 질문에는 쓰지 않는다 (직접 응답).

## 전체 흐름

```
   문제 입력
      │
      ▼
  [Phase 0] 문제 분류 ── code버그 / 운영사고 / framework / unknown
      │
      ▼
  [Phase 1] 원인 추적 ── tracer agent (3-lane 인과 조사, READ-ONLY)
      │                  코드버그면 systematic-debugging 증거기법 참조
      ▼
  [Phase 2] 후보 순위 ── impact × likelihood 정렬 + 모르는 점 정리
      │
      ▼
  [Phase 3] 보고서 ──── user-friendly-reporter 평이화 + 수정 "제안"
                        (수정은 적용하지 않음)
```

## Phase 0 — 문제 분류

입력 신호로 유형을 정한다 (애매하면 unknown 으로 두고 Phase 1 이 판별).

| 신호 | 분류 |
|------|------|
| traceback / 컴파일 오류 / 테스트 실패 로그 | 코드버그 |
| 배포 로그 / 5xx / 컨테이너·K8s·CI 실패 | 운영사고 |
| hook 미발동 / sync drift / agent 라우팅 이상 | framework |
| 위에 안 맞거나 정보 부족 | unknown |

## Phase 1 — 원인 추적 (조사 엔진 재사용)

`tracer` agent 를 호출한다. prompt 에 Phase 0 분류 + 증상 + 재현 조건을 담는다.

```
Agent(subagent_type="tracer",
      description="근본 원인 3-lane 조사",
      prompt="분류=<Phase0 결과>\n증상=<현상>\n재현=<조건>\n"
             "3-lane (code-path / config-env / assumption) 으로 조사하고 "
             "ranked candidates + Critical Unknowns 를 반환하라.")
```

- 코드버그 분류면, `superpowers:systematic-debugging` 의 증거수집 기법(layer 경계마다
  로그 확인, 데이터 흐름 추적)을 tracer prompt 에 추가 지시한다.
- tracer 는 READ-ONLY — 코드를 바꾸지 않는다. 이 스킬도 그 철학을 그대로 따른다.

## Phase 2 — 후보 순위

tracer 가 돌려준 root cause 후보를 정리한다.

- impact(영향 크기) × likelihood(확률) 로 정렬
- 증거가 부족해 단정 못 하는 항목은 **Critical Unknowns** 로 따로 표시
- 후보가 1개로 좁혀지면 그 근거를, 여러 개면 상위 2~3개를 보고서로 넘긴다

## Phase 3 — 보고서 + 수정 제안

`user-friendly-reporter` agent 를 호출해 결과를 15세 기준으로 평이화한다.
형식 상세는 `references/report-template.md` 를 따른다.

```
Agent(subagent_type="user-friendly-reporter",
      description="원인 보고서 평이화",
      prompt="아래 조사 결과를 비개발자용 보고서로 변환하라.\n"
             "TL;DR → 무슨 일 → 진짜 원인(비유) → 근거 → 수정 제안 순서.\n"
             "수정 제안은 '제안'으로만 쓰고 적용하지 마라.\n조사결과:\n<Phase2 결과>")
```

**수정은 제안만 한다.** 실제 적용은 사용자가 보고 결정한다 (`/debug` 가 수정 실행 담당).
사용자가 "그대로 고쳐줘" 라고 명시하면 그때 별도로 수정 작업에 들어간다.

## /debug 와 차이

| | root-cause | /debug |
|--|-----------|--------|
| 헤드라인 | 원인 추적 + 비개발자 보고서 | D0~D4 풀 수정 사이클 |
| 수정 | 제안만 (적용 X) | 실제 수정·검증 포함 |
| 산출물 | 평이한 보고서 | 수정된 코드 + 회고 |

## 한계

- READ-ONLY 라 코드를 직접 고치지 않는다 (의도된 동작).
- 재현 정보가 거의 없으면 tracer 가 Critical Unknowns 만 돌려줄 수 있다 →
  보고서에 "더 필요한 정보" 를 명시하고 멈춘다 (추측으로 단정하지 않는다).
