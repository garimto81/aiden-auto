# Phase 1 Appendix — PRD (요구사항 문서화)

> 이 파일은 `phase-1-plan.md` 의 부록입니다. Step 1.1 진입 시 lazy load.
> 원본: `phase-1-plan.md` (v25.2) 의 Step 1.1 섹션 분리 (Flaw 5 컨텍스트 예산 대응).

> **CRITICAL**: 요구사항 요청 시 반드시 PRD 문서를 먼저 생성/수정한 후 구현을 진행합니다.
> **목적**: 사용자 요구사항을 공식 문서화하여 구현 범위를 명확히 하고, 이후 Phase에서 PRD를 기준으로 검증합니다.
> **스킵 조건**: `--skip-prd` 옵션 명시 시 스킵 가능.

> **v28.1+ 호환 노트**: 아래 Agent() 호출 예시는 v28.1 이전 (`team_name=`, `SendMessage`, `shutdown_request`) 잔재이지만,
> **워크플로우 단계와 PRD 템플릿 자체는 그대로 유효**합니다. 글로벌 CLAUDE.md Subagent Protocol 에 따라
> `team_name=` / `SendMessage()` / `shutdown_request` 는 제거하고 단일 `Agent(subagent_type=..., model=..., description=..., prompt=...)` 호출로 대체하세요.

---

## Step 1.1.1: 기존 PRD 탐색

```
# docs/00-prd/ 디렉토리에서 기존 PRD 탐색
existing_prd = Glob("docs/00-prd/{feature}*.prd.md")

# 관련 PRD가 없으면 docs/00-prd/ 전체 탐색하여 연관 문서 확인
if not existing_prd:
    all_prds = Glob("docs/00-prd/*.prd.md")
    # 유사 이름이나 관련 주제의 PRD가 있으면 참조 대상으로 표시
```

## Step 1.1.2: PRD 생성 또는 수정

**신규 PRD 생성 (기존 PRD 없음):**
```
Agent(subagent_type="executor-high", model=plan["executor"], name="prd-writer", description="PRD 문서 작성", team_name="pdca-{feature}",
     prompt="[Phase 1 PRD 생성] 사용자 요구사항을 PRD 문서로 작성하세요.

     === 사용자 요청 ===
     {user_request}

     === 기존 관련 PRD 요약 ===
     {existing_prds_summary}  (없으면 '없음')

     === PRD 템플릿 (필수 섹션) ===

     # {feature} PRD

     ## 0. Market Context (선택)
     - 시장 배경 / 고객 페인포인트
     - 비즈니스 Impact 범위
     - Target Segment / Volume
     - Appetite: {Small 2주 | Big 6주} (이 기능에 투자할 시간 예산)

     ## 1. 배경 및 목적
     - 왜 이 기능/변경이 필요한지
     - 해결하려는 문제

     ## 2. 요구사항
     ### 2.1 기능 요구사항 (Functional Requirements)
     - FR-001: {요구사항 1}
     - FR-002: {요구사항 2}
     (각 요구사항에 번호 부여, 검증 가능한 수준으로 구체적 기술)

     ### 2.2 비기능 요구사항 (Non-Functional Requirements)
     - NFR-001: 성능, 보안, 접근성 등 해당 사항

     ## 3. 기능 범위 (Scope)
     ### 3.1 포함 (In Scope)
     - 이번에 구현할 항목
     ### 3.2 제외 (Out of Scope)
     - 이번에 구현하지 않을 항목

     ## 4. 제약사항 (Constraints)
     - 기술적 제약, 일정 제약, 의존성

     ## 5. 우선순위 (Priority)
     | 요구사항 | 우선순위 | 근거 |
     |---------|---------|------|
     | FR-001  | P0 필수 | ... |
     | FR-002  | P1 권장 | ... |

     ## 6. 수용 기준 (Acceptance Criteria)
     - AC-001: {검증 가능한 수용 기준}
     - AC-002: ...

     ## Changelog
     | 날짜 | 변경 내용 | 작성자 |
     |------|---------|--------|
     | {오늘 날짜} | 초기 작성 | auto |

     === 출력 ===
     파일 경로: docs/00-prd/{feature}.prd.md
     디렉토리가 없으면 생성하세요.")
SendMessage(type="message", recipient="prd-writer", content="PRD 문서 작성 시작.")
# 완료 대기 → shutdown_request
```

