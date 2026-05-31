---
name: chapter-doc
description: 인간이 읽는 기획 문서 작성 (Reader Panel 강화 모드, GLOBAL v2.0). 5 audience 패널이 사후 독후감 평가하여 작위 침투/정체성 변질 사전 차단 + Autonomous iteration default (MAJOR 시 자동 writer 호출) + ASCII mockup writer 신규 (이미지 필요 지점에 ASCII 와이어프레임 출력).
version: 2.0.0
scope: global
team_pattern: true
agents:
  - planner
  - writer
  - reader-panel
  - doc-critic
  - prose-critic
  - architect
  - content-critic
  - document-specialist
  - ascii-mockup-designer
triggers:
  keywords:
    - "/chapter-doc"
    - "chapter-doc"
model_preference: opus
---

# /chapter-doc — 인간이 읽는 기획 문서 (Reader Panel 강화 v2.0)

## 목적

`/auto` 의 chapter-doc 워크플로우 + **Reader Panel macro 평가 강화** + **Autonomous iteration** + **ASCII mockup 자동 생성**.
직전 사고 (Foundation v3.1 무인화 7곳 작위 침투) 같은 **"작가는 만족하지만 독자는 불편한" 문서를 사전 차단**.

## v1.0 → v2.0 변경 요약

| 영역 | v1.0 | v2.0 (현재) |
|------|------|------------|
| 위치 | project-local (ebs 한정) | **글로벌** (`~/.claude/skills/chapter-doc/`) |
| MAJOR 처리 | 사용자 결정 요청 | **자동 writer 호출 + 자율 iteration** |
| ASCII mockup | 없음 | **writer 자동 생성** (이미지 필요 지점) |
| 사용자 진입점 | 평가 결과 보고 + 결정 | **결과만 보고** (Core Philosophy 합치) |

## 직전 사고 검증

| 사고 위치 (Foundation v3.1) | doc-critic 잡았나? | Reader Panel 잡았나? |
|----------------------------|:------:|:------:|
| §1.4 마지막 단락 작위 framing | ❌ (단락 PASS) | ✅ (artifice) |
| §1.6 미션 챕터 정체성 변질 | ❌ (단락 PASS) | ✅ (identity) |
| §7.3 Vision Layer 통째 80줄 | ❌ (단락 PASS) | ✅ (identity) |

→ 단락 단위 검증 (doc-critic) 으로는 못 잡는 **macro level 작위** 잡는 시스템.

## 사용법

```
/chapter-doc <문서 작성 요청>          # 작성 + Reader Panel + Autonomous iter (default)
/chapter-doc <기존 파일>              # 평가 + MAJOR/MINOR 자동 writer 호출 (default v2.0)
/chapter-doc <기존 파일> --review-only # 평가만, writer 호출 X (구 default)
/chapter-doc <요청> --no-panel         # Reader Panel 스킵
/chapter-doc <요청> --no-mockup        # ASCII mockup writer 스킵
/chapter-doc <요청> --max-iter=N       # iteration cap 변경 (default 3)
```

## 적용 범위 (HARD ENFORCE)

| 문서 종류 | 본 skill 적용 | 이유 |
|----------|:----:|------|
| `tier=external` PRD (외부 인계) | ✅ 강제 | 외부 stakeholder read |
| 200줄+ 기획/Plan/Report | ✅ 권장 | macro 작위 위험 ↑ |
| `tier=internal` 200줄+ | ⭐ 선택 | 내부 SSOT 도 인간 read |
| `tier=internal` 100줄 이하 | ❌ 스킵 | 비용 vs 가치 부적합 |
| backlog / changelog / generated | ❌ 스킵 | 자동 생성 영역 |
| LLM_ONLY (.spec.json) | ❌ 스킵 | 인간이 읽는 문서 아님 |

## ⚡ Autonomous Iteration 워크플로우 (v2.0 핵심)

