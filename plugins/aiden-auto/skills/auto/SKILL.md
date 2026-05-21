---
name: auto
description: >
  Index Router (v28.7) — 사용자 평문을 분석하여 적절한 chapter만 lazy load. v28.7: Phase -1.5 Part E 신규 (Atlassian MCP 인증 자율 점검 — Atlassian 키워드/Part C 활성화/atlassian skill 호출 감지 시만 호출, 미감지 시 호출 자체 없음). v28.6 base: Part D Executive Summary 자율 판단. v28.5 base: Confluence sync (Part C). v28.4 base: Phase -2/-1.5 통합 + brainstorming + @ multi-session + /goal 자율 iteration 본질 재정의 + superpowers 12 skill 매트릭스.
  Auto-trigger ON. Skip for trivial questions, file reads, !quick/!hotfix.
  /aiden-auto:auto / /iteration / iterate / /goal 모두 이 SKILL로 redirect.
  (multi-session 운영은 공식 `claude agents` CLI로 위임 — 2026-05-14 폐기)
version: 28.7.0
auto_trigger: true
output_style: user_friendly  # v28.3 Section 16 — 비개발자 친화 자세한 보고. user-friendly-reporter agent 의무 통과
triggers:
  keywords:
    - "/auto"
    - "auto"
    - "autopilot"
    - "/iteration"
    - "iterate"
    - "cycle"
    - "/goal"
    - "goal"
    - "목표"
    - "쿼타"
    - "quota"
---

# /auto — Index Router (v28.3)

> **안내 데스크 역할**. 본인은 작고, 가리키는 책장은 큽니다. 도서관이 클수록 안내 데스크는 작아야 합니다.

## 5가지 핵심 원칙 (HARD ENFORCE — 모든 chapter 공통)

1. **외부 harness framework 그대로 유지** — bkit-claude-code, anthropics/claude-code, vercel, atlassian, superpowers 등은 *복사하지 않고 참조만*. 매일 자동 update 체크는 `agents/meta/harness-watcher`가 담당.

2. **자가개선 critic 사이클** — 외부 framework update 발견 시 `agents/meta/harness-critic`이 우리 5원칙(특히 진입점 최소화)에 부합하는지 critic으로 검토. APPROVE 시 `agents/meta/harness-applier`가 patch + PR 자동 생성.

3. **SKILL.md = 최소 진입점** — 이 파일은 ≤120줄 유지. 모든 상세는 `references/`로 lazy load. *거대 문서 한 번에 통째 읽는 패턴 금지*.

4. **Intent → Chapter 라우팅** — 평문 메시지 분석 → `references/index.yml` lookup → chapter 1개만 로드. Phase 진입 시 해당 phase reference 1개만 로드.

5. **스킬/커맨드/워크플로우 = 방대 (슈퍼앱)** — SKILL.md는 작아도 그 뒤의 24 skills + 20 commands + 31 agents가 슈퍼앱 역할. 진입점 작고 도구 풍부.

## 진입 흐름

```
사용자 평문 (또는 /auto, /iteration)
            │
            ▼
   ┌───────────────────────────┐
   │ Step 0: Index Lookup      │  ← references/index.yml 만 로드
   │  Read(index.yml)          │
   │  Read(communication-style)│
   └─────────────┬─────────────┘
                 │
                 ▼
   ┌───────────────────────────┐
   │ Step 0.5: Model Router    │  ← Agent(model-router, model=haiku)
   │  → JSON model_plan        │     advisor pattern 강제
   │  → 후속 Agent() model 주입│
   └─────────────┬─────────────┘
                 │
                 ▼
   ┌───────────────────────────┐
   │ Phase -2: Triage          │  ← 모호 시만 references/triage.md
   │  (1줄 의미 차원 확인)       │
   └─────────────┬─────────────┘
                 │
                 ▼
   ┌───────────────────────────┐
   │ Chapter Load (1개만)       │  ← references/chapter-{CAT}.md
   │  DOC/CODE/QA/ITER/RES/MED │
   └─────────────┬─────────────┘
                 │
                 ▼
   Phase -1 → 0 → 1 → 2 → 3 → 4
   (chapter 지정 경로만, 각 phase 진입 시 해당 phase reference 1개만 로드)
```

