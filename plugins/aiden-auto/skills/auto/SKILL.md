---
name: auto
description: >
  Index Router (v28.8) — 사용자 평문을 분석하여 적절한 chapter만 lazy load. v28.8: ⭐ Universal Deployment Premise — Step 0.7 Part 2 (6 기준 자동 평가: 자기복제율/device-agnostic/OS-agnostic/권한-agnostic/idempotent/개인화 격리) + Part 3 위반 표현 강화. v28.7 base: Phase -1.5 Part E (Atlassian MCP 인증). v28.6 base: Part D Executive Summary 자율 판단. v28.5 base: Confluence sync (Part C). v28.4 base: Phase -2/-1.5 통합 + brainstorming + @ multi-session + /goal 자율 iteration.
  Auto-trigger ON. Skip for trivial questions, file reads, !quick/!hotfix.
  /aiden-auto:auto / /iteration / iterate / /goal 모두 이 SKILL로 redirect.
  (multi-session 운영은 공식 `claude agents` CLI로 위임 — 2026-05-14 폐기)
version: 28.8.0
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

## 5 핵심 원칙 (HARD ENFORCE)

| # | 원칙 |
|---|------|
| 1 | 외부 harness framework — *복사 금지, 참조만* (`agents/meta/harness-watcher` 매일 추적) |
| 2 | 자가개선 critic 사이클 — `harness-watcher` → `harness-critic` → `harness-applier` |
| 3 | SKILL.md ≤120줄 — 모든 상세 `references/` lazy load |
| 4 | Intent → Chapter 라우팅 — `index.yml` lookup, chapter 1개만 로드 |
| 5 | 슈퍼앱 — SKILL.md 작고, 뒤의 24 skills + 20 commands + 31 agents 가 방대 |

## 진입 흐름

```
사용자 평문 / /auto / /goal
    │
    ▼ Step 0  Index Lookup (index.yml + communication-style.md)
    ▼ Step 0.4 user-friendly-reporter (haiku)
    ▼ Step 0.5 model-router (haiku) → JSON model_plan
    ▼ Step 0.7 자율 자산 inventory + Universal Premise 6 기준 평가
    ▼ Phase -2 Triage (모호 시만)
    ▼ Phase -1.5 Deep Interview (Part A-E)
    ▼ Chapter Load (1개 — DOC/CODE/QA/ITERATION/RESEARCH/MEDIA)
    ▼ Phase -1 → 0 → 1 → 2 → 3 → 4 → cleanup
```

각 Step 상세: `references/step-0x-entry-mechanism.md`.
## Step 0~0.7 진입 (MANDATORY)

| Step | 역할 | 상세 |
|:----:|------|------|
| 0 | `Read(index.yml + communication-style.md)` | 카탈로그 + 15세 응답 룰 |
| 0.4 | `user-friendly-reporter` (haiku) 응답 친절 변환 | `references/step-0x-entry-mechanism.md` § 0.4 |
| 0.5 | `model-router` (haiku) → JSON model_plan → 후속 Agent() 자동 주입 | § 0.5. 도구: `hooks/auto_workflow_enforcer.py` |
| 0.7 | 자율 자산 inventory + Universal Premise 6 기준 평가 | § 0.7. 체크리스트: `references/universal-deployment-checklist.md` |

## Phase -2 + -1.5: Deep Interview

Step 0.7 직후 5 Part (A brainstorming / B multi-session / C Confluence / D Executive Summary / E Atlassian auth) 즉시 발동. Skip: `!quick` / `!just` / `!hotfix`.
상세: `references/phase-minus-1.5-deep-interview.md`.
## /goal 자율 Iteration Loop (v28.4)

자율 처리 + 안전절 트립 (20 turns / 200k tokens / 5 fails) + 진짜 막힘 시만 사용자 보고. Visual 작업 Phase 4 QA Gate = 스크린샷 ≥ 3장.
상세: `references/goal-operation.md`. State tracker: `scripts/goal_loop_state.py`.

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

매일 자동 (또는 daily hook): `harness-watcher` → `harness-critic` → `harness-applier` 체인. 자동 발동: `hooks/harness_cycle_runner.py` (v3).
상세 (다이어그램 / state file / 발동 시점): `references/harness-cycle-mechanism.md`.
추적 대상 등록: `references/external-harness-registry.md`.
## Progressive Disclosure 로딩 규칙

lazy load 매트릭스 — entry / phase-2 / phase-1.5 / chapter / phase-specific / options 단계별 로드.
상세: `references/index.yml` § loading_rules.
## 평문 트리거 (auto_trigger: true 작동)

키워드 매칭 시 자동 발동. Skip 조건: `!quick` / `!just` / `!hotfix` / `--no-auto` / 단순 질문.
상세: `references/index.yml` § plain_text_triggers.
## Legacy Alias

`/iteration` / `iterate` / `cycle` / `/aiden-auto:auto` / `ralph` / `ulw` / `ultrawork` / `autopilot` / `/goal` → 모두 `/auto` redirect.
상세: `references/index.yml` § legacy_aliases.
## Iron Laws + 금지 (HARD BLOCK)

| IL | Rule |
|----|------|
| 1 TDD | 실패 테스트 없이 코드 금지 |
| 2 Debugging | Root cause 없이 수정 금지 |
| 3 Verification | 증거 없이 완료 선언 금지 |
| 4 Architect Approval | Architect 검증 없이 Phase 4 진입 금지 |
| 5 Bypass 금지 | `--no-verify`, `--force` 등 hook 우회 금지 |

금지: 거대 reference 다중 로드 / 외부 harness 복사 / A/B/C 옵션 나열 / 옵션 silent skip / Architect 없이 완료 / 테스트 삭제 / architect 파일 쓰기 / **추정 표현 (P13)**.
상세: `references/index.yml` § iron_laws + `scripts/forbidden_pattern_check.py` (13 patterns).

## 세부 워크플로우 진입 + 버전

자료: `references/{index.yml,communication-style.md,triage.md,chapter-*.md,phase-*.md,options-handlers.md,external-harness-registry.md,step-0x-entry-mechanism.md,harness-cycle-mechanism.md,goal-operation.md,critic-protocol-unified.md,universal-deployment-checklist.md}`.
버전: v28.8 (Universal Deployment Premise + Step 0.7 자동 평가 + v3 자기 정량화 시스템).