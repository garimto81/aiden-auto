# Phase -2: Requirement Triage (NEW v27.0)

> **목적**: 사용자 요구를 분석하여 어떤 카테고리(DOC/CODE/QA/ITERATION/RESEARCH/MEDIA)에 속하는지 결정하고, 모호성을 사전 명확화하여 Phase 0-4의 모든 단계를 사전 설계한다.
>
> **트리거**: `/auto` 호출 직후 (Phase -1보다 먼저)
>
> **목표 산출물**: `TriageContract` — 카테고리, 모호성 해결 결과, Phase 경로, Agent Team 구성

---

## 핵심 원칙 (사용자 = 바이브 코더 가정)

| 원칙 | 의미 |
|------|------|
| **사전 = 질문 OK** | Phase -2 단계에서만 상세 질문 허용 (모든 phase/task 사전 설계 목적) |
| **실행 중 = 자율** | Phase -1 진입 후엔 architect 검증 + 자율 결정. 결정 점에서 사용자에게 옵션 나열 금지 |
| **종료 = 무한 iteration 방지** | e2e zero-error까지, 단 5회 실패 시 사용자 보고 |
| **기술 선택지 X** | 사용자에게 A/B/C 기술 옵션 나열 금지 (인덱싱 형식, push 방법, 인프라 선택 등). 의미 차원 질문만 |
| **다이어그램 우선** | 명확화 시 텍스트 대신 그림/예시로 |
| **결정 점 자율 + 보고** | 변경 발생 시 자율 결정 + 결과만 친절 설명. "어떻게 할까요?" 금지 |

## 절대 금지 패턴 (CRITICAL)

이 패턴들은 워크플로우 위반으로 즉시 감지되어야 한다:

### 위반 1: 기술 옵션 나열 (A/B/C 4지선다)

```
❌ 금지 예시:
"3가지 옵션이 있습니다:
  A. 새 브랜치 + PR
  B. main 직접 적용
  C. push 보류
어느 것을 선택하시겠습니까?"

✅ 올바른 패턴:
"새 브랜치로 분기하여 PR 생성했습니다 — https://github.com/.../pull/198
이유: main 직접 수정은 위험하고, PR이 marketplace 자동 sync 트리거가 됩니다."
```

### 위반 2: 인프라/포맷 선택지

```
❌ 금지: "인덱싱 형식은 A: YAML lookup / B: tag search / C: script 중 어느 것?"
✅ 올바름: "도서관 카탈로그 방식(index.yml)으로 했습니다 — 이런 비유로 설명..."
```

### 위반 3: 결정 떠넘기기

```
❌ 금지: "fallback 처리 방법은 무엇으로 할까요?"
✅ 올바름: "fallback은 project-level wrapper로 구현했습니다 (이유: ...)"
```

### 감지 시 자동 대응

위 패턴 감지 시 즉시:
1. 옵션 나열 중단
2. Claude가 자율 결정 (best practice 기준)
3. 결과 + 이유 + 비유로 보고
4. `feedback_propose_then_execute` 메모리 트리거

---

## Step -2.0: Lookup Index + Communication Style

```
1. ${SKILL_DIR}/references/index.yml 로딩 (필수)
2. ${SKILL_DIR}/references/communication-style.md 로딩 (필수, v27.1+)
   → 모든 응답을 15세 기준 + 비유 + 다이어그램 형식으로 강제
3. 사용자 입력에서 키워드 매칭
4. 1차 카테고리 후보 + confidence 계산
```

**communication-style.md 로딩 효과**:
- 응답 작성 전 자가 점검 체크리스트 적용
- 기술 용어 등장 시 비유 사전 lookup
- 약어/A-B-C 옵션 등 위반 패턴 즉시 차단
- 카테고리별 chapter도 이 스타일을 강제 상속

---

## Step -2.1: 1차 자동 분류

| confidence | 판정 | 다음 단계 |
|:----------:|------|----------|
| ≥ 0.7 | 카테고리 확정 | Step -2.2로 (모호성 점검만) |
| 0.4-0.7 | 모호 | Step -2.3 명확화 질문 |
| < 0.4 | 미분류 | Step -2.3 카테고리 질문 |

