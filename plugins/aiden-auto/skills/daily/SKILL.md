---
name: daily
description: >
  Daily Dashboard v3.0 - 3-source unified learning + action recommendation engine.
  Gmail/Slack/GitHub incremental collection, AI cross-source analysis, action draft generation.
  Project expert mode + Config Auto-Bootstrap.
version: 3.0.0

triggers:
  keywords:
    - "daily"
    - "오늘 현황"
    - "일일 대시보드"
    - "프로젝트 진행률"
    - "전체 현황"
    - "데일리 브리핑"
    - "morning briefing"
    - "아침 브리핑"
    - "daily-sync"
    - "일일 동기화"
    - "업체 현황"
    - "vendor status"
  file_patterns:
    - "**/daily/**"
    - "**/checklists/**"
    - "**/daily-briefings/**"
  context:
    - "업무 현황"
    - "프로젝트 관리"

capabilities:
  - daily_dashboard
  - incremental_collection
  - cross_source_analysis
  - action_recommendation
  - attachment_analysis
  - expert_context_loading
  - config_auto_bootstrap
  - gmail_housekeeping
  - slack_lists_update

model_preference: sonnet
auto_trigger: true
---

# Daily Skill v3.0 — Index

3-source (Gmail/Slack/GitHub) incremental collection + AI cross-source analysis + action recommendation engine.

**Paradigm**: "collect+display" -> "learn+recommend actions"
**Design Reference**: `C:\claude\docs\02-design\daily-redesign.design.md`
**상세 (모든 phase 명세 + 코드 + Output Format + Subcommands + Changelog)**: `references/phases-detail.md`

## Execution Rules (CRITICAL)

**When this skill activates, you MUST run the 9-Phase Pipeline below in order.**

```
Phase 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8
Config   Expert  Collect  Attach  AI     Action  Project  Gmail    State
Bootstrap Context  (incr)  Analyze Analyze Recom   Ops    Housekp  Update
```

## 9-Phase Summary

| Phase | Name | One-line behavior |
|:-----:|------|-------------------|
| 0 | Config Bootstrap | `.project-sync.yaml` lookup in CWD; auto-generate v2.0 (CLAUDE.md/README.md/dirname + source discovery + type classify) if missing |
| 1 | Expert Context Loading | Build expert_context in 3 tiers (Identity 500t / Operational 2000t / Deep 3000t); injected into Phase 4,5 |
| 2 | Incremental Collection | Auth check then incremental Gmail (History API), Slack (since last_ts), GitHub (gh) using cursors in daily-state |
| 3 | Attachment Analysis | AI-analyze PDF/Excel/image attachments with SHA256 cache; perspective from expert_context |
| 4 | AI Cross-Source Analysis | Per-source analysis then cross-source links (same-topic, action linkage, status mismatch, timeline) |
| 5 | Action Recommendation | Generate concrete drafts (email/Slack/GitHub), tone via communication_style, max 10 sorted by urgency |
| 6 | Project-Specific Ops | Conditional on project_type (vendor_management Slack Lists / development CI+milestones) |
| 7 | Gmail Housekeeping | Auto label apply (7a) + INBOX cleanup auto/confirm/skip (7b) per housekeeping config |
| 8 | State Update | Phase A cursors right after collection; Phase B cache+learned_context after analysis; auto pending_additions |

> 각 phase 의 step 별 코드·yaml·error 처리 전문은 `references/phases-detail.md` 참조.

## Key Behaviors

- **Incremental**: Cursors in `.omc/daily-state/<project>.json` so each run collects only new data. Write failure -> safely re-collected next run.
- **Auth-tolerant**: Skip sources that fail auth; abort only if zero sources active. Single-source -> skip cross-source analysis.
- **Config-driven**: Auto-update config only when `auto_generated: true`; v1.0 / `auto_generated:false` are read-only.
- **Output**: Dashboard with Sources / Cross-Source Insights / Action Items (URGENT->HIGH) / Per-Source Details / Attachment Analysis. vendor_management + development add extra sections.
  상세 포맷: `references/phases-detail.md` (Output Format).

## Invocation / Subcommands

| Command | Description |
|---------|-------------|
| `/daily` | Full dashboard (all 9 phases) |
| `/daily ebs` | EBS daily briefing — `cd C:\claude\ebs\tools\morning-automation && python main.py --post` (상세: `references/phases-detail.md`) |

상세 (EBS workflow, Changelog 전체): `references/phases-detail.md`
