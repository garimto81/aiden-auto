---
name: auto
description: >
  Universal Adaptive Orchestrator (v27.2) — 모든 작업 종류(기획/코드/QA/반복/조사/디자인)를 자동 분류하여 적절한 워크플로우와 Agent Team을 자율 구성하는 통합 스킬. /iteration 흡수 완료. Plugin Master (single global skill, no per-project copies). 평문 트리거 부분 부활 (코드/기획/QA/반복 키워드만). Skip for trivial questions, simple file reads, and !quick/!hotfix prefixed tasks. /aiden-auto:auto와 /iteration은 모두 이 스킬로 redirect. v27.2 — XML 구조화 chapter + Multi-perspective parallel validation + Pipeline metadata + Cleanup phase + 4 specialist agents (security-reviewer, test-engineer, tracer, verifier).
version: 27.2.0
triggers:
  keywords:
    - "/auto"
    - "auto"
    - "autopilot"
    - "/work"
    - "/iteration"
    - "iterate"
    - "cycle"
    - "ralph"
    - "ulw"
    - "ultrawork"
auto_trigger: true
---

# /auto v27.2 — Universal Adaptive Orchestrator (Indexed Chapter Architecture)

> **핵심 변경 (v27.2, 2026-05-04)** — OMC 영감 5개 패턴 적용:
> - **XML 구조화** chapter (`<Purpose>`, `<Use_When>`, `<Steps>` 등) — LLM 파싱 정확도 ↑
> - **Multi-perspective parallel validation** (architect+security+code-reviewer+qa-tester 동시 검증)
> - **Pipeline metadata** (frontmatter `pipeline:`, `next-skill:`, `handoff:`) — skill chaining 명확
> - **Cleanup phase** 명시 (모든 chapter에 state file 삭제 단계)
> - **Specialist agents** 4개 신규 (security-reviewer, test-engineer, tracer, verifier)
>
> **v27.0/v27.1 유지**:
> - `/iteration` 스킬 흡수
> - 카테고리 기반 chapter 라우팅
> - Phase -2 Triage (바이브 코더 친화)
> - communication-style.md 15세 기준 응답 룰
> - `/aiden-auto:auto`, `/iteration` 모두 이 스킬로 redirect

## 진입점

```
사용자 요구 (평문 또는 명령어)
        │
        ▼
┌─────────────────────────────────────┐
│  Step 0: Index Lookup (필수)        │
│  Read(references/index.yml)         │
│  → 카테고리 + chapter 결정           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Phase -2: TRIAGE                   │
│  Read(references/triage.md)         │
│  → 모호성 명확화 + Phase 경로 확정   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Chapter 로딩 (1개만)                │
│  Read(references/chapter-{CAT}.md)  │
│  → 카테고리별 워크플로우 실행         │
└──────────────┬──────────────────────┘
               │
               ▼
       Phase -1 → 0 → 1 → 2 → 3 → 4
       (chapter가 지정한 경로만 진행)
```

## Step 0: Index Lookup (MANDATORY)

`/auto` 호출 시 **반드시 먼저 실행**:

```
Read(C:/claude/plugins/aiden-auto/skills/auto/references/index.yml)
Read(C:/claude/plugins/aiden-auto/skills/auto/references/communication-style.md)  ← v27.1 NEW
```

`index.yml`은 **도서관 카탈로그** 역할:
- 카테고리 키워드 매핑
- chapter 경로
- Agent Team 구성
- Phase 경로
- 모호성 패턴
- 평문 트리거 화이트리스트
- Legacy alias

`communication-style.md`는 **모든 응답의 스타일 룰**:
- 사용자 = 비전문 개발자 + 방송 촬영 전문가 + 바이브 코더
- 모든 응답을 15세 기준으로 작성
- 비유 + 다이어그램 + 표 우선, 텍스트는 보조
- A/B/C 옵션 나열 금지 (자율 결정 + 이유)
- 약어/전문 용어 등장 시 첫 등장에서 풀어 설명

