# /team — 8 Phase 상세

## Phase 1: Context Detect

### 탐지 규칙

```python
# team_detect.py
cwd = Path.cwd()
# 1. EBS 레포 판별: git remote 에서 "ebs" 포함
# 2. team_id 판별: cwd 가 team{N}-* 하위 or sibling dir ebs-team{N}-*
# 3. Conductor: cwd == repo root (team 접두 없음)
```

### uncommitted 처리

```bash
if git status --porcelain | non-empty:
    git add -A
    git commit -m "wip(<team_id>): prelude before /team"
```

### baseline 생성/로드

```
~/.claude/skills/team/state/baseline_<team>_<date>.json
{
  "drift": {"api": {...}, "events": {...}, ...},
  "audit": {"pass": 74, "unknown": 15, "fail": 1, "na": 3},
  "last_sync_sha": "<origin/main HEAD>",
  "timestamp": "2026-04-21T14:30:00Z"
}
```

24h 이상 된 baseline 은 stale 경고 + 재생성.

## Phase 2: Pre-Sync

### fetch + observe

```bash
git fetch origin
git log origin/main --since="<baseline.timestamp>" --format="%h %s (%ar) <%an>"
```

### 다른 세션 filter

- 내 team 커밋 제외
- `wip()` 커밋은 회색으로 표시
- `feat/fix` 만 ✓, 나머지 ✗

### active-edits 조회

```bash
git show meta/active-edits:active.json 2>/dev/null
# {"team1": {"files": ["src/features/lobby/*"], "claimed_at": "..."}}
```

### rebase

```bash
if local/main behind origin/main:
    git pull --rebase origin main
    if conflict: HALT
```

## Phase 3: Branch Prep

### Team 세션

```bash
TS=$(date +%Y%m%d-%H%M%S)
BRANCH="work/${TEAM_ID}/_team-${TS}"
git checkout -b ${BRANCH}
```

이 브랜치는 수명 `/team` 1회 한정. Phase 7 후 `git branch -D` 로 삭제.

### Conductor 세션

main 유지. 브랜치 생성하지 않음. Phase 7 에서 main 에 직접 commit + push.

## Phase 4: Execute

`Skill("auto", args="<task>")` 위임.

`/auto` 의 모든 내부 워크플로우 (PDCA, subagent 배치 등) 를 그대로 사용.

예외 처리:
- `/auto` 가 exit 1 or exception → Phase 7 이전에 rollback 수행
- rollback: `git reset --hard HEAD` + work 브랜치 삭제 + main 복귀

## Phase 5: Verify

### drift scan

```bash
python tools/spec_drift_check.py --all --format=json > /tmp/drift_current.json
```

baseline 과 diff. 각 contract 별:
- D1/D2/D3 증가 → regression
- D4 감소 → regression

회귀 있으면 **warning + user confirm**. 사용자가 `proceed` 또는 `rollback` 선택.

### pytest (team2)

```bash
python -m pytest ${REPO}/team2-backend/tests/ --co -q --rootdir=${REPO}/team2-backend
```

Exit 0 아니면 error. Phase 6 진행 전 block.

### dart analyze (team1/3/4)

```bash
# team3
dart analyze ${REPO}/team3-engine/ebs_game_engine
# team1
dart analyze ${REPO}/team1-frontend
# team4
dart analyze ${REPO}/team4-cc/src
```

0 errors 필수. infos/warnings 무시.

### scope guard

```python
# team_verify.py scope_check
team_owned = {
    "team1": ["team1-frontend/", "docs/2. Development/2.1 Frontend/"],
    "team2": ["team2-backend/", "docs/2. Development/2.2 Backend/"],
    "team3": ["team3-engine/", "docs/2. Development/2.3 Game Engine/"],
    "team4": ["team4-cc/", "docs/2. Development/2.4 Command Center/"],
}
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"]).splitlines()
other_team_paths = [p for p in staged if not any(p.startswith(o) for o in team_owned[TEAM_ID])]
if other_team_paths:
    # v7 free_write 하 허용 — warning + notify 태그
    notify = determine_owner(other_team_paths)
    return {"notify": notify}
```

## Phase 6: Auto Commit

### Conventional 접두사 inference

`team_commit_msg.py`:
```python
task = sys.argv[1].lower()
if any(w in task for w in ["추가", "신규", "구현", "add", "implement"]):
    prefix = "feat"
elif any(w in task for w in ["수정", "fix", "버그", "오류"]):
    prefix = "fix"
elif any(w in task for w in ["문서", "doc"]):
    prefix = "docs"
elif any(w in task for w in ["리팩", "refactor", "정리"]):
    prefix = "refactor"
else:
    prefix = "chore"

msg = f"{prefix}({team_id}): {task[:80]}"
```

### commit 실행

```bash
git add <staged>  # scope_check 통과한 파일만
git commit -m "$(cat <<'EOF'
<generated-msg>

<optional: notify: team{M}>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Phase 7: Merge to main + Push

### Team 세션 merge loop

`team_merge_loop.py`:
```python
for attempt in range(3):
    subprocess.run(["git", "fetch", "origin"])
    subprocess.run(["git", "checkout", "main"])
    subprocess.run(["git", "pull", "--rebase", "origin", "main"])

    # work → main rebase
    subprocess.run(["git", "checkout", BRANCH])
    r = subprocess.run(["git", "rebase", "main"])
    if r.returncode != 0:
        subprocess.run(["git", "rebase", "--abort"])
        # rollback: work 브랜치 유지, user pause
        print("CONFLICT in rebase. resolve manually or re-run /team")
        sys.exit(2)

    # ff-merge
    subprocess.run(["git", "checkout", "main"])
    subprocess.run(["git", "merge", "--ff-only", BRANCH])

    # push
    r = subprocess.run(["git", "push", "origin", "main"])
    if r.returncode == 0:
        # cleanup
        subprocess.run(["git", "branch", "-D", BRANCH])
        break
    else:
        print(f"push rejected (attempt {attempt+1}/3). retrying...")
else:
    print("push failed after 3 attempts. local commit retained.")
```

### Conductor 세션

```python
# 이미 main 에서 commit 완료 (Phase 6)
subprocess.run(["git", "push", "origin", "main"])
# reject 시 retry 3회
```

## Phase 8: Report

### 데이터 수집

- Phase 6 커밋 SHA
- `git diff HEAD~1 --stat`
- Phase 5 drift delta
- audit delta (Phase 5 시 캡처)
- Phase 2/7 에서 본 다른 세션 활동

### 출력 예시

```markdown
## /team 완료 — team3 (3분 12초)

**Commit**: `abc1234` feat(team3): Clock FSM running/paused 전이
**Pushed**: origin/main (now at abc1234)

### 변경 (3 files, +47 −12)
- team3-engine/ebs_game_engine/lib/core/rules/clock_fsm.dart
- team3-engine/ebs_game_engine/test/clock_fsm_test.dart
- docs/2. Development/2.3 Game Engine/Behavioral_Specs/Clock.md

### drift 변화
- fsm: D4 23 → 23 (유지)
- 기타 회귀 없음

### audit 변화
- PASS 74 → 74 (유지)

### 다른 세션 활동 (3분간)
- team2 f5a3b2c feat(team2): settings_kv DB session (2 min ago)

### Tip
다음 `/team` 전까지 sync 완료. 다른 세션이 변경한 main 변동은 다음 `/team` Phase 2 에서 자동 반영.
```