## Step 0: Index Lookup (MANDATORY)

`/auto` 또는 평문 트리거 시 **반드시 먼저**:

```
Read("references/index.yml")
Read("references/communication-style.md")
```

`index.yml` = 도서관 카탈로그 (카테고리/chapter/Agent/Phase 매핑 + 평문 트리거 화이트리스트).
`communication-style.md` = 15세 기준 응답 룰 (비유/다이어그램/표 우선, A/B/C 옵션 나열 금지).

## Step 0.4: User-Friendly Reporter 사전 게이트 (MANDATORY, v28.3+)

Step 0 직후, 사용자 향 모든 응답 작성 직전에 본 agent 통과 의무:

```
Agent(
  subagent_type="user-friendly-reporter",
  model="haiku",
  description="응답 친절 변환",
  prompt="원본_보고=<Claude 응답 초안>"
)
→ 친절 변환된 텍스트
```

**자동 발동 조건** (어느 하나라도):
- 응답에 전문용어 (skill / agent / hook / subagent / critic / refactor / API / schema) 등장
- "어떻게 할까요?" / "진행할까요?" / "확인 부탁드립니다" 패턴
- 응답 50줄 초과
- A/B/C 옵션 나열
- 약어 (NTFS/HVAC/SSOT 등) 첫 등장 풀이 누락

**위반 시 처리**: 응답 작성 중단 → 본 agent 재호출 → 친절 변환된 출력 사용.

## Step 0.5: Model Router 호출 (MANDATORY, HARD ENFORCE — v28.3+)

Step 0 직후, Phase -2 진입 전에 **반드시**:

```
Agent(
  subagent_type="model-router",
  model="haiku",
  description="model_plan 산출",
  prompt="task=<사용자 원문>\ncategory=<index.yml 매핑 결과 or unknown>\ncontext=<직전 1-2줄>"
)
→ JSON model_plan 응답 (31 keys, 하이픈 표기)
```

**응답 처리**:

| 케이스 | 처리 |
|--------|------|
| 파싱 성공 | `plan` 객체 저장. 후속 모든 Agent() 호출에 `model=plan["<role>"]` 명시 주입 |
| 파싱 실패 | 전체 sonnet 폴백 + **사용자 명시 알림 필수** (architect/security-reviewer 등 고복잡도 역할이 sonnet으로 실행됨 경고) |
| 재호출 | 1회 시도. 재실패 시 sonnet 폴백 유지 + 알림 |

**Tier 접미사 (`-high` / `-low`) 처리**:
- `executor-high` → `plan["executor"]`의 한 단계 상향 (sonnet → opus)
- `executor-low` → `plan["executor"]`의 한 단계 하향 (sonnet → haiku)

scope/complexity 급변 시 (파일 수 폭증, 보안 영역 추가 등) router 재호출.

**기본 동작** (안내, v28.3 정책 critic audit P2-7 완화):

| 상황 | 자동 처리 |
|------|----------|
| Step 0.5 미실행 | advisor pattern 미작동 → 다음 Agent() 호출 직전 자동 재호출 |
| model 미주입 | agent frontmatter의 model 사용 (대부분 sonnet fallback) |
| router 응답 파싱 실패 | 전체 sonnet 자동 폴백 → Phase 4 보고서 푸터에 기록 (즉시 사용자 인터럽트 없음) |

상세 정책: 글로벌 CLAUDE.md § Dynamic Model Routing (Advisor Pattern v1) 참조.

## Phase -2 + -1.5: Deep Interview (brainstorming + @, v28.4+)

Step 0.5 직후, 평문 분석과 함께 Deep Interview 즉시 발동.

