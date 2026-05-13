# Phase -1.5: Self-Evaluation Gate — /auto 적합도 평가

> **로딩 시점**: Phase -1 완료 직후, Phase 0 진입 전. 항상 실행.
> **의존**: `references/phase-minus-1-context-detect.md` 의 `fit_score` (0-100).
> **목적**: /auto 가 이 컨텍스트에 적합한지 자체 평가하여 사용자 안내.

---

## 평가 기준 (4개 축, 각 25점)

```
fit_score = docs_layout_score + tools_compat_score + complexity_match_score + domain_fit_score
            (0-25)             (0-25)              (0-25)                 (0-25)
            = 0-100 total
```

### Axis 1: docs_layout_score (0-25)

| docs_layout | score | 근거 |
|-------------|------|------|
| `standard_pdca` | 25 | /auto의 docs/00-prd, 01-plan, ... 기본 가정 일치 |
| `react_style` | 20 | README 갱신만으로 적응 가능 |
| `ebs_style` | 15 | 비표준 path 처리 가능하나 별도 매핑 필요 |
| `python_sphinx` | 18 | rST 출력 어댑터 가능 |
| `custom` | 10 | 사용자 질의 필요, 부정합 위험 |
| `none` | 5 | docs 자체 부재, /auto의 산출물 가치 낮음 |

### Axis 2: tools_compat_score (0-25)

| tools_registry 상태 | score | 근거 |
|--------------------|------|------|
| empty (자체 도구 없음) | 25 | 충돌 없음 — 일반 qa-tester 그대로 |
| drift_check + kpi 모두 발견 | 25 | tool-integration.md로 완전 통합 가능 |
| lint + test + build (표준 web) | 22 | 일반적 통합 OK |
| 일부 도구만 발견 | 15 | 부분 통합 |
| 명시적 conflict (비표준 검증 의무화) | 5 | /auto의 검증 우회 위험 |

### Axis 3: complexity_match_score (0-25)

복잡도는 Phase 0의 5점 만점 점수를 10점 환산 사용:

| 복잡도 (10점) | score | 근거 |
|--------------|------|------|
| 4-7 (PDCA sweet spot) | 25 | /auto 5-phase 구조에 최적 |
| 5 (single feature) | 25 | 가장 적합 |
| 3 (small feature) | 18 | Phase 0 + 2 + 3 만 적합, 0-4 전체는 overkill |
| 1-2 (typo, single line) | 8 | overkill 위험 |
| 8-9 (cross-module refactor) | 15 | 다중 cycle 필요 → /iteration 권장 |
| 10 (architecture migration) | 10 | /iteration 강력 권장 |

### Axis 4: domain_fit_score (0-25)

| domain_profile | score | 근거 |
|----------------|------|------|
| `frontend_react` | 25 | 일반 web app — /auto 검증 가능 |
| `frontend_vue` | 25 | 동상 |
| `backend_python` | 25 | 표준 API 도메인 |
| `backend_node` | 25 | 동상 |
| `monorepo` | 20 | workspace 인식 약함 |
| `ecommerce` | 18 | 결제/PCI DSS 도메인 지식 약함 |
| `poker_game` | 10 | 게임 룰/RFID 등 도메인 지식 부족 |
| 의료/금융/법률 | 5-10 | 컴플라이언스 도메인 강한 부족 |
| `generic` | 25 | 도메인 특수성 없음 = 일반 PDCA 적용 가능 |

## 점수별 분기

```
fit_score:
  ┌─ 80+: 🟢 GO          → 즉시 Phase 0 진입 (현재 v25.6 동작)
  ├─ 50-79: 🟡 PROCEED   → Phase 0 진입, 단 부적합 axis 사용자에게 안내
  └─ <50: 🔴 RECOMMEND_ALTERNATIVE → 사용자 confirm 필요
```

### Branch A: fit_score ≥ 80 (🟢 GO)

자동 진행. 사용자에게 한 줄 안내만:

```
═══ Phase -1.5: Self-Evaluation ═══
fit_score: 88/100 — 🟢 적합
  docs_layout: 25/25  tools: 22/25  complexity: 25/25  domain: 18/25
→ Phase 0 INIT 진입
═══════════════════════════════════
```

### Branch B: 50 ≤ fit_score < 80 (🟡 PROCEED)

진행하되 사용자에게 부적합 axis + 영향 안내:

```
═══ Phase -1.5: Self-Evaluation ═══
fit_score: 65/100 — 🟡 부분 적합

⚠ 부적합 axis:
  - docs_layout: 15/25 (ebs_style, 비표준 path)
    → 영향: PRD/Plan 출력 위치가 docs/1.Product/로 매핑됨
  - domain_fit: 10/25 (poker_game)
    → 영향: 도메인 코드 생성 시 일반 패턴만 적용 (RFID/blind level 의미 모름)

진행 가능. 우려 사항이 있다면 'stop' 입력 시 중단.
3초 대기 후 자동 진행...
═══════════════════════════════════
```

