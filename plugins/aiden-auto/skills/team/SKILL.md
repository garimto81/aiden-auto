---
name: team
description: DEPRECATED v4.0 user-global shim — EBS 레포 내부에서는 project-local `.claude/skills/team/` (v5.1) 이 자동 override. EBS 레포 밖에서 /team 호출은 no-op. 2026-04-22 rename.
---

# /team — DEPRECATED (v4.0 user-global shim)

> **이 user-global 스킬은 2026-04-22 부로 deprecated 이다.** 이번 사건 근거: project-local v5.1 skill(`team-v5`)과 이 user-global v4.0 스킬이 공존하면서 호출자(LLM/사용자)가 관성으로 `/team` 을 입력할 때 v4.0 이 로드되어 shared HEAD 오염 사건 재발 (2026-04-22 Conductor 세션 데이터 손실 실증).

## 지금 무엇을 해야 하나

### EBS 레포 (`C:/claude/ebs/`) 내부에서 `/team` 을 호출한 경우

→ **자동으로 project-local `.claude/skills/team/` (v5.1) 이 override 하여 로드된다.** 이 shim 은 실행되지 않는다. v5.1 4 Phase (Claim → Work → PR → Sync) 을 따른다.

정책: `docs/4. Operations/Multi_Session_Workflow.md` (v5.1).

### EBS 레포 밖에서 `/team` 을 호출한 경우

이 shim 은 **no-op** 이다. v4.0 10 Phase 워크플로우는 더 이상 동작하지 않는다.

v4.0 이 필요하다고 믿는다면, 재고하라. v4.0 의 결함:

- subdir 세션 (`C:/claude/ebs/team{N}-*/`) 허용 → **shared HEAD 오염**. sibling worktree 강제 없음.
- `session_branch_init` manifest/conflict-scan/revise/safety-gate 복잡도 → 실제 race 못 막음.
- Conductor 직접 `git push origin main` 특권 → 4 팀 일관성 깨짐.
- `Phase 1 team_detect.py` 가 "순간값 HEAD" 의존 → race window 내재.

### project-local v5.1 이 누락된 경우 (복구)

```bash
cd C:/claude/ebs
git status .claude/skills/team/         # 유실되었는지 확인
git restore .claude/skills/team/        # 복구
# 또는 (worktree 초기 세팅 필요 시)
python tools/setup_team_worktrees.py --team all
```

## v4.0 스크립트 잔존 (호환)

다음 파일들은 본 shim 교체 이후에도 유지된다. 2026-05-05 까지 호환성 목적:

- `~/.claude/skills/team/scripts/team_declare.py`
- `~/.claude/skills/team/scripts/team_conflict_scan.py`
- `~/.claude/skills/team/scripts/team_plan_revise.py`
- `~/.claude/skills/team/scripts/team_safety_gate.py`
- `~/.claude/skills/team/scripts/team_detect.py`
- `~/.claude/skills/team/scripts/team_observe.py`
- `~/.claude/skills/team/scripts/team_verify.py`
- `~/.claude/skills/team/scripts/team_commit_msg.py`
- `~/.claude/skills/team/scripts/team_merge_loop.py`
- `~/.claude/skills/team/scripts/team_cleanup.py`
- `~/.claude/skills/team/scripts/*` (기타)

직접 `python ...` 호출은 여전히 가능하다. 그러나 `/team` 슬래시 명령 자체는 이 shim 만 로드한다.

2026-05-05 이후 스크립트도 제거 예정.

## 버전 표기 규칙

- **Skill 식별자** (폴더명/호출명) = `team` — major 버전 경계(v4→v5)에서만 변경
- **정책 버전** = `v5.1` — minor 업데이트(v5.0→v5.1)는 문서 내용만 갱신
- 두 값은 독립적. 혼동 시 `docs/4. Operations/Multi_Session_Workflow.md` 의 헤더 참조

## 근거

- `docs/4. Operations/Multi_Session_Workflow.md` §금지 L244 — "v4.0 user-global 스킬 직접 호출 금지"
- `docs/4. Operations/V5_Migration_Plan.md` D8-10 — deprecation shim 교체 계획
- `docs/2. Development/2.5 Shared/team-policy.json` `deprecated_tools` — v4.0 scripts 2026-05-05 제거 예정
- 2026-04-22 Conductor 세션 데이터 손실 사건 (commit `61e27b4` 복구) — 실증 증거

## 마이그레이션 경로

v4.0 에서 v5.1 으로:

| v4.0 | v5.1 |
|------|------|
| 10 Phase (Declare/Conflict-Scan/Revise/Safety-Gate/Detect/Sync/Branch/Execute/Verify/Commit/Merge/Report) | 4 Phase (Claim/Work/PR/Sync) |
| subdir 허용 | **sibling worktree 강제** (`C:/claude/ebs-team{N}-work/`) |
| main 직접 push | GitHub PR + auto-merge workflow |
| Conductor 특권 | Conductor 도 PR (uniform) |
| Manifest 기반 coordination | **Active_Work.md SSOT + `tools/active_work_claim.py`** |

---

**이 shim 은 단일 목적**: v4.0 경로를 닫고, LLM/사용자를 project-local v5.1 로 유도하거나 EBS 밖에서는 침묵하도록 한다.