confidence 계산:
- 키워드 매칭 수 × 0.3 (최대 0.6)
- 사용자가 명령어 옵션 사용 (`--mode=`) 시 +0.4
- 이전 대화 컨텍스트 일치 +0.2

---

## Step -2.2: 모호성 패턴 감지 (5대 패턴)

`index.yml`의 `ambiguity_patterns` 키 lookup:

### 패턴 1 — 감각적 표현
**감지**: "예쁘게", "깔끔하게", "세련되게"
**대응**:
```
"감각 표현 감지했습니다. 3가지 스타일 중 가까운 걸 골라주세요:"

  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │ 미니멀   │ │ 모던     │ │ 클래식   │
  │ (예시)   │ │ (예시)   │ │ (예시)   │
  └─────────┘ └─────────┘ └─────────┘
```

### 패턴 2 — 암묵 가정
**감지**: "당연히", "기본적으로", "그냥"
**대응**:
```
"이렇게 가정했습니다 — 맞나요? (틀리면 1줄로 알려주세요)
  · 가정 1: ...
  · 가정 2: ...
"
```

### 패턴 3 — 범위 모호
**감지**: "다", "전부", "여러"
**대응**:
```
"정확한 범위 확인:
  · 대상 파일/모듈: ?
  · 개수: 몇 개?
"
```

### 패턴 4 — 느낌 기반 거부 (실행 중 발생)
**감지**: "뭔가 이상", "어색"
**대응**:
- critic agent 재검토 자동 트리거
- 가설 3개 제시 → 사용자 1개 선택

### 패턴 5 — 기술 무관심
**감지**: "그냥 되게만", "알아서"
**대응**:
- Claude 자율 결정 + 결과만 비유로 보고
- "이렇게 만들었습니다 — [비유로 설명]"

---

## Step -2.3: 카테고리 명확화 질문 (confidence < 0.7)

