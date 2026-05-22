# Phase 1 Appendix — Plan Steps (사전 분석 → 복잡도 → 계획 수립)

> 이 파일은 `phase-1-plan.md` 의 부록입니다. Step 1.0–1.3 진입 시 lazy load.
> 원본: `phase-1-plan.md` (v25.2) 의 Step 1.0–1.3 섹션 분리 (Flaw 5 컨텍스트 예산 대응).

> **v28.1+ 호환 노트**: 아래 Agent() 호출 예시는 v28.1 이전 (`team_name=`, `SendMessage`, `shutdown_request`, `Mailbox`) 잔재이지만,
> **분석 단계 / 복잡도 점수 / Iron Laws / A1–A7 공격 벡터 / Quality Gate 자체는 그대로 유효**합니다.
> 글로벌 CLAUDE.md Subagent Protocol 에 따라 변환:
> - `Agent(subagent_type=..., name=..., team_name=..., prompt=...) + SendMessage + shutdown_request`
>   → `Agent(subagent_type=..., model=plan[<role>], description=..., prompt=...)` 단일 호출
> - `Mailbox 수신` → `Agent()` 의 return value 직접 사용

---

## Step 1.0: 사전 분석 (병렬 Teammates)

```
# 병렬 spawn (독립 작업)
Agent(subagent_type="explore", model=plan["explore"], name="doc-analyst", description="문서 탐색 분석", team_name="pdca-{feature}", prompt="docs/, .claude/ 내 관련 문서 탐색. 중복 범위 감지 필수. 결과를 5줄 이내로 요약.")

Agent(subagent_type="explore", model=plan["explore"], name="issue-analyst", description="이슈 탐색 분석", team_name="pdca-{feature}", prompt="gh issue list 실행하여 유사 이슈 탐색. 연관 이슈 태깅 필요. 결과를 5줄 이내로 요약.")

# [Intent Inference] analyst(sonnet) — 사용자 의도 심층 분석
Agent(subagent_type="analyst", model=plan["analyst"], name="intent-analyst", description="사용자 의도 심층 분석", team_name="pdca-{feature}",
     prompt="[Phase 1 Intent Analysis] 사용자 요청의 의도를 심층 분석하세요.
             사용자 요청: {user_request}
             분석 항목:
             1. 명시적 요구사항 — 사용자가 직접 말한 것
             2. 암묵적 요구사항 — 당연히 기대하지만 말하지 않은 것
             3. 배경 맥락 — 왜 이 요청을 했는지 동기 추론
             4. 범위 경계 — 포함/제외 판단 (과잉 구현 방지)
             5. 위험 시나리오 2건+ — 잘못 해석하면 발생할 문제
             6. Planner 핵심 지시 (3줄 이내) — 계획 수립 시 반드시 반영할 사항
             코드베이스를 Glob/Grep으로 탐색하여 기술적 맥락을 파악한 뒤 분석하세요.")

# Mailbox로 결과 수신 후 모든 teammate shutdown_request
SendMessage(type="shutdown_request", recipient="doc-analyst")
SendMessage(type="shutdown_request", recipient="issue-analyst")
SendMessage(type="shutdown_request", recipient="intent-analyst")
```

**산출물**: 문서 중복 여부, 연관 이슈 번호, Intent Analysis (Phase 1.3에 사용)

## Step 1.1: 복잡도 점수 판단 (MANDATORY - 6점 만점)

| # | 조건 | 1점 기준 | 0점 기준 |
|:-:|------|---------|---------|
| 1 | **파일 범위** | 3개 이상 파일 수정 예상 | 1-2개 파일 |
| 2 | **아키텍처** | 새 패턴/구조 도입 | 기존 패턴 내 수정 |
| 3 | **의존성** | 새 라이브러리/서비스 추가 | 기존 의존성만 사용 |
| 4 | **모듈 영향** | 2개 이상 모듈/패키지 영향 | 단일 모듈 내 변경 |
| 5 | **사용자 명시** | `ralplan` 키워드 포함 | 키워드 없음 |
| 6 | **Appetite 선언** | "제대로/production-ready" 명시 | "빠르게/간단히/hotfix" 또는 미선언 |

