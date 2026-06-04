---
name: executive-summary-template
version: v28.5
loaded_from: chapter-doc
purpose: 1-page Executive Summary 표준 양식 (문서 전체 안 읽고도 전체 파악)
---

# Executive Summary 표준 양식

## 목적

문서 본문 (수십~수백 줄) 을 안 읽고도 사용자가 **1 페이지 (≤50줄) 로 프로젝트 전체 파악** 가능.

## 비유

비유: 책의 "들어가는 글" 또는 영화의 "예고편". 본문 안 봐도 핵심 결정 + 다음 행동을 알 수 있어야 한다.

## 구조 (총 ≤50줄)

```
+-------------------------------------------------------+
| Executive Summary — <문서 제목>                       |
+-------------------------------------------------------+
|                                                       |
|  1. Hook (1줄, ≤200자)                                |
|     비유 / 통계 / 질문 / 인용 중 하나                  |
|                                                       |
|  2. Thesis (1줄, ≤80자)                               |
|     문서 전체를 한 줄로 압축. 모든 결정이 이 줄로 수렴 |
|                                                       |
|  3. 3 핵심 다이어그램 (각 5-10줄)                      |
|     ┌──────────────────┐                              |
|     │ ① 현재 상태 / 문제 │                            |
|     │ ② 변경 후 / 해결   │                            |
|     │ ③ 전체 흐름        │                            |
|     └──────────────────┘                              |
|                                                       |
|  4. 5 핵심 결정 (각 1줄)                               |
|     - 결정 A: ... → 이유 ...                          |
|     - 결정 B: ... → 이유 ...                          |
|     - (최대 5개)                                       |
|                                                       |
|  5. 3 Action Item (각 1줄)                            |
|     □ Action 1: 사용자가 즉시 해야 할 것              |
|     □ Action 2: ...                                    |
|     □ Action 3: ...                                    |
|                                                       |
|  6. 한 줄 결론 (≤120자)                                |
|     본문 안 읽어도 알아야 할 한 줄                     |
|                                                       |
+-------------------------------------------------------+
```

## 발동 정책 (v28.6 — Phase -1.5 자율 판단 기반)

**자율 판단 기반 발동**. Phase -1.5 Deep Interview 의 Part D 에서 자율 판단 → 필요 시 사용자에게 질문 추가 → 사용자 답변(또는 자동 default)에 따라 `active-goal.json.executive_summary.enabled` 설정.

### 자율 판단 휴리스틱 (Phase -1.5 Part D 자동 평가)

다음 조건 **모두 true** 시 → 인터뷰에 Executive Summary 질문 추가:

1. `chapter == "DOC"` (다른 카테고리는 무조건 skip)
2. `!quick` / `!just` / `!hotfix` Magic Word **부재**
3. 다음 중 **하나 이상** 충족:
   - 사용자 입력에 키워드 ≥ 1개: `PRD` / `기획` / `전략` / `design` / `spec` / `보고서` / `report`
   - spec 예상 길이 ≥ 100줄 (brainstorming 산출물 추정 기준)
   - 이해관계자 키워드: `stakeholder` / `임원` / `전사` / `배포` / `보고`

조건 미충족 → **자동 skip** (질문 안 함, 생성 안 함). 진입점 0.

### 산출물 위치 (생성 시)

- **HTML 한 장 (html — 권장)**: `docs/00-prd/{slug}.summary.html` — 브라우저로 열면 한 장으로 보이는 요약 페이지
- **inline**: 본문 첫 섹션 (`docs/00-prd/{slug}.md` 의 `## Executive Summary` 섹션)
- **별도 파일 (separate)**: `docs/00-prd/{slug}.exec-summary.md` (본문 ≥ 300줄 권장 — 재읽기 부담 ↓)

### HTML 산출 스펙 (mode == html)

문서 본문을 안 읽어도 한 장으로 파악하는 **자기완결 단일 HTML**. B&W Refined Minimal:

- 팔레트만: `#222326 #555555 #8a8a8a #767676 #e5e5e5 #F4F5F8 #fff` / Inter 400·500·600 / `max-width:720px`
- **다이어그램 임베드**: 본문에서 추출한 Mermaid 는 `<pre class="mermaid">…</pre>` + mermaid.js CDN. ASCII 다이어그램은 `<pre>` 로 그대로.
- **CDN 보안**: 외부 script 는 **버전 고정 + crossorigin** 기본. 공유·배포용이면 **실제 SRI** 추가(srihash.org 로 계산). ⚠️ **가짜/플레이스홀더 integrity 해시 절대 금지** — 틀린 해시는 브라우저가 스크립트를 *차단*해 다이어그램이 안 그려진다. 실제 해시를 모르면 `integrity` 를 **생략**(버전 고정 `@11.x` + `crossorigin="anonymous"` 만). (2026-06-05 E2E 검증서 실측 — 에이전트가 가짜 해시 삽입 → mermaid 로드 차단 결함.)
- 섹션 순서 = 양식 구조: Hook → Thesis → 다이어그램 ≤3 → 결정 ≤5 → Action ≤3 → 한 줄 결론
- emoji / SVG / icon-font 금지. 외부 CSS 금지 (mermaid.js 만 예외 — 다이어그램 렌더 목적)