3초 대기 후 사용자가 멈추지 않으면 Phase 0 진입.

### Branch C: fit_score < 50 (🔴 RECOMMEND_ALTERNATIVE)

진행하지 않고 사용자에게 대안 권고:

```
═══ Phase -1.5: Self-Evaluation ═══
fit_score: 35/100 — 🔴 부적합

분석:
  - docs_layout: 5/25 (none, docs 디렉토리 부재)
  - tools_compat: 25/25 (충돌 없음)
  - complexity: 8/25 (typo fix, overkill)
  - domain_fit: 5/25 (의료 컴플라이언스, 도메인 특수)

⛔ /auto 권장하지 않음. 대안:
  1. 직접 처리 — Claude 일반 도구 (Edit, Bash 등)
  2. /iteration — 반복 cycle이 필요한 경우 (drift, 미구현 list)
  3. 그래도 /auto 진행 — 'force' 입력

선택: _
═══════════════════════════════════
```

사용자가 'force' 입력 시에만 Phase 0 진입.

## 본 보고서의 적용 예시

### Example 1: ebs 프로젝트 완성도 검토 (직전 critic 케이스)

```
Phase -1 결과:
  docs_layout: ebs_style → 15
  tools_registry: drift + kpi → 25
  complexity (35건 처리): 7/10 → 22
  domain: poker_game → 10
fit_score = 15 + 25 + 22 + 10 = 72 → 🟡 PROCEED
```

→ 진행하되 docs path + domain 부적합 안내. 사용자 의식적 진행 가능.

### Example 2: 일반 React 신규 기능

```
Phase -1 결과:
  docs_layout: react_style → 20
  tools_registry: lint + test + build + lighthouse → 25
  complexity: 5/10 (single feature) → 25
  domain: frontend_react → 25
fit_score = 20 + 25 + 25 + 25 = 95 → 🟢 GO
```

→ 즉시 진행.

### Example 3: 빈 프로젝트에서 typo fix

```
Phase -1 결과:
  docs_layout: none → 5
  tools_registry: [] → 25
  complexity: 1/10 (typo) → 8
  domain: generic → 25
fit_score = 5 + 25 + 8 + 25 = 63 → 🟡 PROCEED
```

→ 진행 가능하나 overkill 안내. 사용자 'stop' 입력 시 직접 처리 권장.

### Example 4: 의료 데이터 처리 (HIPAA 관련)

```
Phase -1 결과:
  docs_layout: standard_pdca → 25
  tools_registry: 자체 컴플라이언스 검증 도구 → 25
  complexity: 6/10 → 25
  domain: 의료 (HIPAA) → 5
fit_score = 25 + 25 + 25 + 5 = 80 → 🟢 GO 경계

근데 domain axis 5/25는 도메인 부적합 위험 큼 → 사용자 추가 안내 권장
```

→ 80 GO 경계지만 부적합 axis가 한 영역에 너무 낮을 때 추가 경고 추가.

## 추가 안전 장치: critical axis 보정

특정 axis가 극단적으로 낮으면 fit_score와 무관하게 PROCEED 또는 RECOMMEND로 강등:

| 조건 | 결과 |
|------|------|
| `domain_fit ≤ 5` (의료/금융/법률 컴플라이언스) | 🟡 PROCEED (도메인 위험 안내 강제) |
| `tools_compat ≤ 5` (도구 명시적 conflict) | 🔴 RECOMMEND_ALTERNATIVE |
| `complexity = 1` AND fit_score < 90 | 🟡 PROCEED (overkill 안내) |
| `complexity = 10` | 🔴 RECOMMEND_ALTERNATIVE (→ /iteration) |

## 출력 표준

Phase -1.5 항상 다음 형식 출력:

```
═══ Phase -1.5: Self-Evaluation ═══
fit_score: {score}/100 — {🟢|🟡|🔴} {GO|PROCEED|RECOMMEND_ALTERNATIVE}
  axes: docs={N}/25  tools={N}/25  complexity={N}/25  domain={N}/25
{필요 시 부적합 axis 안내 + 대안 권고}
{🟢: → Phase 0 진입 / 🟡: 3초 대기 후 진입 / 🔴: 사용자 confirm 대기}
═══════════════════════════════════
```

## 본 gate의 핵심 가치

직전 critic 보고서의 결론 — "/auto의 한계 = 컨텍스트 무지" — 의 핵심 보완:
- /auto가 자기 자신을 평가
- 사용자에게 솔직한 적합도 전달
- 부적합 시 대안 권고

사용자가 무의식적으로 /auto를 호출해도 자동 평가하여 안내. explicit-invocation 정책과 시너지: 사용자가 명시 호출했지만 적합도 낮으면 재고 기회 제공.
