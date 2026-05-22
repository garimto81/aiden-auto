---
name: workflow-matrix-audit
description: >
  workflow 무결성 검증 스킬. hook 검증, phantom hook 탐지,
  settings.json 등록 hook 파일 존재 여부 전수 audit.
  중복 등록(DUPLICATE_REGISTRATION) 및 미존재 파일(PHANTOM_HOOK) 식별.
trigger: manual
version: 1.0.0
---

# Workflow Matrix Audit

settings.json 의 hooks 섹션을 파싱하여 등록된 모든 hook 의 무결성을 검증한다.

## 실행

```bash
python C:/claude/.claude/skills/workflow-matrix-audit/scripts/audit_workflow.py
```

## 출력

- 콘솔: 각 hook 상태 (OK / PHANTOM_HOOK / DUPLICATE_REGISTRATION)
- JSON: `C:/claude/.claude/state/workflow-matrix-mapping.json`

## Exit Code

- `0`: 모든 hook 정상
- `1`: PHANTOM_HOOK 1개 이상 발견
