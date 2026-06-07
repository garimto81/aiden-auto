---
name: chapter-qa
category: QA
pipeline: [triage, chapter-qa]
next-skill: null
handoff: .claude/state/auto/qa-{slug}.md
agent_team: [prd-to-checklist, qa-tester, architect, executor, test-engineer, security-reviewer, verifier, e2e-qa-prover, iteration-screenshot-verifier, perfect-output-validator, user-friendly-reporter]
phase_path: [-2, -1.5, -1, 0, QA-1, 3, 4, cleanup]
---

# Chapter: QA — 테스트 / E2E / 검증

> **카테고리**: QA
> **트리거 키워드**: 테스트, test, E2E, 검증, QA, regression, 회귀, 품질, 스크린샷 QA, 화면 검수, QA 보고서, 체크리스트 검증
> **v27.2 강화**: XML 구조화 + Multi-perspective + Cleanup + verifier 게이트
> **v28.9 강화**: QA 스크린샷 워크플로우 (기획서→체크리스트→스크린샷→판정→자율수정→보고)

<Purpose>
사용자의 검증 요구를 받아 단위→통합→E2E→보안→성능 사이클로 자율 처리. 실패 시 D0-D4 디버깅 + Iteration Loop 자동 진입.
</Purpose>

<Use_When>
- 전체 테스트 ("테스트 돌려줘")
- E2E 시나리오 ("E2E 돌려줘")
- 회귀 검사 ("회귀 검사")
- 보안 스캔 ("보안 점검")
- 성능 측정 ("벤치마크")
</Use_When>

<Do_Not_Use_When>
- 코드 작성 후 검증은 chapter-code Phase 3에서 자동 처리됨
- 단순 "이 함수 동작 확인" → !quick magic word
- drift 검증은 chapter-iteration
</Do_Not_Use_When>

<Workflow_Diagram>

```
[Triage: QA]
      │
      ▼
Phase 0 (검증 종류 결정)
   단위 | 통합 | E2E | 회귀 | 보안 | 성능 | 전부
      │
      ▼
Phase 3 (Multi-perspective QA, 병렬)
   ├── qa-tester: pytest/jest/flutter test
   ├── test-engineer: flaky 검사 + 커버리지 분석
   ├── security-reviewer: 보안 스캔 (선택)
   └── architect: 결과 해석
   실패 시 → Systematic Debugging D0-D4
      │
      ▼
Phase 3.5 (Verifier — fresh evidence)
      │
      ▼
Phase 4 (qa_report.md + 보고)
      │
      ▼
Phase Cleanup (NEW v27.2)
```

</Workflow_Diagram>

<Steps>

## Phase 0 — 검증 종류 결정

| 입력 | 종류 | 도구 |
|------|------|------|
| "테스트" | 단위/통합 | pytest, jest, vitest |
| "E2E" | 시나리오 | Playwright |
| "회귀" | regression | 최근 PR 영향 범위 |
| "보안" | OWASP | npm audit, bandit, gitleaks |
| "성능" | benchmark | 프로파일링 + 비교 baseline |

## Phase 3 — Multi-perspective QA (NEW v27.2, 병렬, F15 정합 v3)

```
4 핵심 agent (필수, ALL PASS 집계):
┌─────────────────────────┐
│ qa-tester               │  ← 실제 test 실행
├─────────────────────────┤
│ test-engineer           │  ← flaky 패턴 + coverage gap 분석
├─────────────────────────┤
│ architect               │  ← 결과 해석 + 우선순위 ranking
├─────────────────────────┤
│ verifier (Phase 3.5)    │  ← fresh evidence 재검증
└─────────────────────────┘

2 ad-hoc agent (선택, 검증 종류별 추가):
- security-reviewer (보안 검증 종류 시)
- executor (D3 수정 단계 시)

집계 (Aggregation Logic):
  ALL PASS (4 core) → Phase 4 진입
  ANY FAIL (core)   → D0-D4 systematic debugging
  REJECT 2회 누적   → 사용자 알림 (Circuit Breaker)

실패 시:
  D0 — 재현 가능?
  D1 — 가설 3개 (architect)
  D2 — 가설 검증
  D3 — 수정 (executor)
  D3.5 — Solution Critique (HEAVY)
  D4 — 회귀 검사
```

## Phase 3.5 — Verifier (fresh evidence)

```
verifier 호출:
  - test 결과 재실행 (fresh evidence)
  - "0 failed" 확인
  - skipped count 합리적인지
  - flaky test 격리 확인
  
  VERIFIED → Phase 4
  INSUFFICIENT_EVIDENCE → 재실행
```

## Phase 4 — 보고서 + Cleanup

```
qa_report.md 생성
git commit: docs(qa): {scope} 검증 보고서

Cleanup:
  rm -f .claude/state/auto/qa-{slug}.json
  TeamDelete()
```

</Steps>

<QA_Screenshot_Workflow>

## QA 스크린샷 워크플로우 (v28.9, 5단계)

