# Phase 1 Appendix — Design + Plan Approval

> 이 파일은 `phase-1-plan.md` 의 부록입니다. Step 1.4–1.6 진입 시 lazy load.
> 원본: `phase-1-plan.md` (v25.2) 의 복잡도 모드별 실행 + Design + Plan Approval Gate 섹션 분리 (Flaw 5 컨텍스트 예산 대응).

> **v28.1+ 호환 노트**: 아래 Agent() 호출 예시는 v28.1 이전 잔재이지만, Design 항목 / Gate 검증 / Plan Approval 로직 자체는 그대로 유효.
> 호출 방식은 글로벌 CLAUDE.md Subagent Protocol 에 맞춰 변환하세요.

---

## 복잡도 분기 상세 (Phase 1-4 실행 차이)

### LIGHT 모드 (0-1점)

| Phase/Step | 실행 |
|------------|------|
| 1.1 PRD | PRD 생성/수정 + 사용자 승인 (`--skip-prd`로 스킵 가능) |
| 1.2-1.3 PLAN | Explore teammates (haiku) x2 + Planner (sonnet) + Lead Quality Gate |
| 1.4 DESIGN | **스킵** (설계 문서 생성 없음) |
| 2.1 BUILD | Executor teammate (opus) 단일 실행 |
| 2.2-2.3 | — (Code Review, Architect Gate 없음) |
| 3.1 VERIFY | QA Runner 1회 |
| 3.2-3.3 | Architect 최종 검증 (E2E 스킵) |
| 4 CLOSE | sonnet 보고서 |

### STANDARD 모드 (2-3점)

| Phase/Step | 실행 |
|------------|------|
| 1.1 PRD | PRD 생성/수정 + 사용자 승인 (`--skip-prd`로 스킵 가능) |
| 1.2-1.3 PLAN | Explore teammates (haiku) x2 + Planner (opus) + Critic-Lite |
| 1.4 DESIGN | Executor teammate (opus) — 설계 문서 생성 |
| 2.1 BUILD | impl-manager teammate (opus) — 4조건 자체 루프 |
| 2.2-2.3 | Code Review + Architect Gate (외부 검증, max 2회 rejection) |
| 3.1 VERIFY | QA Runner 3회 + Architect 진단 + Domain-Smart Fix |
| 3.2 E2E | E2E 백그라운드 + Architect 최종 검증 |
| 3.3 E2E | E2E 실패 처리 (진단 + Domain-Smart Fix, max 2회) |
| 4 CLOSE | gap < 90% → executor teammate (최대 5회) |

### HEAVY 모드 (4-6점)

| Phase | 실행 |
|-------|------|
| Phase 1.1 | PRD 생성/수정 + 사용자 승인 (`--skip-prd`로 스킵 가능) |
| Phase 1.2-1.3 | Explore teammates (haiku) x2 + Planner-Critic Loop (max 5 iter, A1-A7 adversarial 공격) |
| Phase 1.4 | Executor-high teammate (opus) — 설계 문서 생성 |
| Phase 2.1 | impl-manager teammate (opus) — 4조건 자체 루프 + 병렬 가능 |
| Phase 2.2-2.3 | Code Review + Architect Gate (외부 검증, max 2회 rejection) |
| Phase 3.1 | QA Runner 5회 + Architect 진단 + Domain-Smart Fix |
| Phase 3.2 | E2E 백그라운드 + Architect 최종 검증 |
| Phase 3.3 | E2E 실패 처리 (진단 + Domain-Smart Fix, max 2회) |
| Phase 4 | gap < 90% → executor teammate (최대 5회) |

### 자동 승격 규칙 (Phase 중 복잡도 상향 조정)

| 승격 조건 | 결과 |
|----------|------|
| 빌드 실패 2회 이상 | LIGHT → STANDARD |
| QA 3사이클 초과 (STANDARD→HEAVY만) | STANDARD → HEAVY |
| 영향 파일 5개 이상 | LIGHT/STANDARD → HEAVY |
| Architect REJECT 2회 | 현재 모드 유지, Phase 3 진입 허용 (사용자 알림) |

---

## Phase 1, Step 1.4: DESIGN (설계 통합 — STANDARD/HEAVY만)

> **CRITICAL**: `architect`는 READ-ONLY (Write/Edit 도구 없음). 설계 문서 **생성**에는 executor 계열 사용 필수.

**LIGHT 모드: 스킵** (설계 문서 생성 없음, Phase 2에서 직접 구현)

**STANDARD 모드: Executor opus teammate**
```
Agent(subagent_type="executor-high", name="design-writer", description="설계 문서 작성", team_name="pdca-{feature}",
     prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요.
     필수 포함: 구현 대상 파일 목록, 인터페이스 설계, 데이터 흐름, 테스트 전략.
     출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY 모드: Executor-high opus teammate**
```
Agent(subagent_type="executor-high", name="design-writer", description="설계 문서 작성", team_name="pdca-{feature}",
     prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요.
     필수 포함: 구현 대상 파일 목록, 인터페이스 설계, 데이터 흐름, 테스트 전략, 예상 위험 요소.
     출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**산출물**: `docs/02-design/{feature}.design.md`

### Design→Build Gate: Design 검증

| # | 필수 항목 | 확인 방법 |
|:-:|----------|----------|
| 1 | 구현 대상 파일 목록 | 구체적 파일 경로 나열 존재 |
| 2 | 인터페이스/API 설계 | 함수/클래스 시그니처 정의 |
| 3 | 테스트 전략 | 테스트 범위/방법 언급 존재 |
| 4 | 데이터 흐름 | 입출력 흐름 기술 존재 |

---

## Step 1.6: Plan Approval Gate (HEAVY만)

HEAVY 모드에서는 Phase 2 BUILD 진입 전 사용자에게 계획을 명시적으로 승인받습니다.
토큰 낭비를 방지하고 팀메이트 스폰 전 방향성을 확인합니다.

**실행 조건**: `complexity_mode == "HEAVY"` 일 때만 실행. LIGHT/STANDARD는 스킵.

```python
# Plan Approval Gate (HEAVY만)
if mode == "HEAVY":
    # 1. 계획 요약 출력
    print(f"""
=== Plan Approval Gate (HEAVY) ===
PRD: {prd_path}
Plan: {plan_path}
Design: {design_path}
영향 파일: {len(affected_files)}개
예상 에이전트: {agent_count}개
복잡도: {complexity_score}/6
==================================
""")
    # 2. AskUserQuestion으로 승인 요청
    approval = AskUserQuestion("Phase 2 BUILD 진입을 승인하시겠습니까? (y/n/수정사항)")

    if approval.lower() in ["n", "no", "아니오"]:
        # 계획 수정 → Step 1.3 재실행
        print("[Plan Approval] 거부됨. Phase 1.3 계획 수립으로 복귀.")
    elif approval.lower() in ["y", "yes", "예", "ㅇ"]:
        # Phase 2 진입
        print("[Plan Approval] 승인됨. Phase 2 BUILD 진입.")
    else:
        # 수정사항 반영 후 재승인
        print(f"[Plan Approval] 수정 요청: {approval}")
        # planner에게 수정사항 전달 → 계획 업데이트 → 재승인 (max 2회)
```

**`--interactive` 모드와의 관계**: `--interactive`는 모든 Phase 전환 시 확인. Plan Approval Gate는 HEAVY 전용 심층 검토 (계획 내용까지 표시).
