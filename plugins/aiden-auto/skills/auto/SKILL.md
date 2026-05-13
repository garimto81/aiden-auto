---
name: auto
description: >
  Index Router (v28.2) — 사용자 평문을 분석하여 적절한 chapter만 lazy load. v28.2: /goal 기반 loop driver,
  Deep Interview, multi-session, Perfect Output Gate, advisor-tool quota, adaptive framework, progress hooks.
  Auto-trigger ON. Skip for trivial questions, file reads, !quick/!hotfix.
  /aiden-auto:auto / /iteration / iterate / /goal 모두 이 SKILL로 redirect.
version: 28.2.0
auto_trigger: true
output_style: user_friendly  # v28.2 Section 16 — 비개발자 친화 자세한 보고. user-friendly-reporter agent 의무 통과
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
    - "멀티세션"
    - "multi-session"
---

# /auto — Index Router (v28.1)

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
| Chapter 확정 | `chapter-{CAT}.md` (1개) |
| Phase 진입 | `phase-{N}-*.md` (해당 phase 1개) |
| Plan→Design 전환 | `plan-design-gate.md` (CODE/ITERATION chapter, 자동) |
| 복잡도 산정 직후 | `ml-assist.md` (`.claude/ml/.ml_session_state.json` 존재 시만) |
| Phase 진입 전 토큰 절약 | `compaction-gate.md` (조건부: score>=4 OR load>15KB OR effort=high) |
| critic 호출 시 (verdict 통일) | `critic-protocol-unified.md` (5 기존 critic + compaction-critic) |
| HARNESS chapter (운영) | `chapter-harness.md` ("harness 상태" 평문 트리거) |
| 옵션 사용 | `options-handlers.md` |
| 외부 harness 추적 | `external-harness-registry.md` (harness-watcher 매일 자동) |

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
| v28.1 (2026-05-11) | SKILL.md 311→120줄 정제 + 5원칙 명시 + 외부 harness 자가개선 사이클 추가 |
| v28.0 (2026-05-11) | aiden-auto v18.0 + aiden-auto v27.2 통합 (alpha) |
| v27.2 (2026-05-04) | XML chapter + Multi-perspective + Pipeline + Cleanup + 4 specialist agents |
| v27.0 (2026-05-03) | /iteration 흡수, chapter 라우팅 도입, 평문 트리거 부분 부활 |
