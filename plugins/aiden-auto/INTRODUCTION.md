# aiden-auto 플러그인 소개

> **한 줄 요약**: 120줄짜리 작은 안내데스크가 22개 스킬과 37개 에이전트를 호출하는 Claude Code 플러그인입니다.

버전 v28.1 · 라이선스 MIT · [garimto81/aiden-auto](https://github.com/garimto81/aiden-auto)

---

## 1. 왜 필요한가

Claude Code 플러그인 대부분은 **SKILL.md 한 파일에 모든 내용**을 담습니다. 사용자가 무엇을 하든 그 거대한 파일이 통째로 컨텍스트에 로드됩니다. 결과적으로:

- 정작 작업에 쓸 토큰이 줄어듭니다.
- 관련 없는 내용까지 매번 읽힙니다.
- 파일이 커질수록 응답 속도가 느려집니다.

aiden-auto는 이 문제를 **Index Router 패턴**으로 풀었습니다. SKILL.md를 120줄 안내데스크로 줄이고, 사용자의 의도에 맞는 챕터 1개만 그때그때 읽어옵니다.

---

## 2. 어떻게 작동하나 — Index Router

평문 한 문장이 들어오면 다음과 같이 흐릅니다.

```
  사용자 평문 입력
         |
         v
  +-----------------+
  | Index Router    |
  | (SKILL.md ≤120) |
  +--------+--------+
           |
           v
     index.yml 조회 (의도 분석)
           |
   +-------+--------+--------+--------+--------+--------+
   |       |        |        |        |        |        |
   v       v        v        v        v        v        v
 CODE    DOC       QA     ITER.   RESEARCH  MEDIA   HARNESS
 chap.   chap.    chap.   chap.    chap.    chap.    chap.
   |
   v
  해당 chapter 1개만 lazy load
   |
   v
  필요한 phase 1개만 추가 lazy load
   |
   v
  실제 작업 실행
```

**비유**: 거대한 도서관에 들어가는 대신 **안내데스크**에 갑니다. 안내원은 "어느 책이 필요하세요?"만 묻고 그 책 1권만 꺼내 줍니다. 책장 전체를 들고 다니지 않아도 됩니다.

| 의도 키워드 | 가는 챕터 | 다루는 일 |
|------------|---------|---------|
| "구현해줘", "버그 고쳐" | CODE | 코드 작성·수정 |
| "PRD 써줘", "문서 만들어" | DOC | 기획·요구사항 정리 |
| "테스트 추가", "E2E 검증" | QA | 품질·테스트 |
| "반복 개선", "iterate" | ITERATION | 자율 반복 사이클 |
| "조사해줘", "리서치" | RESEARCH | 코드/외부 조사 |
| "목업", "디자인" | MEDIA | UI·시각 자료 |
| "harness 업데이트" | HARNESS | 외부 프레임워크 추적 |

---

## 3. 5가지 핵심 특징

### (1) 자동 발동 — `/auto` 입력 불필요

평문으로 작업을 부탁하면 자동으로 `/auto` 워크플로우가 발동합니다. 예: "이 함수 리팩토링해줘"라고 쓰면 별도 명령 없이 CODE 챕터가 열립니다.

긴급할 때는 우회도 가능합니다:
- `!quick`, `!just`, `!hotfix` — 분석·검증 단계를 건너뛰고 즉시 실행

### (2) 자기개선 Harness 사이클 — 매일 자동 진화

외부 프레임워크(Claude Code CLI 본체, Vercel, Atlassian 등) 6개의 GitHub 업데이트를 **매일 자동 추적**합니다. 새 버전이 나오면 critic이 우리 5원칙과 부합하는지 평가하고, 통과 시 PR을 자동 생성합니다.

```
   매일 자동 발동
         |
         v
  +-----------------+
  | harness-watcher | 외부 framework 6개의
  | (haiku, daily)  | GitHub release 감지
  +--------+--------+
           |
           v
     변경 발견?
           |
           v
  +-----------------+
  | harness-critic  | 5가지 질문으로 평가
  | (opus, READ)    | (우리 5원칙 부합 여부)
  +--------+--------+
           |
           v
       APPROVE?
           |
     +-----+-----+
     |           |
     v           v
  +---------+ +---------+
  | applier | | 보고만  |
  | (PR 자동| | 종료    |
  |  생성)  | +---------+
  +---------+
       |
       v
  사용자 = PR 검토 1회만
```

**비유**: **식당의 매일 마감 회의**입니다. 영업이 끝나면 오늘 메뉴 어땠는지 직원들이 스스로 평가하고, 내일 레시피를 자동으로 다듬어 놓습니다. 사장님(=사용자)은 다음 날 아침 변경 사항만 한 번 확인하면 됩니다.

### (3) Autonomous Iteration V10.0 — 자율 반복

기능 구현이 한 번에 안 되면 자동으로 다시 시도합니다. 단순 재시도가 아니라 **건축 감리관 검사** 비유로 동작합니다:

- 설계도(spec)를 90% 재현 가능한가? → 통과해야 다음 층 허가
- 변형(drift)이 누적되고 있는가? → 감소 추세여야 함
- 빠진 항목이 0인가?

세 조건이 모두 통과될 때까지 자율로 재시공합니다. 무한 루프 방지를 위해 Circuit Breaker 한계(3·5·3·1회)를 둡니다.

### (4) 다관점 병렬 검증 — Phase 3

코드 작업의 검증 단계에서는 **네 명의 평가자가 동시에** 봅니다:

| 평가자 | 보는 것 |
|--------|--------|
| architect | 설계 정합성 |
| security-reviewer | 보안 결함 |
| code-reviewer | 코드 품질 |
| qa-tester | 테스트 통과 |

한 명이 놓치는 결함을 다른 세 명이 잡습니다. 모두 통과해야 Phase 4(close)로 넘어갑니다.

### (5) 작은 입구 · 거대한 도구 — "슈퍼앱"

진입점(SKILL.md)은 120줄로 작지만, 그 뒤에 도구 162개가 대기합니다. 사용자는 도구를 직접 호출할 필요가 없습니다 — Index Router가 알아서 꺼내 줍니다.

---

## 4. 구성 요소 한눈에

```
  aiden-auto v28.1 (총 162개)
     |
     +-- skills/        22개  (auto + 21개 도구 skill)
     |
     +-- agents/        37개  (opus / sonnet / haiku 혼합)
     |     +-- core/          2  기본 진행 에이전트
     |     +-- creative/      2  카탈로그·doc-critic
     |     +-- domain/        8  cloud·data·db·devops·frontend·github
     |     +-- iteration/    13  V10.0 자율 반복 (curator, runner 등)
     |     +-- meta/          8  harness 3 + advisor 5
     |     +-- verification/  4  architect 외 검증자
     |
     +-- hooks/         27개  (session·edit·iteration 트리거)
     +-- references/    36개  (chapter 7 + phase 7 + 정책 22)
     +-- commands/      20개  (/auto, /commit, /pr 등)
     +-- rules/          8개  (TDD, PRD-first, SSOT 등)
     +-- lib/           13개  (jira·slack·gmail 통합 모듈)
```

> 약어 풀이 — PRD: Product Requirements Document(제품 요구사항 문서) · SSOT: Single Source of Truth(단일 정본) · TDD: Test-Driven Development(테스트 우선 개발) · PR: Pull Request(병합 요청)

---

## 5. 설치와 사용법

### 설치

Claude Code 마켓플레이스(권장):

```bash
/plugin install garimto81/aiden-auto
```

또는 로컬 개발용 git clone:

```bash
git clone https://github.com/garimto81/aiden-auto ~/.claude/plugins/aiden-auto
```

### 사용

설치 후 `/auto`라고 입력할 필요 없습니다. 평문으로 부탁만 하면 됩니다.

| 입력 예 | 자동 라우팅 결과 |
|--------|-----------------|
| "이 함수 리팩토링해줘" | CODE 챕터 → executor + architect 검증 |
| "PRD 초안 작성" | DOC 챕터 → planner + writer + critic |
| "테스트 추가" | QA 챕터 → qa-tester + executor |
| "이 버그 디버깅" | CODE 챕터 → architect 분석 D0-D4 |

긴급 우회:

```
!quick 오타 하나만 고쳐줘    ← 분석·검증 스킵, 즉시 실행
!hotfix 프로덕션 다운 났어   ← 최단 경로
```

---

## 6. 다음 단계

설치를 마쳤다면, 가장 작업해야 할 코드 파일이 열린 상태에서 한 문장 부탁해 보세요:

```
이 파일 코드 정리해줘
```

Index Router가 알아서 CODE 챕터를 열고, executor가 정리를 시작하고, architect가 검증을 마치면 결과만 보고합니다. 사용자 진입점은 그 한 문장이 전부입니다.

---

## 한 줄 요약 (다시)

> **작은 입구로 거대한 도구를 부르는 플러그인** — 평문 한 줄이 챕터 라우팅, 다중 에이전트 검증, 자율 반복까지 흐릅니다.