```
[글로벌 chapter-doc Phase -2 ~ Phase 1.3 보존]
   ↓ ALL APPROVE
─────────────────────────────────────────────
[Phase 3.5 Reader Panel] (NEW v1.0)
   ├ Primary Reader (audience-target 매칭)   ← 명료성 (블로킹)
   ├ Secondary Reader (18세 일반인 default)  ← 명료성 (블로킹)
   ├ Advisory Reader (P6 문예 에디터 = prose-critic)  ← 글맛 (MINOR 한정) 🆕 v2.1
   └ Aggregator → Verdict
        (글맛 verdict 는 MINOR 이상 격상 불가 — 명료성 우선)
   ↓
─────────────────────────────────────────────
[Phase 3.6 Autonomous Writer Self-Fix] (NEW v2.0)
   IF Verdict == APPROVE:
       → Phase 4 진입
   IF Verdict == MINOR:
       → 자율 minor edit + Phase 4
   IF Verdict == MAJOR:
       iter += 1
       IF iter > max_iter (default 3):
           → 사용자 escalation
       ELSE:
           → writer 자동 호출 (Improvement Plan 적용)
           → Phase 3.5 재평가 (loop)
   IF Verdict == REJECT:
       → 즉시 사용자 escalation
─────────────────────────────────────────────
[Phase 4 저장 + 커밋 + Confluence sync + PR]
[Phase Cleanup 사례 등록 + 인덱스 동기화]
```

상세: `references/reader-panel-workflow.md` (v2.0 갱신 예정)

## 🎨 ASCII Mockup Writer (NEW v2.0)

### 트리거 조건

writer 가 본문 작성 중 다음 패턴 감지 시 자동 ASCII mockup 생성:
- "여기 이미지가 있어야 더 명확하다"
- "스크린샷이 필요한 UI 화면 설명"
- "다이어그램으로 시각화하면 좋은 흐름"
- 사용자가 본문에 `<!-- IMG_NEEDED: {설명} -->` 마커 명시

### 생성 형식

```
<!-- IMG_TODO: {설명} -->
\`\`\`ascii
+------------------------------------------+
|              ASCII 와이어프레임          |
|                                          |
|  [Logo]    Header           [User Avatar]|
|  +-------+ +-----------------------+    |
|  | Side  | |   Main Content       |    |
|  | Menu  | |   ...                |    |
|  +-------+ +-----------------------+    |
+------------------------------------------+
\`\`\`
> *MOCKUP · {캡션 — 이 화면이 무엇을 보여주는지}*
> 📌 **사용자 작업 필요**: 본 ASCII 를 이미지로 변환 → `images/foundation/{filename}.png` 저장
```

### 작성 규칙

| 규칙 | 의미 |
|------|------|
| **최대 너비 65자** | 터미널 / 좁은 화면 가독성 |
| **`<!-- IMG_TODO: -->` 마커** | grep 친화적 추적 |
| **캡션 1줄** | 화면 의미 명시 |
| **사용자 작업 안내 1줄** | 변환 방법 + 저장 위치 |
| **rule 11 ASCII 다이어그램 표준 준수** | 일관성 |

### 작업 분담

| 단계 | 주체 |
|------|------|
| ASCII mockup 디자인 | writer 또는 ascii-mockup-designer agent |
| 이미지 변환 (.png) | **사용자 수동** (외부 도구) |
| 본문 ASCII → 이미지 링크 교체 | 사용자 또는 후속 `/chapter-doc --update-images` |

→ ASCII 단계까지가 본 skill 의 책임. 이미지 변환은 사용자 영역.

## Reader Agent 정의

### Primary Reader (audience-target 자동 매칭)

| audience-target | Primary Reader 페르소나 |
|-----------------|----------------------|
| 외부 개발팀 | 신규 합류 시니어 개발자 (도메인 경험 X) |
| 경영진 | CFO/CEO 비전공 |
| PM | 다른 프로덕트 PM |
| 18세 일반인 | doc-critic 페르소나 |
| 운영자/Operator | 카지노 현장 스태프 |

### Secondary Reader (default = 18세 일반인)

### Advisory Reader (P6 문예 에디터 = prose-critic) 🆕 v2.1

DOC 문서에 항상 동반 호출. **글맛(서사·리듬·비유·몰입·기억) 전담**. 명료성은 평가 안 함.
**MINOR 한정** — 글맛 부족만으로 문서를 MAJOR/REJECT 시키지 못함 (명료성이 바닥, 글맛이 천장).

상세: `references/reader-agent-personas.md` (P6) + `agents/creative/prose-critic.md`

## 평가 지표 (명료성 5종 + 글맛 2종)

**명료성 (블로킹 — MAJOR/REJECT 가능)**

