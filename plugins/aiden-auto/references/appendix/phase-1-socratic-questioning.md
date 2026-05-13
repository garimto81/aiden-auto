# Phase 1 Appendix — Socratic Questioning (모호성 >= 0.5 시)

> 이 파일은 `phase-1-plan.md` 의 부록입니다. Phase 0.2 진입 시 lazy load.
> 원본: `phase-1-plan.md` (v25.2) 의 Step 0.2 섹션 분리 (Flaw 5 컨텍스트 예산 대응).

Ambiguity Score >= 0.5 감지 후, 구현 전 사용자 의도를 명확화하는 자동 질문 단계.

---

## Step 0.2a: Ambiguity Score 계산

```python
# Phase 0.2a — 사용자 요청의 모호성을 7개 팩터로 정량 측정
def calculate_ambiguity_score(user_request: str, current_phase: str) -> float:
    score = 0.0
    factors_triggered = []

    # F1: 파일 경로 미언급 (+0.15)
    if not contains_file_path(user_request):  # /, \, .ext 패턴 없음
        score += 0.15
        factors_triggered.append("no_file_path")

    # F2: 기술 용어 부재 (+0.10)
    if not contains_tech_terms(user_request):  # API, 함수명, 클래스명, 라이브러리명 없음
        score += 0.10
        factors_triggered.append("no_tech_terms")

    # F3: 특정 대상 미지정 (+0.15)
    if not contains_identifiers(user_request):  # PascalCase, snake_case, 따옴표 리터럴 없음
        score += 0.15
        factors_triggered.append("no_identifiers")

    # F4: 범위 미정의 (+0.10)
    if not contains_scope_qualifiers(user_request):  # only, all, specific, 단일, 전체 등 한정어 없음
        score += 0.10
        factors_triggered.append("no_scope")

    # F5: 다중 해석 가능 (+0.20) — 가장 높은 가중치
    if has_ambiguous_verbs(user_request) or pronoun_count(user_request) >= 2:
        # 모호 동사: fix, change, update, improve, handle, make, do
        score += 0.20
        factors_triggered.append("multi_interpretation")

    # F6: 컨텍스트 충돌 (+0.15)
    if phase_keyword_mismatch(user_request, current_phase):
        # 예: BUILD Phase에서 "설계 변경" 요청
        score += 0.15
        factors_triggered.append("context_conflict")

    # F7: 짧은 요청 (+0.15)
    if len(user_request) < 30:
        score += 0.15
        factors_triggered.append("short_request")

    return score, factors_triggered
    # 최대 합계: 1.00 (전 팩터 트리거 시)
```

**Magic Word Bypass**: `!quick`, `!just`, `!hotfix` 감지 시 score = 0 강제 (Socratic Questioning 전체 스킵).

## Step 0.2b: 팩터→차원 매핑 (질문 선별)

트리거된 팩터가 어떤 차원의 질문을 생성하는지 결정:

| 팩터 (Factor) | 가중치 | 매핑 차원 (Dimension) | 질문 생성 조건 |
|---------------|:------:|----------------------|---------------|
| F1: no_file_path | 0.15 | 범위 (Scope) | 파일/디렉토리 경로 없으면 범위 질문 |
| F2: no_tech_terms | 0.10 | 제약 (Constraints) | 기술 맥락 불명이면 제약 조건 질문 |
| F3: no_identifiers | 0.15 | 범위 (Scope) | 대상 불명이면 범위 재확인 |
| F4: no_scope | 0.10 | 수용 기준 (Acceptance) | 범위 미정이면 완료 기준 질문 |
| F5: multi_interpretation | 0.20 | 우선순위 (Priority) | 다중 해석이면 우선순위 질문 |
| F6: context_conflict | 0.15 | 목적 (Purpose) | Phase 불일치면 목적 재확인 |
| F7: short_request | 0.15 | 목적 (Purpose) | 정보 부족이면 목적 질문 |

**선별 알고리즘**:
1. 목적(Purpose)은 항상 포함 (가장 중요한 차원)
2. 나머지 4차원 중 트리거된 팩터 가중치 합산 → 상위 2개 차원 선택
3. 최종 3개 질문 (목적 1 + 상위 2)

