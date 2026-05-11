---
name: audit
description: Daily configuration audit, improvement suggestions, and trend-based workflow optimization
triggers:
  keywords:
    - "audit"
    - "trend"
    - "워크플로우 개선"
    - "브리핑 분석"
---

# /audit

이 스킬은 `.claude/commands/audit.md` 커맨드 파일의 내용을 실행합니다.

## 서브커맨드 라우팅

| 서브커맨드 | 동작 |
|-----------|------|
| (없음) | **통합 점검: 설정 점검 + 트렌드 분석 + 자동 적용** |
| `config` | 설정 점검만 (CLAUDE.md, 커맨드, 에이전트, 스킬, 문서 동기화) |
| `quick` | 빠른 점검 (버전/개수만) |
| `deep` | 심층 점검 (내용 분석 포함) |
| `fix` | 발견된 문제 자동 수정 |
| `baseline` | 현재 상태를 기준으로 저장 |
| `suggest [영역]` | 솔루션 추천 |
| `trend` | Gmail 브리핑 기반 트렌드 분석 + 워크플로우 갭 분석 + 메일 삭제 |
| `trend --apply` | 트렌드 분석 + 자동 적용 + 커밋 + 메일 삭제 (완전 자동화) |
| `--auto-implement` | **통합 점검 + 자동 구현 (Phase 0-5, Self-Improving Loop)** |
| `ledger` | 개선 이력 조회 (improvement-ledger.json) |
| `ledger stats` | 개선 통계 요약 (총 제안/적용/PR/백로그/revert) |

## 통합 워크플로우 (기본 동작)

`/audit` 단독 실행 시 설정 점검과 트렌드 분석을 한번에 수행합니다.

```
/audit 실행
    │
    ├─ [Phase 1] 설정 점검
    │       ├─ CLAUDE.md 점검 (버전, 커맨드/에이전트/스킬 개수)
    │       ├─ 커맨드 점검 (frontmatter, 필수 섹션)
    │       ├─ 에이전트 점검 (역할, 전문분야, 도구)
    │       ├─ 스킬 점검 (SKILL.md 존재, 트리거)
    │       └─ 문서 동기화 점검
    │
    ├─ [Phase 2] 웹 리서치 기반 트렌드 분석 (Lead 직접 실행)
    │       ├─ 현재 워크플로우 인벤토리 수집
    │       ├─ Lead가 WebSearch 직접 호출 (3-tier 쿼리 8개, 병렬 권장)
    │       ├─ Lead가 갭 분석 (아티클 vs 인벤토리, 3분류 + 복잡도 태그)
    │       ├─ 개선 아이디어 출력
    │       └─ 결과 캐싱 (.claude/research/audit-trend-<date>.md)
    │
    └─ [Phase 3] 통합 결과 요약
```

**핵심 규칙:**
- Phase 1은 항상 실행
- Phase 2는 WebSearch 타임아웃 시에만 스킵 (설정 점검 결과만 출력)
- 결과 없으면 "관련 아티클 없음" 표시 후 Phase 3으로 진행
- Phase 3에서 설정 점검 + 트렌드 결과 통합 출력
- **Agent Teams 미사용**: #140 blocker 대응으로 2026-04-21부터 Lead 직접 실행 구조

## `trend` 서브커맨드 워크플로우

```
/audit trend 실행
    │
    ├─ [1/5] 현재 워크플로우 인벤토리 수집 (commands/skills/agents/rules)
    ├─ [2/5] Lead가 WebSearch 직접 호출 (3-tier 쿼리 8개)
    ├─ [3/5] Lead가 갭 분석 — 이미 구현 / 부분 구현 / 미구현 3분류
    ├─ [4/5] 개선 아이디어 제안 출력 (출처 URL 포함)
    └─ [5/5] 결과 캐싱 (.claude/research/audit-trend-<date>.md, 24h TTL)
```

**핵심 규칙:**
- `--dry-run` 시 캐싱 스킵
- `--save` 시 `.claude/research/audit-trend-<date>.md` 저장
- `--refresh` 시 캐시 무시하고 새로 검색
- `--apply` 시 Step 4.5(자동 적용 + 커밋) 추가 실행, LOW/MEDIUM 복잡도만 적용

## 커맨드 파일 참조

상세 워크플로우: `.claude/commands/audit.md`
