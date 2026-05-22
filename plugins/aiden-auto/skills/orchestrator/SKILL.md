---
name: orchestrator
description: |
  Universal multi-session orchestration skill (v10.3). Architect-then-Observer 모델로 멀티 세션 병렬 작업 자율 시스템 구축. Phase 0에서 N개 워크트리 폴더 + 모든 파일 사전 세팅, Phase 1+에는 GitHub PR/Issue 모니터링만. 6중 다층 방어 (path + .team + CLAUDE.md + SessionStart hook + PreToolUse hook + GitHub infra). 사용자 진입점 = VSCode 폴더 클릭 1회. Use when starting multi-session parallel work, multi-team development, splitting project into autonomous streams, or 병렬 팀 분담.
auto_trigger: true
triggers:
  keywords:
    - "/orchestrator"
    - "오케스트레이터"
    - "멀티 세션"
    - "병렬 팀"
    - "팀 분담"
    - "워크트리 분리"
    - "동시 작업"
    - "Stream 시작"
    - "multi-session"
disabled_patterns:
  - "!quick"
  - "!just"
  - "!hotfix"
---

# Orchestrator — Multi-Session Autonomous Stream System

## 핵심 철학

> Architect-then-Observer: Phase 0에서 모든 것을 사전 설계 + 사전 세팅, Phase 1+에는 GitHub 모니터링만.

사용자 진입점은 다음 N개로 제한:
1. 스킬 호출 (1회) — `/orchestrator` 또는 평문 트리거
2. Stream 매트릭스 검토 (1회 — 자동 추론 결과 확인, 수정 가능)
3. VSCode에서 워크트리 폴더 열기 (Stream 수만큼, 자연스러운 작업 진입)

그 외 모든 것 = AI 자율.

## Phase -1: 프로젝트 자동 분석

스킬 호출 시 가장 먼저 다음을 자동 수행:

```
1. git rev-parse --show-toplevel    # 레포 루트
2. ls -la <repo>                    # 최상위 폴더 스캔
3. detect tech stack:
   - package.json → Node/JS
   - pyproject.toml → Python
   - pubspec.yaml → Flutter/Dart
   - Cargo.toml → Rust
   - go.mod → Go
4. detect existing team folders:
   - team*-* (EBS 패턴)
   - frontend/, backend/, shared/, mobile/, web/ (일반 패턴)
   - apps/*, packages/* (monorepo 패턴)
5. detect docs:
   - docs/, documentation/
   - PRD/spec 파일
6. detect tests:
   - test/, tests/, integration-tests/, e2e/
```

상세 알고리즘: `references/stream-matrix-inference.md` 참조.

## Phase 0: Architect Mode (90분 자율)

### Step 1. Stream 매트릭스 추론
`references/stream-matrix-inference.md`에 따라 자동 매트릭스 생성.

### Step 2. 사용자 1회 검토 (필수)
추론된 매트릭스를 표로 보여주고 1회 검토. **이게 Phase 0 유일한 사용자 진입점**.

```
+--------+----------+------------------+-------+
| Stream | 이름     | 흡수 폴더        | Phase |
+--------+----------+------------------+-------+
| S1     | ...      | (없음)           | P1    |
| S2     | ...      | frontend/        | P2    |
| ...    | ...      | ...              | ...   |
+--------+----------+------------------+-------+

이대로 진행할까요? (수정 사항 없으면 "진행"으로 답)
```

수정 사항 있으면 매트릭스 갱신 후 재확인. 없으면 즉시 Step 3으로.

### Step 3. 산출물 자동 작성 (15종)
`references/architect-mode.md`의 체크리스트 따라 모두 작성:

```
설계서:
  - <project>/docs/orchestrator/Multi_Session_Design.md
  - <project>/docs/orchestrator/team_assignment.yaml

도구 (프로젝트 tools/orchestrator/로 복사):
  - team_session_start.py
  - team_session_end.py
  - orchestrator_monitor.py
  - sync_design_to_github.py
  - dynamic_stream_activation.py
  - phase_gate_validator.py
  - setup_stream_worktree.py

Hook 템플릿:
  - hook_templates/SessionStart.py
  - hook_templates/PreToolUse.py

GitHub 인프라 (자동 생성):
  - .github/CODEOWNERS
  - .github/branch-protection.yml
  - .github/ISSUE_TEMPLATE/stream_work.yml
  - .github/PULL_REQUEST_TEMPLATE.md
  - .github/workflows/scope_check.yml
  - .github/workflows/dependency_check.yml
  - .github/workflows/phase_gate_check.yml
```

