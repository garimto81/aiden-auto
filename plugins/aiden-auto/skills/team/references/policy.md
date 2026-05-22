# /team — 정책 근거

## 기존 정책 (Multi_Session_Workflow.md v2.0, 2026-04-20)

- Conductor=main 직접, 팀=`work/team{N}/*`
- 팀 세션 → Conductor 세션에서 `/team-merge` 로만 main 병합
- work 브랜치 수명: 세션 전체

## /team 도입 후 (v3.0, 2026-04-21)

### 1. 팀이 main 직접 ff-merge + push

**변경**: 팀 세션도 main 에 직접 commit + merge 가능 (`/team` Phase 7).

**근거**:
- 사용자 요구: "항상 동기화 유지"
- ff-merge + linear history 유지되면 실질적으로 main 직접 작업과 동일
- work 브랜치는 branch_guard hook 호환 layer 로 수명 유지

**제약**:
- `git merge --ff-only` 만 허용 (merge commit 금지)
- conflict 발생 시 자동 중단 + user confirm
- scope guard 가 팀 소유 외 경로 수정 시 notify 태그 강제

### 2. work 브랜치 초단기 수명

**변경**: `work/team{N}/_team-<timestamp>` 는 `/team` 1회 내 생성·사용·삭제.

**근거**:
- 브랜치는 commit grouping 도구일 뿐, isolation 수단 아님
- 수명 길면 merge 시점에 대량 충돌
- ff-merge 후 브랜치 보존 가치 없음

**수명 플로우**:
```
Phase 3: 생성
Phase 4-6: 작업 + commit
Phase 7: main 에 ff-merge → git branch -D
```

### 3. 매 작업 자동 commit + merge + push

**변경**: `/team` 1회 호출 = 1 commit + 1 main push.

**근거**:
- 작업 덩어리 세분화 → 다른 세션이 수 분 내 인지
- 큰 PR 없음 → 머지 충돌 최소화
- 세션 종료 개념 불필요

### 4. Conflict 시 Pause + user confirm

**자동화 한계선**.

- Phase 2 rebase conflict: 즉시 중단
- Phase 7 rebase/ff conflict: rollback + pause
- 3번 push retry 실패: 로컬 commit 유지, 수동 해결 안내

## /team-merge 스킬 관계

기존 `/team-merge` (`tools/team_merge.py`) 는 폐기하지 않고 **backup** 으로 유지:

- `/team` 이 정상 경로
- Conductor 가 여러 팀 브랜치를 일괄 병합할 때 `/team-merge` 사용
- 긴급 상황 (예: `/team` 스킬 자체 버그) 시 `/team-merge` 로 수동 복구

## 거버넌스 v7 호환

- `free_write_with_decision_owner` 모델 유지
- 팀이 다른 팀 경로 수정 시 notify 태그 (commit 메시지)
- 차단 아닌 경고 + 기록

## Subdir vs Worktree 지원

기존 hybrid 모델 유지:

- **Subdir**: `C:/claude/ebs/team{N}-*/` → `team_detect.py` 가 자동 인식
- **Worktree**: `C:/claude/ebs-team{N}-<slug>/` → 동일하게 인식

`/team` 은 둘 다 지원. 차이 없음.

## 변경 영향 범위

| 기존 자산 | 영향 |
|----------|------|
| `.claude/hooks/branch_guard.py` | 그대로 유지 (work 브랜치 생성은 여전히 팀 세션용) |
| `.claude/hooks/pre_push_drift_check.py` | 그대로 유지 (/team Phase 7 에서 실행) |
| `/team-merge` | 유지 (backup) |
| `Multi_Session_Workflow.md` | v2.0 → v3.0 (§"팀 main 직접 merge" 추가) |
| `Multi_Session_Handoff.md` | `/team "<task>"` 권장 명령 추가 |
| 각 팀 `CLAUDE.md` | `/team` 사용 섹션 추가 |

## 위험 수용

1. **팀이 main 을 직접 push → 다른 세션과 race**
   - push rejected 시 3회 retry. 그래도 실패 시 수동 resolve
   - 빈도: 낮음 (ff-merge + rebase 우선)

2. **`/team` 내부 /auto 실패 시 부분 상태**
   - rollback 로직 필수 (stash + branch 삭제)

3. **Scope guard 우회**
   - v7 free_write 원칙상 차단 없음. notify 만 경고
   - 악의적 우회는 PR review (향후 CI 도입 시)

## Changelog

| 날짜 | 버전 | 변경 |
|------|------|------|
| 2026-04-21 | v3.0 | `/team` 스킬 도입. 팀 main 직접 ff-merge 허용, work 브랜치 초단기 수명, 자동 commit+merge+push |
| 2026-04-20 | v2.0 | MVI — Conductor Stop hook, branch_guard 확장, fs lock, FIFO merge queue |
| 2026-04-15 | v1.0 | Worktree 기반 정식화 |
