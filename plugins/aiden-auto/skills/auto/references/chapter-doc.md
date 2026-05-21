---
name: chapter-doc
category: DOC
pipeline: [triage, chapter-doc]
next-skill: null
handoff: .claude/state/auto/doc-{slug}.md
agent_team: [planner, writer, critic, architect, document-specialist, reader-experience]
phase_path: [-2, -1, 0, 1, 4, cleanup]
---

# Chapter: DOC — 기획서 / PRD / Spec 작성

> **카테고리**: DOC
> **트리거 키워드**: 기획, 기획서, PRD, spec, 명세, 문서, 정리, 작성
> **v27.2 강화**: XML 구조화 + Multi-perspective doc validation + Cleanup

<Purpose>
사용자의 문서 작성 요구를 받아 구조 설계 → 본문 작성 → 다중 검증 → 저장 사이클로 자율 처리. 18세 기준 doc-critic + 기술 검증 병렬.
</Purpose>

<Use_When>
- PRD 작성 ("결제 모듈 기획해줘")
- Plan 문서 ("실행 계획 정리")
- Design 문서 ("기술 설계 문서")
- Report 작성 ("일일 보고서")
- spec 명세 ("API spec 작성")
</Use_When>

<Do_Not_Use_When>
- 코드 구현 → chapter-code
- 단순 메모/comment → !quick magic word
- 영상/이미지 디자인 → chapter-media
</Do_Not_Use_When>

<Why_This_Exists>
문서는 작성자만으로 부족. 기술 정확도(architect) + 가독성(critic) + 일관성(document-specialist) 병렬 검증 필요.
</Why_This_Exists>

<Workflow_Diagram>

```
[Triage: DOC]
      │
      ▼
Phase -1 (기존 docs 스캔)
      │
      ▼
Phase 0 (문서 종류 결정)
   └─ PRD | Plan | Design | Report | Generic
      │
      ▼
Phase 0.5 (Provenance Capture, NEW)
   ├─ 직전 같은 슬러그 산출물 탐지
   ├─ 사용자 지시 원문 캡처
   └─ frontmatter Provenance Block 자동 주입
      │
      ▼
Phase 1 (작성 — 4 step)
   ├─ Step 1.0: Reader Plan (Hook/Thesis/Anchor/Arc 사전 설계)
   ├─ Step 1.1: planner (목차 + 4-act 정렬)
   ├─ Step 1.2: writer (Reader Plan 인풋 + Feature Block 직접 작성)
   └─ Step 1.3: Multi-perspective Validation (병렬 4시각)
      ├── critic (doc-critic, 18세 기준)
      ├── architect (기술 검증, 선택)
      ├── document-specialist (구조 일관성)
      └── reader-experience (P7 Hook/Thesis/Anchor/Rhythm/Arc)
      │
      ▼
Phase 4 (저장 + 커밋)
      │
      ▼
Phase Cleanup
```

UI 목업 / 디자인 시안 / 인터랙티브 데모는 본 chapter의 적용 범위가 아니다 → `chapter-media` 또는 `mockup-hybrid` 스킬로 라우팅.

</Workflow_Diagram>

<Execution_Policy>
- 다이어그램 우선 (시각:텍스트 = 80:20)
- 섹션당 개념 3개 이하 (작업기억 한계)
- 12-large-document-protocol.md 준수 (대형 문서 청킹)
- Multi-perspective 병렬 (각자 독립 검증)
- ALL APPROVE 필수
- **rule 19 (Feature Block 기획 문서 표준) 강제**: 기획 문서는 처음부터 `.md`로 직접 작성. Feature Block 4종(Symmetric / Grid / Stat / Flow) 조합 + Provenance Block + Edit History 필수.
</Execution_Policy>

<Phase_0_5_Provenance_Capture>

## Phase 0.5 — Provenance Capture (NEW, rule 19 연동)

본문 작성 직전 **반드시** 출처 캡처. 자동 처리 (사용자 개입 없음):

```
1. 직전 같은 슬러그 산출물 탐지
   → grep ARCHIVE/, docs/templates/, docs/* 슬러그 매칭
   → 발견 시 predecessors 항목 자동 생성

2. 사용자 지시 원문 캡처
   → 현재 세션 마지막 user message 추출
   → trigger_summary + user_directive 자동 생성

3. 직전 산출물 status 자동 판정
   → discarded (사용자가 폐기 지시)
   → superseded (자연 대체)
   → derived_from (계승)

4. frontmatter Provenance Block 자동 주입
5. 본문 상단 Edit History 항목 자동 추가
```

자세한 양식은 `rules/19-feature-block-document.md` § P4/P5 참조.

</Phase_0_5_Provenance_Capture>

<Steps>

## Phase 1 — 본문 작성

### Step 1.0: Reader Plan (NEW, rule 19 § P7 강제)

**본문 작성 전 반드시 수행. 누락 시 writer 호출 차단.**

writer는 다음 4종을 사전 설계한 뒤에야 본문 작성 권한을 얻는다:

```
+-----------------------------------------------------------------+
|  Reader Plan — 본문 시작 전 4종 사전 설계 (rule 19 § P7)        |
+-----------------------------------------------------------------+

1. Hook 초안 (P7-A)
   첫 200자 안에 들어갈 비유 / 인용구 / 충격 통계 / 질문
   → 후보 3개 작성 후 1개 선택

2. Thesis 한 줄 (P7-B)
   문서 전체를 80자 이하로 압축
   → 모든 섹션이 이 한 줄로 수렴 가능한지 검증

3. Reader Anchor (P7-C)
   · 입구: 독자 현재 상태 (한 줄)
   · 출구: 끝까지 읽은 후 변화 (한 줄)
   → "X 상태에서 Y 상태로 데려가는 문서" 형식

4. Narrative Arc (P7-E)
   Act 1 Setup     │ Act 2 Incident │ Act 3 Build │ Act 4 Resolution
   각 act 도입에 1줄 hook 사전 결정
```