**판단 로그 출력 (항상 필수):**
```
=== 복잡도 판단 ===
파일 범위: {0|1}점 ({근거})
아키텍처: {0|1}점 ({근거})
의존성:   {0|1}점 ({근거})
모듈 영향: {0|1}점 ({근거})
사용자 명시: {0|1}점
Appetite: {0|1}점 ({빠르게→0 | 제대로→1 | 미선언→0})
총점: {score}/6 -> {LIGHT|STANDARD|HEAVY}
===================
```

**복잡도 모드:**
- **0-1점**: LIGHT (간단, executor-high 단일)
- **2-3점**: STANDARD (보통, executor-high 루프)
- **4-6점**: HEAVY (복잡, Planner-Critic Loop)

## Step 1.1b: Plugin Activation Scan (Phase 0.4)

복잡도 판단 직후, 프로젝트 루트 파일 감지 + 복잡도 모드 기반으로 플러그인을 자동 활성화합니다.
상세 매핑 테이블: `references/plugin-fusion-rules.md`

```python
# Phase 0.4 — Lead가 직접 실행하는 플러그인 감지 로직
activated_plugins = []

# 1. Project Type Detection
if Glob("tsconfig.json"):
    activated_plugins.append("typescript-lsp")
if Glob("package.json"):
    pkg = Read("package.json")
    if '"react"' in pkg or '"next"' in pkg:
        activated_plugins.extend(["frontend-design", "code-review"])
    else:
        activated_plugins.append("code-review")
if Glob("next.config.*"):
    activated_plugins.append("frontend-design")
if Glob("pyproject.toml") or Glob("setup.py") or Glob("*.py"):
    activated_plugins.append("code-review")
if Glob(".claude/"):
    activated_plugins.extend(["claude-code-setup", "superpowers"])

# 2. Complexity-Tier Escalation
if mode in ["STANDARD", "HEAVY"]:
    activated_plugins.extend(["superpowers", "code-review"])
if mode == "HEAVY":
    activated_plugins.extend(["feature-dev", "claude-code-setup"])

# 3. Deduplicate
activated_plugins = list(set(activated_plugins))

# 4. Iron Laws 주입 (superpowers 활성 시)
iron_laws = ""
if "superpowers" in activated_plugins:
    iron_laws = Read("${CLAUDE_PLUGIN_ROOT}/references/plugin-fusion-rules.md")
    # Section 8 Iron Laws를 impl-manager/QA/Gate prompt에 주입

# 5. 활성화 로그 출력 (항상 필수)
# === Plugin Activation ===
# 프로젝트 타입: {detected_types}
# 복잡도 모드: {mode}
# 활성 플러그인: {activated_plugins}
# Iron Laws: {TDD, Debugging, Verification}
# ===========================
```

**Iron Laws prompt 주입 (superpowers 흡수):**

impl-manager, QA Runner, Architect Gate prompt에 아래를 추가:

```
=== Iron Laws (MANDATORY) ===
1. TDD: 실패 테스트 없이 프로덕션 코드 작성 금지. 테스트 먼저 작성.
2. Debugging: Root cause 조사 없이 수정 금지. D0-D4 체계 준수.
3. Verification: 증거 없이 완료 선언 금지. 빌드/테스트/lint 결과 첨부 필수.
```

## Step 1.2: 계획 수립 (명시적 호출)