confidence 가 0.7 미만이면 작업 종류를 1회만 묻는다. **AskUserQuestion tool 직접 호출** (가르침 #6 — chat inline 표 / 자유 텍스트 질문 금지):

```
AskUserQuestion(
  question="어떤 종류의 작업인지 확인할게요. 가까운 걸 하나 골라주세요.",
  header="작업 종류",
  multiSelect=false,
  options=[
    {label: "기획·PRD 작성", description: "무엇을 만들지 정리하는 기획 문서를 씁니다. 예: '결제 모듈 기획해줘'"},
    {label: "기능 구현·수정", description: "실제 코드를 새로 만들거나 고칩니다. 예: '로그인 추가해줘'"},
    {label: "테스트·검증", description: "이미 만든 것이 잘 도는지 확인합니다. 예: 'E2E 돌려줘'"},
    {label: "반복·drift 검증", description: "빠뜨린 부분을 반복해서 찾아 채웁니다. 예: '미구현 5개 처리'"},
    {label: "조사·분석", description: "자료를 찾아보고 정리해 드립니다. 예: '최신 트렌드 알아봐'"},
    {label: "UI 목업·디자인", description: "화면이 어떻게 생길지 그림으로 보여드립니다. 예: '화면 와이어프레임'"}
  ]
)
```

선택된 label 로 카테고리 확정 (기획·PRD 작성→DOC / 기능 구현·수정→CODE / 테스트·검증→QA / 반복·drift 검증→ITERATION / 조사·분석→RESEARCH / UI 목업·디자인→MEDIA).

---

## Step -2.4: Phase 경로 + Agent Team 결정

`index.yml`의 `categories[CAT].typical_phase_path` + `agent_team` lookup:

| 카테고리 | Phase 경로 | Agent Team |
|---------|-----------|-----------|
| DOC | -2 → -1 → 0 → 1 → 4 | planner + writer + critic + architect |
| CODE | -2 → -1 → 0 → 1 → 2 → 3 → 4 | executor + architect + code-reviewer + qa-tester |
| QA | -2 → -1 → 0 → 3 → 4 | qa-tester + architect + executor |
| ITERATION | -2 → -1 → 0 → 1 → 2 → 3 → loop → 4 | iteration-curator-a/b + drift-reconciler + executor + architect |
| RESEARCH | -2 → -1 → 0 → 1 → 4 | researcher + analyst + writer |
| MEDIA | -2 → -1 → 0 → 1 → 2 → 4 | designer + writer + executor |

---

## Step -2.5: TriageContract 생성

```yaml
TriageContract:
  category: "CODE"  # DOC | CODE | QA | ITERATION | RESEARCH | MEDIA
  confidence: 0.85
  ambiguity_resolved:
    - pattern: "vague_aesthetic"
      user_answer: "미니멀"
    - pattern: "implicit_assumption"
      user_answer: "맞음"
  phase_path: [-2, -1, 0, 1, 2, 3, 4]
  skip_phases: []
  agent_team: [executor, architect, code-reviewer, qa-tester]
  iteration_loop: false  # ITERATION 카테고리이거나 e2e fail 시 true
  hot_swap: false
  drift_check: false
  user_summary: |
    # 사용자에게 1줄 요약 (실행 시작 전 마지막 확인)
    "이 작업은 [기능 구현]입니다.
     [executor + architect + code-reviewer]로 팀을 짜서
     [Phase 1 계획 → 2 구현 → 3 검증 → 4 보고서] 순으로 진행합니다.
     변경사항 발생 시 알아서 결정하고 결과만 알려드릴게요."
```

---

## Step -2.6: 사용자 1줄 확인

Triage 결과를 보여주고 진행 여부를 확인한다. **AskUserQuestion tool 직접 호출** (가르침 #6):

```
AskUserQuestion(
  question="""정리했어요. 이렇게 진행할게요:

  무엇: CODE (기능 구현)
  누가: executor + architect + code-reviewer + qa-tester
  순서: 계획 → 구현 → 검증 → 보고서
  언제 끝: e2e 통과까지 자동 반복

이대로 진행할까요?""",
  header="Triage 확인",
  multiSelect=false,
  options=[
    {label: "이대로 진행", description: "위 계획 그대로 시작합니다. (권장 — 바꿀 게 없으면 이걸 고르세요)"},
    {label: "수정 후 진행", description: "바꾸고 싶은 부분을 알려주시면 반영한 뒤 시작합니다."}
  ]
)
```

→ "이대로 진행" 선택 시 Phase -1 진입. "수정 후 진행" 선택 시 수정사항을 받아 Triage 갱신 후 재확인.
→ **5초 무응답 자동진입 보존**: AskUserQuestion 응답이 5초 안에 없으면 "이대로 진행" 으로 간주하고 Phase -1 자동 진입 (사용자 흐름을 막지 않기 위함 — 무응답 = 동의).

---

## 평문 트리거 처리 (사용자 명령어 없이 평문 입력 시)

`index.yml`의 `plain_text_triggers` lookup:

```
1. enabled_patterns 매칭 → /auto 자동 발동 → Phase -2 진입
2. disabled_patterns 매칭 → /auto 미발동, Claude 일반 응답
3. Magic Word (!quick, !just, !hotfix) → /auto 미발동, 즉시 실행
```

### 예시

| 사용자 입력 | 발동 여부 | 이유 |
|------------|:--------:|------|
| "로그인 기능 구현해줘" | ✅ | "구현해" 매칭 |
| "이 파일 뭐야?" | ❌ | "뭐야" 매칭 |
| "결제 API fix" | ✅ | "fix" 매칭 |
| "보여줘" | ❌ | 단순 read |
| "!quick 오타 수정" | ❌ | Magic Word bypass |

---

## Legacy alias 처리

| 사용자 입력 | redirect |
|------------|---------|
| `/iteration` | `/auto --mode=iteration` |
| `/iterate` | `/auto --mode=iteration` |
| `/cycle` | `/auto --mode=iteration` |
| `/aiden-auto:auto` | `/auto` (동일 SKILL.md) |
| `ralph: ...` | `/auto "..."` |
| `ulw: ...` | `/auto "..."` |
| `ultrawork: ...` | `/auto "..."` |
| `autopilot ...` | `/auto "..."` |

---

## 종료 후 진입

`TriageContract` 완성 → Phase -1 (`phase-minus-1-context-detect.md`) 진입.
