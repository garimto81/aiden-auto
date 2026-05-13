# /auto Phase 1: PLAN — Core Index (Lazy-Load Router)

> 이 파일은 `/auto` Phase 1 진입 시 로딩되는 **코어 인덱스**입니다.
> SKILL.md에서 Phase 1 시작 시 이 파일을 Read합니다.
>
> **v25.3 (2026-05-13)**: 39KB → 5 appendix + ~80줄 코어 인덱스로 분해 (Flaw 5 컨텍스트 예산 대응).
> 원본: REFERENCE.md v25.0에서 분리 → v25.2 Progressive Disclosure → v25.3 Lazy-Load Appendix.

---

## Phase 1 단계 순서

```
[Phase 0]
  Step 0.2  Socratic Questioning   (모호성 >= 0.5 시)
  Step 0.3  Adaptive Model Routing (Task 자동 분류)
[Phase 1]
  Step 1.0  사전 분석 (병렬 explore + intent-analyst)
  Step 1.1  PRD 작성/수정 + 사용자 승인  (--skip-prd 로 스킵 가능)
  Step 1.1b Plugin Activation Scan + Iron Laws 주입
  Step 1.2  계획 수립 (LIGHT / STANDARD / HEAVY 분기)
  Step 1.3  GitHub Issue 연동
  Step 1.4  DESIGN 문서 생성 (STANDARD / HEAVY 만)
  Step 1.6  Plan Approval Gate (HEAVY 만)
```

## Appendix Lazy-Load 매핑

> 아래 appendix 는 **해당 단계 진입 시점에만** `Read` 합니다. 사전 일괄 로드 금지 (컨텍스트 예산 보호).

| 진입 단계 | Lazy-Load 파일 | 핵심 내용 |
|----------|---------------|----------|
| Phase 0.2 | `appendix/phase-1-socratic-questioning.md` | F1-F7 ambiguity score, 차원별 질문 템플릿, Magic Word bypass |
| Phase 0.3 | `appendix/phase-1-model-routing.md` | TRIVIAL/STANDARD/COMPLEX/CRITICAL 분류, --eco 오버라이드 |
| Step 1.1 | `appendix/phase-1-prd.md` | PRD 탐색/생성/수정, 사용자 승인 3옵션, PRD→Phase 1 Gate |
| Step 1.0-1.3 | `appendix/phase-1-plan-steps.md` | 사전 분석, 6점 복잡도, Plugin Activation, Planner LIGHT/STANDARD/HEAVY, Critic A1-A7, Quality Gate |
| Step 1.4-1.6 | `appendix/phase-1-design.md` | LIGHT/STANDARD/HEAVY 모드 비교, 자동 승격 규칙, Design 작성, Plan Approval Gate |

## 핵심 Gate 요약 (각 appendix 의 검증 항목만 발췌)

### PRD→Phase 1 Gate

| # | 검증 항목 |
|:-:|----------|
| 1 | `docs/00-prd/{feature}.prd.md` 존재 |
| 2 | `FR-` 패턴 1개 이상 |
| 3 | `AC-` 패턴 1개 이상 |

### Plan→Build Gate (MANDATORY)

| # | 필수 섹션 |
|:-:|----------|
| 1 | 배경/문제 정의 |
| 2 | 구현 범위 |
| 3 | 예상 영향 파일 |
| 4 | 위험 요소 |

### Design→Build Gate (STANDARD/HEAVY 만)

| # | 필수 항목 |
|:-:|----------|
| 1 | 구현 대상 파일 목록 |
| 2 | 인터페이스/API 설계 |
| 3 | 테스트 전략 |
| 4 | 데이터 흐름 |

## 복잡도 모드 분기 (Quick Reference)

| 점수 | 모드 | DESIGN | BUILD | VERIFY | Approval Gate |
|:----:|------|:------:|-------|--------|:-------------:|
| 0-1 | LIGHT | 스킵 | executor 단일 | QA 1회 | 없음 |
| 2-3 | STANDARD | executor | impl-manager 루프 + Gate | QA 3회 | 없음 |
| 4-6 | HEAVY | executor-high | impl-manager 루프 + Gate | QA 5회 | **AskUserQuestion** |

## v28.1+ 호환성 (전 appendix 공통)

appendix 내 Agent() 호출 예시는 v28.1 이전 패턴 (`team_name=`, `SendMessage`, `shutdown_request`, `Mailbox`) 잔재입니다.
**워크플로우 구조 / 검증 항목 / Gate / 점수표 자체는 그대로 유효** 하며, 호출 메커니즘만 글로벌 CLAUDE.md
Subagent Protocol (`Agent(subagent_type, model, description, prompt)` 단일 호출) 로 변환하여 사용하세요.

또한 `model` 파라미터는 글로벌 model-router(haiku) 가 결정한 `model_plan["<role>"]` 을 동적 주입합니다.
파싱 실패 시 → 전체 sonnet 폴백 + 사용자 알림 필수 (Flaw 4 fix).
