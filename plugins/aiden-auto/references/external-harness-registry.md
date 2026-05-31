# External Harness Framework Registry

> **5원칙 #1+#2**: 외부 framework는 *그대로 유지* (복사하지 않음). 매일 update 자동 체크 → critic 검토 → 자가개선.
>
> **작동 비유**: 도서관이 *외부 신간 목록*을 매일 확인하고, 우리 장서에 추가할 가치 있는지 사서가 검토. 책 자체는 외부 서점에 그대로 두고, 우리는 *참조 카드*만 보유.

## 추적 대상 frameworks

```yaml
frameworks:
  - id: bkit-claude-code
    owner: popup-studio-ai
    repo: bkit-claude-code
    check_method: "tags"
    last_known_version: "v2.1.20"
    last_checked: "2026-05-29"
    interesting_paths:
      - "skills/"
      - "agents/"
      - "references/"
    rationale: "PDCA + chapter routing의 원조. v27.x 진화 영감의 출처."

  - id: react-best-practices
    owner: vercel-labs
    repo: agent-skills
    subdir: "skills/react-best-practices"
    check_method: "subdir-commits"
    last_known_version: "dc8367e6"
    last_checked: "2026-05-29"
    interesting_paths:
      - "skills/react-best-practices/"
    rationale: "Vercel 공식 React/Next.js 성능 최적화 룰셋 (70 rules, 8 categories). React 컴포넌트/data fetching/bundle 최적화 코드 리뷰 및 자동 리팩토링 가이드."

  - id: oh-my-claudecode
    owner: yeachan-heo
    repo: oh-my-claudecode
    check_method: "tags"
    last_known_version: "v4.14.4"
    last_checked: "2026-05-29"
    interesting_paths:
      - "agents/"
      - "skills/"
      - "hooks/"
      - "commands/"
      - "missions/"
      - "CLAUDE.md"
      - "CHANGELOG.md"
    rationale: "Teams-first 멀티 에이전트 오케스트레이션 프레임워크 — agent/skill/hook 구조 및 model routing 패턴 추적 (v4.13.7+)."

  # === 2026-05-26 사용자 결정 ===
  # claude-code / superpowers / frontend-design / claude-code-goal /
  # advisor-tool-beta / statusline-combined / hybrid-statusline /
  # model-usage-line / aiden-auto-telemetry 9 entries 제거
  # 사유: 사용자 본인 워크플로우 추적 가치 없음. registry 자율 추가의
  #       적정성 검증 부재 (G8 갭) 으로 11→3 정리.
  # 메모: 위 9 framework 의 본문 활용 (예: superpowers skill matrix,
  #       advisor pattern, statusline HUD) 는 별도 영역에서 보존 —
  #       registry 추적 만 종료.
```

## v28.2 내부 advisors (자가 등록)

```yaml
internal_advisors:
  - id: quota-advisor
    trigger: "PreToolUse(Task) AND quota_signal"
    verdicts: [PROCEED, DOWNGRADE_ECO, DEFER, BLOCK]
    rationale: "Section 3 quota 운영"

  - id: perfect-output-validator
    trigger: "Phase 4 entry"
    verdicts: [APPROVE, REJECT_GATE1]
    rationale: "Section 5 Gate 1"

  - id: e2e-qa-prover
    trigger: "Gate 1 ALL PASS"
    verdicts: [APPROVE, REJECT_GATE2]
    rationale: "Section 5 Gate 2 (session type 분기)"

  - id: intake-interviewer
    trigger: "Phase -1.5 entry AND ambiguity_score >= 2"
    verdicts: [GOAL_WRITTEN, SKIPPED]
    rationale: "Section 2 Deep Interview"
```

## 감시 주기 결정 (2026-06-01 검증 — #4 개선 제안)