> **활성 조건**: 기획 문서(PRD/spec)가 존재 + 트리거 키워드("스크린샷 QA", "화면 검수", "QA 보고서", "기획서 검수") 또는 화면 산출물 감지. 이 조건이면 Phase 0 다음에 본 5단계가 기존 Phase 3/4 를 대체·확장한다. 화면 없는 순수 코드 검증은 위 기본 Phase 3 경로 유지.

### ⭐ QA 증거 폴더 명명 규칙 (정본 — 사용자 결정 2026-06-08)

> **모든 QA 처리 폴더는 `{YYYYMMDD_HHMM_Description}` 형식으로 저장한다.**
> (예: `20260608_1430_card-deck-images`). 이전의 cycle*/goal-*/qa-YYYYMMDD-HHMMSS
> 등 제각각 명명을 **단일 형식으로 통일** — "혼란스럽게 저장됨" 문제 해소.

| 요소 | 값 |
|------|-----|
| 형식 | `YYYYMMDD_HHMM_Description` (날짜 8자리 + `_` + 24h 시각 4자리 + `_` + 설명 kebab) |
| 시각 | **로컬 시각** 기본 (사람이 QA 돌린 시점 직관). UTC 필요 시 `--utc` |
| Description | kebab-case, ≤6 단어. 이번 QA 회차가 다룬 대상 (한글 허용) |
| 생성 (강제) | `RUN_SLUG="$(python "$HOME/.claude/scripts/qa_evidence_dir.py" "<설명>")"` |

```
   ┌─ 항상-최신 (매 run 재생성, 사람은 여기만 열어 검토) ─┐
   │  <evidence-root>/_latest/                            │
   └──────────────────────────────────────────────────────┘
                       │ run 종료 시 동결 복사
                       ▼
   ┌─ 회차 동결 스냅샷 (정본 명명) ───────────────────────┐
   │  <evidence-root>/{YYYYMMDD_HHMM_Description}/         │
   │  예) 20260608_1430_card-deck-images/                 │
   └──────────────────────────────────────────────────────┘
```

- **본 챕터의 모든 `{slug}` := `{YYYYMMDD_HHMM_Description}`** (위 헬퍼 출력). 따라서
  아래 `test-results/qa-{slug}/` 작업 폴더는 `test-results/qa-20260608_1430_<desc>/` 로,
  프로젝트 증거 스냅샷은 prefix 없이 `{YYYYMMDD_HHMM_Description}/` 로 생성된다.
- `_latest/` (또는 영역 폴더 `cc/`·`lobby/`·`gameplay/`) 는 **롤링 검토 폴더로 유지** — 본 명명 규칙은 *동결 스냅샷*에 적용.
- **기존 폴더는 보존**("Removal ≠ Answer") — 신규 회차만 본 형식 사용. 프로젝트별 INDEX 가 있으면 그 규칙도 본 형식으로 정합.

```
Phase 0 (검증 종류 결정)
      │
      ▼
1단계  PRD → 체크리스트          [prd-to-checklist]
   기획서 수락기준 → checklist.yaml (항목별 kind 박제)
   out: test-results/qa-{slug}/checklist.yaml
      │
  ┌───┴─── 항목별 kind 분기 ───┐
 VISUAL_INTERACTION       LOGIC_DATA
      │                       │
      ▼                       ▼
2단계 스크린샷 수집        2'단계 텍스트 증거 수집
 [iteration-screenshot-     [qa-tester Mode B]
  verifier]                 E2E/unit + 로그 + status matrix
 expected_route 순회        (스크린샷 금지 — §3.B)
 시작/핵심/성공 ≥3장        out: logic-evidence/{id}.md
 out: shots/{id}-{state}.png
      └──────────┬────────────┘
                 ▼
3단계 매핑 + 통과 판정
   [checklist_screenshot_mapper.py] ← 파일 연결 + 구조 게이트
   [e2e-qa-prover]                  ← 의미 판정(콘솔에러/coverage)
   mapper 가 e2e 판정을 --verdicts 로 흡수 → checklist verdict 기록
   [checklist_updater.py]           ← stats 갱신
                 │
            미통과(fail) > 0?
            ┌────┴────┐
           YES        NO
            │          │
            ▼          │
4단계 자율 iteration    │
   [pdca-iterator] + circuit-breaker(rule 17)
   fail_reason → executor 수정 → 2단계 해당 route 재캡처 → 3단계 재판정
   종료(rule 21 Case 3): 전항목 pass | CB 5회 | 동일 fail 3회 PLATEAU
            └────┬─────┘
                 ▼
5단계 사용자 보고
   [perfect-output-validator] Gate1 7항목
   [user-friendly-reporter]   비개발자 변환
   [event_dispatcher.py]      진행률
   out: test-results/qa-{slug}/QA-REPORT.md
```

### 1단계 — 기획 문서 → 체크리스트

```
Agent(subagent_type="prd-to-checklist", model=plan["prd-to-checklist"] or "haiku",
      prompt="PRD={prd_path}\nslug={slug}\n수락기준→checklist.yaml 변환, 항목별 kind 판정")
→ test-results/qa-{slug}/checklist.yaml (pending[] 에 kind/acceptance_criteria/expected_route)
```

