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

  - id: vercel
    owner: vercel
    repo: vercel-plugin
    check_method: "commits"   # no tags, use default branch HEAD
    last_known_version: "61f1903b"
    last_checked: "2026-05-11"
    interesting_paths:
      - "plugins/vercel/"
      - "skills/"
    rationale: "Vercel ecosystem 통합 (AI SDK, AI Gateway, Workflow DevKit)."

  - id: superpowers
    owner: obra
    repo: superpowers
    check_method: "tags"
    last_known_version: "v5.1.0"
    last_checked: "2026-05-11"
    interesting_paths:
      - "skills/"
    rationale: "skill discipline 패턴 (brainstorming, TDD, debugging)."

  - id: atlassian
    owner: atlassian
    repo: atlassian-mcp-server
    check_method: "commits"   # no tags, use default branch HEAD
    last_known_version: "9b52fb18"
    last_checked: "2026-05-11"
    interesting_paths:
      - "skills/"
      - "src/"
    rationale: "Jira/Confluence MCP server. integration 패턴."

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
