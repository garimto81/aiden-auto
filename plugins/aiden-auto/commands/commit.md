---
name: commit
description: Create git commits using Conventional Commit format with emojis. Optional --pr/--ship for PR create + auto-merge chain.
---

# /commit - Conventional Commit & Push (+ PR/Merge Chain)

Create well-formatted git commits following Conventional Commits specification, push to remote, and optionally create/merge a PR in one chain.

## Usage

```
/commit                # Commit + push to current branch
/commit --no-push      # Commit only, skip push
/commit --pr           # Commit + push + create PR (no merge)
/commit --ship         # Commit + push + create PR + auto-merge (조건부)
/commit --ship --force # 조건 무시 강제 머지 (사용자 확인 필수)
/commit --rewrite N    # 최근 N개 커밋 메시지 Conventional Commit으로 재작성
```

## Workflow

Claude Code will:
1. Check for staged changes (`git diff --cached`)
2. If no staged changes, **Claude가 변경 파일을 의미 단위로 그룹화한 추천 커밋 구조를 제시**하고 비파괴 동작이면 즉시 스테이징·커밋 (Decision Protocol)
3. Analyze changes and determine commit type (feat, fix, docs, etc.)
4. Generate descriptive commit message with emoji
5. Execute `git commit`
6. **Push to remote** (`git push`) — reject/diverged 시 Decision Protocol로 단일 추천안 제시
7. **(--pr/--ship)** PR 체인 실행 (아래 "PR Chain" 섹션) — 조건 실패 시 Decision Protocol 적용
8. Show final status

> **Decision Protocol (Propose-then-Execute)**: 판단이 필요한 모든 지점에서 A/B/C 선택지를 나열하며 "어떻게 할까요?" 금지. Claude가 리스크·안전 규칙·메모리 기록을 종합해 단일 추천안을 근거와 함께 제시하고, 비파괴 동작이면 즉시 실행 / 파괴적 동작이면 승인 대기. 상세: `.claude/skills/commit/SKILL.md` "Decision Protocol" 섹션.

## Commit Format

```
<type>(<scope>): <subject> <emoji>

<body>

<footer>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Commit Types

| Type | Description | Emoji |
|------|-------------|-------|
| **feat** | New feature | ✨ |
| **fix** | Bug fix | 🐛 |
| **docs** | Documentation | 📝 |
| **style** | Formatting | 💄 |
| **refactor** | Code restructuring | ♻️ |
| **perf** | Performance | ⚡ |
| **test** | Tests | ✅ |
| **chore** | Maintenance | 🔧 |
| **ci** | CI/CD | 👷 |
| **build** | Build system | 📦 |

## Push Behavior

- **Default**: Push to current tracking branch
- **New branch**: Use `git push -u origin <branch>`
- **Diverged**: Warn user and ask before force push
- **--no-push**: Skip push step entirely

## PR Chain (--pr / --ship)

`--pr`와 `--ship` 옵션은 push 이후 PR 단계를 연결합니다. 기존 `/create pr` 및 `/pr merge` 로직을 재사용합니다.

### 체인 흐름

```
┌──────────┐     ┌────────┐     ┌───────────┐     ┌────────────┐
│  Commit  │ ──▶ │  Push  │ ──▶ │  PR 생성   │ ──▶ │  자동 머지   │
└──────────┘     └────────┘     └───────────┘     └────────────┘
                                   (--pr 이상)        (--ship 만)
```

### 안전 가드

| 조건 | --pr 동작 | --ship 동작 |
|------|-----------|-------------|
| main/master 브랜치 | ❌ 차단 | ❌ 차단 |
| 기존 OPEN PR 있음 | 재사용 (생성 스킵) | 재사용 후 머지 시도 |
| CI 실패 | PR만 생성 | 머지 스킵 + 사유 출력 |
| 충돌 (mergeable=CONFLICTING) | PR만 생성 | 머지 스킵 + 사유 출력 |
| `wip` / `do-not-merge` 라벨 | PR만 생성 | 머지 스킵 + 라벨 명시 |
| `--force` 플래그 | N/A | `AskUserQuestion` 1회 확인 후 `--admin` 머지 |

### 머지 조건 검증 (Step D)

`.claude/config/pr-merge.yaml`의 `required_checks` 기준:

```bash
# CI 상태 조회
gh pr checks <PR번호> --json state,name

# mergeable 확인
gh pr view <PR번호> --json mergeable,mergeStateStatus

# 라벨 확인
gh pr view <PR번호> --json labels
```

하나라도 실패하면 머지 스킵. 사용자에게는 PR URL과 차단 사유 함께 출력.

### 머지 실행

```bash
# 정상 머지 (squash + 브랜치 삭제 — pr-merge.yaml 기본 설정)
gh pr merge <PR번호> --squash --delete-branch

