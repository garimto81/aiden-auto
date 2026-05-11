---
name: chapter-research
category: RESEARCH
pipeline: [triage, chapter-research]
next-skill: chapter-doc  # 리서치 결과를 문서로 정리 가능
handoff: .claude/state/auto/research-{slug}.md
agent_team: [researcher, analyst, writer, critic, tracer]
phase_path: [-2, -1, 0, 1, 4, cleanup]
---

# Chapter: RESEARCH — 조사 / 분석 / 비교 / 트렌드

> **카테고리**: RESEARCH
> **트리거 키워드**: 조사, 리서치, research, 분석, 비교, 트렌드, 알아봐, 찾아봐
> **v27.2 강화**: XML + tracer 통합 + Cleanup

<Purpose>
사용자의 조사/분석 요구를 받아 정보 수집 → 정제 → 보고서 작성. 출처 메타데이터 필수, 신뢰도 명시, 인과 분석 시 tracer 통합.
</Purpose>

<Use_When>
- 코드 분석 ("코드베이스 분석")
- 외부 트렌드 ("최신 트렌드")
- 라이브러리 비교 ("X vs Y 비교")
- 학술 자료 ("논문 검색")
- 인과 추적 (NEW v27.2, "왜 이렇게 됐나?")
</Use_When>

<Workflow_Diagram>

```
[Triage: RESEARCH]
      │
      ▼
Phase 0 (리서치 종류 결정)
   코드 | 외부 | 학술 | 비교 | 트렌드 | 인과(NEW)
      │
      ▼
Phase 1 (수집 → 정제 → 작성)
   ├─ researcher: 정보 수집
   │   · 코드: Glob+Grep+Read
   │   · 외부: WebSearch+WebFetch+context7
   │   · 인과 (NEW): tracer 위임 (3 lane)
   ├─ analyst: 정제 + 패턴
   ├─ writer: 보고서 (Visual-First)
   └─ critic (Multi-perspective, NEW): 신뢰도 검증
      │
      ▼
Phase 4 (저장)
      │
      ▼
Phase Cleanup (NEW)
```

</Workflow_Diagram>

<Steps>

## Phase 1.1 — 정보 수집 (researcher 또는 tracer)

리서치 종류에 따라:
- 일반 조사 → researcher (Glob+Grep+Read+WebSearch+context7)
- **인과 추적** (NEW v27.2) → tracer (3 parallel lanes)

출처 메타데이터 필수:
- 모든 정보에 URL 또는 file:line 인용
- WebSearch 결과는 Sources 섹션 필수
- context7 결과는 라이브러리 버전 명시

## Phase 1.2 — 정제 (analyst)

```
analyst 호출:
  · 중복 제거
  · 충돌 해소 (출처 신뢰도 기준)
  · 패턴 발견
  · 카테고리화

  output:
    summary: 핵심 인사이트 (5개 이하)
    detailed_findings: 카테고리별
    contradictions: 충돌 정보
    confidence: 각 finding의 신뢰도
```

## Phase 1.3 — 보고서 (writer + critic 병렬, NEW)

```
writer:    보고서 작성 (Visual-First, MD-first 강제 — rule 18)
critic:    신뢰도 검증 (병렬)

ALL APPROVE → Phase 4
```

> **rule 18 강제**: 보고서 default = `.md`. HTML 직접 생성은 3조건 모두 만족 시에만 (사용자 명시 + 시각 산출물 + MD 표현 불가). HTML→MD 변환 작업 절대 금지. 좌우 대칭/카드 그리드는 MD 인라인 `<table role="presentation">` 패턴 사용 (rule 11 카탈로그).

## Phase 4 — 저장

```
저장 위치: docs/research/{YYYY-MM-DD}-{topic}.md
git commit: docs(research): {topic} 조사 보고서
```

## Phase Cleanup (NEW v27.2)

```bash
rm -f .claude/state/auto/research-{slug}.json
rm -f .claude/state/auto/research-tracer-{slug}.json
TeamDelete()
```

</Steps>

<User_Friendly_Explanation>

```
"조사 작업이군요. 이렇게 진행할게요:

  1단계: 어디서 찾을지 결정 (내부 코드? 웹? 인과 추적?)
  2단계: 자료 모으고 정리
  3단계: 핵심만 추려서 보고서 작성 (출처 표기)
  4단계: 신뢰도 검증
  5단계: 저장 + 정리

  비전문가도 이해할 수 있게 비유랑 표 위주로."
```

</User_Friendly_Explanation>