### Step 4. 워크트리 폴더 사전 세팅
`scripts/setup_stream_worktree.py`로 N개 폴더 자동 생성:

```
<sibling-dir>/<project>-<stream-slug>/
  ├── (git worktree base: main)
  ├── .team
  ├── CLAUDE.md (override)
  ├── START_HERE.md ★
  ├── .claude/
  │   ├── settings.local.json
  │   └── hooks/
  │       ├── SessionStart.py
  │       └── PreToolUse.py
  └── .vscode/
      └── settings.json
```

### Step 5. 자가 시뮬레이션
모든 Stream의 SessionStart hook 시뮬레이션 → identity 일치 검증.

### Step 6. 사용자에게 완료 보고
```
✅ Phase 0 완료. N개 폴더 준비됨:
   <list of worktree paths>

다음 단계:
   VSCode에서 첫 폴더 열기:
     code <first-worktree-path>
```

## Phase 1+: Observer Mode (영구)

### 30초 폴링 (수동 모드)
```python
while True:
    issues = gh_issue_list()
    prs = gh_pr_list()
    state = analyze(issues, prs)
    
    if dependency_violation(state):
        create_warning_issue()
    
    if user_dynamic_request():
        switch_to_architect_mode_temporarily()
    
    if 24h_idle(state):
        escalate_to_user()
    
    sleep(30)
```

상세: `references/observer-mode.md`.

### 동적 Stream 추가
사용자가 새 작업/팀 요청 시:
1. 현재 GitHub 상태 fetch
2. 매핑 분석
3. team_assignment.yaml 갱신
4. setup_stream_worktree.py로 새 폴더 생성
5. GitHub 인프라 갱신
6. 사용자 보고

상세: `references/dynamic-activation.md`.

## 적용 우선순위

1. 본 스킬 (글로벌, 모든 프로젝트)
2. 프로젝트별 CLAUDE.md (프로젝트 컨텍스트 보강)
3. 프로젝트별 `docs/orchestrator/team_assignment.yaml` (구체 매트릭스)

상위가 하위 override. 단, 이미 정립된 매트릭스(예: EBS v10.3)가 있으면 자동 추론 스킵 + 기존 매트릭스 사용.

## 6중 다층 방어 (Identity + Scope)

`references/6-layer-defense.md` 참조.

| Layer | 메커니즘 | 강제 시점 |
|-------|---------|----------|
| 1 | 워크트리 경로 패턴 | 진입 시 |
| 2 | `.team` 메타 파일 | 진입 시 |
| 3 | 워크트리 CLAUDE.md | LLM context |
| 4 | SessionStart hook | 세션 시작 |
| 5 | PreToolUse hook | Edit/Write 직전 |
| 6 | GitHub 인프라 | PR 생성 시 |

## 금지 사항

- 명시 호출 없이 destructive 작업 (워크트리 강제 제거 등) 금지
- 매트릭스 사용자 검토 스킵 금지 (단, 이미 정립된 프로젝트는 예외)
- Phase 0 미완료 상태에서 Phase 1 진입 금지
- Orchestrator가 PR 머지 직접 수행 금지 (각 Stream 자율)
- Orchestrator가 코드/문서 직접 작성 금지 (Phase 1+ 모드)

## 위반 감지 시 자동 대응

위 금지 사항 위반 패턴 감지 시:
1. 작업 중단
2. Architect/Observer 모드 재확인
3. 자율 결정 가능하면 즉시 정정
4. 결과만 보고

## References

상세 가이드는 `references/` 디렉토리:
- `architect-mode.md` — Phase 0 90분 자율 실행 체크리스트
- `observer-mode.md` — Phase 1+ 모니터링 + 동적 처리
- `stream-matrix-inference.md` — 자동 추론 알고리즘
- `6-layer-defense.md` — 식별 + scope 강제 6중 layer
- `github-infrastructure.md` — CODEOWNERS, branch protection, CI
- `dynamic-activation.md` — 동적 Stream 추가 시퀀스

도구는 `scripts/`, 템플릿은 `templates/`, hook은 `hook_templates/`.

## Edit History

| 날짜 | 버전 | 트리거 | 변경 |
|------|:----:|--------|------|
| 2026-05-07 | v10.3.0 | 사용자 directive — EBS v10.3 글로벌화 | 최초 작성 — EBS 특화 제거, 보편 패턴 추출 |
