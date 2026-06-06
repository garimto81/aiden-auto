---
name: commit
description: Conventional Commit 형식으로 git 커밋 생성 + push + 배포(deploy)까지 한 번에 처리하는 원클릭 프로젝트 업데이트 커맨드. 기본 풀 체인 = commit → push → (기능 브랜치면 PR) → 프로젝트 자동 감지 배포(framework sync / Vercel / npm deploy / 배포 스크립트). production 등 비가역 배포는 1회 확인. --no-deploy/--no-push 로 단계 생략, --pr/--ship 으로 PR·머지 제어. 결정 지점에서는 Claude가 단일 추천안을 먼저 제시.
version: 3.2.0
triggers:
  keywords:
    - "commit"
    - "커밋"
    - "git commit"
    - "/commit"
---

# /commit - Conventional Commit & Push (+ PR/Merge Chain)

## ⚠️ 필수 실행 규칙 (CRITICAL)

**이 스킬이 활성화되면 반드시 아래 워크플로우를 실행하세요!**

## 풀 체인 개요 — "한 번 쓰면 끝까지 업데이트"

기본 `/commit`은 커밋 한 줄 만드는 게 아니라, **그 프로젝트를 외부까지 끝까지 올리는 원클릭 업데이트**입니다. 브랜치 맥락에 맞춰 자동으로 단계가 결정됩니다.

```
   /commit  (옵션 없음)
       │
       ▼
   ① commit   ── Conventional Commit 메시지 자동 생성
       │
       ▼
   ② push     ── 현재 브랜치를 remote로 (Step 5)
       │
       ▼
   ③ PR       ── 기능 브랜치일 때만 자동 생성 (머지는 --ship일 때만)
       │        main/master면 건너뜀
       ▼
   ④ deploy   ── 프로젝트 종류 자동 감지 후 배포 (Step 9)
                 preview는 자동 / production 등 비가역은 1회 확인
```

| 브랜치 | 자동으로 도는 단계 |
|--------|-------------------|
| **기능 브랜치** (feat/…) | commit → push → PR 생성 → deploy(preview) |
| **main / master** | commit → push → deploy |

> 단계를 빼고 싶을 때만 플래그: `--no-push`(push 생략), `--no-deploy`(배포 생략), `--ship`(PR 머지까지). 자세한 건 하단 "옵션" 표 참고.

## Decision Protocol (Propose-then-Execute)

워크플로우 중 판단이 필요한 지점(스테이징 그룹화, diverged push, --ship 조건 실패 등)에서는 **A/B/C 선택지를 나열하며 사용자에게 떠넘기지 않는다**. 대신 Claude가 먼저 판단하여 단일 추천안을 제시한다.

### 판단 3요소

| # | 요소 | 데이터 소스 |
|:-:|------|-------------|
| 1 | **리스크 vs 편익** | 되돌릴 수 있는가? 블래스트 반경은? 같은 결과를 더 안전하게 얻을 수 있는가? |
| 2 | **프로젝트 안전 규칙** | `CLAUDE.md`, `.claude/rules/*.md` — force push 금지, main 직접 수정 경로 제한 등 |
| 3 | **메모리 기록** | `~/.claude/projects/.../memory/MEMORY.md` — 기지 이슈 (예: Windows 절대경로 오염 → rebase 차단) |

### 출력 형식 (MANDATORY)

```
═══ 결정 제안 ═══
상황: [1줄 요약 — 왜 판단이 필요한가]
추천: [단일 최적안 — "A안 실행"]
근거:
  - 리스크: [블래스트 반경 / 되돌림 비용]
  - 규칙: [적용되는 CLAUDE.md / rules 항목]
  - 기록: [관련 MEMORY 엔트리 또는 "해당 없음"]
대안: [차선책 1개만 간략히 — "선택 시 ~~ 이유로 비권장"]
진행: [실행 커맨드 또는 "승인 요청"]
═════════════════
```

### 실행 분기

