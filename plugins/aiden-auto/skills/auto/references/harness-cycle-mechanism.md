---
name: harness-cycle-mechanism
version: v3
loaded_from: skill-auto
purpose: 자가개선 critic 사이클 메커니즘 상세 (SKILL.md 분리 — F19 해소)
---

# 자가개선 critic 사이클 (외부 harness 추적 — 원칙 1+2 실행)

본 reference 는 SKILL.md 본문에서 분리. 외부 framework 자동 추적 + critic + applier 사이클의 상세 메커니즘.

## 흐름 다이어그램

```
매일 자동 (또는 daily hook 발동)
    │
    ▼
┌───────────────────────────────┐
│ harness-watcher (haiku, daily)│
│  external-harness-registry    │
│  → GitHub API로 신규 tag/release│
│  → diff 요약 산출              │
└──────────────┬────────────────┘
               │ 신규 update 발견
               ▼
┌───────────────────────────────┐
│ harness-critic (opus)         │
│  우리 5원칙 부합 여부 판정      │
│  · 진입점 줄이는가?            │
│  · 자율 이터레이션 늘리는가?    │
│  · 복사 아닌 참조로 가능한가?   │
└──────────────┬────────────────┘
               │ APPROVE
               ▼
┌───────────────────────────────┐
│ harness-applier (sonnet)      │
│  patch 생성 → branch + PR     │
└───────────────────────────────┘
```

추적 대상 등록: `external-harness-registry.md`.

## 자동 발동 시점 (v3 — harness_cycle_runner.py 통합)

- daily SessionStart hook (`~/.claude/hooks/harness_cycle_runner.py` 자동 발동)
- on-demand (사용자 평문 "harness 상태")
- first-fail (외부 framework 호출 실패 누적 시)
- post-cmd (특정 cmd 직후 검증)

## State file

| 파일 | 역할 |
|------|------|
| `state/harness-updates-{date}.json` | watcher 산출 (외부 framework diff) |
| `state/harness-critic-pending-{framework}.flag` | critic 호출 대기 (runner 가 생성) |
| `state/harness-cycle-{date}.json` | 본 cycle invocation 기록 |
| `state/framework-applied-{date}.json` | applier 적용 기록 |

## Anti-patterns

- 외부 harness 파일을 plugin 내부로 복사 (참조만)
- critic verdict 없이 applier 호출
- patch + PR 자동 생성 후 사용자 검토 없이 merge

## 관련 자산

- `agents/meta/harness-watcher.md`
- `agents/meta/harness-critic.md`
- `agents/meta/harness-applier.md`
- `hooks/harness_cycle_runner.py` (v3 자동 발동)
- `references/external-harness-registry.md`

## 변경 이력

| 날짜 | 변경 |
|------|------|
| 2026-05-23 | v3 신규 — SKILL.md 분리 (F19 해소) |