**기존 PRD 수정 (PRD 존재 시):**
```
Agent(subagent_type="executor-high", model=plan["executor"], name="prd-writer", description="PRD 문서 작성", team_name="pdca-{feature}",
     prompt="[Phase 1 PRD 수정] 기존 PRD를 새 요구사항에 맞게 수정하세요.

     === 기존 PRD 파일 ===
     docs/00-prd/{existing_prd_file}

     === 추가/변경 요구사항 ===
     {user_request}

     === 수정 규칙 ===
     1. 기존 요구사항(FR-xxx)은 보존하되, 변경된 항목은 명시적으로 표시
     2. 새 요구사항은 기존 번호 체계에 이어서 추가 (FR-003, FR-004 ...)
     3. 삭제된 요구사항은 ~~취소선~~ 처리 (이력 보존)
     4. ## Changelog 섹션에 변경 이력 추가
     5. 범위(Scope) 섹션도 요구사항 변경에 맞게 갱신
     6. 수용 기준(Acceptance Criteria)도 요구사항 변경에 맞게 갱신")
Agent(subagent_type="writer", model=plan["writer"],
      description="PRD 수정",
      prompt="(위 prompt 내용을 그대로 전달)")
# v28.1+ Agent() 단일 호출 (폐기된 SendMessage/shutdown_request 제거)
```

## Step 1.1.3: PRD 작성 보고 (자동 진행, v28.3+ Core Philosophy 적용)

```
# PRD 내용을 사용자에게 요약 보고 (AskUserQuestion 제거 — A/B/C 옵션 나열 금지)
prd_content = Read("docs/00-prd/{feature}.prd.md")

# 사용자에게 PRD 요약 출력 (안내형)
print("=== PRD 작성 완료 ===")
print("파일: docs/00-prd/{feature}.prd.md")
print("요구사항 {N}건, 수용 기준 {M}건")
print("주요 변경: {summary_one_line}")
print("이의 없으면 자동으로 Phase 1 진입합니다.")
print("수정 필요 시 별도 메시지로 알려주세요 (사용자 자율 진입점).")
print("========================")

# Phase 1 자동 진입 (Core Philosophy: 사용자 진입점 최소화)
```

**v28.3 변경 사유** (정책 critic audit P0-1, 2026-05-14):
- 기존 AskUserQuestion 3옵션 (승인/수정요청/직접수정)은 글로벌 CLAUDE.md "A/B/C 기술 옵션 나열 금지"와 정면 충돌
- 신규: PRD 자동 작성 + 사후 이의제기 패턴. 사용자가 명시적으로 수정 요청 시에만 Step 1.1.2 재실행
- 효과: PRD 단계 진입점 1회 제거, 자율 워크플로우 흐름 유지

## PRD→Phase 1 Gate

PRD 승인 후 Phase 1 진입 전 최소 검증:

| # | 검증 항목 | 확인 방법 |
|:-:|----------|----------|
| 1 | PRD 파일 존재 | `docs/00-prd/{feature}.prd.md` 존재 |
| 2 | 요구사항 1건 이상 | `FR-` 패턴 1개 이상 존재 |
| 3 | 수용 기준 1건 이상 | `AC-` 패턴 1개 이상 존재 |

미충족 시: PRD 보완 후 재검증 (1회). 2회 실패 → Phase 1 진입 허용 (경고 포함).

## PRD와 이후 Phase 연계

| Phase | PRD 활용 |
|-------|---------|
| Phase 1 PLAN | Planner가 PRD 참조하여 계획 수립 |
| Phase 1 DESIGN | Design 문서에 PRD 요구사항 번호 매핑 |
| Phase 2 BUILD | impl-manager가 PRD 요구사항 기반 구현 |
| Phase 3 VERIFY | Architect가 PRD 수용 기준 기반 검증 |
| Phase 4 CLOSE | 보고서에 PRD 대비 달성률 포함 |