| 추천안 성격 | Claude 동작 |
|-------------|-------------|
| **비파괴 + 되돌림 가능** (예: 로컬 커밋, PR 생성) | 제안 직후 **즉시 실행**. 사용자는 결과만 확인 |
| **파괴적·비가역적** (force push, `--admin` merge, drop commits) | 제안 후 **AskUserQuestion tool 의무 사용** (가르침 #6, 2026-05-29). 명시적 승인 대기 (`y/N` chat text 금지). Iron Law 준수 |
| **외부 시스템 영향** (다른 브랜치 변경, 공개 PR 머지) | 제안 후 **AskUserQuestion tool 의무 사용**. 승인 대기 |

### 파괴적 결정의 AskUserQuestion 호출 표준 (가르침 #6 정합)

```
   AskUserQuestion
   ├─ question: "{action} 실행할까요? 영향: {blast radius}"
   ├─ header: 짧은 라벨 (예: "Force push", "Admin merge")
   ├─ multiSelect: false
   └─ options:
       ├─ "예, 실행" — description: 결과 명시 + 되돌림 비용
       ├─ "아니오, 보류" — description: 다른 대안 + 진행 권고
       └─ (선택) "다른 방법 추천" — description: 대안 1 안내
```

### 금지

- ❌ 2개 이상 선택지를 동등하게 나열하며 "어떻게 할까요?"
- ❌ 추천 없이 "사용자 판단 필요" 로 종료
- ❌ 파괴적 동작을 승인 없이 "추천에 따라" 즉시 실행
- ❌ **파괴적 결정 chat text 승인 요청** (`y/N` 자유 텍스트) — AskUserQuestion 의무 (가르침 #6, 2026-05-29)

### Step 1: 상태 확인 (병렬 실행)

```bash
# 동시에 실행
git status                    # unstaged/untracked 파일 확인
git diff --stat              # 변경 통계
git log --oneline -5         # 최근 커밋 스타일 확인
```

### Step 2: 스테이징 (Propose-then-Execute)

**staged 변경사항이 없을 때**: 사용자에게 "무엇을 커밋할까요?" 질문 금지. 대신 Claude가:

1. `git status` + `git diff --stat` 결과를 기반으로 변경 파일을 **의미 단위로 그룹화** (예: 같은 기능, 같은 모듈, 문서/코드 분리)
2. 민감 파일(`.env`, credentials), 자동 생성물(`*.lock`, snapshot) 감지 시 **제외 후보** 로 분류
3. **추천 커밋 구조** 를 "Decision Protocol" 형식으로 제시:

```
═══ 결정 제안 ═══
상황: unstaged 변경 {N}개 파일 + untracked {M}개
추천: 커밋 {K}개로 분리 (그룹별 근거 포함)
  - C1: feat(scope): ... → {files}
  - C2: chore(scope): ... → {files}
  - 제외: {snapshot/lock/secrets} → 이유 명시
근거:
  - 리스크: 로컬 커밋 — 되돌림 가능 (git reset)
  - 규칙: Conventional Commit, 섹션별 scope 분리
  - 기록: [해당 없음 또는 관련 MEMORY]
진행: 즉시 스테이징 + 커밋 (비파괴 동작)
═════════════════
```

4. 추천 구조가 합리적이면 **즉시 실행** (로컬 커밋은 되돌림 가능하므로). 사용자는 결과만 확인.
5. 파일 성격이 애매할 때(예: 비밀번호 같아 보이는 `.yaml`)만 예외적으로 승인 대기.

### Step 3: 커밋 메시지 생성

**Conventional Commit 형식:**

```
<type>(<scope>): <subject> <emoji>

<body>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**타입:**

| Type | 설명 | Emoji |
|------|------|-------|
| feat | 새 기능 | ✨ |
| fix | 버그 수정 | 🐛 |
| docs | 문서 | 📝 |
| refactor | 리팩토링 | ♻️ |
| test | 테스트 | ✅ |
| chore | 유지보수 | 🔧 |
| perf | 성능 개선 | ⚡ |
| style | 포맷팅 | 💄 |

### Step 4: 커밋 실행

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject> <emoji>

<body>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### Step 5: Push (--no-push 없는 경우)

기본 경로는 `git push origin <current-branch>` — 새 브랜치는 `-u` 추가. 정상 fast-forward는 제안 없이 즉시 실행.

**Reject 발생 시 (non-fast-forward, diverged 등)**: 사용자에게 "어떻게 할까요?" 금지. "Decision Protocol" 원칙 적용:

1. `git log origin/<br>..HEAD` + `git log HEAD..origin/<br>` 로 양방향 diverge 분석
2. 원인 분류:

| 패턴 | 추천 |
|------|------|
| 단순 신규 remote 커밋 (충돌 없음) | `git pull --rebase` → 재push. 비파괴 → **즉시 실행** |
| 충돌 예상 (파일 겹침) + main 아님 | `git pull --rebase`, 충돌 나면 해당 시점에 재판단 |
| 충돌 예상 + main 브랜치 + MEMORY에 관련 이슈 기록 | PR 분리 전략 추천 (기능 브랜치로 cherry-pick 후 push) |
| 단순 로컬 앞섬 (reject 외 사유) | 원인 분석 후 개별 추천 |

3. 추천안을 Decision Protocol 형식으로 제시하고, 비파괴면 즉시 실행 / 파괴적(force push 등)이면 승인 대기.

**force push 관련**: `main`/`master` 대상 force push는 근본적으로 금지(CLAUDE.md 안전 규칙). 다른 브랜치에 대한 force push는 추천 가능하지만 실행 전 승인 필수.

### Step 6: 결과 출력

```
✅ Committed and pushed: feat(auth): 로그인 기능 추가 ✨
   Branch: feat/login
   Remote: https://github.com/user/repo/commit/abc1234
```

### Step 7: PR 체인

기본 `/commit` 풀 체인에서 **현재 브랜치가 기능 브랜치면 PR을 자동 생성**합니다(머지는 하지 않음 — PR 생성은 되돌릴 수 있는 비파괴 동작). `main`/`master`면 PR 단계를 건너뜁니다. 머지까지 원하면 `--ship`을 명시합니다.

| 옵션 | 동작 | 안전도 |
|------|------|:------:|
| `/commit` (기능 브랜치) | commit + push + **PR 자동 생성** + deploy | 안전 (PR은 reversible) |
| `/commit` (main/master) | commit + push + deploy | 안전 (기본) |
| `/commit --ship` | commit + push + PR 생성 + 자동 머지 + deploy | 조건부 자동 |
| `/commit --ship --force` | 조건 무시 강제 머지 | ⚠️ 위험 |

**판단 로직 (`--pr` / `--ship` 공통):**

```
Step A: 브랜치 체크
  ├─ main/master → ❌ 차단 ("기능 브랜치에서만 PR 가능")
  └─ feature 브랜치 → 진행

Step B: 기존 PR 존재 여부
  └─ gh pr view --json number,state,url 2>/dev/null
     ├─ 있음 (OPEN) → 재사용 (PR 번호 기록)
     └─ 없음 → 새로 생성 (아래 Step C)

Step C: PR 생성 (PR 없을 때만)
  └─ gh pr create --title "{커밋 subject}" --body "{Auto-generated}"
     - 제목: 방금 생성한 커밋 subject 재사용
     - 본문: Summary(커밋 목록) + Test Plan + Related(PRD 참조)

Step D: --ship 인 경우에만 머지 시도
  └─ .claude/config/pr-merge.yaml 조건 검증:
     1. CI 통과 (gh pr checks) 
     2. 충돌 없음 (gh pr view --json mergeable)
     3. block_merge 라벨 없음 (wip, do-not-merge 등)
     ├─ 전부 통과 → gh pr merge --squash --delete-branch
     └─ 하나라도 실패 → Decision Protocol 적용 (아래 표)
```

**--ship 조건 실패 시 추천안**: 사유에 따라 Claude가 단일 대안 제시 (사용자에게 "뭐 할까요" 금지):

| 실패 사유 | 추천안 | 실행 방식 |
|-----------|--------|-----------|
| CI 실패 (flaky 의심, 재실행 시 복구 예상) | `gh pr checks <N> --watch` 로 재확인 후 통과 시 merge | 비파괴 → 즉시 실행 |
| CI 실패 (실제 코드 결함) | 머지 보류 + 실패 로그 요약 + 수정 지점 식별 제안 | PR만 남김 |
| 충돌 (mergeable=CONFLICTING) | `gh pr view` 로 충돌 파일 조사 → 간단 충돌이면 로컬 rebase 시도 추천 | 승인 대기 (rebase는 비파괴지만 문맥 확인 필요) |
| `wip`/`do-not-merge` 라벨 | 머지 보류. 라벨 부착 의도 존중 | PR만 남김 |
| 필수 리뷰어 미승인 | 머지 보류 + 알림 링크만 제공 | PR만 남김 |

**--ship --force 처리 (destructive):**
- 조건 검증을 건너뛰고 바로 머지
- Lead는 반드시 `AskUserQuestion`으로 1회 명시 확인 후 진행
- 예외: 사용자 요청에 `--force-confirm` 명시돼 있으면 스킵

**구현 명령어:**

```bash
# --pr
gh pr create --title "$(git log -1 --pretty=%s)" --body "$(cat <<'EOF'
## Summary
{최근 커밋 메시지 body}

## Test Plan
- [ ] Manual verification
- [ ] CI 통과 확인

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# --ship (조건 통과 시)
gh pr merge --squash --delete-branch

# --ship --force (사용자 명시 승인 후)
gh pr merge --squash --delete-branch --admin
```

### Step 8: 결과 출력 확장

```
✅ Committed and pushed: feat(auth): 로그인 기능 추가 ✨
   Branch: feat/login
   Remote: https://github.com/user/repo/commit/abc1234

🔗 PR: #42 생성됨 (https://github.com/user/repo/pull/42)   # --pr 또는 --ship
✅ Merged: squash → main, feat/login 삭제됨                 # --ship 성공
⏸  Merge 보류: CI 실패 (2/5 check failed)                   # --ship 조건 미달
```

### Step 9: Deploy (기본 자동, `--no-deploy`로 생략)

push(및 PR/머지)가 끝나면 **프로젝트 종류를 자동 감지해서 배포**합니다. 위에서부터 순서대로 검사하여 **첫 번째로 매치되는 한 가지** 배포 경로를 실행합니다. 모든 검사는 현재 작업 디렉토리(repo 루트) 기준입니다.

**배포 대상 자동 감지 (우선순위 순):**

| # | 감지 조건 | 배포 동작 | 안전도 |
|:-:|----------|----------|:------:|
| 1 | repo 루트가 framework 정본(`~/.claude/`) 또는 그 프로젝트 미러(`.claude/`가 핵심 자산)인 경우 | framework는 SessionEnd 시 `framework_github_sync.py`가 자동 배포됨 → **즉시 배포 원하면** 해당 스크립트 1회 실행, 아니면 "세션 종료 시 자동 배포" 안내 | 안전 (sync는 idempotent) |
| 2 | `vercel.json` 또는 `.vercel/` 존재 | `vercel:deploy` 스킬 호출 → **preview 배포** (production 아님) | 안전 (preview) |
| 3 | `package.json`의 `scripts`에 `deploy` 존재 | 감지된 패키지 매니저로 `<pm> run deploy` (lockfile로 npm/pnpm/yarn 판별) | 프로젝트 정의 따름 |
| 4 | `deploy.sh` / `scripts/deploy.*` / `Makefile`에 `deploy` 타깃 | 해당 스크립트/타깃 실행 (실행 명령 1줄 보고 후 진행) | 프로젝트 정의 따름 |
| 5 | 위 어느 것도 없음 | 배포 생략 — "이 프로젝트의 배포 방식을 못 찾아 배포는 건너뜀" 안내 (**에러 아님**) | — |

**production(실서비스) 배포 안전장치 (CRITICAL):**

자동 감지된 배포가 **production / 실서비스 대상**이면 (예: `vercel:deploy prod`, `deploy --production`, prod 환경 변수) — 이는 *외부 시스템 영향 + 비가역* 동작이므로 Decision Protocol에 따라 **자동 실행하지 않고 `AskUserQuestion`으로 1회 확인**합니다. 사용자가 "항상 자동 풀 체인"을 선택했더라도, 기본 자동 경로는 **preview/staging**으로 가고 production은 명시 확인 또는 `--prod` 플래그를 요구합니다. 이렇게 해야 "사소한 커밋이 실서비스로 나가는" 사고를 막습니다.

```
   배포 대상 = production?
        │
        ├─ 아니오 (preview/staging/framework sync) → 즉시 배포 (비파괴/되돌림 가능)
        │
        └─ 예 → AskUserQuestion 1회 확인
                 ├─ "예, production 배포" → 실행
                 └─ "아니오, preview만" → preview로 강등 실행
```

**배포 실패 시:** 커밋·push는 이미 성공했으므로 되돌리지 않습니다. 배포 단계 실패만 분리 보고하고, Decision Protocol로 재시도/원인 요약 중 단일 추천안을 제시합니다.

### Step 10: 최종 결과 출력 (풀 체인)

```
✅ Committed and pushed: feat(auth): 로그인 기능 추가 ✨
   Branch: feat/login
   Remote: https://github.com/user/repo/commit/abc1234

🔗 PR: #42 생성됨 (https://github.com/user/repo/pull/42)
🚀 Deploy: Vercel preview → https://repo-abc123.vercel.app   # 감지·배포 성공
⏭  Deploy: 배포 방식 미감지 — 건너뜀                          # 감지 실패
⏸  Deploy: production 대상 — 확인 대기                         # production 안전장치
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--no-push` | 커밋만 하고 push 생략 (push가 빠지면 deploy도 자동 생략) |
| `--no-deploy` | 배포 단계 생략 (commit + push + PR까지만) |
| `--prod` | 배포 시 production(실서비스) 대상으로. 그래도 비가역 배포는 1회 확인 |
| `--pr` | commit + push + PR 생성 (머지 제외) — 기능 브랜치 기본 동작과 동일 |
| `--ship` | commit + push + PR 생성 + 조건부 자동 머지 + deploy |
| `--force` | (--ship 전용) 조건 검증 무시 강제 머지. 사용자 확인 필수 |
| `--rewrite N` | 최근 N개 커밋 메시지를 Conventional Commit으로 재작성 |

**옵션 조합 규칙:**
- `--no-push` + `--pr`/`--ship` → 모순. 에러 출력 후 중단
- `--no-push` → push가 없으면 배포 대상이 올라가지 않으므로 deploy도 자동 생략
- `--no-deploy` + `--prod` → 모순. 에러 출력 후 중단
- `--pr` + `--ship` → `--ship`이 우선 (`--pr` 무시)
- `--force` 단독 사용 → 무효 (반드시 `--ship`과 함께)

## 금지 사항

- ❌ main/master에 force push (명시적 요청 없이)
- ❌ .env, credentials 파일 커밋
- ❌ pre-commit hook 실패 시 --no-verify 사용
- ❌ `--ship --force` 를 사용자 확인 없이 실행
- ❌ main/master 브랜치에서 `--pr`/`--ship` 실행 (차단)
- ❌ **production(실서비스) 배포를 사용자 확인 없이 자동 실행** — preview로 강등하거나 AskUserQuestion 필수
- ❌ 배포 실패를 이유로 이미 성공한 커밋/push를 되돌리기

## 관련 커맨드

- `/create pr` - PR 단독 생성 (수동)
- `/pr review` - PR 코드 리뷰
- `/pr merge` - PR 단독 머지 (수동)
- `/pr auto` - 리뷰 + 머지 (블로커 검사 포함)
- `/session changelog` - 커밋 전 changelog 업데이트

> **언제 `/commit --ship` vs `/pr auto`?**
> - `/commit --ship`: 커밋부터 머지까지 한 번에 (lint 통과한 깔끔한 변경 사항)
> - `/pr auto`: 이미 PR이 있고 코드 리뷰까지 엄격히 (블로커 감지 포함)
