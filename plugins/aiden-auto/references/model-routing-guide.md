# Smart Model Routing Guide (v25.0)

> 에이전트별 최적 모델 선택 가이드. `/auto` Phase별 라우팅 + `--eco` 세분화 규칙.

---

## 의사결정 트리

```
작업 유형 판단
├─ READ-ONLY 탐색/비교? ──────── Haiku
│   (explore, gap-detector, analyst, vision)
├─ 정규식/템플릿 기반 생성? ──── Haiku
│   (catalog-engineer, writer, claude-expert)
├─ 표준 구현/리뷰/QA? ────────── Sonnet
│   (executor, code-reviewer, designer, qa-tester)
├─ 복잡한 추론/판단 필요? ────── Opus
│   (architect, planner, critic, executor-high, scientist-high)
└─ 불확실? ────────────────────── Sonnet (기본값)
```

---

## 에이전트 모델 분류표

### Opus (5개) — 복잡한 설계/구현/검증

| 에이전트 | 용도 |
|----------|------|
| architect | 전략적 아키텍처 검증 (READ-ONLY) |
| critic | Adversarial 약점 분석 |
| executor-high | 복잡한 다중 파일 구현 |
| planner | 전략적 계획 수립 |
| scientist-high | 복잡한 연구/ML/가설 검증 |

### Sonnet (19개) — 표준 실행/분석/리뷰

| 에이전트 | 용도 |
|----------|------|
| ai-engineer | AI/ML 솔루션 |
| architect-medium | 중간 복잡도 아키텍처 |
| build-fixer | 빌드 에러 수정 |
| cloud-architect | 클라우드 인프라 |
| code-reviewer | 코드 리뷰 |
| data-specialist | 데이터 분석/ETL |
| database-specialist | DB 설계/최적화 |
| designer | UI/UX 개발 |
| designer-high | 복잡한 UI 아키텍처 |
| devops-engineer | DevOps/CI/CD |
| executor | 표준 구현 |
| explore-high | 심층 코드 탐색 |
| frontend-dev | 프론트엔드 개발 |
| qa-tester | QA 실행 |
| qa-tester-high | 프로덕션 QA |
| researcher | 외부 문서 리서치 |
| scientist | 데이터 분석/실험 |
| security-reviewer | 보안 취약점 탐지 |
| tdd-guide | TDD 가이드 |

### Haiku (18개) — 빠른 조회/단순 작업

| 에이전트 | 용도 |
|----------|------|
| analyst | 요구사항 분석 (체크리스트 기반) |
| architect-low | 빠른 코드 질문 |
| build-fixer-low | 단순 빌드 에러 |
| catalog-engineer | WSOPTV 카탈로그/제목 생성 |
| claude-expert | Claude Code 설정 |
| code-reviewer-low | 빠른 코드 체크 |
| designer-low | 단순 스타일링 |
| executor-low | 단일 파일 실행 |
| explore | 빠른 파일 탐색 |
| explore-medium | 중간 코드 탐색 (도구 의존적) |
| gap-detector | 설계-구현 Gap 분석 (7항목 체크리스트) |
| github-engineer | Git 워크플로우 |
| researcher-low | 빠른 문서 조회 |
| scientist-low | 빠른 데이터 검사 |
| security-reviewer-low | 빠른 보안 스캔 |
| tdd-guide-low | 빠른 테스트 제안 |
| vision | 이미지/PDF 분석 |
| writer | 기술 문서 작성 |

---

## 비용 비교표

| 모델 | Input ($/1M tokens) | Output ($/1M tokens) | 상대 비용 |
|------|:-------------------:|:--------------------:|:---------:|
| Opus | $15 | $75 | 60x |
| Sonnet | $3 | $15 | 12x |
| Haiku | $0.25 | $1.25 | 1x (기준) |

---

## /auto Phase별 라우팅

### LIGHT 모드 (복잡도 0-1)

| Phase | 에이전트 | 모델 |
|-------|----------|:----:|
| 0 INIT | explore | haiku |
| 1 PLAN | planner | opus |
| 2 BUILD | executor-high | opus |
| 3 VERIFY | qa-tester | sonnet |
| 4 CLOSE | writer | haiku |

### STANDARD 모드 (복잡도 2-3)

| Phase | 에이전트 | 모델 |
|-------|----------|:----:|
| 0 INIT | explore x2 | haiku |
| 1 PLAN | planner, analyst, critic | opus, haiku, opus |
| 2 BUILD | executor-high, code-reviewer, architect, gap-detector | opus, sonnet, opus, haiku |
| 3 VERIFY | qa-tester, architect | sonnet, opus |
| 4 CLOSE | writer, executor-high | haiku, opus |

### HEAVY 모드 (복잡도 4-6)

STANDARD와 동일 + 병렬 executor 추가 + QA 5사이클.

---

## --eco 세분화 규칙

### 레벨 정의

| 레벨 | Opus→ | Sonnet→ | 예상 절감 | 용도 |
|------|:-----:|:-------:|:---------:|------|
| `--eco` | Sonnet | 유지 | ~30% | 일반 비용 절감 |
| `--eco-2` | Sonnet | 비핵심만 Haiku | ~50% | 중간 절감 |
| `--eco-3` | Sonnet | 전부 Haiku | ~70% | 프로토타이핑 전용 |

### --eco-2 다운그레이드 대상 (Sonnet → Haiku)

