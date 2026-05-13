# 스킬 라우팅 규칙

모든 스킬은 Agent Teams 패턴으로 직접 실행합니다. 로컬 에이전트 (`C:\claude\.claude\agents\`)를 사용합니다.

## 스킬 매핑 테이블

| 스킬 | 실행 방식 | 서브커맨드 |
|------|----------|-----------|
| `/auto` | 직접 실행 (PDCA orchestrator, Agent Teams 단일 패턴) | Phase 1-5, --gdocs, --mockup, --daily 등 + Error Context Critic |
| `/check` | Agent Teams (QA 사이클) | --fix, --e2e, --perf, --security, --all, --react, --level |
| `/debug` | Agent Teams (architect 분석) | D0-D4 Phase + D3.5 Solution Critique |
| `/tdd` | Agent Teams (tdd-guide) | - |
| `/parallel` | Agent Teams (병렬 executor) | dev, test, review, research, check |
| `/research` | Agent Teams (researcher) | code, web, plan, review |
| `/plan` | 직접 실행 (Plan mode 전용 UI 목업: ASCII + mockup-spec) | --screens, --layout, --flow, --prd, --backend |
| `/commit`, `/issue`, `/pr`, `/verify`, `/mockup-hybrid` | 직접 실행 | 각 고유 서브커맨드 |
| `--critic` | `/auto` 옵션 (critic→researcher 3-Phase 파이프라인) | — |
| `--jira` | `/auto` 옵션 (lib/jira/jira_client.py 실행) | epics, project, board, search, issue |
| `--figma` | `/auto` 옵션 (Figma MCP 플러그인 래퍼, OAuth 인증) | `<url>`, `connect <url>`, `rules`, `capture`, `auth` |
| `--con` | `/auto` 옵션 (`lib/confluence/md2confluence.py` 실행) | `<page_id>`, `<file>`, `--dry-run` |
| `--spec` | `/auto` 옵션 — Phase 0.15 (Plan → Atomic Tasks 분해) 활성화. Phase 0.0(PRD 수정)은 **기본 ON**이므로 `--spec` 불필요 | `--new`, `--skip-prd`, `--skip-critic` |
| `--new` | `/auto` 옵션 — Phase 0.0에서 신규 PRD 생성 | — |
| `--skip-prd <이유>` | `/auto` 옵션 — Phase 0.0 스킵. 이유 필수 (`hotfix`/`docs-typo`/`config`/`refactor`) | Rule 13 예외 케이스 |
| `--skip-critic` | `/auto` 옵션 (embedded critic 게이트 생략) | — |
| `/overlay-fallback` | 직접 실행 (자동 트리거: T-1~T-5 조건) | — |
| `calendar` | 스킬 (lib/calendar CLI wrapper, gws 하이브리드) | today, week, list, create, delete |
| `/doc-critic` | Agent Teams (doc-critic 분석) | --dry-run |

## 외부 플러그인 연동

| 플러그인 | 역할 | 통합 상태 |
|---------|------|----------|
| `frontend-design` | 프론트엔드 미학 가이드라인 (Typography, Color, Motion, Spatial, Anti-Patterns) | `designer.md`에 가이드라인 직접 내장 완료. 플러그인은 세션 컨텍스트 보강용. |
| `figma` | Figma MCP 서버 + MCP 도구 13개 (implement, connect, rules, capture, auth) | 로컬 래퍼 스킬 `.claude/skills/figma/SKILL.md`로 /auto 통합 완료. OAuth 인증 자동. |

## Deprecated 스킬 리다이렉트

| 옛 커맨드 | 현재 |
|-----------|------|
| `/work`, `/auto-workflow`, `/auto-executor` | `/auto` |
| `/tdd-workflow` | `/tdd` |
| `/cross-ai-verifier` | `/verify` |
| `/issue-resolution` | `/issue fix` |
| `/daily-sync` | `/daily` |

> 전체 이력: git log 참조. 여기에는 사용자가 실수로 입력할 가능성이 있는 항목만 유지.

## 에이전트 티어 라우팅

| 복잡도 | 티어 | 에이전트 예시 |
|--------|------|--------------|
| 간단 | LOW (haiku) | `explore`, `executor-low`, `writer` |
| 보통 | MEDIUM (sonnet) | `executor`, `designer`, `qa-tester` |
| 복잡 | HIGH (opus) | `architect`, `planner`, `executor-high` |

## --eco 모드 라우팅

| 레벨 | Opus→ | Sonnet→ | 절감 | 용도 |
|------|:-----:|:-------:|:----:|------|
| `--eco` | Sonnet | 유지 | ~30% | 일반 비용 절감 |
| `--eco-2` | Sonnet | 비핵심만 Haiku | ~50% | 중간 절감 |
| `--eco-3` | Sonnet | 전부 Haiku | ~70% | 프로토타이핑 전용 |

> `--eco-3`은 프로토타이핑 전용. 프로덕션 금지.

## 인과관계 그래프

상세: `.claude/references/skill-causality-graph.md` (이 관계가 무너지면 5계층 Discovery 전체 작동 불가)

## 금지 사항

- SKILL.md에 "참조하세요"만 작성 금지 (실행 지시 필수)
- 서브프로젝트에 리소스 로컬 생성 금지 (Junction 사용)
- 인과관계 파괴 금지 (커맨드 삭제/변경 시 연쇄 확인 필수)
