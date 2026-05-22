# 6중 다층 방어 (Identity + Scope)

## 핵심 원칙

신분증 한 장은 위조 가능. 6중 검문소를 모두 통과해야 출입 허가.

## Layer 매트릭스

| # | Layer | 메커니즘 | 강제 시점 | 위조 난이도 |
|:-:|------|---------|---------|:----------:|
| 1 | 워크트리 경로 패턴 | 정규식 매칭 | 진입 시 | LOW |
| 2 | `.team` 메타 파일 | yaml SSOT | 진입 시 | MED |
| 3 | 워크트리 CLAUDE.md | LLM context | 세션 시 | LOW (LLM 무시 가능) |
| 4 | SessionStart hook | Python script | 세션 시작 | HIGH |
| 5 | PreToolUse hook | Python script | Edit/Write 직전 | HIGH |
| 6 | GitHub 인프라 | CODEOWNERS + branch protection + CI | PR 생성/머지 | VERY HIGH |

## Layer 1 — 워크트리 경로 패턴

```
정규식: ^<project>-(.+)$
예시:
  ebs-foundation        → S1 Foundation
  ebs-lobby-stream      → S2 Lobby
  myapp-frontend        → S2 Frontend
```

team_assignment.yaml의 `streams[X].worktree` 와 정확히 일치 검증.

## Layer 2 — `.team` 메타 파일

워크트리 root에 위치. yaml 형식. 모든 hook + 도구가 참조하는 SSOT.

스키마는 `templates/team_assignment.yaml.j2` 의 `streams[X]` 섹션 그대로.

## Layer 3 — 워크트리 CLAUDE.md (override)

```markdown
# {Stream Name} Session

## 🎯 Your Identity
You are working as **{Stream Name}** in {project} multi-session orchestration.
Source of Truth: `.team` file in this worktree root. Read it FIRST.

## 🚫 Hard Boundaries
You CANNOT edit:
- Other streams' SCOPE
- Meta files: CLAUDE.md (root), MEMORY.md, team_assignment.yaml
- Files outside `scope_owns`

You CAN edit (only):
{list scope_owns}

## ✅ Workflow
1. Session start → SessionStart hook auto-injects identity
2. Verify scope before any Edit/Write
3. PreToolUse hook blocks scope violations automatically
```

## Layer 4 — SessionStart hook

`hook_templates/SessionStart.py` 참조. 핵심:

1. cwd 정규식 매칭 → team_id_from_path
2. `.team` 파일 read → team_data
3. 일치 검증 (불일치 시 exit 1)
4. 의존성 상태 GitHub fetch
5. context에 identity + status 강제 주입

## Layer 5 — PreToolUse hook

`hook_templates/PreToolUse.py` 참조. 핵심:

1. Edit/Write/MultiEdit 도구 detection
2. 대상 파일 추출
3. 메타 파일 차단 (exit 2 + stderr)
4. SCOPE 외 차단 (exit 2 + stderr)
5. BLOCKED 의존성 시 차단

## Layer 6 — GitHub 인프라

### CODEOWNERS
Stream별 SCOPE 폴더 → 해당 Stream 라벨 보유 PR만 수정 허용.

### Branch Protection (main)
```yaml
required_pull_request_reviews:
  require_code_owner_reviews: true
required_status_checks:
  strict: true
  contexts:
    - scope_check
    - dependency_check
    - phase_gate_check
enforce_admins: false  # admin도 강제
allow_force_pushes: false
```

### CI Workflows
- `scope_check.yml`: PR 변경 파일이 Stream SCOPE 내인지 검증
- `dependency_check.yml`: blocked_by Stream의 PR이 모두 merged인지 검증
- `phase_gate_check.yml`: Phase 시간차 SCOPE 활성화 검증

## 위반 시도 시나리오 매트릭스

| # | 시도 | 차단 Layer |
|:-:|------|----------|
| 1 | 잘못된 워크트리 진입 | L1 + L4 |
| 2 | `.team` 누락 | L4 |
| 3 | `.team` 조작 (path 불일치) | L4 |
| 4 | LLM이 CLAUDE.md 무시 | L5 |
| 5 | 메타 파일 편집 시도 | L5 |
| 6 | SCOPE 외 편집 | L5 |
| 7 | hook 우회 (--no-hooks) | L6 |
| 8 | main 직접 push | L6 (branch protection) |
| 9 | 의존성 위반 PR 머지 | L6 (CI) |

## 결과

정확성 6/6 + 엄격성 6/6 + 진입점 0회.