# --force (사용자 확인 후 admin 권한)
gh pr merge <PR번호> --squash --delete-branch --admin
```

## Example

**Input**: `/commit`

**Output**:
```bash
# 1. Commit
git commit -m "feat(auth): Add OAuth2 authentication ✨

- Implement OAuth2 provider
- Add token validation
- Create auth middleware

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 2. Push
git push origin main

# 3. Result
✅ Committed and pushed: feat(auth): Add OAuth2 authentication ✨
   Remote: https://github.com/user/repo/commit/abc1234
```

## Safety

- Never force push to main/master without explicit user confirmation
- Check for upstream changes before push
- Show diff summary before commit

## --rewrite N 모드 (커밋 메시지 재작성)

최근 N개 커밋의 메시지를 Conventional Commit 형식으로 AI 재작성합니다.

### 제약 사항

- Claude Code 환경에서 `git rebase -i` (interactive) 사용 불가
- `git commit --amend` 체인 방식으로 처리
- 원격 브랜치에 이미 push된 커밋은 --force-push 필요 → **사용자 확인 후 실행**

### 실행 워크플로우

```bash
# 1. 최근 N개 커밋 목록 확인
git log --oneline -N

# 2. 각 커밋별 diff 추출 및 AI 분석
git diff HEAD~i..HEAD~(i-1)

# 3. Conventional Commit 메시지 재작성 (AI 생성)
# type(scope): subject emoji
# - body
# 🤖 Generated with Claude Code

# 4. git commit --amend 체인 (non-interactive)
# ⚠️ 원격 브랜치 존재 시 force-push 필요 → 사용자 확인
```

### 예시

```bash
/commit --rewrite 3

# 처리 전:
# abc1234 fix stuff
# def5678 update code
# ghi9012 wip

# 처리 후:
# abc1234 fix(auth): OAuth 토큰 갱신 로직 수정 🐛
# def5678 refactor(api): 클라이언트 코드 구조 개선 ♻️
# ghi9012 feat(ui): 로그인 페이지 초기 구현 ✨
```

### 안전 장치

- main/master 브랜치에서 실행 시 경고 + 사용자 확인 필수
- 원격 브랜치 존재 시 force-push 경고 + 사용자 확인 필수
- 재작성 전 원본 메시지 백업 출력
- 품질 점수 60 미만 커밋만 대상 (이미 좋은 메시지는 스킵)

### 커밋 메시지 품질 점수 (post-commit hook)

커밋 후 자동으로 품질을 측정합니다:

| 점수 | 상태 | 조치 |
|------|------|------|
| 80+ | 우수 | - |
| 60-79 | 보통 | 경고만 |
| 60 미만 | 낮음 | `/commit --rewrite 1` 제안 |

점수 기준:
- Conventional Commit 형식 준수: +40점
- 이모지 포함: +10점
- 영어/한글 명확한 subject: +20점
- Body 설명 포함: +20점
- 50자 이내 subject: +10점 (50-72자: +5점)

## Example: --ship

**Input**: `/commit --ship`

**Output**:
```bash
# 1~6. 기존 commit + push (생략)
✅ Committed and pushed: feat(auth): OAuth2 인증 추가 ✨

# 7a. PR 상태 확인
gh pr view --json number,state
→ PR 없음

# 7b. PR 생성
gh pr create --title "feat(auth): OAuth2 인증 추가" --body "..."
→ 🔗 PR #42 (https://github.com/user/repo/pull/42)

# 7c. 머지 조건 검증
gh pr checks 42 → ✅ CI passed (5/5)
gh pr view 42 --json mergeable → MERGEABLE
라벨 확인 → block_merge 없음

# 7d. 머지 실행
gh pr merge 42 --squash --delete-branch
→ ✅ Merged to main, feat/oauth 브랜치 삭제됨
```

**차단 예시 (--ship 조건 미달)**:
```bash
✅ Committed and pushed
🔗 PR #43 생성됨

⏸  머지 보류 — 사유:
   - CI 실패: 2/5 checks failed (test, lint)
   - 수동 확인 후 `/pr auto #43`로 재시도 가능
```

## Related

- `/create pr` - PR 단독 생성 (수동)
- `/pr review` - PR 코드 리뷰
- `/pr merge` - PR 단독 머지
- `/pr auto` - 리뷰 + 자동 머지 (블로커 검사 포함)
- `/session changelog` - Update changelog before commit

### When to use each

| 상황 | 권장 |
|------|------|
| 커밋만 필요 | `/commit` |
| 커밋 + PR, 리뷰는 나중에 | `/commit --pr` |
| 작은 변경, 바로 머지하고 싶음 | `/commit --ship` |
| 큰 변경, 엄격 리뷰 후 머지 | `/commit --pr` + `/pr auto` |
