# Architect Mode — Phase 0 자율 실행 체크리스트

## 트리거

스킬 호출 후 사용자 매트릭스 검토 통과 즉시.

## 90분 자율 실행 (사용자 진입점 0회)

### Step 1. 디렉토리 + 설계서 (10분)

```
<project>/docs/orchestrator/
  ├── Multi_Session_Design.md       (templates/multi_session_design.md.j2 렌더)
  └── team_assignment.yaml          (templates/team_assignment.yaml.j2 렌더)

<project>/CLAUDE.md
  → orchestrator 거버넌스 섹션 추가 (이미 있으면 update)

<project>/.gitignore
  → "<project>-*/" 추가 (워크트리 sibling-dir 제외)
```

### Step 2. 도구 7종 (15분)

`scripts/` 에서 `<project>/tools/orchestrator/` 로 복사:

```
team_session_start.py
team_session_end.py
orchestrator_monitor.py
sync_design_to_github.py
dynamic_stream_activation.py
phase_gate_validator.py
setup_stream_worktree.py
```

각 스크립트 첫 줄에 프로젝트별 환경 변수 자동 주입:

```python
PROJECT_ROOT = "<project absolute path>"
PROJECT_NAME = "<project name>"
WORKTREE_SIBLING = "<sibling dir for worktrees>"
```

### Step 3. Hook 템플릿 2종 (5분)

`hook_templates/` 에서 `<project>/.claude/hook_templates/` 로 복사:

```
SessionStart.py
PreToolUse.py
```

이건 워크트리에 복사될 원본. 직접 워크트리에 들어가는 건 Step 6.

### Step 4. GitHub 인프라 (15분)

`templates/` 의 .j2 파일들을 `<project>/.github/` 에 렌더:

```
CODEOWNERS
branch-protection.yml          (gh-cli로 적용)
ISSUE_TEMPLATE/stream_work.yml
PULL_REQUEST_TEMPLATE.md
workflows/scope_check.yml
workflows/dependency_check.yml
workflows/phase_gate_check.yml
```

### Step 5. sync_design_to_github.py 실행 (5분)

```bash
python <project>/tools/orchestrator/sync_design_to_github.py
```

이게 자동 수행:
- branch protection 규칙 적용 (`gh api`)
- CODEOWNERS commit
- workflows commit
- PR 생성 + auto-merge

### Step 6. setup_stream_worktree.py 실행 (30분)

핵심 단계. N개 워크트리 폴더 + 모든 파일 사전 세팅:

```bash
for stream in $(yq '.streams | keys[]' team_assignment.yaml); do
  python <project>/tools/orchestrator/setup_stream_worktree.py \
    --stream=$stream \
    --project-root=<project> \
    --sibling-dir=<sibling>
done
```

각 Stream에 대해:
1. `git worktree add <sibling>/<project>-<stream-slug>` (브랜치 자동 생성)
2. 워크트리에 `.team` 작성 (Layer 2)
3. 워크트리에 `CLAUDE.md` (Layer 3)
4. 워크트리에 `START_HERE.md` 작성 (의존성 상태 반영)
5. 워크트리에 `.claude/hooks/SessionStart.py` + `PreToolUse.py` 복사 (Layer 4, 5)
6. 워크트리에 `.vscode/settings.json` 자동 작성

### Step 7. 자가 시뮬레이션 (5분)

각 워크트리에서 SessionStart hook 모의 실행:

```python
for stream_dir in worktrees:
    result = subprocess.run(
        ['python', f'{stream_dir}/.claude/hooks/SessionStart.py'],
        env={...},
        capture_output=True
    )
    assert "You are S" in result.stdout
    assert .team identity matches path
```

실패 시 자동 정정 + 재시도 (최대 3회).

### Step 8. 사용자 보고 (5분)

다음 형식으로 1회 메시지:

```
✅ Phase 0 완료 (예상 90분 → 실제 XX분)

📂 N개 워크트리 폴더 준비됨:
  <sibling>/<project>-foundation/    (S1, READY)
  <sibling>/<project>-frontend/      (S2, BLOCKED by S1)
  <sibling>/<project>-backend/       (S3, BLOCKED by S1)
  ...

🔧 GitHub 인프라:
  - branch protection 적용됨
  - CODEOWNERS 활성
  - 3개 workflow 등록됨

▶️ 다음 단계:
  VSCode에서 첫 폴더 열기:
    code <sibling>/<project>-foundation/
  
  자동으로:
    - SessionStart hook이 identity 주입
    - START_HERE.md 표시
    - "작업 시작" 한 줄로 issue + draft PR 자동 생성
```

## 실패 시 자율 정정

각 Step에서 실패 발생 시:

```
1. 에러 메시지 분석
2. 원인 진단 (auto-detect):
   - git worktree 실패 → 기존 worktree 정리 + 재시도
   - GitHub API rate limit → 60초 대기 + 재시도
   - 권한 부족 → 사용자 escalate
3. 3회 재시도 후 실패 시 → 사용자 escalate
   - 어느 Step에서 실패했는지 보고
   - 부분 완료 상태 보존
   - 사용자가 "재개" 신호 시 실패 Step부터 이어서 실행
```

## 종료 조건

- 모든 Step 통과 → Observer Mode로 전환
- Step 8 사용자 보고 완료 → Architect Mode 종료

## 시간 예산 초과 시

90분 초과 시 (예: 대규모 프로젝트):
- 사용자에게 진척 보고 (Step X / 8)
- 계속 진행 또는 일시 중단 결정 (사용자 1회 진입점)