| 지표 | 측정 방법 | PASS 기준 |
|------|---------|----------|
| **recall** | read 직후 thesis 5 회상 | ≥4/5 |
| **ambiguity** | 모호 지점 식별 | ≤5 항목 |
| **cognitive** | 인지 부담 (5 챕터 산문 등) | ≥4/5 |
| **identity** | 챕터 메시지 ↔ 정체성 | =5/5 |
| **artifice** | 작위적 삽입 | =0 항목 |

**글맛 (advisory — MINOR 한정, 비블로킹) 🆕 v2.1**

| 지표 | 측정 방법 | 권고 기준 |
|------|---------|----------|
| **emotional_engagement** | 끝까지 읽고 싶은 몰입·재미 | ≥3/5 (미만 시 MINOR 권고) |
| **memorability** | 24시간 후 한 컷 회상 | ≥3/5 (미만 시 MINOR 권고) |

상세: `references/evaluation-schema.md` (v2.0)

## Verdict 룰 (3-tier + REJECT)

| Verdict | 조건 | 후속 (v2.0 autonomous) |
|---------|------|---------------------|
| **APPROVE** | 명료성 5 지표 PASS + 글맛 OK | Phase 4 진입 |
| **MINOR** | 명료성 1-2 지표 약한 FAIL | 자율 minor edit + Phase 4 |
| **LITERARY_MINOR** 🆕 | 명료성 PASS + 글맛만 FLAT | **권고 기록만 + Phase 4 (자동 수정 X)** |
| **MAJOR** | 3+ FAIL OR identity/artifice 위반 | **자동 writer 호출 + 재평가 (max 3 iter)** |
| **REJECT** | 5 모두 FAIL OR 회복 불가 | 즉시 사용자 escalation |

> **글맛 지표(emotional_engagement·memorability)는 MINOR 한정 (v2.1)**: 명료성이 PASS인데 글맛만 낮으면 verdict = MINOR (자율 minor edit + Phase 4). 글맛 부족은 MAJOR/REJECT 를 절대 유발하지 않음 — 명료성 게이트(identity/artifice)만 블로킹 권한 보유. "글맛 때문에 명료한 문서가 막히는 일" 없음.

## Circuit Breaker (CLAUDE.md Iron Law 4 정합)

| 상황 | 대응 |
|------|------|
| MAJOR iteration 3회 도달 | 사용자 escalation (강제) |
| 같은 챕터 MAJOR 3회 반복 | 사용자 escalation (강제) |
| Reader-Primary REJECT | 즉시 사용자 escalation |
| Reader 평가 자체 실패 (timeout) | Phase 4 그대로 진입 + 경고 |
| writer self-fix 동일 문제 반복 | 사용자 escalation |

## 기존 도구와의 분담

| 계층 | 도구 | 역할 |
|:---:|------|------|
| L1 자가 점검 | 룰 19 P7 (10항목) | 형식/구조 (작가 본인) |
| L2 micro 평가 | doc-critic skill | 단락별 이해도 (18세 일반인) |
| L2 챕터 평가 | content-critic agent | 챕터별 ★ + 강/약 문장 인용 |
| **L3 macro 평가 + auto fix** | **본 skill (Reader Panel + Autonomous Writer)** | **전체 narrative + 작위/정체성 + 자율 정합** |
| **L3 글맛 평가 (advisory)** | **prose-critic agent (P6)** | **서사·리듬·비유·몰입·기억 — MINOR 권고 한정** |
| L4 사용자 검증 | 사용자 review | REJECT 또는 max iter 도달 시만 |

→ doc-critic = micro 명료성 / Reader Panel = macro 명료성 / **prose-critic = 글맛 (advisory)**. 셋 다 **보완적 (대체 X)**. 명료성이 항상 우선, 글맛은 그 위에 더해지는 품질.

## CLAUDE.md Core Philosophy 정합

| 원칙 | 본 skill 정합 방식 |
|------|------------------|
| 사용자 진입점 최소화 | `/chapter-doc` 1회 호출 → 모든 Phase 자율 (REJECT/max iter 시만 escalation) |
| A/B/C 옵션 나열 금지 | Verdict 자동 판정 + 자율 iteration |
| 자율 iteration 최대화 | max 3 iter 안에서 자율 (writer self-fix 포함) |
| 결과만 보고 | iteration 진행 사일런트, 최종 결과만 보고 |
| 가장 완벽한 산출물 | 사용자 부담 0 + Reader Panel verdict APPROVE 보장 |

## 비용 통제

