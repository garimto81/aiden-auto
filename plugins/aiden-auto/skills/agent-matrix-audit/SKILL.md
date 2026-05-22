---
name: agent-matrix-audit
description: enforcer.py 의 MATRIX_NORMAL 에 등록된 모든 agent 의 실제 파일 위치를 3 경로 (project local / global user / plugin marketplace) 에서 검색하여 매트릭스 무결성을 검증한다. phantom entry (매트릭스에만 존재, 파일 없음), 중복 정의 (multiple paths), built-in shadow, plugin/global/local 경로 충돌을 자동 감지하고 JSON + 표로 리포트한다. agent 추가/삭제/이름변경 직후, model routing 디버깅 시, "FILE_MISSING" / "phantom agent" / "매트릭스 audit" / "enforcer 무결성" / "agent 위치 확인" 등이 언급될 때 반드시 사용. 매트릭스 변경이 의심되는 모든 상황에 적극 활용 — 결함을 조기에 잡는 것이 디버깅 비용을 크게 줄임.
---

# Agent Matrix Audit

## When to use

이 skill 은 다음 상황에 즉시 사용한다:

- `agent_model_enforcer.py` 의 `MATRIX_NORMAL` 을 수정한 직후 무결성 검증
- 사용자가 "FILE_MISSING", "phantom agent", "매트릭스 무결성", "agent 위치", "enforcer 검증" 등을 언급
- model routing 이상 (예: sonnet $0 같은 측정 갭) 을 디버깅할 때
- 새 plugin 설치 후 agent 가 매트릭스에 추가됐는지 확인
- agent 이름 변경 / 이동 / 삭제 후 매트릭스 sync 점검

매트릭스에 등록만 하고 파일이 없으면 enforcer 결정이 실제로 적용되지 않는다 (Claude Code 가 frontmatter 를 못 찾아 Lead 상속 → 의도 외 model 로 실행). 이 skill 은 그런 결함을 조기에 잡는다.

## How to use

```bash
python C:/claude/.claude/skills/agent-matrix-audit/scripts/audit_matrix.py
```

5 초 이내 실행. exit code:
- `0` = phantom 없음 (matrix 정상)
- `1` = phantom 1 개 이상 발견 (수정 필요)

## Output

### 콘솔 출력 형식 (표 + 문제 케이스)

```
=== Matrix Audit Report (2026-05-12T12:34:56) ===

Matrix entries: 47

Status distribution:
  LOCAL              :  14
  GLOBAL             :   0
  PLUGIN             :  29
  BUILT_IN           :   3
  PHANTOM            :   1

Issues found: 1

  [PHANTOM           ] explore                        model=haiku
      → (no paths found)

Saved to: C:/claude/.claude/state/agent-matrix-mapping.json
```

### JSON 출력 형식

`.claude/state/agent-matrix-mapping.json`:

```json
{
  "ts": "...",
  "matrix_total": 47,
  "summary": {"LOCAL": 14, "PLUGIN": 29, "BUILT_IN": 3, "PHANTOM": 1, ...},
  "results": [
    {"name": "executor", "matrix_model": "sonnet", "status": "LOCAL",
     "paths": ["C:/claude/.claude/agents/executor.md"]},
    {"name": "explore", "matrix_model": "haiku", "status": "PHANTOM", "paths": []},
    {"name": "Explore", "matrix_model": "haiku", "status": "BUILT_IN", "paths": []}
  ]
}
```

## Status 의미

| status | 의미 | 조치 |
|--------|------|------|
| **LOCAL** | `.claude/agents/<name>.md` 에 존재 | OK (최우선 경로) |
| **GLOBAL** | `~/.claude/agents/<name>.md` 에 존재 | OK (사용자 전역) |
| **PLUGIN** | plugin marketplace 에 존재 | OK (3 순위 fallback) |
| **BUILT_IN** | 파일 없으나 Anthropic 시스템 내장 | OK (Explore/Plan/general-purpose) |
| **DUPLICATE** | 2 곳 이상에 동시 존재 | ⚠ 우선순위 충돌 가능. 의도 확인 후 1 곳만 남길지 결정 |
| **BUILT_IN_SHADOWED** | built-in 인데 같은 이름 파일도 있음 | ⚠ 어느 것이 우선되는지 Claude Code 동작 검증 필요 |
| **PHANTOM** | 매트릭스 등록만 있고 파일 없음 | ❌ 매트릭스에서 제거 또는 agent 파일 생성 |

## After audit — PHANTOM 발견 시 권장 조치

PHANTOM entry 가 있으면 2 가지 중 하나:

1. **매트릭스 항목 제거**: 호출되지 않는 dead code 라면 `enforcer.py` 의 `MATRIX_NORMAL` 에서 해당 라인 삭제
2. **agent 파일 생성**: 호출 필요한 agent 라면 적절한 경로에 `.md` 파일 생성 (project local 권장)

PHANTOM 을 방치하면 enforcer 가 사용되지 않는 결정을 내림 → logger 통계 오염 → 측정 데이터 신뢰도 저하.

## Examples

**Example 1 — 정상 매트릭스**
```
Status distribution:
  LOCAL    : 14
  PLUGIN   : 29
  BUILT_IN : 3
No issues found. Matrix integrity intact.
```

**Example 2 — phantom entry 1 개**
```
Issues found: 1
  [PHANTOM] explore  model=haiku
      → (no paths found)
```
→ `enforcer.py` 에서 `"explore": "haiku",` 라인 제거 또는 `agents/explore.md` 생성

**Example 3 — 중복 정의**
```
Issues found: 1
  [DUPLICATE] architect  model=sonnet
      → C:/claude/.claude/agents/architect.md
      → C:/Users/AidenKim/.claude/agents/architect.md
```
→ 두 정의 비교 후 1 개만 남기거나, 의도된 우선순위면 무시

## Limitations

- Anthropic built-in agent 목록 (`Explore`, `Plan`, `general-purpose`) 은 하드코딩. 새 built-in 추가 시 스크립트 수정 필요.
- `.md` 파일만 검색. agent 가 다른 형식이면 미탐지 (현재 모든 agent 는 .md).
- 동기적 실행. 매트릭스 100 항목 + plugin 깊은 트리에서 ~5 초.