```
   평문 입력
        │
        ▼
   Phase -2 평문 1차 분석 (카테고리 + ambiguity)
        │
        ▼
   ┌────────────────────────────────────────┐
   │ Phase -1.5 (평문 직후 즉시 발동)        │
   │                                        │
   │ Part A: brainstorming (의도 명료화)      │
   │   Skill("superpowers:brainstorming")    │
   │   · 1 question at a time                │
   │   · 2-3 approaches + 사용자 승인         │
   │   · docs/superpowers/specs/*.md 산출    │
   │                                        │
   │ Part B: @ (multi-session 처리 방식 선택) │
   │   · 추천 + 4 선택지 (A/B/C/D)            │
   │   · multi_session_method 필드 저장      │
   │                                        │
   │ Part C: Confluence sync (DOC 전용)       │
   │   · YES update / YES new / NO           │
   │                                        │
   │ Part D: Executive Summary (v28.6 신규)  │
   │   · DOC + 휴리스틱 충족 시만 질문 추가   │
   │   · 미충족 시 자동 skip (질문 X)         │
   │   · executive_summary 필드 저장          │
   │                                        │
   │ Part E: Atlassian 인증 점검 (v28.7 신규)│
   │   · Atlassian 키워드/skill/Part C 감지   │
   │   · 미감지 시 호출 자체 없음 (부하 0)    │
   │   · atlassian_auth.py executor 호출      │
   └─────────────────┬──────────────────────┘
                     │
                     ▼ (spec → active-goal.json 변환)
   /goal 자율 iteration 시동
```

**Skip 조건**: `!quick` / `!just` / `!hotfix` Magic Word, /goal 명시 condition.

**Part B 선택지**:
- A. Claude Agents (별도 OS 세션) — 큰 task N개 / 1일+
- B. Subagent (같은 세션) — 단발 위임 / 가장 가벼움
- C. Superpowers Subagent — plan + 2-stage 자동 리뷰
- D. Claude 자율 (기본값) — 추천 결과 그대로 적용

상세: `references/phase-minus-1.5-deep-interview.md`.

## /goal 자율 Iteration Loop (v28.4 본질 재정의)

> **/goal = "자율 다음 단계 진행 + 자율 판단 다음 단계 처리 + 자율 처리할 게 없을 때 QA + 스크린샷 엄격 검증 + 모든 단계 통과 시 사용자 보고"**

**3 멈춤 조건**:
1. 자율 처리할 게 더 없음 → QA + 스크린샷 검증 진입
2. 안전절 트립 (20 turns / 200k tokens / 5 fails) → 강제 멈춤 + 보고
3. 진짜 막힘 (외부 정보 필요) → 사용자 결정 영역 1줄 보고

**Phase 4 QA Gate (Visual 작업 시)**: 스크린샷 ≥ 3장 의무.

상세: `references/goal-operation.md`.

## 카테고리 → Chapter 매핑

| 카테고리 | Chapter 파일 | Phase 경로 | Agent Team |
|---------|--------------|-----------|-----------|
| **DOC** | `chapter-doc.md` | -2 → -1 → 0 → 1 → 4 | planner + writer + critic + architect |
| **CODE** | `chapter-code.md` | -2 → -1 → 0 → 1 → 2 → 3 → 4 | executor + architect + code-reviewer + qa-tester |
| **QA** | `chapter-qa.md` | -2 → -1 → 0 → 3 → 4 | qa-tester + architect + executor |
| **ITERATION** | `chapter-iteration.md` | -2 → -1 → 0 → 1 → 2 → 3 → loop → 4 | iteration-curator-a/b + drift-reconciler + executor + architect |
| **RESEARCH** | `chapter-research.md` | -2 → -1 → 0 → 1 → 4 | researcher + analyst + writer |
| **MEDIA** | `chapter-media.md` | -2 → -1 → 0 → 1 → 2 → 4 | designer + writer + executor |

## 자가개선 사이클 (외부 harness 추적 — 원칙 1+2 실행)

```
매일 자동 (또는 daily hook 발동)
    │
    ▼
┌───────────────────────────────┐
│ harness-watcher (haiku, daily)│
│  external-harness-registry    │
│  → GitHub API로 신규 tag/release│
│  → diff 요약 산출              │
└──────────────┬────────────────┘
               │ 신규 update 발견
               ▼
┌───────────────────────────────┐
│ harness-critic (opus)         │
│  우리 5원칙 부합 여부 판정      │
│  · 진입점 줄이는가?            │
│  · 자율 이터레이션 늘리는가?    │
│  · 복사 아닌 참조로 가능한가?   │
└──────────────┬────────────────┘
               │ APPROVE
               ▼
┌───────────────────────────────┐
│ harness-applier (sonnet)      │
│  patch 생성 → branch + PR     │
└───────────────────────────────┘
```

