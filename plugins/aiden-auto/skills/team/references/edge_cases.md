# /team — Edge Cases

## E1. Phase 2 rebase conflict

**상황**: 내 local main 이 origin/main 과 conflict.

**대응**:
1. `git rebase --abort`
2. 출력:
   ```
   ❌ Phase 2 conflict: origin/main 과 local 충돌
   충돌 파일:
   - path/to/file
   해결 후 `/team "<task>"` 재호출
   ```
3. exit. 이후 Phase 진행하지 않음.

## E2. Phase 4 /auto 실패

**상황**: `/auto` 내부에서 exception or exit 1.

**대응**:
1. `git stash push --include-untracked`
2. (team 세션) `git checkout main && git branch -D <work-branch>`
3. (Conductor) `git reset --hard HEAD`
4. 출력: "Phase 4 /auto 실패 — 원상복구 완료. 로그 참조"
5. exit.

## E3. Phase 5 drift 회귀

**상황**: 예상치 못한 D1/D2/D3 증가 또는 D4 감소.

**대응**:
1. 회귀 상세 출력:
   ```
   ⚠ drift 회귀 감지
   - api: D3 0 → 3 (+3)
     • POST /api/v1/new-endpoint  (code-only)
   ```
2. user confirm:
   - `proceed`: Phase 6 진행
   - `rollback`: Phase 4 의 stash/branch 롤백

## E4. Phase 5 test/analyze error

**상황**: pytest collect error 또는 dart analyze error.

**대응**:
1. 에러 상세 출력
2. **강제 block** (user confirm 없이 진행 금지)
3. 사용자에게 "error 수정 후 `/team` 재호출" 안내
4. 현재 변경은 work 브랜치에 유지 (잃지 않음)

## E5. Phase 7 rebase conflict

**상황**: work → main rebase 중 conflict (Phase 2 이후 origin 변경).

**대응**:
1. `git rebase --abort`
2. work 브랜치로 복귀
3. user confirm:
   - `resolve`: 수동 rebase 후 user 가 `/team` 재호출 (이어서 merge+push)
   - `abort`: work 브랜치 삭제 + main 복귀

## E6. Phase 7 push rejected (race)

**상황**: 다른 세션이 먼저 push → origin/main 이 또 ahead.

**대응**:
1. `fetch + rebase + ff-merge + push` 재시도
2. 최대 3회 retry
3. 모두 실패 시:
   - 로컬 commit 유지
   - 출력: "push 3회 실패. 로컬 커밋은 유지됨. 수동 `git push origin main` 필요"
   - exit

## E7. cwd 가 EBS 레포 아님

**상황**: 사용자가 다른 프로젝트에서 `/team` 호출.

**대응**:
- `team_detect.py` 가 `git remote -v` 에서 "ebs" 미발견 시 exit
- 출력: "❌ /team 은 EBS 레포 전용. `cd C:/claude/ebs` 먼저"

## E8. cwd 가 정확히 어느 팀인지 불명

**상황**: `cd team1-frontend/lib/features/` 같은 깊은 path.

**대응**: `team_detect.py` 가 cwd 상위로 올라가며 `team{N}-*` 패턴 매칭. 찾으면 TEAM_ID 확정.

## E9. 여러 팀 폴더 동시 접근

**상황**: 사용자가 `ebs/team1-frontend` 에서 `team2-backend/` 파일 수정.

**대응**: Phase 5 scope_check 가 staged 파일 분석.
- team1 owned: `team1-frontend/*`, `docs/.../2.1 Frontend/*`
- team2 files 발견 → warning + `notify: team2` commit 태그

차단 아님 (v7 free_write).

## E10. Prelude WIP commit 필요 (Phase 1)

**상황**: `/team` 호출 시 이미 미커밋 변경 존재.

**대응**:
1. `git add -A`
2. `git commit -m "wip(<team_id>): prelude before /team"`
3. 사용자에게 "Prelude WIP 커밋 생성됨" 알림
4. Phase 2 진행

## E11. baseline 파일 stale (24h+)

**상황**: 세션 오래 쉰 후 `/team` 호출. baseline.timestamp 가 24h+ 이전.

**대응**: baseline 재생성. "baseline 재생성됨 (이전: <old-ts>)" 알림.

## E12. `/team` 없이 args

**상황**: 사용자가 `/team` 만 호출 (task 없음).

**대응**: status 모드
1. `team_detect.py` 실행 (팀 ID, 브랜치)
2. `team_observe.py` 실행 (다른 세션)
3. drift/audit 현재 수치
4. staged/unstaged 파일
5. 다음 `/team "<task>"` 제안

작업 실행 없음.

## E13. `/team` 재진입 (동일 세션 반복 호출)

**상황**: 사용자가 `/team "task1"` 완료 후 `/team "task2"` 즉시 호출.

**대응**: 각 호출이 독립 트랜잭션.
- Phase 1: 새 baseline 생성 (직전 `/team` 의 결과가 새 baseline)
- Phase 3: 새 work 브랜치 (timestamp 다름)
- 정상 8 Phase 반복

## E14. Conductor 세션에서 `/team`

**상황**: cwd = `C:/claude/ebs/` (Conductor).

**대응**: Conductor mode
- Phase 3: 브랜치 생성 안 함 (main 유지)
- Phase 6: main 에 직접 commit
- Phase 7: `git push origin main` (rebase loop 없음)
- scope guard: Conductor 는 모든 경로 소유 (`docs/1.`, `docs/2.5`, `docs/4.`, `tools/`, `.claude/` 등)

## E15. Subagent 내부에서 `/team` 호출

**상황**: 다른 스킬이 subagent 로 `/team` 호출.

**대응**: 허용. subagent 도 독립 세션. 단 subagent 가 중첩 `/team` 호출하지 않도록 guard (환경변수 `EBS_TEAM_RUNNING=1` 체크).
