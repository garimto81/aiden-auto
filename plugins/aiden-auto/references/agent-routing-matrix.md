# Smart Model Routing v25.5

## Core Principle

기본 모델은 Agent 정의 파일(`.claude/agents/*.md`)의 `model:` 필드가 결정. Agent() 호출 시 `model` 파라미터(`"sonnet"`, `"opus"`, `"haiku"`)로 오버라이드 가능. Fallback(general-purpose) 시 `model` 명시 필수.

## 3-Tier Workload Model

| Tier | 모델 | 비율 | 기준 |
|:----:|:----:|:----:|------|
| T1 Strategic | Opus | 19% | 깊은 추론·아키텍처·전략 판단 |
| T2 Execution | Sonnet | 38% | 표준 구현·리뷰·QA·도메인 전문 |
| T3 Retrieval | Haiku | 43% | 조회·탐색·템플릿·문서 작성 |

## subagent_type → 모델 티어 매핑

| subagent_type | 모델 티어 | 용도 |
|---------------|----------|------|
| explore | haiku | 파일 탐색, 이슈 검색 등 단순 조회 |
| executor, code-reviewer, qa-tester, designer | sonnet | 반복 실행, QA, 코드 리뷰 |
| executor-high, architect, planner, critic | opus | 구현, 설계, 검증, 계획, 진단 |
| security-reviewer, designer-high, qa-tester-high | opus | v25.5 선별 승격 (오탐 비용 > 모델 비용) |
| writer | haiku | 간단 문서 작성 |

> 모델 분포: Opus 8 (19%) / Sonnet 16 (38%) / Haiku 18 (43%)

## --eco 모드 세분화

| 레벨 | Opus→ | Sonnet→ | 절감 | 용도 |
|------|:-----:|:-------:|:----:|------|
| `--eco` | Sonnet | 유지 | ~30% | 일반 비용 절감 |
| `--eco-2` | Sonnet | 비핵심만 Haiku | ~50% | 중간 절감 |
| `--eco-3` | Sonnet | 전부 Haiku | ~70% | 프로토타이핑 전용 |

> `--eco-3`은 프로토타이핑 전용. 프로덕션 금지.

## Skill Routing (Local Only)

| Pattern Detected | Action |
|------------------|--------|
| "autopilot", "build me", "I want a" | `/auto` (PDCA 자동 진행) |
| Broad/vague request | `/auto` Phase 1 (explore → plan) |
| "plan this", "plan the" | `/auto` Phase 1 |
| `--eco` / `--eco-2` / `--eco-3` 옵션 | `/auto` 비용 절감 모드 |
| UI/component/styling work | `designer` agent 직접 위임 |
| Git/commit work | `/commit` |
| "debug", "investigate" | `/debug` |
| "critic", "약점 분석", "문제점 찾아" | `/auto --critic` |
| "research", "analyze data" | `/research` |
| "tdd", "test first", "red green" | `/tdd` |
| "schedule", "routine", "cron", "매일", "반복" | `/schedule` (Routines + OS scheduler) |
| "stop", "cancel", "abort" | `cancel` |
| "이미지 분석", "OCR", "텍스트 추출" | OCR 자동 실행 |

상세: `.claude/references/model-routing-guide.md`