## Phase -2: TRIAGE (NEW v27.0)

`Read(references/triage.md)` 후 다음 6 step 수행:

| Step | 동작 |
|:----:|------|
| -2.0 | index.yml lookup |
| -2.1 | 1차 자동 분류 + confidence 계산 |
| -2.2 | 모호성 패턴 감지 (5대 패턴) |
| -2.3 | 카테고리 명확화 질문 (confidence < 0.7) |
| -2.4 | Phase 경로 + Agent Team 결정 |
| -2.5 | TriageContract 생성 |
| -2.6 | 사용자 1줄 확인 |

**핵심 원칙** (사용자 = 바이브 코더):
- 사전 = 질문 OK (Phase -2)
- 실행 중 = 자율 결정 + architect 검증
- 종료 = e2e zero-error까지 자동 iteration

## 카테고리 → Chapter 매핑

| 카테고리 | Chapter 파일 | Phase 경로 | Agent Team |
|---------|--------------|-----------|-----------|
| **DOC** | `chapter-doc.md` | -2 → -1 → 0 → 1 → 4 | planner + writer + critic + architect |
| **CODE** | `chapter-code.md` | -2 → -1 → 0 → 1 → 2 → 3 → 4 | executor + architect + code-reviewer + qa-tester |
| **QA** | `chapter-qa.md` | -2 → -1 → 0 → 3 → 4 | qa-tester + architect + executor |
| **ITERATION** | `chapter-iteration.md` | -2 → -1 → 0 → 1 → 2 → 3 → loop → 4 | iteration-curator-a/b + drift-reconciler + executor + architect |
| **RESEARCH** | `chapter-research.md` | -2 → -1 → 0 → 1 → 4 | researcher + analyst + writer |
| **MEDIA** | `chapter-media.md` | -2 → -1 → 0 → 1 → 2 → 4 | designer + writer + executor |

## Progressive Disclosure 로딩 규칙

각 Phase 진입 시 **해당 reference만** Read:

| Phase | 로딩 대상 | 로딩 시점 |
|:-----:|----------|----------|
| 진입 | `references/index.yml` + `references/communication-style.md` | /auto 호출 직후 (Step 0) |
| -2 | `references/triage.md` | Triage 단계 |
| chapter | `references/chapter-{CAT}.md` | 카테고리 확정 후 |
| -1 | `references/phase-minus-1-context-detect.md` | Triage 종료 후 |
| -1.5 | `references/self-evaluation-gate.md` | Phase -1 완료 후 |
| 0 | `references/common.md` (Contract 스키마, Fallback) | 필요 시 |
| 1 | `references/phase-1-plan.md` | Phase 1 진입 |
| 2 | `references/phase-2-build.md` | Phase 2 진입 |
| 3 | `references/phase-3-verify.md` | Phase 3 진입 |
| 4 | `references/phase-4-close.md` | Phase 4 진입 |

**옵션/특수 reference**:

| 파일 | 로딩 조건 |
|------|----------|
| `references/options-handlers.md` | `--mockup`, `--anno`, `--critic` 등 옵션 |
| `references/adaptive-phase-selection.md` | 복잡도 산정 직후 |
| `references/project-profiles.md` | profile 결정 시 |
| `references/multi-paradigm-support.md` | `--paradigm` 사용 시 |
| `references/kpi-pluggability.md` | `.claude/auto-config.yml` 존재 시 |
| `references/tool-integration.md` | tools_registry 비어있지 않을 때 |
| `guidelines/image-analysis.md` | 이미지 분석 시 |

## 평문 트리거 (부분 부활, v27.0)

`index.yml`의 `plain_text_triggers` lookup:

| 입력 패턴 | 발동 |
|-----------|:----:|
| "구현해", "추가해", "fix", "만들어" | ✅ |
| "기획해", "PRD", "spec 작성", "정리해" | ✅ |
| "테스트", "검증해" | ✅ |
| "반복", "cycle", "iterate" | ✅ |
| "뭐야", "어디야", "보여줘", "?" | ❌ (단순 read) |
| `!quick`, `!just`, `!hotfix` | ❌ (Magic Word bypass) |

## Legacy Alias (자동 redirect)

| 입력 | 처리 |
|------|------|
| `/iteration` | `/auto --mode=iteration` (chapter-iteration.md 자동 로딩) |
| `iterate`, `cycle` | 동일 |
| `/aiden-auto:auto` | `/auto` (동일 SKILL.md) |
| `ralph`, `ulw`, `ultrawork`, `autopilot` | `/auto "..."` |

## Agent Teams 패턴 (모든 chapter 공통)

```
TeamCreate(team_name="auto-{feature}")
  → Agent(subagent_type="...", name="...", description="...", team_name="auto-{feature}")
  → SendMessage(to="...", content="...", timeout=60)
  → TeamDelete()
```

**SendMessage timeout = 60초 표준**. Team-Lead `shutdown_response` 호출 금지.

## 무한 루프 차단 인프라

| 메커니즘 | 위치 | 동작 |
|----------|------|------|
| `loop_detector.py` PreToolUse(Agent) hook | `~/.claude/plugins/.../hooks/` | 동일 (subagent_type, prompt) 600초 내 3회 반복 시 자동 BLOCK |
| `circuit-breaker.json` 카운터 | `~/.claude/state/` | loop_detector_block, architect_reject, pdca_iter, auto_recursion 도메인 카운터 |
| SendMessage timeout=60 | 모든 호출 | 60초 미수신 시 다음 단계 진입 |
| TeamDelete 직전 session.yaml reset | Phase 4 CLOSE | 좀비 세션 방지 |

## Iron Laws (전 Phase 적용)

1. **TDD**: 실패 테스트 없이 코드 금지
2. **Debugging**: Root cause 없이 수정 금지
3. **Verification**: 증거 없이 완료 선언 금지
4. **Architect Approval**: Architect 검증 없이 Phase 4 진입 금지
5. **Bypass 금지**: `--no-verify`, `--force` 등 hook 우회 금지

## 자율 결정 시 검증 게이트 (v27.0 신규)

실행 중 변경사항 발생 시:

```
변경 감지 → WebSearch + WebFetch (최신 트렌드)
         → architect agent 검토 요청
         → APPROVE → 적용 + 1줄 보고
         → REJECT → 대안 검색 + 재검증
         → 3회 REJECT → 사용자 보고
```

## 옵션 통합 테이블

### 흐름 제어
| 옵션 | 효과 |
|------|------|
| `--skip-prd` | Phase 1 PRD 스킵 |
| `--skip-analysis` | Phase 1 사전 분석 스킵 |
| `--no-issue` | 이슈 연동 스킵 |
| `--strict` | E2E 1회 실패 즉시 중단 |
| `--skip-e2e` | E2E 검증 전체 스킵 |
| `--dry-run` | Phase 0-1까지만 실행 |
| `--eco` / `--eco-2` / `--eco-3` | 비용 절감 ~30% / ~50% / ~70% |
| `--worktree` | feature worktree에서 작업 |
| `--interactive` | Phase 전환 시 사용자 확인 |
| `--mode=iteration` | ITERATION 카테고리 강제 (구 /iteration alias) |

### 실행 옵션 (Step 2.0 처리)
| 옵션 | 효과 |
|------|------|
| `--mockup [파일]` / `--mockup-q` | 3-Tier 목업 / Quasar Minimal |
| `--gdocs` | Google Docs PRD 동기화 |
| `--critic` | 약점 분석 |
| `--debate` | 3-AI 병렬 분석 |
| `--research` | 코드베이스/외부 리서치 |
| `--daily` | 일일 대시보드 |
| `--slack <채널>` / `--gmail` | Slack/Gmail 분석 |
| `--con <page_id>` | Confluence 발행 |
| `--jira <cmd> <target>` | Jira 조회/분석 |
| `--figma <url>` | Figma 디자인 연동 |
| `--anno [파일]` | Screenshot→HTML→Annotation |
| `--drift-check` | drift detection (구 /iteration 기능) |
| `--evolve` | hot-swap curator 활성 (구 /iteration 기능) |