추적 대상 등록: `references/external-harness-registry.md`.

## Progressive Disclosure 로딩 규칙

| 시점 | 로드 |
|------|------|
| 진입 | `index.yml` + `communication-style.md` |
| Phase -2 | `triage.md` (모호 시만) |
| Phase -1.5 entry (v28.4+) | `phase-minus-1.5-deep-interview.md` + `Skill("superpowers:brainstorming")` |
| Phase -1.5 Part C (v28.5+, DOC만) | `confluence-sync-flow.md` (Confluence sync 선택 시) |
| Phase -1.5 Part D (v28.6+, DOC만, 자율 판단 충족 시) | `executive-summary-template.md` (자율 판단 휴리스틱 + 양식) |
| Phase -1.5 Part E (v28.7+, Atlassian 사용 감지 시만) | `~/.claude/hooks/atlassian_auth.py` (executor wrapper) + `agents/meta/atlassian-auth-{executor,advisor}.md` |
| /goal 자율 iteration 시동 | `goal-operation.md` |
| Phase 1.3 (DOC, v28.6+, `executive_summary.enabled=true` 시) | `executive-summary-template.md` (Executive Summary 양식 + 검증 룰) |
| Chapter 확정 | `chapter-{CAT}.md` (1개) |
| Phase 진입 | `phase-{N}-*.md` (해당 phase 1개) |
| Plan→Design 전환 | `plan-design-gate.md` (CODE/ITERATION chapter, 자동) |
| 복잡도 산정 직후 | `ml-assist.md` (`.claude/ml/.ml_session_state.json` 존재 시만) |
| Phase 진입 전 토큰 절약 | `compaction-gate.md` (조건부: score>=4 OR load>15KB OR effort=high) |
| critic 호출 시 (verdict 통일) | `critic-protocol-unified.md` (5 기존 critic + compaction-critic) |
| HARNESS chapter (운영) | `chapter-harness.md` ("harness 상태" 평문 트리거) |
| 옵션 사용 | `options-handlers.md` |
| 외부 harness 추적 | `external-harness-registry.md` (harness-watcher 매일 자동, superpowers 12 skill 매트릭스 포함) |

## 평문 트리거 (auto_trigger: true 작동 조건)

`index.yml`의 `plain_text_triggers` 화이트리스트 매칭 시 발동:

| 패턴 | 발동 |
|------|:----:|
| "구현해/추가해/fix/만들어" | ✅ |
| "기획해/PRD/spec/정리해" | ✅ |
| "테스트/검증해" | ✅ |
| "반복/cycle/iterate" | ✅ |
| "뭐야/어디야/보여줘/?" | ❌ (단순 read) |
| `!quick`, `!just`, `!hotfix` | ❌ (Magic Word bypass) |

## Legacy Alias (자동 redirect)

| 입력 | 처리 |
|------|------|
| `/iteration` / `iterate` / `cycle` | `/auto --mode=iteration` |
| `/aiden-auto:auto` | `/auto` |
| `ralph` / `ulw` / `ultrawork` / `autopilot` | `/auto` |

## Iron Laws (전 Phase 적용)

1. TDD: 실패 테스트 없이 코드 금지
2. Debugging: Root cause 없이 수정 금지
3. Verification: 증거 없이 완료 선언 금지
4. Architect Approval: Architect 검증 없이 Phase 4 진입 금지
5. Bypass 금지: `--no-verify`, `--force` 등 hook 우회 금지

## 금지 (HARD BLOCK)

