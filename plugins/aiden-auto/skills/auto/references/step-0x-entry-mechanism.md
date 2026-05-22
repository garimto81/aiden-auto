---
name: step-0x-entry-mechanism
version: v3
loaded_from: skill-auto
purpose: Step 0.4 / 0.5 / 0.7 진입 메커니즘 상세 (SKILL.md 분리 — F19 결함 해소)
---

# Step 0.4 / 0.5 / 0.7 진입 메커니즘 (SKILL.md 분리, v3)

본 reference 는 SKILL.md 본문에서 분리된 3개 Step 의 상세 정의. SKILL.md 는 ≤120줄 도서관 안내 데스크 유지 (F19 정합).

---

## Step 0.4: User-Friendly Reporter 사전 게이트 (MANDATORY, v28.3+)

Step 0 직후, 사용자 향 모든 응답 작성 직전에 본 agent 통과 의무.

```
Agent(
  subagent_type="user-friendly-reporter",
  model="haiku",
  description="응답 친절 변환",
  prompt="원본_보고=<Claude 응답 초안>"
)
→ 친절 변환된 텍스트
```

**자동 발동 조건** (어느 하나라도):
- 응답에 전문용어 (skill / agent / hook / subagent / critic / refactor / API / schema) 등장
- "어떻게 할까요?" / "진행할까요?" / "확인 부탁드립니다" 패턴
- 응답 50줄 초과
- A/B/C 옵션 나열
- 약어 (NTFS/HVAC/SSOT 등) 첫 등장 풀이 누락

**위반 시 처리**: 응답 작성 중단 → 본 agent 재호출 → 친절 변환된 출력 사용.

---

## Step 0.5: Model Router 호출 (MANDATORY, HARD ENFORCE — v28.3+)

Step 0 직후, Phase -2 진입 전에 **반드시**:

```
Agent(
  subagent_type="model-router",
  model="haiku",
  description="model_plan 산출",
  prompt="task=<사용자 원문>\ncategory=<index.yml 매핑 결과 or unknown>\ncontext=<직전 1-2줄>"
)
→ JSON model_plan 응답 (31 keys, 하이픈 표기)
```

**응답 처리**:

| 케이스 | 처리 |
|--------|------|
| 파싱 성공 | `plan` 객체 저장 → `~/.claude/state/auto/model_plan-{session}.json`. 후속 모든 Agent() 호출에 `model=plan["<role>"]` 명시 주입 |
| 파싱 실패 | 전체 sonnet 폴백 + 사용자 명시 알림 (architect/security-reviewer 등 고복잡도 역할 경고) |
| 재호출 | 1회 시도. 재실패 시 sonnet 폴백 유지 + 알림 |

**Tier 접미사 (`-high` / `-low`) 처리**:
- `executor-high` → `plan["executor"]` 한 단계 상향 (sonnet → opus)
- `executor-low` → `plan["executor"]` 한 단계 하향 (sonnet → haiku)

scope/complexity 급변 시 (파일 수 폭증, 보안 영역 추가 등) router 재호출.

**기본 동작** (안내, v28.3 정책 critic audit P2-7 완화):

| 상황 | 자동 처리 |
|------|----------|
| Step 0.5 미실행 | advisor pattern 미작동 → 다음 Agent() 호출 직전 자동 재호출 |
| model 미주입 | agent frontmatter의 model 사용 (대부분 sonnet fallback) |
| router 응답 파싱 실패 | 전체 sonnet 자동 폴백 → Phase 4 보고서 푸터에 기록 (즉시 사용자 인터럽트 없음) |

자동 실행 도구: `hooks/auto_workflow_enforcer.py` 의 `save_model_plan()` + `resolve_model_for_role()`.
상세 정책: 글로벌 CLAUDE.md § Dynamic Model Routing (Advisor Pattern v1) 참조.

---

## Step 0.7: 자율 자산 Inventory + Universal Deployment 평가 (MANDATORY — v28.8+)

> **결함 차단 패치**: 2026-05-22~23 root cause 분석 결과 — `/auto` 워크플로우에 "기존 자율 자산 검색" + "universal deployment 평가" 단계 부재로 사용자에게 "수동 처리" + device-scoped 표현 반복 사용. 본 step 으로 차단.

