---
name: iteration
description: >
  DEPRECATED v11.0 (2026-05-03). 이 스킬은 /auto v27.0에 흡수됨. /iteration 입력은 /auto --mode=iteration으로 자동 redirect됨. 새 chapter 위치 — auto/references/chapter-iteration.md. Hot-swap curator + drift detection 메커니즘 모두 보존됨. 13 iteration- prefix agents 글로벌 보존. 본 SKILL.md는 호환성 stub.
version: 11.0.0
auto_trigger: false
explicit_invocation_only: true
deprecated: true
deprecation_date: "2026-05-03"
replaced_by: "auto"
redirect_to: "auto"
---

# /iteration — DEPRECATED v11.0 (Stub)

> **🔴 DEPRECATED 2026-05-03**
> 이 스킬은 `/auto` v27.0에 흡수됨. 모든 기능 보존, 진입점만 변경.

## Migration

| 이전 (v10.x) | 현재 (v27.0+) |
|--------------|--------------|
| `/iteration` | `/auto --mode=iteration` (자동 redirect) |
| `/iteration "미구현 5개"` | `/auto "미구현 5개"` (Triage가 ITERATION 자동 분류) |
| `iterate`, `cycle` | `/auto` (동일 redirect) |
| Skill body | `auto/references/chapter-iteration.md` |
| Workflows | `auto/workflows/impl-first-7-step.md`, `auto/workflows/spec-first-5-step.md` |
| Curators | `auto/curators/swap_policy.md`, `auto/curators/rotation_log.md` |
| Drift script | `auto/scripts/spec_drift_check.py` |
| Reimplementability script | `auto/scripts/reimplementability_audit.py` |
| 13 iteration- agents | `~/.claude/plugins/.../aiden-auto/agents/iteration-*.md` (불변) |

## 진입 시 동작 (호환성)

`/iteration` 호출 또는 `iterate`/`cycle` 키워드 감지 시:

```
1. /auto SKILL.md로 redirect
2. /auto Phase -2 Triage가 자동으로 ITERATION 카테고리 분류
3. chapter-iteration.md 로딩
4. 기존 워크플로우 (Impl-first 7-step / Spec-first 5-step) 그대로 실행
```

## 새 사용법

```bash
# 자동 분류 (권장)
/auto "미구현 API 5개 처리"

# 명시적 모드
/auto --mode=iteration "drift 검증"

# Drift만 실행
/auto --drift-check

# Hot-swap curator 활성
/auto --evolve "반복 작업"
```

## 본 파일

영구 stub. legacy alias redirect 호환성 위해 보존.