kind 조기 판정 — `iteration-spec-classifier` audience 로직 재사용:
`user|art-designer → VISUAL_INTERACTION` / `developer|모호 → LOGIC_DATA` / `!visual|!logic` override.

### 2단계 — 증거 수집 (kind 분기)

- **VISUAL 항목** → `iteration-screenshot-verifier`: `expected_route` 순회, 상태 변형(초기/핵심/성공) ≥3장 → `test-results/qa-{slug}/shots/{id}-{state}.png`. 정적 mockup 은 `scripts/screenshot-capture.ps1` 배치 캡처.
- **LOGIC 항목** → `qa-tester` Mode B: E2E/unit + 로그/status matrix → `test-results/qa-{slug}/logic-evidence/{id}.md` (스크린샷 금지).

### 3단계 — 매핑 + 통과 판정

```bash
# 1) e2e-qa-prover 가 kind별 의미 판정 → verdicts.json 산출
#    (VISUAL: 콘솔에러0+edge≥3 / LOGIC: status matrix+ERROR0+coverage≥80%)
# 2) mapper 가 파일 연결 + 구조 게이트(VISUAL≥3장, LOGIC 증거존재) + e2e verdict 흡수
python "$HOME/.claude/scripts/checklist_screenshot_mapper.py" \
  --checklist test-results/qa-{slug}/checklist.yaml \
  --verdicts test-results/qa-{slug}/e2e-verdicts.json
# → 각 항목 evidence + verdict(pass|fail) + fail_reason 기록, all_pass 요약 stdout
```

### 4단계 — 자율 iteration (circuit-breaker 연결)

```
mapper 요약 all_pass == false →
  pdca_iterator.count += 1 (state/circuit-breaker.json, rule 17)
  count < 5:
    fail 항목 fail_reason → executor 수정
    → 2단계 재진입 (해당 route/항목만 재캡처)
    → 3단계 재판정 (mapper 재실행)
    ※ screenshot-verifier regression diff 로 "수정이 다른 화면 깨뜨렸나" 자동 감지
  count >= 5 OR 동일 fail_reason 3회 PLATEAU:
    → rule 17 Circuit Breaker 에스컬 출력 (요구사항 재정의/reset/중단)
```

### 5단계 — QA 문서 보고 + 회차 동결

```
perfect-output-validator (Gate1 7항목) PASS
  → user-friendly-reporter 가 QA-REPORT.md 비개발자 변환
  → event_dispatcher.py COMPLETED 이벤트
  → 회차 동결: _latest/ → {YYYYMMDD_HHMM_Description}/ 복사 (정본 명명 규칙)
```

회차 동결 (정본 명명 규칙 적용):
```bash
RUN_SLUG="$(python "$HOME/.claude/scripts/qa_evidence_dir.py" "<이번 QA 설명>")"
# 예: RUN_SLUG=20260608_1430_card-deck-images
cp -r <evidence-root>/_latest "<evidence-root>/$RUN_SLUG"   # 동결 스냅샷 보존
```

`QA-REPORT.md` 구성: TL;DR 한 줄(통과 N/총 M) + 체크리스트 통과 현황 표 + 화면 갤러리(VISUAL, 캡션) + "테스트 N건 통과"(LOGIC, 스크린샷 없음) + 자동 수정 내역 + 한 줄 요약. 내부 ID(QA-003)/verdict 코드는 reporter 가 평문 변환.

</QA_Screenshot_Workflow>

<User_Friendly_Explanation>

```
"검증 작업이군요. 이렇게 진행할게요:

  1단계: 어떤 검사가 필요한지 파악
  2단계: 4명 동시 검사
         · 검수원: 실제 테스트 실행
         · 테스트 전략가: flaky 패턴 분석
         · 보안 검사관: 취약점 (보안 종류 시)
         · 건축가: 결과 해석
  3단계: 검증관(verifier)이 결과 진짜인지 확인
  4단계: 보고서 + 정리

  실패 5번 반복 → 사용자 보고 (무한 루프 방지)"
```

스크린샷 QA(화면 검수) 일 때:

```
"화면 검수 작업이군요. 이렇게 진행할게요:

  1단계: 기획서를 읽고 '확인할 항목 목록'(체크리스트)을 만들어요
         (화면 항목은 사진으로, 백엔드 항목은 테스트로 자동 구분)
  2단계: 화면을 실제로 띄워서 사진을 최대한 많이 찍어요
  3단계: 체크리스트 항목마다 알맞은 사진/테스트를 붙여 통과 여부 판정
  4단계: 통과 못한 항목은 자동으로 고치고 다시 찍어 재확인 (반복)
  5단계: 사진 갤러리 + 통과 현황표가 담긴 QA 보고서를 드려요
         이번 회차 사진은 '날짜_시각_설명' 폴더(예: 20260608_1430_카드덱)에
         가지런히 저장돼요 — 폴더가 뒤죽박죽 안 되게 이름이 항상 같은 규칙

  실패 5번 반복 → 사용자 보고 (무한 루프 방지)"
```

</User_Friendly_Explanation>