> **결론: 현행 daily 유지** (premise 검증 결과 주간 전환 불필요).
>
> 실측: 채택 이력 0건(critic-decisions 0, APPROVE 0, applier PR 0). 그러나 "매일 비용 worth 줄이기" premise 가 **이미 성립 안 함** —
> ① 비싼 GitHub-API 표면은 2026-05-26 11→3 정리로 **73% 절감 완료**,
> ② 매 세션 도는 `harness_cycle_runner` 는 local state 읽고 graceful-skip 하는 **값싼 no-op**(GitHub 미접근),
> ③ 채택 0 ≠ 가치 0 (진입점 증가 변경을 거르는 **필터** 역할 — 2건 모두 정당 REJECT),
> ④ 주간 전환 시 절감 미미 + 좋은 update 를 최대 6일 지연.
> → verify-policy-premise 적용: "최적화(주간)" 종결점 강제 안 함. 향후 추적 framework 증가 또는 update 빈도 상승 시 재검토.

## 자가개선 사이클

```
매일 (daily hook 또는 cron)
    │
    ▼
┌────────────────────────────────────────┐
│ Step 1. harness-watcher (haiku)        │
│   각 framework GitHub API 체크          │
│   신규 tag/release/commit 감지          │
│   → diff 요약 산출 + last_checked 갱신  │
└─────────────┬──────────────────────────┘
              │ 신규 update 발견
              ▼
┌────────────────────────────────────────┐
│ Step 2. harness-critic (opus)          │
│   우리 5원칙 부합 여부 판정              │
│                                        │
│   질문 5개:                             │
│   1) 사용자 진입점을 *줄이는가*?         │
│   2) 자율 이터레이션을 *늘리는가*?       │
│   3) 우리 chapter 구조와 정합한가?      │
│   4) 복사 아닌 *참조*로 가능한가?       │
│   5) Circuit Breaker 룰 위배 없는가?    │
│                                        │
│   APPROVE / REJECT / NEEDS_INFO        │
└─────────────┬──────────────────────────┘
              │ APPROVE
              ▼
┌────────────────────────────────────────┐
│ Step 3. harness-applier (sonnet)       │
│   patch 생성 (참조 추가 또는 reference  │
│   파일 갱신)                            │
│   feature/harness-{id}-{date} branch    │
│   PR 자동 생성 (사용자 검토만 필요)      │
└────────────────────────────────────────┘
```

## 변경 로그

| 날짜 | id | version | critic 판정 | 적용 위치 |
|------|----|---------|------------|----------|
| 2026-05-11 | (initial) | — | — | registry 신규 생성 |
| 2026-05-11 | (dry-run baseline) | 6 framework | — | 첫 watcher dry-run으로 4건 owner 보정 + 4건 baseline 신규 수립 (claude-code v2.1.138, vercel 61f1903b, atlassian 9b52fb18, frontend-design 00679aef). 2건은 일치 (bkit-claude-code v2.1.12, superpowers v5.1.0). 신규 update 0건. |
| 2026-05-13 | (manual) | — | bypass | 사용자 직접 결정 (critic 우회): `atlassian` 제거, `vercel`→`react-best-practices` 교체 (vercel-labs/agent-skills subdir-commits, dc8367e6), `oh-my-claudecode` 신규 추가 (yeachan-heo, tags v4.13.7). |
| 2026-05-26 | (manual) | 11 → 3 | bypass | 사용자 직접 결정 (G8 갭 정정): registry 11 entry 중 8 entry 제거 — claude-code / superpowers / frontend-design / claude-code-goal / advisor-tool-beta / statusline-combined / hybrid-statusline / model-usage-line / aiden-auto-telemetry. 사유: 추적 가치 부재. 유지 3개: bkit-claude-code, react-best-practices, oh-my-claudecode. daily harness_cycle_runner API 호출 비용 73% 즉시 절감. |
| 2026-05-29 | bkit-claude-code | v2.1.12 → v2.1.20 (8 commits) | **REJECT** | 사용자 명시 "자가 진화 테스트" cycle. GitHub spot check 실측 정합 100%. critic 5+1 lens 평가 → Q1/Q3/Q6 FAIL — "Sprint Management / Trust Score / 21-key manifest 검증" 추가 = 진입점 ↑, Plan B 폐기 (어제) 와 동일 anti-pattern. applier 미발동. |
| 2026-05-29 | oh-my-claudecode | v4.13.7 → v4.14.4 (minor bump) | **REJECT** | 같은 cycle. critic Q1 FAIL — `omc ultragoal` CLI 신규 명령어 = "워크플로우 자체도 진입점" Core Philosophy 위배. **영감 후보 1건** (skill-bodies registry shim 패턴) backlog 보존. applier 미발동. |
| 2026-05-29 | react-best-practices | dc8367e6 (변화 없음) | — | NO_CHANGE 확인. 다음 daily 추적 지속. |