**LIGHT (0-1점): Planner sonnet teammate**
```
Agent(subagent_type="planner", model=plan["planner"], name="planner", description="계획 수립", team_name="pdca-{feature}", prompt="... (복잡도: LIGHT {score}/6, 단일 파일 수정 예상).
     PRD 참조: docs/00-prd/{feature}.prd.md (있으면 반드시 기반으로 계획 수립).
     PRD의 요구사항 번호(FR-xxx)를 Plan 항목에 매핑하세요.
     사용자 확인/인터뷰 단계를 건너뛰세요. 바로 계획 문서를 작성하세요.
     === Intent Analysis (Step 1.0 산출물) ===
             {intent_analysis_result}
             위 분석의 암묵적 요구사항과 범위 경계를 계획에 반영하세요.
     === Mermaid 다이어그램 규칙 ===
             한 레벨 노드 최대 4개 (5개+ 시 subgraph 분할). 줄바꿈: <br/> 사용 (\n 금지). 노드 6개+ 시 단계적 빌드업.
     docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**STANDARD (2-3점): Planner opus teammate**
```
Agent(subagent_type="planner", model=plan["planner"], name="planner", description="계획 수립", team_name="pdca-{feature}", prompt="... (복잡도: STANDARD {score}/6, 판단 근거 포함).
     PRD 참조: docs/00-prd/{feature}.prd.md (있으면 반드시 기반으로 계획 수립).
     PRD의 요구사항 번호(FR-xxx)를 Plan 항목에 매핑하세요.
     사용자 확인/인터뷰 단계를 건너뛰세요. 바로 계획 문서를 작성하세요.
     === Intent Analysis (Step 1.0 산출물) ===
             {intent_analysis_result}
             위 분석의 암묵적 요구사항과 범위 경계를 계획에 반영하세요.
     === Mermaid 다이어그램 규칙 ===
             한 레벨 노드 최대 4개 (5개+ 시 subgraph 분할). 줄바꿈: <br/> 사용 (\n 금지). 노드 6개+ 시 단계적 빌드업.
     docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY (4-6점): Planner-Critic Loop (max 5 iterations)**

```
critic_feedback = ""      # Lead 메모리에서 관리
iteration_count = 0

Loop (max 5 iterations):
  iteration_count += 1

  # Step A: Planner Teammate
  Agent(subagent_type="planner", model=plan["planner"], name="planner-{iteration_count}", description="계획 수립 반복",
       team_name="pdca-{feature}",
       prompt="[Phase 1 HEAVY] 계획 수립 (Iteration {iteration_count}/5).
               작업: {user_request}
               이전 Critic 피드백: {critic_feedback}
               계획 문서 작성 후 사용자 확인 단계를 건너뛰세요.
               Critic teammate가 reviewer 역할을 대신합니다.
               계획 완료 시 바로 '계획 작성 완료' 메시지를 전송하세요.
               필수 포함: 배경, 구현 범위, 영향 파일, 위험 요소.
               === Intent Analysis (Step 1.0 산출물) ===
               {intent_analysis_result}
               위 분석의 암묵적 요구사항과 범위 경계를 계획에 반영하세요.
               === Mermaid 다이어그램 규칙 ===
               한 레벨 노드 최대 4개 (5개+ 시 subgraph 분할). 줄바꿈: <br/> 사용 (\n 금지). 노드 6개+ 시 단계적 빌드업.
               출력: docs/01-plan/{feature}.plan.md")
  SendMessage(type="message", recipient="planner-{iteration_count}", content="계획 수립 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step B: Architect Teammate
  Agent(subagent_type="architect", model=plan["architect"], name="arch-{iteration_count}", description="기술적 타당성 검증",
       team_name="pdca-{feature}",
       prompt="[Phase 1 HEAVY] 기술적 타당성 검증.
               Plan 파일: docs/01-plan/{feature}.plan.md
               검증 항목: 1. 파일 경로 존재 여부 2. 의존성 충돌 3. 아키텍처 일관성 4. 성능/보안 우려
               소견을 5줄 이내로 요약하세요.")
  SendMessage(type="message", recipient="arch-{iteration_count}", content="타당성 검증 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step C: Critic Teammate (Adversarial Weakness Analyzer)
  Agent(subagent_type="critic", model=plan["critic"], name="critic-{iteration_count}", description="adversarial 약점 분석",
       team_name="pdca-{feature}",
       prompt="[Phase 1 HEAVY] Adversarial Plan 공격 (Iteration {iteration_count}/5).
               Plan 파일: docs/01-plan/{feature}.plan.md
               Architect 소견: {architect_feedback}
               이전 iteration 약점 수정 이력: {previous_weakness_fixes}
               당신은 adversarial 분석자입니다. 이 문서의 약점, 결함, 모순, 누락만 찾으세요.
               === 7가지 공격 벡터 ===
               A1 논리적 결함: 빠진 단계, 근거 없는 가정, 순환 논리
               A2 실패 시나리오: 외부 의존성 실패, 해피패스 붕괴, 미처리 엣지 케이스
               A3 모호성: '적절히','필요 시','가능하면','등' 등 모호어, 측정 불가 기준
               A4 내부 모순: 섹션 간 불일치, 기존 아키텍처 충돌, 목표-범위 불일치
               A5 누락 컨텍스트: 미존재 파일 참조, 미언급 의존성, 미고려 이해관계자
               A6 과잉 설계: 요구사항에 없는 기능/추상화, 조기 최적화, 범위 확장
               A7 OOP 설계 위반: 제어 결합도(3+), God Module(응집도 6-7), 순환 의존성, DIP 위반, 공통 결합도
               모든 벡터에서 공격하세요. 약점마다 문제-위치-영향을 명시하세요.
               이해할 수 없거나 도메인 지식이 부족한 부분은 QUESTION으로 표시하세요.
               반드시 첫 줄에 VERDICT: DESTROYED, VERDICT: QUESTION, 또는 VERDICT: SURVIVED를 출력하세요.
               SURVIVED는 Critical 0건 + Major 0건일 때만. 첫 iteration에서 SURVIVED는 거의 불가능합니다.")
  SendMessage(type="message", recipient="critic-{iteration_count}", content="Plan 공격 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step D: Lead 판정
  critic_message = Mailbox에서 수신한 critic 메시지
  first_line = critic_message의 첫 줄

  if "VERDICT: SURVIVED" in first_line:
      → Loop 종료, Phase 2 진입
  elif "VERDICT: QUESTION" in first_line:
      → Loop 즉시 중단
      → critic_message에서 질문 목록 추출
      → AskUserQuestion으로 사용자에게 질문 전달
      → 사용자 답변을 다음 iteration의 previous_weakness_fixes에 주입
      → 다음 iteration 재개
  elif "VERDICT: DESTROYED" in first_line:
      → critic_feedback = critic_message에서 VERDICT: 줄 이후 전체 (약점 목록)
      → 누적 피드백이 1,500t 초과 시 최신 2회분만 유지
        (이전: "Iteration {N}: {핵심 요약 1줄}" 형태로 압축)
      → Planner에게 critic_feedback 전달하여 문서 재설계
      → 다음 iteration
  else:
      → DESTROYED로 간주 (안전 기본값)

  if iteration_count >= 5 and not SURVIVED:
      → # 설계 자체에 근본적 문제가 있음 — 강제 통과 금지
      → 미해결 약점 요약 보고서 작성 (남은 Critical/Major 약점 전체 목록)
      → AskUserQuestion으로 사용자에게 보고:
        "Critic 5회 반복 후에도 다음 약점이 해결되지 않았습니다: {남은 약점 요약}.
         설계 자체에 근본적 문제가 있을 수 있습니다."
        옵션:
        1. "요구사항 재정의" → Phase 1 처음부터 재시작 (PRD 재검토)
        2. "미해결 약점 수용 후 진행" → Plan에 WARNING 섹션 추가 + Phase 2 진입
        3. "작업 중단" → wip 커밋 + TeamDelete + 세션 종료
```

**Critic 판정 파싱 규칙:**
- 판정 추출: Critic 메시지 첫 줄에서 `VERDICT: DESTROYED`, `VERDICT: QUESTION`, 또는 `VERDICT: SURVIVED` 키워드 확인
- 키워드 불일치: 첫 줄에 VERDICT 없으면 DESTROYED로 간주
- DESTROYED 시: `VERDICT:` 줄 이후 전체 약점 목록을 critic_feedback에 저장 → Planner에게 전달하여 문서 재설계
- QUESTION 시: Loop 즉시 중단 → 질문 목록 추출 → AskUserQuestion으로 사용자에게 전달 → 답변 후 다음 iteration 재개
- 피드백 1,500t 이하: 전체 누적 유지 / 초과: 최신 2회분 전문 + 이전은 1줄 압축 / 5회 초과: 사용자 보고 + 판단 요청 (강제 통과 금지)

**산출물**: `docs/01-plan/{feature}.plan.md`

## Step 1.2 LIGHT: Lead Quality Gate (v22.1)

LIGHT(0-1점) 모드에서 Planner(sonnet) 완료 후 Lead가 직접 수행하는 최소 검증:

```
# Lead Quality Gate (에이전트 추가 비용: 0)
plan_content = Read("docs/01-plan/{feature}.plan.md")

# 조건 1: plan 파일 존재 + 내용 있음 (빈 파일 거부)
if not plan_content or len(plan_content.strip()) < 50:
    → Planner 1회 재요청 ("계획 내용이 부족합니다. 최소 배경, 구현 범위, 영향 파일을 포함하세요.")

# 조건 2: 파일 경로 1개 이상 언급
if no file path pattern (e.g., "src/", ".py", ".ts", ".md") found:
    → Planner 1회 재요청 ("구현 대상 파일 경로를 1개 이상 포함하세요.")

# 미충족 시 1회만 재요청. 2회째 실패 → 그대로 Phase 2 진입 (LIGHT이므로 과도한 차단 불필요)
```

## Step 1.2 STANDARD: Critic-Lite 단일 검토 (v22.1)

STANDARD(2-3점) 모드에서 Planner(opus) 완료 후 Critic-Lite 1회 검토:

```
Agent(subagent_type="critic", model=plan["critic"], name="critic-lite", description="Critic-Lite 단일 약점 공격", team_name="pdca-{feature}",
     prompt="[Phase 1 STANDARD Critic-Lite] Adversarial Plan 공격 (1회).
             Plan 파일: docs/01-plan/{feature}.plan.md

             당신은 adversarial 분석자입니다. 이 문서의 약점만 찾으세요.
             === 7가지 공격 벡터 ===
             A1 논리적 결함: 빠진 단계, 근거 없는 가정, 순환 논리
             A2 실패 시나리오: 외부 의존성 실패, 해피패스 붕괴, 미처리 엣지 케이스
             A3 모호성: '적절히','필요 시','가능하면','등' 등 모호어, 측정 불가 기준
             A4 내부 모순: 섹션 간 불일치, 기존 아키텍처 충돌, 목표-범위 불일치
             A5 누락 컨텍스트: 미존재 파일 참조, 미언급 의존성
             A6 과잉 설계: 요구사항에 없는 기능/추상화
             A7 OOP 설계 위반: 제어 결합도(3+), God Module(응집도 6-7), 순환 의존성, DIP 위반, 공통 결합도

             반드시 첫 줄에 VERDICT: DESTROYED, VERDICT: QUESTION, 또는 VERDICT: SURVIVED를 출력하세요.
             약점마다 문제-위치-영향을 명시하세요. 이해 불가 시 QUESTION으로 표시.
             SURVIVED는 Critical 0건 + Major 0건일 때만.")
SendMessage(type="message", recipient="critic-lite", content="Plan 공격 시작.")
# 완료 대기 → shutdown_request

# VERDICT 파싱
critic_message = Mailbox에서 수신한 critic-lite 메시지
if "VERDICT: SURVIVED" in first_line:
    → Phase 2 진입
elif "VERDICT: QUESTION" in first_line:
    → 질문 추출 → AskUserQuestion으로 사용자에게 전달 → 답변과 함께 Planner 1회 수정
    → 수정본 수용 (추가 Critic 검토 없음, 무한 루프 방지)
elif "VERDICT: DESTROYED" in first_line:
    → Planner 1회 수정 (critic_feedback = 약점 목록 전달)
    → 수정본 수용 (추가 Critic 검토 없음, 무한 루프 방지)
else:
    → DESTROYED로 간주
```

## Step 1.3: 이슈 연동 (GitHub Issue)

**Step 1.0에서 연관 이슈 발견 시**: `gh issue comment <issue-number> "관련 Plan: docs/01-plan/{feature}.plan.md"`

**신규 이슈 생성 필요 시**: `gh issue create --title "{feature}" --body "Plan: docs/01-plan/{feature}.plan.md" --label "auto"`

---

## Plan→Build Gate: Plan 검증 (MANDATORY)

| # | 필수 섹션 | 확인 방법 |
|:-:|----------|----------|
| 1 | 배경/문제 정의 | `## 배경` 또는 `## 문제 정의` 헤딩 존재 |
| 2 | 구현 범위 | `## 구현 범위` 또는 `## 범위` 헤딩 존재 |
| 3 | 예상 영향 파일 | 파일 경로 목록 포함 |
| 4 | 위험 요소 | `## 위험` 또는 `위험 요소` 헤딩 존재 |

**누락 시**: Plan 문서를 먼저 보완한 후 Phase 2로 진행.
