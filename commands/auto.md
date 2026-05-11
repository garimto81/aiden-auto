---
name: auto
version: 23.0.0
description: PDCA Orchestrator - Agent Teams + PDCA 통합 워크플로우
aliases: [autopilot, ulw, ultrawork, ralph]
deprecated: false
---

# /auto - PDCA Orchestrator (Agent Teams)

> **워크플로우 정의**: `.claude/skills/auto/SKILL.md`
> **상세 PDCA/옵션 워크플로우**: `.claude/skills/auto/REFERENCE.md`

이 커맨드는 `/auto` 스킬을 실행합니다. 모든 워크플로우 로직은 SKILL.md에 정의되어 있습니다.

## 사용법

```bash
/auto "작업 내용"           # 명시적 작업 실행
/auto                       # 자율 발견 모드
/auto status                # 현재 상태
/auto stop                  # 중지
/auto resume                # 재개

# 옵션 체인
/auto --gdocs --mockup "화면명"
/auto --gmail "from:client"
/auto --slack C09N8J3UJN9
/auto --research "키워드"
/auto --debate "주제"
/auto --con 123456 "PRD 발행"
/auto --con 123456 docs/00-prd/xxx.prd.md --dry-run
/auto --daily
/auto --interactive "작업"
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--gdocs` | Google Docs PRD 동기화 |
| `--mockup` | 목업 생성 (하위: `--force-html`, `--prd=`). B&W Refined Minimal 기본 적용. `--bnw` deprecated |
| `--debate` | 3AI 토론 |
| `--research` | 리서치 모드 |
| `--gmail` | Gmail 메일 분석 후 컨텍스트 주입 |
| `--slack <채널ID>` | Slack 채널 분석 후 컨텍스트 주입 |
| `--jira <cmd> <target>` | Jira 조회/분석 (epics, project, board, search, issue) |
| `--figma <url> [connect\|rules]` | Figma 디자인 연동 (implement-design, code-connect, design-system-rules) |
| `--con <page_id> [file]` | Confluence 페이지 발행 (`lib/confluence/md2confluence.py`). 파일 생략 시 PRD/Plan 자동 탐지. `--dry-run` 지원 |
| `--daily` | daily v3.0 9-Phase Pipeline |
| `--interactive` | 각 Phase 전환 시 사용자 승인 요청 |
| `--max N` | 최대 N회 반복 |
| `--eco` | 토큰 절약 모드 (Haiku 우선) |
| `--skip-analysis` | Phase 1 사전 분석 스킵 |
| `--no-issue` | 이슈 생성/연동 스킵 |
| `--strict` | E2E 1회 실패 시 중단 |
| `--dry-run` | 판단만 출력, 실행 안함 |
| `--spec` | Phase 0.15 (Plan → Atomic Tasks 분해) 활성화. Phase 0.0(PRD 수정)은 기본 ON이므로 `--spec` 불필요 |
| `--new` | Phase 0.0에서 신규 PRD 생성 (기존 PRD 매칭 없을 때) |
| `--skip-prd <이유>` | Phase 0.0 (PRD 수정) 스킵. 이유 필수: `hotfix`/`docs-typo`/`config`/`refactor` |
| `--skip-critic` | 문서 생성 후 embedded critic 게이트 생략 |

## 레거시 키워드 라우팅

| 키워드 | 동작 |
|--------|------|
| `ralph: 작업` | → `/auto "작업"` |
| `ulw: 작업` | → `/auto "작업"` |
| `ultrawork: 작업` | → `/auto "작업"` |
| `ralplan: 작업` | → `/auto "작업"` (계획 모드 강제) |
| `/work "작업"` | → `/auto "작업"` |
| `/work --auto "작업"` | → `/auto "작업"` |