Step 0.5 직후, Phase -2 진입 전에 **반드시**:

### Part 1: 자율 자산 inventory (기존)

작업 영역별 자율 자산 검색

```
1. ~/.claude/hooks/registry/{event}/*.json  (자동 hook)
2. ~/.claude/agents/meta/*.md               (advisor pattern + 기타 자율 agent)
3. ~/.claude/skills/*/SKILL.md              (관련 skill)
```

### 작업 키워드별 우선 검색 매핑

| 작업 키워드 | 우선 검색 대상 |
|------------|--------------|
| commit / push / GitHub / sync | `framework_github_sync.py`, `bidirectional_sync.py`, `marketplace-sync` 패턴 |
| auth / 인증 / token / OAuth | `cc-auth-executor/advisor`, `atlassian-auth-executor/advisor` |
| plugin / SSOT / mirror / drift | `plugin-ssot-audit`, `machine_framework_watcher.py` |
| spec / drift / verify | `spec-verify.py`, `audit_spec_code_drift.py` |
| matrix / 무결성 / audit | `agent-matrix-audit`, `command-matrix-audit`, `skill-matrix-audit`, `workflow-matrix-audit` |

### 출력 형식 (MANDATORY)

작업 시작 응답에 다음 inventory 결과 표시:

```
[자율 자산 inventory 결과]
- 관련 hook: N개 발견
- 관련 advisor agent: N개 발견
- 관련 skill: N개 발견
- 자동 trigger 시점: SessionEnd / PostToolUse / on-demand
```

### Part 2: Universal Deployment 평가 (v28.8+ 신규)

> 글로벌 CLAUDE.md § Universal Deployment Premise (0 순위) 의 운영 게이트.

**평가 대상**: 변경이 framework 자산 (`~/.claude/{hooks,agents,skills,commands,rules,references,hud,lib,scripts}/`, plugin 본체) 일 때만.
**평가 제외**: 본인 PC 만의 자산 (`state/`, `projects/memory/`, `.credentials.json`, `settings.json` 등) — 개인화 영역.

#### 6 기준 자동 평가

| # | 기준 | 통과 검증 |
|---|------|----------|
| 1 | 자기복제율 ≥95% | 변경 후 신규 PC 동일 작동? (`measure-replication.py`) |
| 2 | hardcoded path 0 | `C:\\claude\\...` 직접 참조 안 함? (`forbidden_pattern_check.py`) |
| 3 | OS-agnostic | `pathlib.Path` 만 사용? |
| 4 | 권한-agnostic | admin/sudo 명시 안 함? |
| 5 | idempotent | 재실행/재install 안전? |
| 6 | 개인화 격리 | credentials/state/memory EXCLUDE 명시? |

위 6 중 하나라도 통과 못 함 → 변경 보류 + premise 위배 사유 보고.

자동 실행 도구: `hooks/auto_workflow_enforcer.py` 의 `enforce_premise_on_change()`.
상세: `~/.claude/references/universal-deployment-checklist.md`.

### Part 3: 금지 (HARD BLOCK — root cause 차단)

본 inventory + premise 평가 확인 전에 다음 표현 사용 금지:

- ❌ "사용자가 수동으로 …" (자율 자산 inventory 위반)
- ❌ "사용자 결정 영역" (의미 결정 아닌 단순 실행 영역)
- ❌ "별도 cycle 권장"
- ❌ "다음에 직접 …"
- ❌ "본인 PC 에서만", "내 환경" (universal premise 위반, v28.8+)
- ❌ `C:\claude\...`, `C:\aiden-auto-repo\...` hardcoded (universal premise 위반, v28.8+)
- ❌ "다른 PC 는 수동" (universal premise 위반, v28.8+)
- ❌ **"추정 N", "약 N", "대략" 정량 표현 (v3 D4 — P13-estimation-expr)**

이 표현 사용 전 의무: inventory + premise 6 기준 통과 확인. 자산 존재 + premise 통과 시 **자동 활용 + 자율 진행**.

---

## 변경 이력

| 날짜 | 변경 |
|------|------|
| 2026-05-23 | v3 신규 — SKILL.md F19 결함 해소 (430→120줄 정제 위한 분리) |
