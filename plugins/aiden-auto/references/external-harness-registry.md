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
    last_known_version: "v2.1.12"
    last_checked: "2026-05-11"
    interesting_paths:
      - "skills/"
      - "agents/"
      - "references/"
    rationale: "PDCA + chapter routing의 원조. v27.x 진화 영감의 출처."

  - id: claude-code
    owner: anthropics
    repo: claude-code
    check_method: "releases"
    last_known_version: "v2.1.138"
    last_checked: "2026-05-11"
    interesting_paths:
      - "CHANGELOG.md"
      - "docs/"
    rationale: "CC CLI 본체. hook spec / MCP / skills 표준 변화 추적."

  - id: react-best-practices
    owner: vercel-labs
    repo: agent-skills
    subdir: "skills/react-best-practices"
    check_method: "subdir-commits"
    last_known_version: "dc8367e6"
    last_checked: "2026-05-13"
    interesting_paths:
      - "skills/react-best-practices/"
    rationale: "Vercel 공식 React/Next.js 성능 최적화 룰셋 (70 rules, 8 categories). React 컴포넌트/data fetching/bundle 최적화 코드 리뷰 및 자동 리팩토링 가이드."

  - id: superpowers
    owner: obra
    repo: superpowers
    check_method: "tags"
    last_known_version: "v5.1.0"
    last_checked: "2026-05-11"
    interesting_paths:
      - "skills/"
    rationale: "skill discipline 패턴 (brainstorming, TDD, debugging)."

  - id: frontend-design
    owner: anthropics
    repo: claude-plugins-public
    subdir: "plugins/frontend-design"   # 본 plugin은 mono-repo 하위 디렉토리
    check_method: "subdir-commits"
    last_known_version: "00679aef"
    last_checked: "2026-05-11"
    interesting_paths:
      - "plugins/frontend-design/"
    rationale: "디자인 시스템 가이드라인 (Typography, Color, Motion). Anthropic 통합 plugin repo의 하위."

  - id: oh-my-claudecode
    owner: yeachan-heo
    repo: oh-my-claudecode
    check_method: "tags"
    last_known_version: "v4.13.7"
    last_checked: "2026-05-13"
    interesting_paths:
      - "agents/"
      - "skills/"
      - "hooks/"
      - "commands/"
      - "missions/"
      - "CLAUDE.md"
      - "CHANGELOG.md"
    rationale: "Teams-first 멀티 에이전트 오케스트레이션 프레임워크 — agent/skill/hook 구조 및 model routing 패턴 추적 (v4.13.7+)."

  # === v28.2 신규 추적 (Section 1, 13, 14) ===
  - id: claude-code-goal
    owner: anthropics
    repo: claude-code
    check_method: "releases"
    last_known_version: "v2.1.138"
    last_checked: "2026-05-13"
    interesting_paths:
      - "docs/slash-commands/goal*"
      - "docs/hooks*"
    rationale: "CC 빌트인 /goal — auto-loop until condition. v28.2 /auto의 loop driver. reference only."

  - id: advisor-tool-beta
    owner: anthropics
    repo: anthropic-cookbook
    check_method: "url-hash"   # v28.2 신규 check_method
    url: "https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool"
    last_known_version: "advisor-tool-2026-03-01"
    last_checked: "2026-05-13"
    rationale: "advisor-tool API beta. header 회전 시 quota-advisor fallback."

  - id: agent-view-cli
    owner: anthropics
    repo: claude-code
    check_method: "releases"
    min_version: "v2.1.139"
    last_known_version: "v2.1.138"
    last_checked: "2026-05-13"
    interesting_paths:
      - "docs/agent-view*"
      - "docs/worktrees*"
    rationale: "멀티세션 CLI surface (claude --bg, claude agents). v2.1.139+ 필요."

  # === Host statusline tools (v28.2 Section 15 정정) ===
  # aiden-auto의 statusline은 자체 구현이 아니라 호스트의 hud/* 도구 그대로 채택.
  # Core Philosophy #1 (외부 도구 그대로 유지, 참조만) 정합.
  - id: statusline-combined
    owner: host
    path: "~/.claude/hud/statusline-combined.mjs"
    check_method: "optional-host-file"
    optional: true
    last_checked: "2026-05-13"
    rationale: "Multi-line combinator (hybrid + model usage). aiden-auto의 statusline 진입점. GLOBAL settings.json statusLine으로 등록되어 매 세션 화면에 출력. 미존재 시 plugin/hud/ fallback."

  - id: hybrid-statusline
    owner: host
    path: "~/.claude/hud/hybrid-statusline.mjs"
    check_method: "optional-host-file"
    optional: true
    last_checked: "2026-05-13"
    rationale: "메인 statusline (디렉토리, git 브랜치, 사용 중 모델). 호스트 표준 출력 1줄. 미존재 시 plugin/hud/ fallback."

  - id: model-usage-line
    owner: host
    path: "~/.claude/hud/model-usage-line.py"
    check_method: "optional-host-file"
    optional: true
    last_checked: "2026-05-13"
    rationale: "3-tier visibility 모델별 토큰 사용량 + 비용 출력 (opus / sonnet / haiku 각 1줄, 총 3줄). transcript 파싱 + Anthropic 가격 적용. 미존재 시 plugin/hud/ fallback."

  - id: aiden-auto-telemetry
    owner: host
    path: "~/.claude/hud/aiden-auto-telemetry.mjs"
    state_source: "~/.claude/state/telemetry.json"
    check_method: "optional-host-file"
    optional: true
    last_checked: "2026-05-13"
    rationale: "Aiden-auto 한 줄 텔레메트리 (phase · agent · model · pdca · cost · breaker). 사용자가 '어디까지 했어?' 질문하지 않게 만드는 핵심 장치. 데이터 미존재 시 silent skip. 결정 횟수 0~2회 목표 정합. 미존재 시 plugin/hud/ fallback."
```

## v28.2 내부 advisors (자가 등록)

```yaml
internal_advisors:
  - id: quota-advisor
    trigger: "PreToolUse(Task) AND quota_signal"
    verdicts: [PROCEED, DOWNGRADE_ECO, DEFER, BLOCK]
    rationale: "Section 3 quota 운영"

  - id: multi-session-router
    trigger: "Phase 0 plan complete AND splittable_signal"
    verdicts: [SINGLE, RECOMMEND_AUTO_LAUNCH]
    rationale: "Section 4 멀티세션 판정"

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