> **CRITICAL**: 실행 옵션 사용 시 `references/options-handlers.md` 반드시 Read.

## 자율 발견 모드

`/auto` 단독 호출 시:
- Tier 0 CONTEXT → 1 EXPLICIT → 2 URGENT → 3 WORK → 4 SUPPORT → 5 AUTONOMOUS
- 상세: `references/common.md`

## 세션 관리

| 명령 | 동작 |
|------|------|
| `/auto status` | 현재 상태 |
| `/auto stop` | 중지 + TeamDelete |
| `/auto resume` | 재개 |
| `python C:\claude\.claude\scripts\emergency_stop.py` | 완전 frozen 시 강제 종료 |

## 금지 사항 (HARD BLOCK)

### 작업 진행 관련
- 옵션 실패 시 조용히 스킵
- Architect 검증 없이 완료 선언
- 증거 없이 "완료됨" 주장
- 테스트 삭제로 문제 해결
- TeamDelete 없이 세션 종료
- architect로 파일 생성 (READ-ONLY)
- Skill() 호출 (Agent Teams 단일 패턴)
- Team-Lead `shutdown_response` 호출 (즉시 메인 세션 종료)
- 평문 트리거 disabled_patterns 매칭 시 발동

### 결정 점 패턴 (CRITICAL — v27.0 추가)

사용자 = 비전문 개발자/바이브 코더. 다음 패턴은 워크플로우 위반:

| 위반 | 예시 | 올바른 패턴 |
|------|------|-----------|
| **A/B/C 기술 옵션 나열** | "옵션 A: 새 브랜치 / B: main 직접 / C: 보류 — 선택?" | Claude 자율 결정 후 결과 + 이유 보고 |
| **인프라 형식 선택지** | "YAML / JSON / TOML 중 어느 것?" | best practice로 결정, 비유로 설명 |
| **fallback 떠넘기기** | "manifest 수정 불가 시 어떻게 할까요?" | 자율 처리 후 "이렇게 했습니다" |
| **threshold 결정 요청** | "confidence 0.6 / 0.7 / 0.8 중?" | 0.7로 결정, 근거 1줄 |

**감지 시 자동 대응**:
1. 옵션 나열 중단
2. Claude가 자율 결정 (세계 최고 개발자 역할 수행)
3. 결과 + 이유 + 비유로 친절 설명
4. `references/triage.md` 절대 금지 패턴 섹션 참조

### 사전 vs 실행 중 구분

| 단계 | 질문 가능 | 비고 |
|:----:|:---------:|------|
| Phase -2 (Triage) | ✅ 의미 차원 질문 OK | 카테고리 분류, 모호성 명확화 |
| Phase -1 ~ 4 | ❌ 결정 점 질문 금지 | 자율 + architect 검증 |
| 종료/보고 | ❌ 옵션 나열 금지 | 결과만 보고 |

## Migration from v25/v26 (2026-05-03)

| 변경 | v25/v26 | v27.0 |
|------|---------|-------|
| /iteration 스킬 | 별도 SKILL | 흡수 (chapter-iteration.md) |
| 카테고리 분류 | 없음 (모두 일반 PDCA) | Phase -2 Triage + 6 카테고리 |
| 평문 트리거 | 폐기 (16-auto-default DEPRECATED) | 부분 부활 (화이트리스트) |
| chapter 분할 | references/phase-N | + chapter-{CAT}.md (카테고리별) |
| index | 없음 | index.yml (Lookup DB) |
| /aiden-auto:auto | 별도 namespace | redirect to /auto |