| 시나리오 | 추가 LLM call |
|---------|:------------:|
| 1 iter APPROVE (best case) | +2 (Primary + Secondary) |
| 2 iter (1 MAJOR → fix → APPROVE) | +5 (eval 2 + Primary + Secondary + writer fix) |
| 3 iter MAJOR (worst case) | +11 |
| ASCII mockup 1개 추가 | +1 (mockup designer) |

→ 적용 범위 한정 (tier=external 또는 200줄+) → 월 ~30 호출 이내

## 출력 형식

### 성공 (APPROVE — iter 1)

```
✅ Reader Panel APPROVE — {파일} (iter 1/3)

Primary ({audience}): APPROVE | recall:5/5 ambiguity:0 cognitive:5/5 identity:5/5 artifice:0
Secondary (18세 일반인): APPROVE | recall:4/5 ambiguity:2 cognitive:4/5 identity:5/5 artifice:0

→ Phase 4 진행 (저장 + 커밋 + Confluence sync)
```

### 자율 정합 후 성공 (APPROVE — iter 2)

```
🔄 iter 1: MAJOR (identity 위반 2건 + artifice 4건)
   ↓ writer 자동 호출 — 7 항목 정합
✅ iter 2: APPROVE — Phase 4 진행

총 비용: +5 LLM call / 사용자 진입점: 0
```

### REJECT (사용자 escalation)

```
❌ Reader Panel REJECT — {파일} (iter 3/3 도달)

iter history:
  1: MAJOR (identity 위반 4건)
  2: MAJOR (artifice 3건 — 새 위반 추가됨)
  3: MAJOR (cognitive 2/5 — 인지 부담 ↑)

writer self-fix 가 회복 불가능. 사용자 결정 필요:
  Path A: 본 plan으로 진행 강행
  Path B: 다른 audience 로 재평가
  Path C: 작업 보류
```

## 관련 룰

- `19-feature-block-document.md` (P7 Reader Experience Standard)
- `13-requirements-prd.md` (PRD subtype)
- `12-large-document-protocol.md` (대형 문서 청킹)
- `20-doc-discovery-pre-work.md` (변경 영향 추적)
- `11-ascii-diagram.md` (ASCII mockup 표준)

## 참조

- `references/reader-panel-workflow.md` — Phase 3.5 + 3.6 상세
- `references/reader-agent-personas.md` — 5 audience 페르소나
- `references/evaluation-schema.md` — 5 지표 + verdict 판정
- 글로벌 chapter-doc reference: aiden-auto plugin 의 `skills/auto/references/chapter-doc.md` (device-agnostic)

## 직전 사고 SSOT (영구 학습)

직전 사고 (Foundation v3.1, 2026-05-06):
- 무인화 7 곳 작위 침투 (§1.4, §1.6×2, §5.4, §7.3, §9.1, §9.2, §9.3)
- 룰 19 P7 자가 점검 10/10 통과시켰는데도 사고
- 사용자 critic 으로만 발견됨

**v2.0 첫 실전 결과** (2026-05-06):
- Reader Panel 작동 확인 — 직전 사고 정확히 잡음 (identity 2건 + artifice 5건)
- 추가로 사용자가 안 잡은 결함 10건 발견 (P1: contract 누락 6건 + P4: 약어 폭격 4건)
- v2.0 Autonomous iteration 으로 즉시 정합 진행 → Foundation v3.2

사례: `~/.claude/projects/C--claude-ebs/memory/case_studies/2026-05-06_chapter_doc_v2_first_run.md` (등록 예정)

## Edit History

| 날짜 | 버전 | 트리거 | 변경 |
|------|:----:|--------|------|
| 2026-05-06 | v1.0 | 사용자 directive — 신설 | project-local skill 신설 (`.claude/skills/chapter-doc/`) |
| 2026-05-06 | v2.0 | 사용자 directive — 글로벌 + 자율 iteration + ASCII mockup | 글로벌 이전 (`~/.claude/skills/chapter-doc/`) + Phase 3.6 Autonomous Writer Self-Fix + ASCII mockup writer 신규 + sample 사용자 진입점 0 default |
| 2026-06-01 | v2.1 | 문학적 매력 전담 장치 추가 (사용자 결정) | Advisory Reader P6(prose-critic) 연동 + 글맛 지표 2종(emotional_engagement·memorability) advisory 추가. MINOR 한정 — 명료성 게이트 불변. "명료성=바닥, 글맛=천장" 원칙 명문화 |