산출물: `.claude/state/auto/reader-plan-{slug}.md` (writer 호출 시 인풋)

### Step 1.1: 구조 설계 (planner)
- 목차 skeleton만 (내용 X)
- 다이어그램/스크린샷 위치 사전 지정
- 용어는 부록으로
- **Reader Plan의 4-act 구조에 목차 정렬** (Setup → Incident → Build → Resolution 매핑)

### Step 1.2: 본문 작성 (writer)
- Reader Plan을 인풋으로 사용 (Hook/Thesis/Anchor/Arc 모두 반영)
- 12-large-document-protocol.md 준수
- 소형 (<100줄): Write 단일
- 중형 (100~300줄): Write skeleton + Edit 섹션별
- 대형 (300줄+): Map-Reduce 청킹

### Step 1.3: Executive Summary 작성 (NEW v28.5 — **v28.6 Phase -1.5 자율 판단 기반**)

**Trigger Logic (v28.6)**: Phase -1.5 Part D 결과로 `active-goal.json.executive_summary.enabled == true` 자동 설정 시 본 단계 발동. `false` (또는 부재) 시 자동 skip → Step 1.4 직행.

### 자율 판단 결과별 동작

| executive_summary.enabled | mode | 동작 |
|--------------------------|------|------|
| true | inline | 본문 첫 섹션 `## Executive Summary` 자동 생성 |
| true | separate | 별도 파일 `docs/00-prd/{slug}.exec-summary.md` 자동 생성 |
| false / 부재 | — | Step 1.3 skip → Step 1.4 직행 |

### 양식

- 구조 (≤50줄): Hook + Thesis + 3 다이어그램 + 5 결정 + 3 Action + 한 줄 결론
- 양식 + 검증 룰: `references/executive-summary-template.md`
- 자율 판단 휴리스틱: `references/phase-minus-1.5-deep-interview.md` Part D
- 검증: 다음 Step 1.4 의 4 시각이 본문 + Executive Summary 모두 검증

목적: 사용자가 본문 안 읽고도 1 페이지로 전체 파악 (Core Philosophy 정합 + 자율 판단으로 진입점 최소화).

### Step 1.4: Multi-perspective Validation (병렬 4시각)

```
4개 agent 동시 호출:

┌─────────────────────────┐
│ critic (doc-critic)     │  ← 18세 일반인 이해도, 비약 감지
├─────────────────────────┤
│ architect (READ-ONLY)   │  ← 기술 정확도 (기술 문서 시)
├─────────────────────────┤
│ document-specialist     │  ← 구조/네이밍/일관성
├─────────────────────────┤
│ reader-experience NEW   │  ← Hook/Thesis/Anchor/Rhythm/Arc (P7)
└─────────────────────────┘

집계:
  ALL PASS → Phase 4
  ANY NEEDS_REVISION → writer 재호출 (max 2회)

reader-experience REJECT 트리거:
  · P7-A 위반 → Hook 부재 / 메타 시작
  · P7-B 위반 → Thesis 80자 초과 / 누락
  · P7-C 위반 → 입구/출구 둘 중 하나 누락
  · P7-D 위반 → 5섹션 연속 산문
  · P7-E 위반 → Act 누락 / 평탄 구조
```

## Phase 4 — 저장 + 커밋 + Confluence Sync (NEW v28.5)

| 단계 | 동작 |
|------|------|
| 4.0 | 파일 저장 위치 확정 (docs/00-prd/, docs/01-plan/) |
| 4.1 | git commit: `docs(prd): {feature} 요구사항 반영` |
| 4.2 | **Confluence sync (NEW v28.5 + trigger logic 강화 v28.5.2)**. Trigger: Phase -1.5 Part C 답변 결과로 `active-goal.json.confluence_sync.enabled == true` 자동 설정. 본 Phase 4.2 진입 시 자동 호출 (사용자 확인 Q 없음). `python C:/claude/lib/confluence/md2confluence.py <md_file> <page_id>` 자동 호출. Executive Summary 가 별도 파일이면 child 페이지로 sync. 상세: `references/confluence-sync-flow.md` |
| 4.3 | 사용자 보고: 경로 + 줄수 + 다이어그램 N개 + (sync 시) Confluence URL |

## Phase Cleanup — NEW v27.2

```bash
rm -f .claude/state/auto/doc-{slug}.json
TeamDelete()
ls .claude/state/ | grep {slug} | wc -l  # 0
```

</Steps>

<User_Friendly_Explanation>

```
"기획서 작성 작업이군요. 이렇게 진행할게요:

  1단계: 독자 경험 설계 (이 문서가 사람을 어디로 데려갈지)
         · 첫 문장 hook (어떻게 끌어당길지)
         · 한 줄 thesis (전체를 80자로 압축)
         · 입구/출구 (독자가 얻을 변화)
         · 4단계 서사 (Setup → 사건 → 전개 → 결말)
  2단계: 무슨 내용을 다룰지 목차부터 짜고 (그림 위주로)
  3단계: 본문 작성 (다이어그램 80%, 글 20%)
  4단계: 4명 검토팀 동시 검토
         · 비평가: 15세도 이해되나?
         · 건축가: 기술적으로 맞나?
         · 문서 전문가: 다른 문서랑 일관되나?
         · 독자 경험 검토자: 끝까지 읽고 싶나?
  5단계: 저장 + 커밋
  6단계: 작업 흔적 정리"
```

</User_Friendly_Explanation>
