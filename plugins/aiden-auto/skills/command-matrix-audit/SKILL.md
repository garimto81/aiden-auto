---
name: command-matrix-audit
description: command .md 파일의 무결성을 전수 감사한다. redirect stub (Skill 호출만 하는 껍데기), broken redirect (redirect 대상 skill 없음), empty command (5줄 미만), duplicate name (동일 이름 여러 위치)를 자동 탐지. "command 무결성", "redirect stub", "broken redirect", "커맨드 감사", "command 현황 확인" 이 언급될 때 즉시 사용. command 추가/삭제/이름변경 직후 반드시 실행.
---

# Command Matrix Audit

## When to use

이 skill 은 다음 상황에 즉시 사용한다:

- command `.md` 파일 추가/삭제/이름변경 직후
- redirect stub 이 실제로 존재하는 skill 을 가리키는지 확인
- "broken redirect", "커맨드 현황", "command 무결성" 언급 시
- 새 plugin 설치 후 command 중복 충돌 확인

## How to use

```bash
python C:/claude/.claude/skills/command-matrix-audit/scripts/audit_commands.py
```

10 초 이내 실행. exit code:
- `0` = 문제 없음
- `1` = BROKEN_REDIRECT 1 개 이상 발견 (즉시 수정 필요)

## Search paths

| 우선순위 | 경로 |
|----------|------|
| 1 (local) | `C:/claude/.claude/commands/` |
| 2 (global) | `C:/Users/AidenKim/.claude/commands/` |
| 3 (plugin) | `C:/Users/AidenKim/.claude/plugins/marketplaces/**/commands/*.md` |

## Output

### 콘솔 출력 형식

```
=== Command Audit Report (2026-05-12T12:34:56) ===

Commands found: 43

Status distribution:
  OK                   :  28
  REDIRECT_STUB        :  12
  BROKEN_REDIRECT      :   1
  EMPTY                :   2
  DUPLICATE            :   3

Issues found: 4

  [BROKEN_REDIRECT    ] work                 → skill 'workflow' not found
      → C:/claude/.claude/commands/work.md
  [EMPTY              ] gmail                 2 lines
      → C:/claude/.claude/commands/gmail.md
  [DUPLICATE          ] commit
      → C:/claude/.claude/commands/commit.md
      → C:/Users/AidenKim/.claude/commands/commit.md

Saved to: C:/claude/.claude/state/command-matrix-mapping.json
```

### JSON 출력

`C:/claude/.claude/state/command-matrix-mapping.json`:

```json
{
  "ts": "...",
  "commands_total": 43,
  "summary": {"OK": 28, "REDIRECT_STUB": 12, "BROKEN_REDIRECT": 1, "EMPTY": 2, "DUPLICATE": 3},
  "results": [
    {"name": "auto", "status": "REDIRECT_STUB", "redirect_target": "auto",
     "redirect_resolved": true, "lines": 6,
     "paths": ["C:/claude/.claude/commands/auto.md"]},
    {"name": "work", "status": "BROKEN_REDIRECT", "redirect_target": "workflow",
     "redirect_resolved": false, "lines": 4,
     "paths": ["C:/claude/.claude/commands/work.md"]}
  ]
}
```

## Status 의미

| status | 의미 | 조치 |
|--------|------|------|
| **OK** | 본문 10줄+, redirect 아님 | 정상 |
| **REDIRECT_STUB** | skill redirect 만 존재, 대상 skill 확인됨 | 정상 (stub 의도적) |
| **BROKEN_REDIRECT** | redirect 대상 skill 없음 | ❌ skill 이름 수정 또는 stub 제거 |
| **EMPTY** | 본문 5줄 미만 | ⚠ 내용 보강 필요 |
| **DUPLICATE** | 동일 이름 2 곳+ | ⚠ 우선순위 충돌 확인 |

## BROKEN_REDIRECT 발견 시 조치

1. redirect 가 가리키는 skill 이름 확인
2. skill 경로(`C:/claude/.claude/skills/` 또는 plugin) 에서 실재 여부 확인
3. skill 이름 오타면 command 파일의 skill 참조 수정
4. skill 이 폐기됐으면 command 도 함께 제거 또는 새 skill 로 redirect 변경
