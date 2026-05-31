---
name: pr
description: PR review, improvement suggestions, and auto-merge workflow
---

# /pr - PR 리뷰 및 머지 관리

PR 리뷰 → 개선 제안 → 자동 머지까지 통합 워크플로우입니다.

## Usage

```
/pr <action> [#PR번호] [options]

Actions:
  review [#N]     PR 코드 리뷰 실행
  merge [#N]      조건 확인 후 머지
  auto [#N]       리뷰 + 자동 머지 (전체 워크플로우)
  list            리뷰 대기 PR 목록
```

---

## /pr review - PR 리뷰

```bash
/pr review           # 현재 브랜치의 PR 리뷰
/pr review #42       # 특정 PR 리뷰
/pr review --strict  # 엄격 모드 (경고도 블로커)
```

### 리뷰 워크플로우

```
PR 리뷰 시작
    │
    ├─ [병렬 검사] ─────────────────────────┐
    │      │                                 │
    │      ├─ 코드 품질 (lint, type)         │
    │      ├─ 테스트 검증 (coverage)         │ 병렬
    │      └─ 보안 검사 (secrets, deps)      │
    │                                   ─────┘
    │
    ├─ 결과 분석
    │      ├─ Critical/High → 블로커 (머지 차단)
    │      ├─ Medium → 개선 제안
    │      └─ Low → 참고 사항
    │
    └─ 리뷰 코멘트 작성
           └─ gh pr comment --body "..."
```

### 리뷰 체크리스트

| 카테고리 | 검사 항목 | 심각도 | 자동 수정 |
|----------|----------|--------|----------|
| **코드 품질** | Lint 오류 | High | ✅ |
| | Type 오류 | High | ❌ |
| | 복잡도 초과 (>10) | Medium | ❌ |
| **테스트** | 테스트 실패 | High | ❌ |
| | 커버리지 <80% | Medium | ❌ |
| | 신규 코드 테스트 없음 | Low | ❌ |
| **보안** | 하드코딩된 시크릿 | Critical | ❌ |
| | 취약한 의존성 | High | ⚠️ |
| **스타일** | 포맷팅 오류 | Low | ✅ |

### 리뷰 결과 출력

```markdown
## PR #42 리뷰 결과

### ✅ 통과
- [x] CI 빌드 성공
- [x] 테스트 42/42 통과
- [x] 커버리지 85%

### ❌ 블로커 (머지 차단)
1. **src/api.py:78** - 하드코딩된 API 키 발견
   ```python
   # 문제
   API_KEY = "<YOUR_API_KEY>"  # ❌ 시크릿 노출

   # 해결
   API_KEY = os.getenv("API_KEY")  # ✅ 환경변수
   ```

### ⚠️ 개선 제안
1. **src/auth.py:45** - 함수 복잡도 12 (권장: 10)
   - 헬퍼 함수로 분리 권장

### 💡 참고
- 테스트 커버리지 양호 (85%)
- 코드 스타일 일관성 유지

---
**결과**: 🔴 블로커 발견 - 수정 필요
```

---

## /pr merge - PR 머지

```bash
/pr merge            # 현재 브랜치 PR 머지
/pr merge #42        # 특정 PR 머지
/pr merge --force    # 조건 무시하고 머지 (위험)
```

### 머지 조건

```yaml
# 필수 조건 (하나라도 실패 시 머지 차단)
required:
  - ci_passed: true        # CI 통과
  - no_conflicts: true     # 충돌 없음
  - no_blockers: true      # Critical/High 이슈 없음

# 권장 조건 (경고만, 머지 가능)
recommended:
  - branch_updated: true   # 베이스 브랜치 최신
  - test_coverage: 80      # 커버리지 80% 이상
```

### 머지 방법

```bash
# 기본: squash merge (커밋 정리)
gh pr merge #42 --squash --delete-branch

# 옵션
--merge     # 일반 머지 (커밋 유지)
--rebase    # 리베이스 머지
--no-delete # 브랜치 유지
```

---

## /pr auto - 자동 리뷰 + 머지

```bash
/pr auto             # 현재 브랜치 PR
/pr auto #42         # 특정 PR
/pr auto --strict    # 엄격 모드
```

### 전체 워크플로우

