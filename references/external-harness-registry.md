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

## 운영 규칙

- **last_checked 갱신 의무**: watcher가 매번 갱신해야 다음 daily에 정확한 delta 계산 가능
- **NEEDS_INFO 처리**: critic이 정보 부족으로 판정 보류 시 사용자에게 1줄 보고 후 다음날 재시도
- **REJECT 누적**: 같은 framework에서 3회 연속 REJECT 시 해당 framework 추적 일시 정지 (사용자 결정으로 재개)
- **check_method 종류**:
  - `tags`: GitHub releases/tags API (semantic version)
  - `releases`: GitHub releases API (release notes 포함)
  - `commits`: default branch HEAD commit sha (tag 없는 repo)
  - `subdir-commits`: monorepo의 하위 디렉토리 commit (path 필터)