- ❌ 거대 reference를 한 번에 다중 로드 (1 phase = 1 reference)
- ❌ 외부 harness 파일을 plugin 내부로 복사 (참조만, registry 등록만)
- ❌ A/B/C 기술 옵션 나열, "어떻게 할까요?" (자율 결정 + 결과 보고)
- ❌ 옵션 실패 시 조용히 스킵
- ❌ Architect 검증 없이 완료 선언
- ❌ 테스트 삭제로 문제 해결
- ❌ `architect` 에이전트로 파일 쓰기 (READ-ONLY)

## 세부 워크플로우 진입

| 자료 | 위치 |
|------|------|
| 인덱스 카탈로그 | `references/index.yml` |
| 응답 스타일 | `references/communication-style.md` |
| Triage | `references/triage.md` |
| Chapter 6종 | `references/chapter-{doc,code,qa,iteration,research,media}.md` |
| Phase 6종 | `references/phase-{minus-1,1,2,3,4}-*.md` |
| 옵션 핸들러 | `references/options-handlers.md` |
| 외부 harness | `references/external-harness-registry.md` |

## 버전 이력

| 버전 | 핵심 변경 |
|------|----------|
| v28.7 (2026-05-22) | Phase -1.5 Part E 신규 (Atlassian MCP 인증 자율 점검). 이전 SessionStart 자동 발동 폐기 — Atlassian 미사용 프로젝트 부하 차단. 키워드/Part C/skill 호출 감지 시만 `atlassian_auth.py` executor 호출. registry/SessionStart/atlassian-auth.json → `_disabled/` 격리 (deregistration). 사용자 피드백 정정 |
| v28.6 (2026-05-22) | Phase -1.5 Part D 신규 (Executive Summary 자율 판단). v28.5.1 "default 무조건" 폐기 → DOC 카테고리 + 키워드/길이/이해관계자 휴리스틱 충족 시만 인터뷰 질문 추가, 미충족 시 자동 skip. chapter-doc Step 1.3 trigger 를 `active-goal.json.executive_summary.enabled` 기반으로 전환. Core Philosophy "사용자 진입점 최소화 + 자율 영역 확대" 정합 |
| v28.5.2 (2026-05-19) | critic 4 결정 자율 정정: plugin.json version 28.3.0 → 28.5.1 bump (2 mirror) + chapter-doc Step 1.3 / Phase 4.2 trigger logic 강조 (R3 운영 검증 강화) + R7 Context 누적 우려 폐기 (시작 직후라 무의미) + R10 Confluence Q 진입점 정당화 (Sync 위해 정보 필요) + R12 "permanent close" 표현 폐기 → "deferred" (GG NETWORK 자료 확보 시 재개 가능) |
| v28.5.1 (2026-05-19) | 방송 도메인 비유 폐기 (communication-style.md 도메인 중립화 — 글로벌 정책 정합) + Executive Summary default 무조건 (200줄 조건 제거, !quick/!just 만 skip) + GG NETWORK STYLE 복원 작업 deferred (Task 2 deferred — v28.5.2 표현 갱신). Confluence sync 는 Deep Interview Part C 유지 |
| v28.5 (2026-05-19) | Phase -1.5 Part C (Confluence sync 선택, DOC 전용) + chapter-doc Step 1.3 Executive Summary 1-page 양식 + Phase 4.2 Confluence 자동 sync (md2confluence.py 연동) + 신규 reference 3종 (phase-minus-1.5-deep-interview / executive-summary-template / confluence-sync-flow) |
| v28.4 (2026-05-19) | Phase -2 + -1.5 통합 (brainstorming + @ multi-session) + /goal 자율 iteration 본질 재정의 + superpowers 12 skill 매트릭스 |
| v28.3 (2026-05-14) | Step 0.4 user-friendly-reporter 게이트 + Step 0.5 model-router 필수화 |
| v28.1 (2026-05-11) | SKILL.md 311→120줄 정제 + 5원칙 명시 + 외부 harness 자가개선 사이클 추가 |
| v28.0 (2026-05-11) | aiden-auto v18.0 + aiden-auto v27.2 통합 (alpha) |
| v27.2 (2026-05-04) | XML chapter + Multi-perspective + Pipeline + Cleanup + 4 specialist agents |
| v27.0 (2026-05-03) | /iteration 흡수, chapter 라우팅 도입, 평문 트리거 부분 부활 |
