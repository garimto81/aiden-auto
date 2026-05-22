# Embedded Critic Protocol (Quick Validation)

문서 생성 직후 삽입되는 빠른 품질 게이트. `/doc-critic`의 전체 4-Phase와 달리 문서 유형별 3개 핵심 기준만 검증.

## 호출 패턴

```
IF NOT --skip-critic:
  Agent(
    subagent_type="doc-critic",
    model=plan["doc-critic"],
    name="quick-critic-{doc_type}",
    description="{doc_type} 빠른 검증",
    team_name="{current_team}",
    prompt="[QUICK VALIDATION MODE]
    대상 문서: {filepath}
    문서 유형: {doc_type}
    
    아래 기준만 평가 (전체 4-Phase 아님, 빠른 검증):
    {criteria_for_doc_type}
    
    출력 형식:
    VERDICT: APPROVE | REJECT
    CONFIDENCE: HIGH | MEDIUM | LOW
    RISK_SCORE: 1-5
    FEEDBACK: [REJECT 시 구체적 개선 지시 — 어떤 섹션을 어떻게 수정해야 하는지]"
  )
  SendMessage(to="quick-critic-{doc_type}", message={type: "shutdown_request"})
```

## 문서 유형별 평가 기준

### plan

1. 필수 섹션 4개 존재 (배경, 구현 범위, 영향 파일, 위험 요소)
2. 섹션 간 논리 흐름 — 비약 0건 (앞 섹션에서 설명하지 않은 개념이 뒤 섹션에 등장하면 비약)
3. 설명 없는 전문 용어 0건

### design

1. 목차 연결성 + 비약 탐지 (맥락 연결, 비약 0건, 직관적 흐름, 난이도 순서)
2. 300자+ 섹션에 시각 자료(mermaid, 표, 이미지) 1개 이상 존재
3. 설명 없는 전문 용어 0건

### report

1. PDCA 4개 Phase(Plan, Design/Do, Check, Act) 모두 참조됨
2. 평균 문장 길이 40자 이하
3. 정량 지표(숫자, 퍼센트, 기간) 1개 이상 포함

## Rewrite Loop

```
IF VERDICT == REJECT AND FEEDBACK exists:
  1. 원래 writer 에이전트가 FEEDBACK 기반 1회 수정
     - Plan → executor (sonnet)
     - Design → architect (opus)
     - Report → writer (haiku)
  2. 동일 기준으로 재검증 (quick-critic-{doc_type}-retry)
  3. 재검증 결과는 최종 — 추가 rewrite 없음

IF VERDICT == REJECT AND FEEDBACK 없음:
  → APPROVE로 간주 (실행 가능한 피드백 없이 거부는 무효)
```

## 생략 조건

- `--skip-critic` 옵션 존재 시 모든 embedded critic 게이트 생략
- `--eco-3` 모드에서는 critic을 sonnet으로 다운그레이드

## 기존 게이트와의 관계

| 게이트 | 검증 대상 | 시점 | 공존 |
|--------|----------|------|------|
| Plan 4섹션 구조 검증 | 헤딩 존재 여부 | Design 진입 전 | critic 이후 실행 |
| Design 존재 검증 | 파일 존재 여부 | Do 진입 전 | critic 이후 실행 |
| Embedded Critic | 내용 품질 | 문서 생성 직후 | 구조 검증보다 먼저 실행 |
| `/doc-critic` | 전체 심층 분석 | 사후 수동 호출 | 독립적으로 유지 |
