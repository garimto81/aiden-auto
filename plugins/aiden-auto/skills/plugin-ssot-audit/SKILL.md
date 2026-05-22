---
name: plugin-ssot-audit
description: Plugin SSOT 정책 (rule 19) 준수 검증 + 자율 sync. project source (C:/claude/plugins/aiden-auto/) 와 marketplace cache (~/.claude/plugins/marketplaces/.../plugins/aiden-auto/) 두 로컬 mirror 의 SHA256 비교를 통해 drift / proj_only / cache_only 자동 감지. cache 가 정본이라는 정책에 따라 cache → project source 자율 sync. "plugin sync", "plugin drift", "마켓플레이스 동기화", "SSOT 검증", "plugin mirror 확인" 이 언급될 때 즉시 사용. plugin 작업 직후 + 매 audit-loop cycle 자동 호출.
---

# Plugin SSOT Audit + Sync

## When to use

이 skill 은 다음 상황에 즉시 사용한다:

- plugin source (`C:/claude/plugins/aiden-auto/`) 또는 marketplace cache 의 파일을 편집한 직후
- `audit-loop` cycle 의 일부 (정합성 자동 검증)
- 사용자가 "plugin sync", "drift", "마켓플레이스 동기화", "SSOT 검증" 등 언급
- 새로운 환경 세팅 시 (clean checkout 직후)
- plugin commit 또는 GitHub push 전 (drift 검증)

## Background — 정책 (rule 19, A-29 갱신 Cycle 24)

**Path α detach 이전 (2026-05-18 14:46 이전)**:
```
   외부 GitHub `garimto81/aiden-auto` (SSOT)
        │
        ├── marketplace cache (CC 로드 대상)
        └── project source mirror (git 추적, 작업 위치)
   불변 조건: 두 mirror SHA256 동일 (대칭)
```

**Path α detach 이후 (현재, 2026-05-18 14:46~)**:
```
   외부 GitHub `garimto81/aiden-auto` (plugin 정본)
        │
        └── marketplace cache (CC 로드 대상, plugin 원본 보관)

   project source (C:/claude/plugins/aiden-auto/)
        = audit 스크립트 + 커스텀 파일만 (의도된 비대칭)
   
   비대칭 정책:
   - cache 가 plugin 원본 (365 파일)
   - project source 는 우리 커스텀 영역 (9 파일)
   - is_perfect_mirror = False 가 정상 상태
```

**A-29 (Cycle 24 critic Weakness 1)**: detach 후 "두 mirror SHA256 동일" 가정 폐기. is_perfect_mirror 가 항상 False 이며 이는 결함이 아닌 detach 의도. audit 가 보고하는 374 actions 는 "비대칭 패턴 가시화" 이며 사용자 결정 영역 (sync 실행 여부).

## How to use

### 검증만 (dry-run, 기본)
```bash
python C:/claude/.claude/skills/plugin-ssot-audit/scripts/audit_and_sync.py
```

### 자율 sync 실행 (cache → project source)
```bash
python C:/claude/.claude/skills/plugin-ssot-audit/scripts/audit_and_sync.py --sync
```

exit code:
- `0` = PERFECT MIRROR (정책 준수)
- `1` = drift 발견 (sync 또는 사용자 확인 필요)

## Output

### 콘솔
```
=== Plugin SSOT Audit Report (2026-05-12T22:00:00) ===

  Project mirror: C:/claude/plugins/aiden-auto
  Cache mirror:   ~/.claude/plugins/marketplaces/.../plugins/aiden-auto
  
  proj total: 318
  cache total: 318
  same content: 318
  drift: 0
  proj_only: 0
  cache_only: 0
  
  STATUS: ✓ PERFECT MIRROR (정책 준수)
```

### JSON
`.claude/state/plugin-ssot-mapping.json` 에 저장:
```json
{
  "ts": "...",
  "summary": {
    "proj_total": 318,
    "cache_total": 318,
    "same": 318,
    "drift": 0,
    "proj_only": 0,
    "cache_only": 0,
    "is_perfect_mirror": true
  },
  "drift_paths": [],
  "proj_only_paths": [],
  "cache_only_paths": []
}
```

## Drift 분류 + 조치

| 항목 | 의미 | 자율 조치 |
|------|------|----------|
| **drift** | 같은 path, 다른 SHA256 | cache 값으로 덮어쓰기 |
| **proj_only** | project 에만 있음 (cache 에 없음) | project 에서 제거 (cache 가 정본) |
| **cache_only** | cache 에만 있음 (project 에 없음) | project 에 추가 |
| **build_artifact** (`__pycache__`, `*.pyc`) | runtime 생성물 | 검증 + sync 대상 제외 |

## audit-loop 통합

`audit-loop` skill 의 cycle 1 에서 자동 호출:

```
Cycle 1
  ↓
agent-matrix-audit ┐
skill-matrix-audit ├── 4 audit 병렬
command-matrix-audit ├
workflow-matrix-audit ┘
plugin-ssot-audit    ← 신규: SSOT 정합성 검증
  ↓
critic self-verify
  ↓
자율 정리 (PHANTOM + drift)
  ↓
exit_criteria: 4 audit issue == 0 (A-30 정정 Cycle 24)
                 (plugin-ssot drift 는 detach 의도로 보고만)
```

## After audit — drift 발견 시 권장 절차

1. **검증 (dry-run)**: 어떤 파일이 drift 했는지 확인
2. **원인 분석**: 누가/언제/왜 drift 만들었는지 git log 추적
3. **자율 sync**: `--sync` 옵션으로 cache → project source mirror
4. **commit**: project source 의 변경을 git commit (외부 GitHub push 준비)
5. **push** (수동): `git push origin main` 으로 외부 GitHub 정본 update

## Limitations

- `__pycache__/`, `*.pyc` 등 build artifact 는 검증 + sync 대상 제외 (자동 생성됨)
- 외부 GitHub `garimto81/aiden-auto` 와의 sync 는 본 skill 범위 밖 (별도 git push/pull 필요)
- 두 mirror 의 동시 수정 (race condition) 시 cache 우선 (사용자 의도 손실 가능 — 작업 전 audit 권장)

## 관련 정책

- 정책 문서: `C:/claude/.claude/rules/19-plugin-ssot-policy.md`
- 통합 audit: `C:/claude/.claude/skills/audit-loop/SKILL.md`
- 4 다른 audit skill: `agent-matrix-audit`, `skill-matrix-audit`, `command-matrix-audit`, `workflow-matrix-audit`