```python
# Step 0.2b — 질문 선별
def select_questions(factors_triggered: list) -> list:
    # 목적은 항상 포함
    selected = ["purpose"]

    # 팩터→차원 가중치 집계
    dimension_scores = {
        "scope": 0, "constraints": 0, "priority": 0, "acceptance": 0
    }
    factor_to_dim = {
        "no_file_path": "scope", "no_tech_terms": "constraints",
        "no_identifiers": "scope", "no_scope": "acceptance",
        "multi_interpretation": "priority", "context_conflict": "purpose",
        "short_request": "purpose"
    }
    factor_weights = {
        "no_file_path": 0.15, "no_tech_terms": 0.10, "no_identifiers": 0.15,
        "no_scope": 0.10, "multi_interpretation": 0.20,
        "context_conflict": 0.15, "short_request": 0.15
    }
    for f in factors_triggered:
        dim = factor_to_dim[f]
        if dim != "purpose":  # purpose는 이미 선택됨
            dimension_scores[dim] += factor_weights[f]

    # 상위 2개 차원 선택
    top_2 = sorted(dimension_scores, key=dimension_scores.get, reverse=True)[:2]
    selected.extend(top_2)
    return selected  # 항상 3개
```

## Step 0.2c: 질문 생성 프롬프트

선별된 3개 차원에 대해 사용자 요청 컨텍스트를 반영한 구체적 질문을 생성:

```
# Lead가 AskUserQuestion으로 전달할 질문 생성 프롬프트
사용자 요청: "{user_request}"
트리거된 팩터: {factors_triggered}
선별된 차원: {selected_dimensions}

아래 차원별 템플릿을 사용자 요청에 맞게 구체화하세요.
각 질문은 1문장, 사용자가 바로 답할 수 있는 구체적 형태여야 합니다.
전문 용어 대신 평이한 한글을 사용하세요.

---
차원별 질문 템플릿:

[목적 Purpose]
- 기본: "이 작업으로 달성하려는 핵심 결과는 무엇인가요?"
- 구체화: "{user_request}의 최종 목표가 [A]인가요, [B]인가요?"
  (요청에서 추론 가능한 2개 선택지를 제시)

[범위 Scope]
- 기본: "변경 범위가 어디까지인가요?"
- 구체화 (F1 트리거): "어떤 파일/폴더를 수정해야 하나요?"
- 구체화 (F3 트리거): "구체적으로 어떤 함수/컴포넌트를 변경하나요?"

[제약 Constraints]
- 기본: "지켜야 할 기술적 제약이 있나요?"
- 구체화: "기존 {관련_시스템}과의 호환성을 유지해야 하나요?"
- 구체화: "성능/메모리/시간 제약이 있나요?"

[우선순위 Priority]
- 기본: "여러 변경 중 가장 먼저 해결할 것은?"
- 구체화: "요청에서 [A], [B], [C]가 감지되었는데, 우선순위는?"
  (요청에서 추출한 세부 항목을 나열)

[수용 기준 Acceptance]
- 기본: "완료로 판단할 구체적 기준은?"
- 구체화: "어떤 테스트/동작이 확인되면 완료인가요?"
- 구체화: "기존 동작이 변경되어도 괜찮나요?"
```

## Step 0.2d: 답변 처리 및 InitContract 반영

```python
# Step 0.2d — 답변을 InitContract에 구조화하여 반영
def process_socratic_answers(answers: list, init_contract: dict) -> dict:
    """
    사용자 답변을 InitContract.clarifications에 구조화.
    이후 Phase 1 (PRD, Plan)에서 참조.
    """
    clarifications = []
    for answer in answers:
        clarifications.append({
            "dimension": answer["dimension"],  # purpose/scope/constraints/priority/acceptance
            "question": answer["question"],
            "answer": answer["user_answer"],
        })

    init_contract["clarifications"] = clarifications

    # 답변 기반 복잡도 재조정 (선택적)
    # 범위 답변이 "시스템 전체"면 복잡도 +1
    for c in clarifications:
        if c["dimension"] == "scope" and "전체" in c["answer"]:
            init_contract["complexity_score"] = min(6, init_contract["complexity_score"] + 1)
        # 제약 답변이 구체적이면 STANDARD 이상 강제
        if c["dimension"] == "constraints" and len(c["answer"]) > 50:
            init_contract["complexity_score"] = max(2, init_contract["complexity_score"])

    return init_contract
```

## Step 0.2 전체 흐름 요약

```
사용자 요청 수신
  │
  ├─ Magic Word (!quick/!just/!hotfix) 감지? ──YES──→ score=0, 스킵
  │
  └─ Step 0.2a: Ambiguity Score 계산
       │
       ├─ score < 0.5 ──→ 질문 없이 Phase 0.3으로 진행
       │
       └─ score >= 0.5
            │
            ├─ Step 0.2b: 팩터→차원 매핑 → 3개 차원 선별
            ├─ Step 0.2c: 질문 생성 (차원별 템플릿 구체화)
            ├─ AskUserQuestion(3개 질문, 한 번에 전달)
            └─ Step 0.2d: 답변 → InitContract.clarifications 반영
                          + 복잡도 재조정 (scope/constraints 기반)
```