```
/pr auto 실행
    │
    ├─ Step 1: PR 정보 확인
    │      └─ gh pr view #N --json ...
    │
    ├─ Step 2: 리뷰 실행 (/pr review)
    │      │
    │      ├─ 블로커 발견 → 개선 제안 + 종료
    │      │     └─ 사용자 수정 대기
    │      │
    │      └─ 블로커 없음 → Step 3 진행
    │
    ├─ Step 3: 머지 조건 검증
    │      │
    │      ├─ CI 상태 확인
    │      ├─ 충돌 확인
    │      └─ 브랜치 상태 확인
    │
    ├─ Step 4: 사용자 확인 (--auto-approve 없을 시)
    │      │
    │      └─ AskUserQuestion 호출 (머지 승인 — 비가역)
    │           question: "이 PR을 main 브랜치에 squash merge로
    │                      합칩니다. 한 번 합치면 되돌리기 어렵습니다.
    │                      진행할까요?"
    │           header: "머지 승인"
    │           multiSelect: false
    │           options:
    │             - 예, 머지 진행: "지금 main에 합칩니다.
    │                 합치면 브랜치가 삭제되고 되돌리기 어렵습니다."
    │             - 아니오, 보류: "지금은 합치지 않고 멈춥니다.
    │                 나중에 다시 /pr merge로 진행할 수 있습니다."
    │
    └─ Step 5: 머지 실행
           │
           ├─ gh pr merge --squash --delete-branch
           └─ 완료 메시지 출력
```

### 자동 승인 모드

```bash
# 블로커 없으면 자동 머지 (확인 생략)
/pr auto --auto-approve

# 사용 조건
# - CI 통과
# - 리뷰 블로커 없음
# - 충돌 없음
```

---

## /pr list - PR 목록

```bash
/pr list             # 모든 Open PR
/pr list --mine      # 내가 생성한 PR
/pr list --review    # 리뷰 요청된 PR
```

### 출력 예시

```markdown
## Open PRs (3개)

| # | 제목 | 브랜치 | CI | 리뷰 |
|---|------|--------|-----|------|
| #42 | Add OAuth2 | feat/auth | ✅ | 🟡 대기 |
| #41 | Fix login bug | fix/login | ✅ | ✅ 승인 |
| #40 | Update docs | docs/api | ❌ | - |

### 권장 액션
- #41: 머지 가능 (`/pr merge #41`)
- #40: CI 실패 확인 필요
```

---

## 설정

### 머지 설정 파일

```yaml
# .claude/config/pr-merge.yaml
merge:
  method: squash           # squash, merge, rebase
  delete_branch: true      # 머지 후 브랜치 삭제

review:
  strict_mode: false       # true: 경고도 블로커
  auto_fix: true           # lint/format 자동 수정

thresholds:
  complexity: 10           # 함수 복잡도 한계
  coverage: 80             # 최소 커버리지 (%)

labels:
  auto_merge:              # 자동 머지 허용 라벨
    - "auto-merge"
    - "trivial"
  block_merge:             # 머지 차단 라벨
    - "wip"
    - "do-not-merge"
```

---

## 연동 워크플로우

```
/auto "기능 구현"
    │
    ├─ 구현 완료
    │
    ├─ /create pr
    │      └─ PR 생성
    │
    └─ /pr auto
           ├─ 리뷰 실행
           ├─ 개선 제안 (필요 시)
           └─ 자동 머지
```

---

## 예시

### 기본 사용

```bash
$ /pr auto

🔍 PR #42 정보 확인...
   브랜치: feat/oauth → main
   커밋: 3개
   변경: +150 / -20

🔬 리뷰 실행 중...
   [1/3] 코드 품질 검사... ✅
   [2/3] 테스트 검증... ✅ (85% coverage)
   [3/3] 보안 검사... ✅

📋 리뷰 결과
   ✅ 블로커: 0
   ⚠️ 개선 제안: 2
   💡 참고: 1

✅ 머지 조건 충족
   - CI: ✅ 통과
   - 충돌: ✅ 없음
   - 브랜치: ✅ 최신

[AskUserQuestion] 머지 승인
  question: "이 PR을 main 브랜치에 squash merge로 합칩니다.
             한 번 합치면 되돌리기 어렵습니다. 진행할까요?"
  options: [예, 머지 진행 (되돌리기 어려움)] / [아니오, 보류]
  → 사용자 선택: 예, 머지 진행

🎉 PR #42 머지 완료!
   → main 브랜치에 squash merge
   → feat/oauth 브랜치 삭제됨
```

### 블로커 발견 시

```bash
$ /pr auto

🔬 리뷰 실행 중...
   [1/3] 코드 품질 검사... ❌
   [2/3] 테스트 검증... ✅
   [3/3] 보안 검사... ⚠️

📋 리뷰 결과

### ❌ 블로커 (1개)
1. **src/config.py:12** - 하드코딩된 시크릿
   ```python
   # 현재
   DB_PASSWORD = "secret123"

   # 수정 방법
   DB_PASSWORD = os.getenv("DB_PASSWORD")
   ```

### ⚠️ 개선 제안 (1개)
1. 취약한 의존성: requests==2.25.0
   - 권장: requests>=2.31.0

🔴 머지 차단됨 - 블로커 수정 후 다시 실행하세요.
```

---

## 관련

- `/create pr` - PR 생성
- `/check` - 코드 품질 검사
- `/commit` - 커밋 생성
- `pr-review-agent` 스킬 - 상세 리뷰 로직