## Internal Advisors (자가개선 사이클 내부 advisor)

> external framework와 별개로, plugin 내부의 자율 advisor 추세를 harness-watcher가 함께 추적한다. Anthropic 공식 advisor-tool 패턴 차용분(2026-05-12).

```yaml
internal_advisors:
  - id: cc-auth-advisor
    trigger: SessionStart
    executor_agent: agents/meta/cc-auth-executor.md
    advisor_agent: agents/meta/cc-auth-advisor.md
    hook_script: hooks/cc_auth_check.py
    state_file_pattern: "state/cc-auth-decisions-{date}.json"
    protocol: references/cc-auth-advisor-protocol.md
    weekly_thresholds:
      prompt_user_warn: 3       # 주 3회 이상 → "scope 사전 등록 권고" issue 자동 생성
      block_alert: 1            # 주 1회 이상 → "rate limit / 보안 점검 권고" issue 자동 생성
    last_reviewed: "2026-05-12"
    rationale: "Claude Code CLI 자체 OAuth(.credentials.json claudeAiOauth) 사전 점검. advisor-tool 패턴 차용 (Executor-Advisor 2-tier)."
```

watcher가 daily 실행 시 `state/cc-auth-decisions-{date}.json` 7일치를 읽어 위 임계값 초과 시 issue 자동 생성 (harness-applier에 위임).

## 운영 규칙

- **last_checked 갱신 의무**: watcher가 매번 갱신해야 다음 daily에 정확한 delta 계산 가능
- **NEEDS_INFO 처리**: critic이 정보 부족으로 판정 보류 시 사용자에게 1줄 보고 후 다음날 재시도
- **REJECT 누적**: 같은 framework에서 3회 연속 REJECT 시 해당 framework 추적 일시 정지 (사용자 결정으로 재개)
- **check_method 종류**:
  - `tags`: GitHub releases/tags API (semantic version)
  - `releases`: GitHub releases API (release notes 포함)
  - `commits`: default branch HEAD commit sha (tag 없는 repo)
  - `subdir-commits`: monorepo의 하위 디렉토리 commit (path 필터)

### Registry 추가 룰 (D4 사용자 결정 — 2026-05-26)

> **D1 정신 (critic mode 게이트) 적용**: registry 추가도 critic 게이트 + 사용자 명시 승인 요구.

**현재 (R5 + D4 정합) 정책**:

```
   harness-watcher 신규 framework 발견
        │
        ▼
   state/harness-discoveries-{date}.json 에 후보 기록만
        │
        ▼
   harness-critic 의 5+1 lens 평가
   (사용자 워크플로우 가치 lens 추가 — 본 framework 사용자가
    실제 추적할 가치 있는가?)
        │
        ▼
   APPROVE → 사용자에게 추가 제안 (1줄 보고)
        │
        ▼
   사용자 명시 승인 (예: "/registry add <id>") 시만 등록
   ┌────────────────────────────────────────────┐
   │ ★ 자율 추가 금지 ★                          │
   │ R5 의 11→3 cleanup 학습 — 잡음 73% 회피      │
   └────────────────────────────────────────────┘
```