| 에이전트 | 이유 |
|----------|------|
| gap-detector | READ-ONLY 체크리스트 비교 |
| explore-medium | READ-ONLY 도구 의존적 탐색 |
| analyst | 체크리스트 기반 구조화 출력 |
| vision | 멀티모달 정보 추출 |
| catalog-engineer | 정규식 기반 제목 생성 |
| claude-expert | 참조 문서 기반 설정 |
| researcher | 외부 문서 검색/요약 |

### --eco-2 Sonnet 유지 (핵심)

| 에이전트 | 이유 |
|----------|------|
| code-reviewer | 코드 품질 판단 정확도 필수 |
| executor | 구현 정확성 필수 |
| designer | UI 미학 판단 필수 |
| qa-tester | 테스트 로직 정확성 필수 |
| build-fixer | 빌드 에러 해결 정확성 |
| security-reviewer | 보안 판단 정확성 |
| tdd-guide | TDD 패턴 정확성 |

### --eco-3 경고

> **프로토타이핑 전용**. 프로덕션 워크플로우에서 `--eco-3` 사용 금지.
> 전체 Haiku 강제 시 코드 리뷰/보안 검토 품질이 크게 저하될 수 있음.

---

## 모델 선택 Quick Reference

| 상황 | 추천 모델 | 에이전트 |
|------|:---------:|----------|
| "이 파일 뭐하는 거야?" | haiku | explore |
| "이 버그 원인 분석해줘" | opus | architect |
| "이 함수 리팩토링해줘" | sonnet | executor |
| "전체 아키텍처 설계해줘" | opus | planner |
| "이 PR 리뷰해줘" | sonnet | code-reviewer |
| "보안 취약점 확인해줘" | sonnet | security-reviewer |
| "ML 모델 평가해줘" | opus | scientist-high |
| "카탈로그 제목 생성해줘" | haiku | catalog-engineer |
| "설계-구현 Gap 확인해줘" | haiku | gap-detector |
| "README 작성해줘" | haiku | writer |

---

## Adaptive Model Routing (v25.1 — Task 자동 분류)

Phase 0에서 Task 특성을 자동 분류하여 에이전트별 최적 모델을 결정합니다.

### 분류 기준

| 분류 | 감지 신호 | 기본 모델 | --eco 적용 시 |
|------|----------|:---------:|:------------:|
| **Trivial** | 파일 1개, 포맷/요약/오타/rename 키워드 | Haiku | Haiku |
| **Standard** | 파일 2-5개, 일반 구현/리뷰 | Sonnet | Sonnet (--eco-2: Haiku) |
| **Complex** | 파일 5+개, refactor/debug/design 키워드 | Opus | Sonnet |
| **Critical** | architect/system/migration/breaking 키워드 | Opus | Opus (강제 유지) |

### 감지 우선순위

```
1. 키워드 매칭 (최우선): Critical > Complex > Standard > Trivial
2. 파일 수 (보조): 1개 → Trivial, 2-5개 → Standard, 5+개 → Complex
3. 기본값: Standard (불확실 시)
```

### --eco 결합 규칙

| Adaptive 결과 | --eco | --eco-2 | --eco-3 |
|:------------:|:-----:|:-------:|:-------:|
| Trivial | Haiku | Haiku | Haiku |
| Standard | Sonnet | Haiku (비핵심) | Haiku |
| Complex | Sonnet | Sonnet | Haiku |
| Critical | Opus | Sonnet | Sonnet |

> **Critical + --eco-3**: Sonnet까지만 다운그레이드 (Haiku 금지, 아키텍처 품질 보장).

### InitContract 확장

```json
{
  "adaptive_tier": "TRIVIAL | STANDARD | COMPLEX | CRITICAL",
  "adaptive_signals": {
    "file_count": 3,
    "keywords": ["refactor"],
    "eco_override": null
  }
}
```

---

## 버전 이력

| 버전 | 변경 |
|------|------|
| v25.2 | eco 자동 선택 (--auto-eco) — Adaptive tier 기반 자동 매핑 |
| v25.1 | Adaptive Model Routing — Task 자동 분류 + --eco 결합 규칙 |
| v25.0 | Opus 5 / Sonnet 19 / Haiku 18 재배치. --eco-2, --eco-3 도입 |
| v24.4 | Agent 정의 파일 model 필드 + Agent() model 오버라이드 확인 |
| v24.3 | Opus 기본 모델 전환 |

---

## eco 자동 선택 (v25.1)

`--auto-eco` 플래그 사용 시 Phase 0.3 Adaptive Model Routing의 분류 결과에 따라 eco 레벨 자동 매핑:

| adaptive_tier | eco 레벨 | 적용 모델 변경 |
|:------------:|:--------:|--------------|
| Trivial | --eco-3 | 전부 Haiku (프로토타이핑) |
| Standard | --eco | Opus→Sonnet (~30% 절감) |
| Complex | (없음) | 변경 없음 |
| Critical | (없음) | 변경 없음 |

### 우선순위

1. 사용자 명시적 `--eco[-N]` → 최우선 (자동 선택 무시)
2. `--no-eco` → 자동 선택 비활성화
3. `--auto-eco` → Adaptive tier 기반 자동 선택
4. (없음) → eco 미적용 (기본값)

### 주의사항

- `--auto-eco`는 opt-in 전용. 기본값은 eco 미적용
- Trivial 분류 정확도가 낮으면 --eco-3 과적용 위험 → 분류 정확도 모니터링 필요
- 프로덕션 워크플로우에서는 Complex/Critical 보호를 위해 자동 eco 비활성화 권장