```html
<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=720">
<title>Executive Summary — {제목}</title>
<style>
  body{font-family:Inter,sans-serif;max-width:720px;margin:0 auto;padding:32px;
       background:#fff;color:#222326;line-height:1.6}
  .hook{font-size:20px;font-weight:600}
  .thesis{color:#555555;border-left:3px solid #e5e5e5;padding-left:12px;margin:16px 0}
  h2{font-size:14px;color:#767676;text-transform:uppercase;margin-top:28px}
  pre{background:#F4F5F8;padding:16px;border-radius:6px;overflow-x:auto}
  ul{padding-left:18px} .concl{margin-top:24px;font-weight:500}
</style></head><body>
  <p class="hook">{Hook}</p>
  <p class="thesis">{Thesis}</p>
  <h2>핵심 흐름</h2>
  <pre class="mermaid">{본문에서 추출한 다이어그램}</pre>
  <h2>핵심 결정</h2><ul><li>…</li></ul>
  <h2>다음 행동</h2><ul><li>☐ …</li></ul>
  <p class="concl">{한 줄 결론}</p>
  <!-- 공유·배포용이면 integrity="sha384-…" 추가 -->
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js" crossorigin="anonymous"></script>
  <script>mermaid.initialize({startOnLoad:true});</script>
</body></html>
```

### 변천 이력

| 버전 | 정책 |
|------|------|
| v28.5 | 본문 200줄 조건부 |
| v28.5.1 | default 무조건 (200줄 조건 폐기) |
| **v28.6 (현재)** | Phase -1.5 자율 판단 기반 — 사용자 진입점 최소화 + 자율 영역 확대 |

## 생성 시점 (v28.9 — 본문 확정 후로 재배치)

`chapter-doc.md` 의 본문이 **검토·확정된 뒤** (Multi-perspective Validation 통과 후) 생성:

```
Phase 1.0  Reader Plan
Phase 1.1  planner (목차)
Phase 1.2  writer (본문)
Phase 1.4  Multi-perspective Validation (4 시각 — 본문만 검증·확정)
Phase 1.5  Executive Summary 추출 (확정본에서 후처리)   ← 재배치 (옛 1.3 → 1.5)
```

**왜 확정 후인가**: 요약은 *확정본의 핵심 비주얼·내용을 뽑는 추출* 작업이다. 본문 확정 전 생성하면 (옛 v28.5~v28.8 의 1.3 위치) 1.4 검증에서 본문이 수정될 때 요약이 낡은 채 남는다 (stale). 그래서 검증 후가 정위치.

## 검증 룰 (HARD ENFORCE)

| 항목 | 한계 | 위반 시 |
|------|:----:|--------|
| 전체 길이 | ≤ 50줄 | writer 자동 재호출 (max 2회) |
| Hook 길이 | ≤ 200자 | 재작성 |
| Thesis 길이 | ≤ 80자 | 재작성 |
| 다이어그램 개수 | ≤ 3개 | 압축 |
| 결정 개수 | ≤ 5개 | 우선순위 5개만 남김 |
| Action 개수 | ≤ 3개 | 우선순위 3개만 남김 |

## 작성 원칙

1. **Hook 우선**: 첫 200자로 사용자 끌어당김. 본문 안 읽고 끝낼 사람도 이 한 줄은 본다.
2. **Thesis 수렴**: 모든 결정/내용이 80자 Thesis 한 줄로 수렴 가능해야 함.
3. **다이어그램 = 본문에서 추출 (창작 금지)**: ≤3개 다이어그램은 **확정 본문에 이미 있는 것을 그대로 골라 재사용**한다. 새로 지어내지 않는다 (본문에 없는 그림 = 요약 아님). 시각 비율 ≥50%.
4. **결정 ≠ 작업**: 결정 = 의사결정 (선택지 중 하나). 작업 = 진행 단계. 혼동 금지.
5. **Action ≠ 결정**: Action = 사용자가 다음으로 할 일. "확인하기 / 승인하기 / 검토하기" 등.

## 응답 스타일 정합

`communication-style.md` 15세 기준:
- 비유 필수
- 다이어그램 우선
- 약어 풀이
- 한 줄 요약 마지막

## 예시 (참고용)

```markdown
# Executive Summary — 결제 모듈 PRD

**Hook**: 매일 1000명이 결제 실패로 이탈한다.

**Thesis**: 외부 PG 의존 단점 차단 위해 자체 결제 게이트웨이 도입.

## 현재 상태
[다이어그램 1]

## 변경 후
[다이어그램 2]

## 전체 흐름
[다이어그램 3]

## 핵심 결정
- A: PG 직접 통합 → 의존성 차단
- B: 토큰화 자체 구현 → PCI-DSS 비용 절감
- C: 카드 정보 미저장 → 보안 위험 ↓

## Action Item
□ 1주 안: 사용자 카드 데이터 마이그레이션 plan 승인
□ 2주 안: PG 계약 갱신
□ 3주 안: 결제 페이지 UI 시안 결정

**결론**: 자체 게이트웨이로 PG 의존 제거 + 결제 실패율 50% 감소 목표.
```