**핵심 변경**:

| 옛 정책 | 새 정책 (D4) |
|---------|------------|
| watcher 자율 추가 | 후보 기록만 (state/harness-discoveries-{date}.json) |
| critic 만 평가 | critic + 사용자 명시 승인 |
| 누적만 (제거 룰 없음) | 추가 시 보수적, 제거는 R5 패턴 (사용자 명시 결정) |
| 등록 후 daily 추적 자동 | 등록 자체가 사용자 명시 결정 |

**자율 추가 허용 예외** (없음):

```
   D4 정책의 엄격함:
     • 자율 추가 예외 0건
     • monorepo auto_discover_subdir 도 후보 기록만
     • critic APPROVE 만으로는 등록 불가
     • 사용자 명시 발화 ("이거 추가해", "/registry add ..." 등) 필수
```

**state 자산**:

- `~/.claude/state/harness-discoveries-{date}.json` — 후보 목록 (사용자 확인 대기)
- `~/.claude/state/harness-critic-decisions-{date}.json` — critic 평가 결과
- `~/.claude/references/external-harness-registry.md` — 실제 등록 목록 (사용자 명시 결정 후만 갱신)

## v28.4 신규: superpowers 12 skill 매트릭스 (Deep Interview brainstorming 위임 정합)

> **Why**: 사용자 지시 2026-05-19 — "Deep Interview는 superpowers의 brainstorming + @ 로 처리".
> 본 매트릭스는 superpowers 의 12 skill 이 우리 phase 의 어느 단계에서 위임되는지 명시.
> 5원칙 #1 정합 — 참조만, 복사 X.

```yaml
superpowers_skill_matrix:
  - skill: brainstorming
    our_phase: "Phase -1.5 Part A"
    role: "의도 명료화 (Deep Interview)"
    invocation: "Skill('superpowers:brainstorming')"
    output: "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md"

  - skill: writing-plans
    our_phase: "Phase 1 (Design)"
    role: "구체 구현 plan 작성"
    invocation: "Skill('superpowers:writing-plans')"
    output: "plans/<feature>.md"

  - skill: executing-plans
    our_phase: "Phase 2 (Build)"
    role: "plan 실행"
    invocation: "Skill('superpowers:executing-plans')"

  - skill: subagent-driven-development
    our_phase: "Phase 2 (multi_session_method == C)"
    role: "작업당 fresh subagent + 2-stage 리뷰"
    invocation: "Skill('superpowers:subagent-driven-development')"
    trigger: "@ Q4 = C 선택 시"

  - skill: test-driven-development
    our_phase: "Phase 2 (CODE chapter)"
    role: "TDD Red→Green→Refactor"
    invocation: "Skill('superpowers:test-driven-development')"
    trigger: "CODE / ITERATION chapter 코드 작성 시"

  - skill: systematic-debugging
    our_phase: "Phase 3 (실패 시)"
    role: "가설-검증 디버깅"
    invocation: "Skill('superpowers:systematic-debugging')"
    trigger: "test fail / unexpected behavior"

  - skill: verification-before-completion
    our_phase: "Phase 4 Gate 1"
    role: "완료 선언 전 증거 검증"
    invocation: "Skill('superpowers:verification-before-completion')"

  - skill: finishing-a-development-branch
    our_phase: "Phase 4 close"
    role: "merge / PR / cleanup 결정"
    invocation: "Skill('superpowers:finishing-a-development-branch')"

  - skill: using-git-worktrees
    our_phase: "Phase 2 (격리 필요 시)"
    role: "git worktree 격리 작업"
    invocation: "Skill('superpowers:using-git-worktrees')"

  - skill: dispatching-parallel-agents
    our_phase: "Phase 2 (multi_session_method == B 변형)"
    role: "다중 agent 병렬 발동"
    invocation: "Skill('superpowers:dispatching-parallel-agents')"
    trigger: "@ Q4 = B 선택 + 다중 task"

  - skill: requesting-code-review
    our_phase: "Phase 3"
    role: "code review 요청 template"
    invocation: "Skill('superpowers:requesting-code-review')"

  - skill: receiving-code-review
    our_phase: "Phase 3"
    role: "code review 응답"
    invocation: "Skill('superpowers:receiving-code-review')"
```

### 추가 외부 framework 참조 워크플로우 (보강, 사용자 지시 2026-05-19 — "다른 하네스 프레임워크 참조 누락")

| Framework | 활용 chapter / phase | 역할 | 추적 상태 |
|-----------|----------------------|------|----------|
| **bkit-claude-code** | 전체 SKILL 영감 | PDCA + chapter routing 패턴 원조 | ✅ 추적 |
| **react-best-practices** | CODE chapter (React 작업) | Vercel 70 rules 자동 참조 | ✅ 추적 |
| **oh-my-claudecode** | multi_session method A 영감 | Teams-first 멀티 에이전트 패턴 | ✅ 추적 |
| ~~claude-code~~ | ~~hook spec / MCP / skills 표준~~ | ~~CC CLI 본체 추적~~ | ❌ 2026-05-26 제거 |
| ~~claude-code-goal~~ | ~~/goal 본질 정의~~ | ~~CC 빌트인 /goal~~ | ❌ 2026-05-26 제거 |
| ~~frontend-design~~ | ~~MEDIA chapter~~ | ~~디자인 시스템~~ | ❌ 2026-05-26 제거 |
| ~~advisor-tool-beta~~ | ~~advisor 2-tier 패턴~~ | ~~참조 패턴은 본문 유지~~ | ❌ 2026-05-26 제거 |
| ~~statusline-combined~~ | ~~시각화 진입점~~ | ~~host hud/ 직접 사용~~ | ❌ 2026-05-26 제거 |
| ~~hybrid-statusline~~ | ~~메인 statusline~~ | ~~host hud/ 직접 사용~~ | ❌ 2026-05-26 제거 |
| ~~model-usage-line~~ | ~~3-tier model usage~~ | ~~host hud/ 직접 사용~~ | ❌ 2026-05-26 제거 |
| ~~aiden-auto-telemetry~~ | ~~텔레메트리 1줄~~ | ~~host hud/ 직접 사용~~ | ❌ 2026-05-26 제거 |

각 framework 의 update 추적은 daily harness-watcher 가 처리 (위 cycle 참조).

> **메모 (2026-05-26)**: 제거된 9 framework 의 패턴/구현은 본 framework 내부에 이미 흡수되었거나 (예: advisor-tool 패턴 → cc-auth-advisor, quota-advisor) 호스트 자원으로 보존됨. registry 의 daily 추적만 종료.

## v28.3 신규: auto_discover_subdir + cc-researcher chain

### auto_discover_subdir (B 영역)
```yaml
# 사용 예 (frontend-design 같은 monorepo plugin)
auto_discover_subdir: true       # default false
discovery_path: "plugins/*"       # subdir 패턴
discovery_threshold: 3            # 한 번에 N건 이상 발견 시 사용자 보고
discovered_ignore: []             # 3회 거절 누적 시 자동 추가
```

watcher가 monorepo 하위 plugin 후보 발견 → `state/harness-discoveries-{date}.json` → 사용자 옵트인 등록.

### cc-researcher chain (A 영역)
`claude-code` framework 신규 release 감지 시:
```
1. watcher가 last_known_version != current 감지
2. Write state/cc-researcher-pending.flag {framework_id: claude-code, from, to, priority: HIGH}
3. cc-version-researcher (opus, on-flag) 발동 → 심층 분석 → state/cc-research-{date}.json
4. harness-critic이 cc-research 결과 흡수 후 5질문 평가 (deep analysis 가중 반영)
```

watcher 본체 *수정 없음* — flag 한 줄만 추가.
